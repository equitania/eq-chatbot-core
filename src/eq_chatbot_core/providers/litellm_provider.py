"""
LiteLLM provider implementation.

Connects to any OpenAI-compatible gateway — primarily a LiteLLM proxy, but also
vLLM, self-hosted endpoints, or other vendors that expose the OpenAI Chat
Completions / Audio API. Built on the standard ``openai`` SDK (already a core
dependency); no extra package is required.

Unlike the cloud providers, this provider has **no default base_url**: the caller
must supply the endpoint explicitly via ``base_url``. The default model is a soft
default (overridable per call or via the ``model`` constructor argument).

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

from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider

# Audio defaults are referenced in method signatures below, so they must be
# module-level. The chat DEFAULT_MODEL is a class attribute (aliased at the
# bottom of this module for backwards compatibility).
DEFAULT_TTS_MODEL = "kokoro-tts-1"
DEFAULT_TTS_VOICE = "af_bella"
DEFAULT_STT_MODEL = "whisper-large-v3"


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
    # Soft default — overridable per call or via the ``model`` constructor argument.
    DEFAULT_MODEL = "qwen3.6-35b-a3b"
    # Gateways may be public or self-hosted on a LAN, so private ranges are
    # allowed here; cloud-metadata and link-local targets stay blocked.
    ALLOW_PRIVATE_RANGES = True
    MISSING_BASE_URL_MESSAGE = (
        "LiteLLMProvider requires an explicit base_url (e.g. 'https://api.ccsio.ai/v1'). There is no default endpoint."
    )

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


# Module-level alias kept for backwards compatibility with existing importers.
DEFAULT_MODEL = LiteLLMProvider.DEFAULT_MODEL
