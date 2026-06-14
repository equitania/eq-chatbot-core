"""
LiteLLM provider implementation.

Connects to any OpenAI-compatible gateway — primarily a LiteLLM proxy, but also
vLLM, self-hosted endpoints, or other vendors that expose the OpenAI Chat
Completions / Audio API. Built on the standard ``openai`` SDK (already a core
dependency); no extra package is required.

Unlike the cloud providers, this provider has **no default base_url**: the caller
must supply the endpoint explicitly via ``base_url``. The default model is a soft
default (overridable per call or via the ``model`` constructor argument).

Reference endpoints (OpenAI-compatible):
- POST /v1/chat/completions   (chat + streaming)
- POST /v1/audio/speech       (text-to-speech)
- POST /v1/audio/transcriptions (speech-to-text)
- GET  /v1/models
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

# Soft defaults — all overridable. These match the CCSolutions.io LiteLLM proxy
# documented in the vendor usage guide, but the provider is endpoint-agnostic.
DEFAULT_MODEL = "qwen3.6-35b-a3b"
DEFAULT_TTS_MODEL = "kokoro-tts-1"
DEFAULT_TTS_VOICE = "af_bella"
DEFAULT_STT_MODEL = "whisper-large-v3"


class LiteLLMProvider(BaseLLMProvider):
    """
    Provider for OpenAI-compatible gateways (LiteLLM proxy, vLLM, custom endpoints).

    Requires an explicit ``base_url`` (no default) and an ``api_key`` sent as a
    Bearer token. Supports chat completion, streaming, tool calls, model listing,
    and — via the OpenAI Audio API — text-to-speech and speech-to-text.
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
        Initialize the LiteLLM provider.

        Args:
            api_key: API key sent as ``Authorization: Bearer <api_key>``.
            base_url: OpenAI-compatible endpoint, e.g. ``https://api.ccsio.ai/v1``.
                Required — there is intentionally no default.
            timeout: Request timeout in seconds.
            max_retries: Number of retries on transient failures.
            model: Default model id for this instance (overridable per call).
                Falls back to ``DEFAULT_MODEL`` when not given.

        Raises:
            ValueError: If ``base_url`` is missing/empty or fails URL validation.
        """
        if not base_url or not base_url.strip():
            raise ValueError(
                "LiteLLMProvider requires an explicit base_url (e.g. "
                "'https://api.ccsio.ai/v1'). There is no default endpoint."
            )

        # SSRF guard: gateways may be public or self-hosted on a LAN, so private
        # ranges are allowed — but reject non-HTTP schemes and cloud-metadata /
        # link-local targets. Imported lazily to avoid an import cycle.
        from eq_chatbot_core.utils.url_validation import validate_url

        validate_url(base_url, allow_private_ranges=True)

        super().__init__(api_key, base_url, timeout, max_retries)
        self._model = model
        self._client: Any = None  # Lazy initialization

    @property
    def provider_name(self) -> str:
        return "litellm"

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
        """Send a chat completion request to the gateway."""
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

            # Note: reasoning models (e.g. qwen) may also return a non-standard
            # `reasoning_content` field. It is preserved in raw_response below but
            # intentionally NOT merged into `content` (the answer != the thinking).
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
        """Stream a chat completion response from the gateway."""
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
            # (e.g. LiteLLM/vLLM) send `finish_reason` and the usage totals in
            # SEPARATE chunks, with usage arriving last.
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

                # Only the answer content is streamed as `content`; the optional
                # non-standard `reasoning_content` delta is not folded in.
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
        List models advertised by the gateway.

        Returns all models from the OpenAI-compatible ``/v1/models`` endpoint
        without provider-specific name filtering — the gateway may serve models
        from any backend (e.g. ``qwen3.6-35b-a3b``) plus audio models.
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

    def text_to_speech(
        self,
        text: str,
        *,
        model: str = DEFAULT_TTS_MODEL,
        voice: str = DEFAULT_TTS_VOICE,
        response_format: str = "wav",
        **kwargs,
    ) -> bytes:
        """
        Synthesize speech from text via the gateway's TTS endpoint.

        Args:
            text: Input text to synthesize.
            model: TTS model id (default: ``kokoro-tts-1``).
            voice: Voice id (default: ``af_bella``).
            response_format: Audio container, e.g. ``wav`` or ``mp3``.
            **kwargs: Additional provider-specific parameters.

        Returns:
            Raw audio bytes.
        """
        try:
            response = self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format=response_format,
                **kwargs,
            )
            # openai SDK returns a binary response wrapper; .read() yields bytes.
            return response.read()
        except Exception as e:
            raise self._handle_error(e) from e

    def transcribe(
        self,
        audio: Any,
        *,
        model: str = DEFAULT_STT_MODEL,
        **kwargs,
    ) -> str:
        """
        Transcribe audio to text via the gateway's STT endpoint.

        Args:
            audio: Audio input accepted by the OpenAI SDK ``file`` parameter — a
                file-like object opened in binary mode, raw ``bytes``, or a
                ``(filename, bytes, content_type)`` tuple.
            model: STT model id (default: ``whisper-large-v3``).
            **kwargs: Additional provider-specific parameters.

        Returns:
            The transcribed text.
        """
        try:
            response = self.client.audio.transcriptions.create(
                model=model,
                file=audio,
                **kwargs,
            )
            return response.text
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

    def __enter__(self) -> "LiteLLMProvider":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
