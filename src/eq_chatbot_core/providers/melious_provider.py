"""
Melious.ai provider implementation.

Connects to Melious — a sovereign, EU-hosted, OpenAI-compatible inference
gateway (GDPR-compliant, green hosting, European infrastructure). Built on the
standard ``openai`` SDK (already a core dependency); no extra package is required.

Like the IONOS provider, Melious exposes a **fixed public endpoint**, so
``base_url`` defaults to the official Melious URL and is optional. The API key
(prefix ``sk-mel-``) is generated in the Melious account dashboard and sent as a
Bearer token. The default model is a soft default (overridable per call or via the
``model`` constructor argument).

Reference endpoints (OpenAI-compatible):
- POST /v1/chat/completions   (chat + streaming)
- GET  /v1/models

Note: Melious additionally offers embeddings, reranking, image generation and
speech-to-text, but those are out of scope for this chat-focused provider.
Melious-specific response fields (``environment_impact``, ``billing_cost``) and
request extras (``preset``, ``:flavor`` model suffix) pass through transparently
via ``**kwargs`` and are ignored by the OpenAI SDK.
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
from eq_chatbot_core.providers.temperature_constraints import clamp_temperature

# Official Melious OpenAI-compatible endpoint (sovereign EU infrastructure).
DEFAULT_BASE_URL = "https://api.melious.ai/v1"
# Soft default — overridable per call or via the ``model`` constructor argument.
DEFAULT_MODEL = "minimax-428b-m3"


class MeliousProvider(BaseLLMProvider):
    """
    Provider for Melious.ai (sovereign EU-hosted, OpenAI-compatible).

    Uses an ``api_key`` sent as a Bearer token and a ``base_url`` that defaults to
    the official Melious endpoint. Supports chat completion, streaming, tool calls,
    and model listing via the OpenAI-compatible Chat Completions / Models API.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        model: str | None = None,
    ):
        """
        Initialize the Melious provider.

        Args:
            api_key: Melious API key sent as ``Authorization: Bearer <api_key>``.
            base_url: OpenAI-compatible endpoint. Defaults to the official Melious
                URL (``DEFAULT_BASE_URL``); override only to route through a proxy.
            timeout: Request timeout in seconds.
            max_retries: Number of retries on transient failures.
            model: Default model id for this instance (overridable per call).
                Falls back to ``DEFAULT_MODEL`` when not given.

        Raises:
            ValueError: If ``base_url`` fails URL validation.
        """
        base_url = base_url or DEFAULT_BASE_URL

        # SSRF guard: Melious is a fixed public cloud endpoint, so private ranges
        # are rejected. Reject non-HTTP schemes and cloud-metadata / link-local
        # targets too. Imported lazily to avoid an import cycle.
        from eq_chatbot_core.utils.url_validation import validate_url

        validate_url(base_url, allow_private_ranges=False)

        super().__init__(api_key, base_url, timeout, max_retries)
        self._model = model
        self._client: Any = None  # Lazy initialization

    @property
    def provider_name(self) -> str:
        return "melious"

    @property
    def default_model(self) -> str:
        return self._model or DEFAULT_MODEL

    @property
    def client(self) -> Any:
        """Lazy initialization of the OpenAI-compatible client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError("OpenAI package not installed. Install with: pip install openai") from e

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._client

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to Melious."""
        model = model or self.default_model

        try:
            params: dict[str, Any] = {
                "model": model,
                "messages": messages,
            }

            # Clamp temperature per model constraints (skip for reasoning models)
            clamped = clamp_temperature(model, temperature)
            if clamped is not None:
                params["temperature"] = clamped

            if max_tokens:
                params["max_tokens"] = max_tokens

            if tools:
                params["tools"] = tools

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
        """Stream a chat completion response from Melious."""
        model = model or self.default_model

        try:
            params: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": True,
                "stream_options": {"include_usage": True},
            }

            clamped = clamp_temperature(model, temperature)
            if clamped is not None:
                params["temperature"] = clamped

            if max_tokens:
                params["max_tokens"] = max_tokens

            if tools:
                params["tools"] = tools

            params.update(kwargs)

            stream = self.client.chat.completions.create(**params)

            final_input_tokens = 0
            final_output_tokens = 0
            finish_reason: str | None = None
            accumulated_tool_calls: dict[int, dict[str, Any]] = {}

            # Content / tool deltas are streamed as they arrive (never marked
            # final). The authoritative final chunk is emitted AFTER the loop so
            # that trailing usage-only frames are always reflected — some gateways
            # send `finish_reason` and the usage totals in SEPARATE chunks, with
            # usage arriving last.
            for chunk in stream:
                if hasattr(chunk, "usage") and chunk.usage:
                    final_input_tokens = chunk.usage.prompt_tokens or 0
                    final_output_tokens = chunk.usage.completion_tokens or 0

                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if choice.finish_reason is not None:
                    finish_reason = choice.finish_reason

                content = delta.content or ""

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

                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.id or "",
                                "type": "function",
                                "function": {
                                    "name": "",
                                    "arguments": "",
                                },
                            }

                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                accumulated_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

                if content or tool_call_delta is not None:
                    yield StreamChunk(
                        content=content,
                        is_final=False,
                        finish_reason=None,
                        tool_call_delta=tool_call_delta,
                    )

            complete_tool_calls = None
            if accumulated_tool_calls:
                complete_tool_calls = [accumulated_tool_calls[idx] for idx in sorted(accumulated_tool_calls.keys())]

            yield StreamChunk(
                content="",
                is_final=True,
                finish_reason=finish_reason,
                tool_calls=complete_tool_calls,
                input_tokens=final_input_tokens,
                output_tokens=final_output_tokens,
            )

        except Exception as e:
            raise self._handle_error(e) from e

    def list_models(self) -> list[dict[str, Any]]:
        """
        List models advertised by Melious.

        Returns all models from the OpenAI-compatible ``/v1/models`` endpoint
        without provider-specific name filtering.
        """
        try:
            models = self.client.models.list()

            result = []
            for model in models.data:
                result.append(
                    {
                        "id": model.id,
                        "name": model.id,
                        "created": getattr(model, "created", None),
                        "owned_by": getattr(model, "owned_by", None),
                        "provider": self.provider_name,
                    }
                )

            result.sort(key=lambda m: m["id"])
            return result

        except Exception as e:
            raise self._handle_error(e) from e

    def _handle_error(self, error: Exception) -> ProviderError:
        """Convert SDK exceptions to ProviderError types (secrets scrubbed)."""
        from eq_chatbot_core.utils.secret_scrub import scrub_secrets

        message = scrub_secrets(str(error))
        error_str = message.lower()

        if "rate limit" in error_str or "429" in error_str:
            return RateLimitError(message=message, provider=self.provider_name, status_code=429)

        if "authentication" in error_str or "401" in error_str:
            return AuthenticationError(message=message, provider=self.provider_name, status_code=401)

        if "context length" in error_str or "token" in error_str:
            return ContextLengthError(message=message, provider=self.provider_name)

        return ProviderError(message=message, provider=self.provider_name)

    def close(self) -> None:
        """Close the underlying HTTP client, if initialized."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "MeliousProvider":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
