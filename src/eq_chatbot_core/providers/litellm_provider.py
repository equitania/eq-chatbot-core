"""
LiteLLM provider implementation.

Connects to any OpenAI-compatible gateway — primarily a LiteLLM proxy, but also
vLLM, self-hosted endpoints, or other vendors that expose the OpenAI Chat
Completions / Audio API. Built on the standard ``openai`` SDK (already a core
dependency); no extra package is required.

Unlike the cloud providers, this provider has **no default base_url**: the caller
must supply the endpoint explicitly via ``base_url``. There is no default model, TTS model, voice or STT model: pass them per call or to the constructor.

Chat, streaming and model listing are inherited from
:class:`OpenAICompatibleProvider`; this module adds the OpenAI Audio API surface
(text-to-speech and speech-to-text), which the pure chat gateways do not expose.

Reference endpoints (OpenAI-compatible):
- POST /v1/chat/completions   (chat + streaming)
- GET  /v1/models
- POST /v1/audio/speech       (text-to-speech)
- POST /v1/audio/transcriptions (speech-to-text)
"""

from typing import Any

from eq_chatbot_core.providers.base import ModelNotSpecifiedError
from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider


class LiteLLMProvider(OpenAICompatibleProvider):
    """
    Provider for OpenAI-compatible gateways (LiteLLM proxy, vLLM, custom endpoints).

    Requires an explicit ``base_url`` (no default) and an ``api_key`` sent as a
    Bearer token. Supports chat completion, streaming, tool calls, model listing,
    and — via the OpenAI Audio API — text-to-speech and speech-to-text.
    """

    PROVIDER_NAME = "litellm"
    # Intentionally no default endpoint — a gateway address cannot be guessed.
    DEFAULT_BASE_URL = None
    # Gateways may be public or self-hosted on a LAN, so private ranges are
    # allowed here; cloud-metadata and link-local targets stay blocked.
    ALLOW_PRIVATE_RANGES = True
    MISSING_BASE_URL_MESSAGE = "LiteLLMProvider requires an explicit base_url (e.g. 'https://litellm.example.com/v1'). There is no default endpoint."

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        model: str | None = None,
        *,
        tts_model: str | None = None,
        tts_voice: str | None = None,
        stt_model: str | None = None,
    ):
        """
        Initialize the gateway provider.

        Args:
            api_key: Gateway key, sent as a Bearer token.
            base_url: OpenAI-compatible endpoint (required).
            timeout: Request timeout in seconds.
            max_retries: Number of retries on transient failures.
            model: Chat model used when a call passes none.
            tts_model: Text-to-speech model used when ``text_to_speech`` gets none.
            tts_voice: Voice used when ``text_to_speech`` gets none.
            stt_model: Speech-to-text model used when ``transcribe`` gets none.
        """
        super().__init__(api_key, base_url, timeout, max_retries, model)
        self.tts_model = tts_model or None
        self.tts_voice = tts_voice or None
        self.stt_model = stt_model or None

    def text_to_speech(
        self,
        text: str,
        *,
        model: str | None = None,
        voice: str | None = None,
        response_format: str = "wav",
        **kwargs: Any,
    ) -> bytes:
        """
        Synthesize speech from text via the gateway's TTS endpoint.

        Args:
            text: Input text to synthesize.
            model: TTS model id; falls back to the constructor's ``tts_model``.
            voice: Voice id; falls back to the constructor's ``tts_voice``.
            response_format: Audio container, e.g. ``wav`` or ``mp3``.
            **kwargs: Additional provider-specific parameters.

        Returns:
            Raw audio bytes.

        Raises:
            ModelNotSpecifiedError: If no model or no voice is given anywhere.
        """
        model = model or self.tts_model
        if not model:
            raise ModelNotSpecifiedError(
                self.provider_name, what="text-to-speech model", constructor_argument="tts_model"
            )
        voice = voice or self.tts_voice
        if not voice:
            raise ModelNotSpecifiedError(
                self.provider_name, what="text-to-speech voice", argument="voice", constructor_argument="tts_voice"
            )
        try:
            response = self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format=response_format,
                **kwargs,
            )
            # openai SDK returns a binary response wrapper; .read() yields bytes.
            value: bytes = response.read()
            return value
        except Exception as e:
            raise self._handle_error(e) from e

    def transcribe(
        self,
        audio: Any,
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Transcribe audio to text via the gateway's STT endpoint.

        Args:
            audio: Audio input accepted by the OpenAI SDK ``file`` parameter — a
                file-like object opened in binary mode, raw ``bytes``, or a
                ``(filename, bytes, content_type)`` tuple.
            model: STT model id; falls back to the constructor's ``stt_model``.
            **kwargs: Additional provider-specific parameters.

        Returns:
            The transcribed text.

        Raises:
            ModelNotSpecifiedError: If no model is given anywhere.
        """
        model = model or self.stt_model
        if not model:
            raise ModelNotSpecifiedError(
                self.provider_name, what="speech-to-text model", constructor_argument="stt_model"
            )
        try:
            response = self.client.audio.transcriptions.create(
                model=model,
                file=audio,
                **kwargs,
            )
            value: str = response.text
            return value
        except Exception as e:
            raise self._handle_error(e) from e
