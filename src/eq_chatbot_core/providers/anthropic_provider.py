"""
Anthropic Claude provider implementation.
"""

from typing import Any, Iterator

from eq_chatbot_core.providers.base import (
    BaseLLMProvider,
    LLMResponse,
    StreamChunk,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ContextLengthError,
)


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic API provider for Claude models.

    Supports:
    - Claude 4.5 Opus (claude-opus-4-5-20251101) - newest, most capable
    - Claude 4 Sonnet (claude-sonnet-4-20250514)
    - Claude 3.5 Sonnet (claude-3-5-sonnet-20241022)
    - Claude 3.5 Haiku (claude-3-5-haiku-20241022)
    - Claude 3 Opus (claude-3-opus-20240229)
    """

    DEFAULT_BASE_URL = "https://api.anthropic.com"

    # Models that don't support temperature
    NO_TEMPERATURE_MODELS = ("claude-3-opus",)

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        super().__init__(api_key, base_url, timeout, max_retries)
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def default_model(self) -> str:
        return "claude-sonnet-4-20250514"

    @property
    def client(self) -> Any:
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError as e:
                raise ImportError(
                    "Anthropic package not installed. Install with: pip install anthropic"
                ) from e

            self._client = Anthropic(
                api_key=self.api_key,
                base_url=self.base_url or self.DEFAULT_BASE_URL,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._client

    def _extract_system_prompt(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """
        Extract system prompt from messages.

        Anthropic requires system prompt as a separate parameter.
        """
        system_prompt = None
        filtered_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                # Concatenate multiple system messages
                content = msg.get("content", "")
                if system_prompt:
                    system_prompt = f"{system_prompt}\n\n{content}"
                else:
                    system_prompt = content
            else:
                filtered_messages.append(msg)

        return system_prompt, filtered_messages

    def _convert_tools_to_anthropic(
        self, tools: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]] | None:
        """Convert OpenAI-style tools to Anthropic format."""
        if not tools:
            return None

        anthropic_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                anthropic_tools.append({
                    "name": func.get("name"),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {}),
                })

        return anthropic_tools if anthropic_tools else None

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to Anthropic."""
        model = model or self.default_model

        try:
            system_prompt, filtered_messages = self._extract_system_prompt(messages)
            anthropic_tools = self._convert_tools_to_anthropic(tools)

            params: dict[str, Any] = {
                "model": model,
                "messages": filtered_messages,
                "max_tokens": max_tokens or 4096,
            }

            # Only add temperature if model supports it
            if not any(prefix in model.lower() for prefix in self.NO_TEMPERATURE_MODELS):
                params["temperature"] = temperature

            if system_prompt:
                params["system"] = system_prompt

            if anthropic_tools:
                params["tools"] = anthropic_tools

            params.update(kwargs)

            response = self.client.messages.create(**params)

            # Extract text content
            content = ""
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": str(block.input),
                        },
                    })

            return LLMResponse(
                content=content,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                finish_reason=response.stop_reason,
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
        """Stream a chat completion response from Anthropic."""
        model = model or self.default_model

        try:
            system_prompt, filtered_messages = self._extract_system_prompt(messages)
            anthropic_tools = self._convert_tools_to_anthropic(tools)

            params: dict[str, Any] = {
                "model": model,
                "messages": filtered_messages,
                "max_tokens": max_tokens or 4096,
            }

            # Only add temperature if model supports it
            if not any(prefix in model.lower() for prefix in self.NO_TEMPERATURE_MODELS):
                params["temperature"] = temperature

            if system_prompt:
                params["system"] = system_prompt

            if anthropic_tools:
                params["tools"] = anthropic_tools

            params.update(kwargs)

            # Track usage for final chunk
            final_input_tokens = 0
            final_output_tokens = 0

            # Accumulate tool calls from stream events
            # Key: content block index, Value: tool call data
            accumulated_tool_calls: dict[int, dict[str, Any]] = {}
            current_block_index = 0

            with self.client.messages.stream(**params) as stream:
                for event in stream:
                    # Capture input tokens from message_start event
                    if event.type == "message_start":
                        if hasattr(event, "message") and hasattr(event.message, "usage"):
                            final_input_tokens = event.message.usage.input_tokens or 0

                    # Capture output tokens from message_delta event
                    elif event.type == "message_delta":
                        if hasattr(event, "usage"):
                            final_output_tokens = event.usage.output_tokens or 0

                    # Track content block index
                    elif event.type == "content_block_start":
                        current_block_index = getattr(event, "index", 0)
                        # Check if this is a tool_use block
                        if hasattr(event, "content_block"):
                            block = event.content_block
                            if hasattr(block, "type") and block.type == "tool_use":
                                # Initialize tool call accumulator
                                accumulated_tool_calls[current_block_index] = {
                                    "id": getattr(block, "id", ""),
                                    "type": "function",
                                    "function": {
                                        "name": getattr(block, "name", ""),
                                        "arguments": "",
                                    },
                                }
                                # Emit tool_call_delta for the start
                                yield StreamChunk(
                                    content="",
                                    is_final=False,
                                    tool_call_delta={
                                        "index": current_block_index,
                                        "id": getattr(block, "id", ""),
                                        "function": {
                                            "name": getattr(block, "name", ""),
                                            "arguments": None,
                                        },
                                    },
                                )

                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if hasattr(delta, "text"):
                            yield StreamChunk(
                                content=delta.text,
                                is_final=False,
                            )
                        # Handle tool input JSON deltas
                        elif hasattr(delta, "type") and delta.type == "input_json_delta":
                            partial_json = getattr(delta, "partial_json", "")
                            if current_block_index in accumulated_tool_calls:
                                # Accumulate the JSON arguments
                                accumulated_tool_calls[current_block_index]["function"]["arguments"] += partial_json
                                # Emit tool_call_delta
                                yield StreamChunk(
                                    content="",
                                    is_final=False,
                                    tool_call_delta={
                                        "index": current_block_index,
                                        "id": None,
                                        "function": {
                                            "name": None,
                                            "arguments": partial_json,
                                        },
                                    },
                                )

                    elif event.type == "message_stop":
                        # Build complete tool calls list
                        complete_tool_calls = None
                        if accumulated_tool_calls:
                            complete_tool_calls = [
                                accumulated_tool_calls[idx]
                                for idx in sorted(accumulated_tool_calls.keys())
                            ]

                        yield StreamChunk(
                            content="",
                            is_final=True,
                            finish_reason="end_turn",
                            tool_calls=complete_tool_calls,
                            input_tokens=final_input_tokens,
                            output_tokens=final_output_tokens,
                        )

        except Exception as e:
            raise self._handle_error(e) from e

    def _get_model_constraints(self, model_id: str) -> dict[str, Any]:
        """Get temperature, token, and capability constraints for a model."""
        model_lower = model_id.lower()

        # Check if it's a model that doesn't support temperature
        supports_temp = not any(
            prefix in model_lower for prefix in self.NO_TEMPERATURE_MODELS
        )

        # All Claude 3.x and 4.x models support vision
        # Check for various naming patterns: claude-3-*, claude-4-*, claude-haiku-*, etc.
        supports_vision = (
            "claude-3" in model_lower
            or "claude-4" in model_lower
            or any(v in model_lower for v in ("haiku", "sonnet", "opus"))
        )

        # Determine max output tokens based on model family
        if "opus-4" in model_lower or "sonnet-4" in model_lower:
            max_output = 16384
        elif "3-5" in model_lower or "3.5" in model_lower:
            max_output = 8192
        else:
            max_output = 4096

        return {
            "supports_temperature": supports_temp,
            "default_temperature": 1.0,
            "min_temperature": 0.0,
            "max_temperature": 1.0,  # Anthropic max is 1.0
            "supports_reasoning": False,
            "supports_vision": supports_vision,
            "max_output_tokens": max_output,
            "default_max_tokens": 4096,
            "context_length": 200000,  # All Claude models support 200k context
        }

    def list_models(self) -> list[dict[str, Any]]:
        """
        List available Claude models from the Anthropic API.

        Uses the Models API endpoint to fetch available models dynamically.

        Returns:
            List of model dicts with 'id', 'name', constraints, and metadata.
        """
        try:
            # Fetch models from API
            models_response = self.client.models.list(limit=100)

            chat_models = []
            for model in models_response.data:
                constraints = self._get_model_constraints(model.id)
                chat_models.append({
                    "id": model.id,
                    "name": getattr(model, "display_name", model.id),
                    "created": getattr(model, "created_at", None),
                    "provider": self.provider_name,
                    **constraints,
                })

            # Sort by creation date (newest first) or by ID
            chat_models.sort(
                key=lambda m: m.get("created") or "",
                reverse=True,
            )
            return chat_models

        except Exception as e:
            raise self._handle_error(e) from e

    def _handle_error(self, error: Exception) -> ProviderError:
        """Convert Anthropic exceptions to ProviderError types."""
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

        if "context" in error_str or "token" in error_str:
            return ContextLengthError(
                message=str(error),
                provider=self.provider_name,
            )

        return ProviderError(
            message=str(error),
            provider=self.provider_name,
        )
