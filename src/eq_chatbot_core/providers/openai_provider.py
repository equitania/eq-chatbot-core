"""
OpenAI provider implementation.
"""

from collections.abc import Iterator
from typing import Any

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    BaseLLMProvider,
    ContextLengthError,
    LLMResponse,
    ProviderError,
    RateLimitError,
    StreamChunk,
)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI API provider for GPT models.

    Supports:
    - GPT-4 Turbo (gpt-4-turbo)
    - GPT-4o (gpt-4o, gpt-4o-mini)
    - GPT-5 series (gpt-5, gpt-5.2)
    - O1/O3 series (o1, o1-mini, o1-preview, o3)
    """

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    # Models that require max_completion_tokens instead of max_tokens
    # All GPT-4o, GPT-5.x, O1, and O3 models use the new API
    NEW_API_MODELS = (
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-5",
        "gpt-5.1",
        "gpt-5.2",
        "o1",
        "o1-mini",
        "o1-preview",
        "o3",
        "o3-mini",
        "o4",
        "o4-mini",
    )

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        organization: str | None = None,
    ):
        super().__init__(api_key, base_url, timeout, max_retries)
        self.organization = organization
        self._client: Any = None  # Lazy initialization

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return "gpt-4o"

    @property
    def client(self) -> Any:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError("OpenAI package not installed. Install with: pip install openai") from e

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url or self.DEFAULT_BASE_URL,
                timeout=self.timeout,
                max_retries=self.max_retries,
                organization=self.organization,
            )
        return self._client

    def _uses_new_token_api(self, model: str) -> bool:
        """Check if model uses max_completion_tokens instead of max_tokens."""
        model_lower = model.lower()
        return any(model_lower.startswith(prefix) for prefix in self.NEW_API_MODELS)

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to OpenAI."""
        model = model or self.default_model

        try:
            params: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }

            if max_tokens:
                if self._uses_new_token_api(model):
                    params["max_completion_tokens"] = max_tokens
                else:
                    params["max_tokens"] = max_tokens

            if tools:
                params["tools"] = tools

            # Add any additional kwargs
            params.update(kwargs)

            response = self.client.chat.completions.create(**params)

            choice = response.choices[0]
            tool_calls = []

            if choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ]

            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                finish_reason=choice.finish_reason,
                tool_calls=tool_calls,
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
            )

        except Exception as e:
            raise self._handle_error(e) from e

    def stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> Iterator[StreamChunk]:
        """Stream a chat completion response from OpenAI."""
        model = model or self.default_model

        try:
            params: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
                "stream_options": {"include_usage": True},  # Request usage in stream
            }

            if max_tokens:
                if self._uses_new_token_api(model):
                    params["max_completion_tokens"] = max_tokens
                else:
                    params["max_tokens"] = max_tokens

            if tools:
                params["tools"] = tools

            params.update(kwargs)

            stream = self.client.chat.completions.create(**params)

            # Track usage for final chunk
            final_input_tokens = 0
            final_output_tokens = 0

            # Accumulate tool calls from deltas
            # Key: tool call index, Value: accumulated tool call data
            accumulated_tool_calls: dict[int, dict[str, Any]] = {}

            for chunk in stream:
                # Check for usage data (sent in final chunk with stream_options)
                if hasattr(chunk, "usage") and chunk.usage:
                    final_input_tokens = chunk.usage.prompt_tokens or 0
                    final_output_tokens = chunk.usage.completion_tokens or 0

                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                content = delta.content or ""
                is_final = choice.finish_reason is not None

                tool_call_delta = None
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        tool_call_delta = {
                            "index": idx,
                            "id": tc.id,
                            "function": {
                                "name": tc.function.name if tc.function else None,
                                "arguments": tc.function.arguments if tc.function else None,
                            },
                        }

                        # Accumulate tool call data
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.id or "",
                                "type": "function",
                                "function": {
                                    "name": "",
                                    "arguments": "",
                                },
                            }

                        # Update with new data (deltas send partial data)
                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                accumulated_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

                # On final chunk, include accumulated tool calls
                complete_tool_calls = None
                if is_final and accumulated_tool_calls:
                    # Convert dict to sorted list by index
                    complete_tool_calls = [accumulated_tool_calls[idx] for idx in sorted(accumulated_tool_calls.keys())]

                yield StreamChunk(
                    content=content,
                    is_final=is_final,
                    finish_reason=choice.finish_reason,
                    tool_call_delta=tool_call_delta,
                    tool_calls=complete_tool_calls,
                    input_tokens=final_input_tokens if is_final else 0,
                    output_tokens=final_output_tokens if is_final else 0,
                )

        except Exception as e:
            raise self._handle_error(e) from e

    # Chat model prefixes to filter from models list
    CHAT_MODEL_PREFIXES = (
        "gpt-3.5",
        "gpt-4",
        "gpt-5",
        "o1",
        "o3",
        "o4",
        "chatgpt",
    )

    # Reasoning models that don't support temperature
    REASONING_MODELS = ("o1", "o3", "o4")

    # Model context lengths (approximate, for common models)
    MODEL_CONTEXT_LENGTHS = {
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4": 8192,
        "gpt-3.5-turbo": 16385,
        "o1": 200000,
        "o1-mini": 128000,
        "o1-preview": 128000,
        "o3": 200000,
        "o3-mini": 200000,
        "o4-mini": 200000,
        "gpt-5": 200000,
    }

    def _get_model_constraints(self, model_id: str) -> dict[str, Any]:
        """Get temperature, token, and capability constraints for a model."""
        model_lower = model_id.lower()

        # Check if it's a reasoning model (O1, O3, O4)
        is_reasoning = any(model_lower.startswith(prefix) for prefix in self.REASONING_MODELS)

        # Check if model supports vision (GPT-4o, GPT-4-turbo, GPT-5, O1, O3, O4)
        vision_prefixes = ("gpt-4o", "gpt-4-turbo", "gpt-5", "o1", "o3", "o4")
        supports_vision = any(model_lower.startswith(prefix) for prefix in vision_prefixes)

        # Get context length
        context_length = None
        for prefix, length in self.MODEL_CONTEXT_LENGTHS.items():
            if model_lower.startswith(prefix):
                context_length = length
                break

        if is_reasoning:
            return {
                "supports_temperature": False,
                "default_temperature": 1.0,
                "min_temperature": 1.0,
                "max_temperature": 1.0,
                "supports_reasoning": True,
                "supports_vision": supports_vision,
                "max_output_tokens": 100000 if "o1" in model_lower else 65536,
                "default_max_tokens": 16384,
                "context_length": context_length or 200000,
            }
        else:
            return {
                "supports_temperature": True,
                "default_temperature": 1.0,
                "min_temperature": 0.0,
                "max_temperature": 2.0,
                "supports_reasoning": False,
                "supports_vision": supports_vision,
                "max_output_tokens": 16384 if "gpt-4o" in model_lower else 4096,
                "default_max_tokens": 4096,
                "context_length": context_length or 128000,
            }

    def list_models(self) -> list[dict[str, Any]]:
        """
        List available chat models from OpenAI.

        Returns:
            List of model dicts with 'id', 'name', constraints, and metadata.
            Only returns models suitable for chat completion.
        """
        try:
            models = self.client.models.list()

            chat_models = []
            for model in models.data:
                model_id = model.id.lower()

                # Filter for chat-capable models
                if any(model_id.startswith(prefix) for prefix in self.CHAT_MODEL_PREFIXES):
                    constraints = self._get_model_constraints(model.id)
                    chat_models.append(
                        {
                            "id": model.id,
                            "name": model.id,  # OpenAI uses ID as name
                            "created": model.created,
                            "owned_by": model.owned_by,
                            "provider": self.provider_name,
                            **constraints,
                        }
                    )

            # Sort by model ID for consistent ordering
            chat_models.sort(key=lambda m: m["id"])
            return chat_models

        except Exception as e:
            raise self._handle_error(e) from e

    def _handle_error(self, error: Exception) -> ProviderError:
        """Convert OpenAI exceptions to ProviderError types."""
        error_str = str(error).lower()

        if "rate limit" in error_str or "429" in error_str:
            return RateLimitError(
                message=str(error),
                provider=self.provider_name,
                status_code=429,
            )

        if "authentication" in error_str or "401" in error_str:
            return AuthenticationError(
                message=str(error),
                provider=self.provider_name,
                status_code=401,
            )

        if "context length" in error_str or "token" in error_str:
            return ContextLengthError(
                message=str(error),
                provider=self.provider_name,
            )

        return ProviderError(
            message=str(error),
            provider=self.provider_name,
        )
