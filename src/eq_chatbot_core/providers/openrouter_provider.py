"""
OpenRouter provider implementation.

OpenRouter provides access to 400+ AI models through a unified API,
including OpenAI, Anthropic, Google, Meta, Mistral, and many more.
"""

import json
import logging
from collections.abc import Iterator
from typing import Any

import httpx

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    BaseLLMProvider,
    ContextLengthError,
    LLMResponse,
    ProviderError,
    RateLimitError,
    StreamChunk,
)

_logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseLLMProvider):
    """
    OpenRouter API provider for 400+ AI models.

    Supports models from multiple providers through a unified API:
    - OpenAI (GPT-4, GPT-4o, O1, O3, O4)
    - Anthropic (Claude 3, Claude 3.5, Claude 4)
    - Google (Gemini Pro, Gemini Ultra)
    - Meta (Llama 3, Llama 4)
    - Mistral (Mistral Large, Mixtral)
    - And many more...

    Model IDs follow the format: provider/model-name
    Examples:
    - openai/gpt-4o
    - anthropic/claude-3.5-sonnet
    - google/gemini-pro-1.5
    - meta-llama/llama-3.1-70b-instruct
    """

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

    # Reasoning models that don't support temperature
    REASONING_MODEL_PREFIXES = (
        "openai/o1",
        "openai/o3",
        "openai/o4",
    )

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        site_url: str | None = None,
        site_name: str | None = None,
    ):
        """
        Initialize the OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            base_url: Optional custom base URL (defaults to OpenRouter API)
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures
            site_url: Optional site URL for HTTP-Referer header (for rankings)
            site_name: Optional site name for X-Title header (for display)
        """
        super().__init__(api_key, base_url or self.DEFAULT_BASE_URL, timeout, max_retries)
        self.site_url = site_url
        self.site_name = site_name
        self._client: httpx.Client | None = None

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def default_model(self) -> str:
        return "openai/gpt-4o"

    @property
    def client(self) -> httpx.Client:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            if self.site_url:
                headers["HTTP-Referer"] = self.site_url
            if self.site_name:
                headers["X-Title"] = self.site_name

            self._client = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    def _is_reasoning_model(self, model: str) -> bool:
        """Check if model is a reasoning model (O1, O3, O4)."""
        model_lower = model.lower()
        return any(model_lower.startswith(prefix.lower()) for prefix in self.REASONING_MODEL_PREFIXES)

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to OpenRouter."""
        model = model or self.default_model

        try:
            # Build request payload (OpenAI-compatible format)
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
            }

            # Only include temperature for non-reasoning models
            if not self._is_reasoning_model(model):
                payload["temperature"] = temperature

            if max_tokens:
                payload["max_tokens"] = max_tokens

            if tools:
                payload["tools"] = tools

            # Add any additional kwargs
            payload.update(kwargs)

            response = self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            choice = data["choices"][0]
            message = choice["message"]

            # Parse tool calls if present
            tool_calls = []
            if message.get("tool_calls"):
                tool_calls = [
                    {
                        "id": tc["id"],
                        "type": tc["type"],
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for tc in message["tool_calls"]
                ]

            usage = data.get("usage", {})

            return LLMResponse(
                content=message.get("content") or "",
                model=data.get("model", model),
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                finish_reason=choice.get("finish_reason"),
                tool_calls=tool_calls,
                raw_response=data,
            )

        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
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
        """Stream a chat completion response from OpenRouter."""
        model = model or self.default_model

        try:
            # Build request payload
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": True,
            }

            # Only include temperature for non-reasoning models
            if not self._is_reasoning_model(model):
                payload["temperature"] = temperature

            if max_tokens:
                payload["max_tokens"] = max_tokens

            if tools:
                payload["tools"] = tools

            payload.update(kwargs)

            # Use streaming request
            with self.client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()

                # Track usage for final chunk
                final_input_tokens = 0
                final_output_tokens = 0

                # Accumulate tool calls from deltas
                accumulated_tool_calls: dict[int, dict[str, Any]] = {}

                for line in response.iter_lines():
                    if not line:
                        continue

                    # Handle SSE format
                    if line.startswith("data: "):
                        line = line[6:]  # Remove "data: " prefix

                    if line == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(line)
                    except json.JSONDecodeError:
                        _logger.warning(f"Failed to parse SSE chunk: {line[:200]}")
                        continue

                    # Check for usage data
                    if "usage" in chunk_data:
                        usage = chunk_data["usage"]
                        final_input_tokens = usage.get("prompt_tokens", 0)
                        final_output_tokens = usage.get("completion_tokens", 0)

                    if not chunk_data.get("choices"):
                        continue

                    choice = chunk_data["choices"][0]
                    delta = choice.get("delta", {})

                    content = delta.get("content") or ""
                    is_final = choice.get("finish_reason") is not None

                    # Handle tool call deltas
                    tool_call_delta = None
                    if delta.get("tool_calls"):
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)
                            func = tc.get("function", {})

                            tool_call_delta = {
                                "index": idx,
                                "id": tc.get("id"),
                                "function": {
                                    "name": func.get("name"),
                                    "arguments": func.get("arguments"),
                                },
                            }

                            # Accumulate tool call data
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": tc.get("id") or "",
                                    "type": "function",
                                    "function": {
                                        "name": "",
                                        "arguments": "",
                                    },
                                }

                            # Update with new data
                            if tc.get("id"):
                                accumulated_tool_calls[idx]["id"] = tc["id"]
                            if func.get("name"):
                                accumulated_tool_calls[idx]["function"]["name"] += func["name"]
                            if func.get("arguments"):
                                accumulated_tool_calls[idx]["function"]["arguments"] += func["arguments"]

                    # On final chunk, include accumulated tool calls
                    complete_tool_calls = None
                    if is_final and accumulated_tool_calls:
                        complete_tool_calls = [
                            accumulated_tool_calls[idx] for idx in sorted(accumulated_tool_calls.keys())
                        ]

                    yield StreamChunk(
                        content=content,
                        is_final=is_final,
                        finish_reason=choice.get("finish_reason"),
                        tool_call_delta=tool_call_delta,
                        tool_calls=complete_tool_calls,
                        input_tokens=final_input_tokens if is_final else 0,
                        output_tokens=final_output_tokens if is_final else 0,
                    )

        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
        except Exception as e:
            raise self._handle_error(e) from e

    def list_models(self) -> list[dict[str, Any]]:
        """
        List available models from OpenRouter.

        Returns:
            List of model dicts with 'id', 'name', constraints, pricing, and metadata.
        """
        try:
            response = self.client.get("/models")
            response.raise_for_status()
            data = response.json()

            models = []
            for model_data in data.get("data", []):
                model_id = model_data.get("id", "")
                constraints = self._get_model_constraints(model_data)
                pricing = self._extract_pricing(model_data)

                models.append(
                    {
                        "id": model_id,
                        "name": model_data.get("name", model_id),
                        "description": model_data.get("description", ""),
                        "context_length": model_data.get("context_length"),
                        "provider": self.provider_name,
                        "created": model_data.get("created"),
                        **constraints,
                        **pricing,
                    }
                )

            # Sort by model ID for consistent ordering
            models.sort(key=lambda m: m["id"])
            return models

        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
        except Exception as e:
            raise self._handle_error(e) from e

    def _get_model_constraints(self, model_data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract temperature, token, and capability constraints from model data.

        OpenRouter provides:
        - supported_parameters: list of parameters the model accepts
        - default_parameters: dict of default values
        - input_modalities: list like ["text", "image"]
        - output_modalities: list like ["text"]
        """
        model_id = model_data.get("id", "").lower()
        supported_params = model_data.get("supported_parameters", [])
        default_params = model_data.get("default_parameters", {})
        input_modalities = model_data.get("input_modalities", ["text"])
        output_modalities = model_data.get("output_modalities", ["text"])

        # Check if it's a reasoning model
        is_reasoning = any(model_id.startswith(prefix.lower()) for prefix in self.REASONING_MODEL_PREFIXES)

        # Determine temperature support
        # Either from supported_parameters or by checking if not a reasoning model
        supports_temperature = "temperature" in supported_params if supported_params else not is_reasoning

        # Get temperature bounds from default_parameters or use defaults
        if is_reasoning:
            min_temp = 1.0
            max_temp = 1.0
            default_temp = 1.0
        else:
            # Try to extract from model data, fallback to standard bounds
            min_temp = default_params.get("min_temperature", 0.0)
            max_temp = default_params.get("max_temperature", 2.0)
            default_temp = default_params.get("temperature", 1.0)

        # Vision support from input modalities
        supports_vision = "image" in input_modalities

        # Tool/function calling support
        supports_tools = "tools" in supported_params or "tool_choice" in supported_params

        # Max output tokens
        max_output = model_data.get("top_provider", {}).get("max_completion_tokens")
        if not max_output:
            max_output = model_data.get("max_tokens", 4096)

        return {
            "supports_temperature": supports_temperature,
            "default_temperature": default_temp,
            "min_temperature": min_temp,
            "max_temperature": max_temp,
            "supports_reasoning": is_reasoning,
            "supports_vision": supports_vision,
            "supports_tools": supports_tools,
            "supports_streaming": True,  # OpenRouter supports streaming for all models
            "max_output_tokens": max_output,
            "default_max_tokens": min(max_output, 4096) if max_output else 4096,
            "input_modalities": input_modalities,
            "output_modalities": output_modalities,
        }

    def _extract_pricing(self, model_data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract pricing information from model data.

        OpenRouter provides pricing in the 'pricing' field:
        - prompt: cost per input token (as string like "0.000001")
        - completion: cost per output token (as string)
        """
        pricing = model_data.get("pricing", {})

        try:
            prompt_price = float(pricing.get("prompt", "0")) if pricing.get("prompt") else None
            completion_price = float(pricing.get("completion", "0")) if pricing.get("completion") else None
            image_price = float(pricing.get("image", "0")) if pricing.get("image") else None
        except (ValueError, TypeError):
            prompt_price = None
            completion_price = None
            image_price = None

        return {
            "input_cost_per_token": prompt_price,
            "output_cost_per_token": completion_price,
            "image_cost_per_token": image_price,
        }

    def _handle_http_error(self, error: httpx.HTTPStatusError) -> ProviderError:
        """Convert HTTP errors to ProviderError types."""
        status = error.response.status_code
        try:
            error_data = error.response.json()
            message = error_data.get("error", {}).get("message", str(error))
        except (ValueError, KeyError):
            message = str(error)

        if status == 429:
            return RateLimitError(
                message=message,
                provider=self.provider_name,
                status_code=429,
            )

        if status == 401:
            return AuthenticationError(
                message=message,
                provider=self.provider_name,
                status_code=401,
            )

        if status == 400 and "context" in message.lower():
            return ContextLengthError(
                message=message,
                provider=self.provider_name,
            )

        return ProviderError(
            message=message,
            provider=self.provider_name,
            status_code=status,
        )

    def _handle_error(self, error: Exception) -> ProviderError:
        """Convert general exceptions to ProviderError."""
        return ProviderError(
            message=str(error),
            provider=self.provider_name,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "OpenRouterProvider":
        return self

    def __exit__(self, *args) -> None:
        self.close()
