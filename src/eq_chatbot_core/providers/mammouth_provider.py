"""
Mammouth AI provider implementation.

Mammouth AI (https://mammouth.ai) provides access to 30+ AI models through a
unified OpenAI-compatible API, including OpenAI, Anthropic, Google, Mistral,
xAI, DeepSeek, Meta, and more.
"""

import json
import logging
from collections.abc import Iterator
from typing import Any

import httpx2

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    BaseLLMProvider,
    ContextLengthError,
    LLMResponse,
    OverloadedError,
    ProviderError,
    RateLimitError,
    StreamChunk,
    ToolDefinition,
    normalize_tools,
)
from eq_chatbot_core.providers.stream_accumulator import ToolCallAccumulator
from eq_chatbot_core.providers.temperature_constraints import (
    clamp_temperature as _shared_clamp_temperature,
)
from eq_chatbot_core.providers.temperature_constraints import (
    get_temperature_constraints as _shared_get_temperature_constraints,
)
from eq_chatbot_core.utils.secret_scrub import scrub_secrets

_logger = logging.getLogger(__name__)


class MammouthProvider(BaseLLMProvider):
    """
    Mammouth AI API provider for 30+ AI models.

    Supports models from multiple providers through a unified API:
    - OpenAI (GPT-4o, GPT-4.1, GPT-5.x, O1, O3, O4)
    - Anthropic (Claude Opus/Sonnet/Haiku 4.5)
    - Google (Gemini 2.5 Pro/Flash)
    - Mistral (Mistral Large)
    - xAI (Grok)
    - DeepSeek (Chat, Reasoner)
    - Meta (Llama 4)
    - And more...

    Model IDs use simple names without provider prefix (e.g. "gpt-4o",
    "claude-sonnet-4-5") unlike OpenRouter which uses "provider/model" format.
    """

    DEFAULT_BASE_URL = "https://api.mammouth.ai/v1"
    MODELS_URL = "https://api.mammouth.ai/public/models"

    # Reasoning models that don't support temperature parameter
    REASONING_MODEL_PREFIXES = ("o1", "o3", "o4")

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        """
        Initialize the Mammouth AI provider.

        Args:
            api_key: Mammouth AI API key
            base_url: Optional custom base URL (defaults to Mammouth API)
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures
        """
        # Initialize the client attribute BEFORE validation so close()/__del__
        # stay safe if the SSRF guard below raises.
        self._client: httpx2.Client | None = None

        # SSRF guard: only a caller-supplied base_url is validated — the fixed
        # public default needs no DNS round-trip. Imported lazily to avoid an
        # import cycle.
        if base_url:
            from eq_chatbot_core.utils.url_validation import validate_url

            validate_url(base_url, allow_private_ranges=False)

        super().__init__(api_key, base_url or self.DEFAULT_BASE_URL, timeout, max_retries)

    @property
    def provider_name(self) -> str:
        return "mammouth"

    @property
    def default_model(self) -> str:
        return "gpt-4o"

    @property
    def client(self) -> httpx2.Client:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            # Pin the resolved addresses against DNS rebinding. Done here rather
            # than in __init__ so the fixed public default still costs no DNS
            # round-trip until the client is actually used.
            from eq_chatbot_core.utils.url_validation import build_pinned_transport_for_url

            # __init__ always passes `base_url or DEFAULT_BASE_URL` to super(),
            # so this is never None despite the base attribute's wider type.
            base_url = self.base_url or self.DEFAULT_BASE_URL
            self._client = httpx2.Client(
                base_url=base_url,
                transport=build_pinned_transport_for_url(base_url),
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    def _is_reasoning_model(self, model: str) -> bool:
        """Check if model is a reasoning model (O1, O3, O4)."""
        model_lower = model.lower()
        return any(model_lower.startswith(prefix) for prefix in self.REASONING_MODEL_PREFIXES)

    def _get_temperature_constraints(self, model: str) -> dict[str, Any]:
        """Get temperature constraints for a specific model. Delegates to shared module."""
        return _shared_get_temperature_constraints(model)

    def _clamp_temperature(self, model: str, temperature: float) -> float | None:
        """Clamp temperature to valid range for the model. Delegates to shared module."""
        return _shared_clamp_temperature(model, temperature)

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: "list[ToolDefinition] | list[dict[str, Any]] | None" = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion request to Mammouth AI."""
        model = model or self.default_model
        # Accept ToolDefinition instances as the base class promises; the
        # request payload below needs plain OpenAI-format dicts.
        tools = normalize_tools(tools)

        try:
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
            }

            # Clamp temperature per model constraints
            clamped_temp = self._clamp_temperature(model, temperature)
            if clamped_temp is not None:
                payload["temperature"] = clamped_temp

            if max_tokens:
                payload["max_tokens"] = max_tokens

            if tools:
                payload["tools"] = tools

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

        except httpx2.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
        except Exception as e:
            raise self._handle_error(e) from e

    def stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: "list[ToolDefinition] | list[dict[str, Any]] | None" = None,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """Stream a chat completion response from Mammouth AI."""
        model = model or self.default_model
        # Accept ToolDefinition instances as the base class promises; the
        # request payload below needs plain OpenAI-format dicts.
        tools = normalize_tools(tools)

        try:
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": True,
            }

            # Clamp temperature per model constraints
            clamped_temp = self._clamp_temperature(model, temperature)
            if clamped_temp is not None:
                payload["temperature"] = clamped_temp

            if max_tokens:
                payload["max_tokens"] = max_tokens

            if tools:
                payload["tools"] = tools

            payload.update(kwargs)

            with self.client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()

                final_input_tokens = 0
                final_output_tokens = 0

                # Accumulate tool calls from deltas
                tool_calls_acc = ToolCallAccumulator()

                for line in response.iter_lines():
                    if not line:
                        continue

                    # SSE comment / keep-alive lines (lines starting with ':') are not
                    # data — ignore them per the SSE spec instead of failing to JSON-parse
                    # and logging a warning for every ping.
                    if line.startswith(":"):
                        continue

                    # Handle SSE format
                    if line.startswith("data: "):
                        line = line[6:]

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

                        tool_calls_acc.add(delta["tool_calls"])

                    # On final chunk, include accumulated tool calls
                    complete_tool_calls = tool_calls_acc.result() if is_final else None

                    yield StreamChunk(
                        content=content,
                        is_final=is_final,
                        finish_reason=choice.get("finish_reason"),
                        tool_call_delta=tool_call_delta,
                        tool_calls=complete_tool_calls,
                        input_tokens=final_input_tokens if is_final else 0,
                        output_tokens=final_output_tokens if is_final else 0,
                    )

        except httpx2.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
        except Exception as e:
            raise self._handle_error(e) from e

    def list_models(self) -> list[dict[str, Any]]:
        """
        List available models from Mammouth AI.

        Uses the /public/models endpoint (separate from the v1 base URL).
        Merges API response data with local temperature constraints.

        Returns:
            List of model dicts with 'id', 'name', constraints, and metadata.
        """
        try:
            # Models endpoint is at a different URL than the chat API
            response = httpx2.get(
                self.MODELS_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
                follow_redirects=False,
            )
            response.raise_for_status()
            data = response.json()

            models = []
            # Mammouth returns a list directly or wrapped in "data"
            model_list = data if isinstance(data, list) else data.get("data", data.get("models", []))

            for model_data in model_list:
                model_id = model_data.get("id", model_data.get("model", ""))
                if not model_id:
                    continue

                temp_constraints = self._get_temperature_constraints(model_id)
                is_reasoning = self._is_reasoning_model(model_id)

                models.append(
                    {
                        "id": model_id,
                        "name": model_data.get("name", model_id),
                        "provider": self.provider_name,
                        "context_length": model_data.get("max_input_tokens"),
                        "max_output_tokens": model_data.get("max_output_tokens"),
                        "supports_temperature": temp_constraints["supports_temperature"],
                        "min_temperature": temp_constraints["min"],
                        "max_temperature": temp_constraints["max"],
                        "supports_reasoning": is_reasoning,
                        "supports_streaming": True,
                    }
                )

            models.sort(key=lambda m: m["id"])
            return models

        except httpx2.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
        except Exception as e:
            raise self._handle_error(e) from e

    def _handle_http_error(self, error: httpx2.HTTPStatusError) -> ProviderError:
        """Convert HTTP errors to ProviderError types (secrets scrubbed)."""
        status = error.response.status_code
        try:
            # For streaming responses, content may not have been read yet
            if not error.response.is_stream_consumed:
                try:
                    error.response.read()
                except Exception:
                    pass
            error_data = error.response.json()
            # Mammouth may return {"error": "message"} (string) or {"error": {"message": "..."}} (dict)
            err_field = error_data.get("error", str(error))
            if isinstance(err_field, dict):
                message = err_field.get("message", str(error))
            else:
                message = str(err_field)
        except (ValueError, KeyError, httpx2.ResponseNotRead):
            message = str(error)

        # Gateway error bodies can echo request headers/credentials — mask before
        # the message reaches a logger or an API caller.
        message = scrub_secrets(message)

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

        if status in (503, 529):
            return OverloadedError(
                message=message,
                provider=self.provider_name,
                status_code=status,
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
        """Convert general exceptions to ProviderError (secrets scrubbed)."""
        return ProviderError(
            message=scrub_secrets(str(error)),
            provider=self.provider_name,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "MammouthProvider":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()
