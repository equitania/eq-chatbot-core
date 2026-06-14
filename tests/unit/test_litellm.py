"""
Unit tests for the LiteLLM provider (OpenAI-compatible gateway).

All tests use mocked responses - no real API calls. The provider is built on the
openai SDK, so the openai module is mocked at import time.
"""

import sys
from unittest.mock import MagicMock

import pytest

# Mock the openai module before importing the provider.
mock_openai_module = MagicMock()
sys.modules["openai"] = mock_openai_module

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    ContextLengthError,
    ProviderError,
    RateLimitError,
)
from eq_chatbot_core.providers.litellm_provider import (
    DEFAULT_MODEL,
    DEFAULT_STT_MODEL,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    LiteLLMProvider,
)

# Loopback URL keeps validate_url hermetic (no DNS / network in unit tests).
TEST_BASE_URL = "http://localhost:4000/v1"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_chat_response():
    """Mock chat completion response (with a reasoning_content raw field)."""
    response = MagicMock()
    response.model = "qwen3.6-35b-a3b"
    response.choices = [MagicMock()]
    response.choices[0].message.content = "A MoE model routes tokens to experts."
    response.choices[0].message.tool_calls = None
    response.choices[0].finish_reason = "stop"
    response.usage = MagicMock()
    response.usage.prompt_tokens = 12
    response.usage.completion_tokens = 8
    response.model_dump.return_value = {
        "model": "qwen3.6-35b-a3b",
        "choices": [{"message": {"reasoning_content": "thinking about experts..."}}],
    }
    return response


@pytest.fixture
def mock_stream_chunks():
    """Mock streaming chunk generator."""

    def generate():
        for content in ["Hel", "lo", "!"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = content
            chunk.choices[0].delta.tool_calls = None
            chunk.choices[0].finish_reason = None
            chunk.usage = None
            yield chunk

        final = MagicMock()
        final.choices = [MagicMock()]
        final.choices[0].delta.content = ""
        final.choices[0].delta.tool_calls = None
        final.choices[0].finish_reason = "stop"
        final.usage = MagicMock()
        final.usage.prompt_tokens = 5
        final.usage.completion_tokens = 3
        yield final

    return generate


@pytest.fixture
def mock_models_list():
    """Mock /v1/models response — gateway serves non-gpt models + audio models."""
    models = MagicMock()
    models.data = [
        MagicMock(id="qwen3.6-35b-a3b", created=1700000000, owned_by="ccsio"),
        MagicMock(id="kokoro-tts-1", created=1700000000, owned_by="ccsio"),
        MagicMock(id="whisper-large-v3", created=1700000000, owned_by="ccsio"),
    ]
    return models


@pytest.fixture(autouse=True)
def _use_litellm_openai_mock():
    """Install our openai mock for each test, then restore the prior entry.

    Other provider test modules (e.g. test_openai.py) also replace
    sys.modules["openai"] at import time, so the live entry depends on import
    order. Installing our mock per-test and restoring afterwards makes these
    tests isolation-proof in both directions.
    """
    saved = sys.modules.get("openai")
    sys.modules["openai"] = mock_openai_module
    try:
        yield
    finally:
        if saved is not None:
            sys.modules["openai"] = saved
        else:
            sys.modules.pop("openai", None)


def _make_provider_with_client(mock_client) -> LiteLLMProvider:
    """Build a provider whose openai client is the given mock."""
    mock_openai_module.OpenAI = MagicMock(return_value=mock_client)
    provider = LiteLLMProvider(api_key="test-key", base_url=TEST_BASE_URL)
    provider._client = None  # force lazy re-creation through the mocked OpenAI()
    return provider


# =============================================================================
# Initialization
# =============================================================================


@pytest.mark.unit
class TestLiteLLMProviderInit:
    def test_basic_init(self):
        provider = LiteLLMProvider(api_key="test-key", base_url=TEST_BASE_URL)
        assert provider.api_key == "test-key"
        assert provider.base_url == TEST_BASE_URL
        assert provider.timeout == 60.0
        assert provider.max_retries == 2

    def test_base_url_required(self):
        with pytest.raises(ValueError, match="base_url"):
            LiteLLMProvider(api_key="test-key")

    def test_base_url_empty_rejected(self):
        with pytest.raises(ValueError, match="base_url"):
            LiteLLMProvider(api_key="test-key", base_url="   ")

    def test_ssrf_metadata_blocked(self):
        with pytest.raises(ValueError):
            LiteLLMProvider(api_key="test-key", base_url="http://169.254.169.254/v1")

    def test_non_http_scheme_blocked(self):
        with pytest.raises(ValueError):
            LiteLLMProvider(api_key="test-key", base_url="file:///etc/passwd")

    def test_lazy_client(self):
        provider = LiteLLMProvider(api_key="test-key", base_url=TEST_BASE_URL)
        assert provider._client is None

    def test_client_created_with_base_url(self):
        mock_openai_class = MagicMock()
        mock_openai_module.OpenAI = mock_openai_class

        provider = LiteLLMProvider(api_key="test-key", base_url=TEST_BASE_URL)
        provider._client = None
        _ = provider.client

        mock_openai_class.assert_called_once_with(
            api_key="test-key",
            base_url=TEST_BASE_URL,
            timeout=60.0,
            max_retries=2,
        )


@pytest.mark.unit
class TestLiteLLMProviderProperties:
    def test_provider_name(self):
        provider = LiteLLMProvider(api_key="x", base_url=TEST_BASE_URL)
        assert provider.provider_name == "litellm"

    def test_default_model_fallback(self):
        provider = LiteLLMProvider(api_key="x", base_url=TEST_BASE_URL)
        assert provider.default_model == DEFAULT_MODEL

    def test_default_model_override(self):
        provider = LiteLLMProvider(api_key="x", base_url=TEST_BASE_URL, model="custom-1")
        assert provider.default_model == "custom-1"


# =============================================================================
# Chat completion
# =============================================================================


@pytest.mark.unit
class TestLiteLLMChatCompletion:
    def test_simple_completion(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        response = provider.chat_completion(messages=[{"role": "user", "content": "What is a MoE model?"}])

        assert response.content == "A MoE model routes tokens to experts."
        assert response.model == "qwen3.6-35b-a3b"
        assert response.input_tokens == 12
        assert response.output_tokens == 8
        assert response.finish_reason == "stop"

    def test_uses_default_model(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])
        assert mock_client.chat.completions.create.call_args.kwargs["model"] == DEFAULT_MODEL

    def test_explicit_model_and_max_tokens(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        provider.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            model="qwen3.6-35b-a3b",
            max_tokens=128,
        )
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "qwen3.6-35b-a3b"
        assert kwargs["max_tokens"] == 128

    def test_tools_passed_through(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]
        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}], tools=tools)
        assert mock_client.chat.completions.create.call_args.kwargs["tools"] == tools

    def test_reasoning_content_in_raw_not_in_content(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        response = provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])
        # The answer is the content; the reasoning lives only in raw_response.
        assert "thinking about experts" not in response.content
        assert response.raw_response is not None

    def test_tool_calls_parsed(self):
        tool_call = MagicMock()
        tool_call.id = "call_1"
        tool_call.type = "function"
        tool_call.function.name = "get_weather"
        tool_call.function.arguments = '{"city": "Berlin"}'

        resp = MagicMock()
        resp.model = "qwen3.6-35b-a3b"
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = None
        resp.choices[0].message.tool_calls = [tool_call]
        resp.choices[0].finish_reason = "tool_calls"
        resp.usage = MagicMock(prompt_tokens=5, completion_tokens=2)
        resp.model_dump.return_value = {}

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = resp
        provider = _make_provider_with_client(mock_client)

        response = provider.chat_completion(messages=[{"role": "user", "content": "weather?"}])
        assert response.content == ""
        assert response.tool_calls[0]["function"]["name"] == "get_weather"


# =============================================================================
# Streaming
# =============================================================================


@pytest.mark.unit
class TestLiteLLMStreamCompletion:
    def test_basic_stream(self, mock_stream_chunks):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_stream_chunks()
        provider = _make_provider_with_client(mock_client)

        chunks = list(provider.stream_completion(messages=[{"role": "user", "content": "Hi"}]))
        full = "".join(c.content for c in chunks if c.content)
        assert full == "Hello!"
        assert chunks[-1].is_final is True
        assert chunks[-1].input_tokens == 5
        assert chunks[-1].output_tokens == 3

    def test_stream_requests_usage(self, mock_stream_chunks):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_stream_chunks()
        provider = _make_provider_with_client(mock_client)

        list(provider.stream_completion(messages=[{"role": "user", "content": "Hi"}]))
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["stream"] is True
        assert kwargs["stream_options"] == {"include_usage": True}


# =============================================================================
# list_models
# =============================================================================


@pytest.mark.unit
class TestLiteLLMListModels:
    def test_returns_all_models_unfiltered(self, mock_models_list):
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_models_list
        provider = _make_provider_with_client(mock_client)

        models = provider.list_models()
        ids = [m["id"] for m in models]
        # The non-gpt qwen model must NOT be filtered out.
        assert "qwen3.6-35b-a3b" in ids
        assert all(m["provider"] == "litellm" for m in models)


# =============================================================================
# Error handling
# =============================================================================


@pytest.mark.unit
class TestLiteLLMErrorHandling:
    def _provider_raising(self, exc: Exception) -> LiteLLMProvider:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = exc
        return _make_provider_with_client(mock_client)

    def test_rate_limit(self):
        provider = self._provider_raising(Exception("429 rate limit exceeded"))
        with pytest.raises(RateLimitError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    def test_authentication(self):
        provider = self._provider_raising(Exception("401 authentication failed"))
        with pytest.raises(AuthenticationError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    def test_context_length(self):
        provider = self._provider_raising(Exception("context length exceeded"))
        with pytest.raises(ContextLengthError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    def test_generic_error(self):
        provider = self._provider_raising(Exception("something odd happened"))
        with pytest.raises(ProviderError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    def test_error_scrubs_secret(self):
        provider = self._provider_raising(Exception("500 error for key sk-leakedsecret12345"))
        with pytest.raises(ProviderError) as exc_info:
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])
        assert "sk-leakedsecret12345" not in str(exc_info.value)


# =============================================================================
# Audio: TTS + STT
# =============================================================================


@pytest.mark.unit
class TestLiteLLMAudio:
    def test_text_to_speech_returns_bytes(self):
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value.read.return_value = b"RIFFfake-wav-bytes"
        provider = _make_provider_with_client(mock_client)

        audio = provider.text_to_speech("Hello from ccsolutions.")
        assert audio == b"RIFFfake-wav-bytes"
        kwargs = mock_client.audio.speech.create.call_args.kwargs
        assert kwargs["model"] == DEFAULT_TTS_MODEL
        assert kwargs["voice"] == DEFAULT_TTS_VOICE
        assert kwargs["input"] == "Hello from ccsolutions."

    def test_text_to_speech_custom_voice_and_model(self):
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value.read.return_value = b"data"
        provider = _make_provider_with_client(mock_client)

        provider.text_to_speech("Hi", model="kokoro-tts-2", voice="af_nova", response_format="mp3")
        kwargs = mock_client.audio.speech.create.call_args.kwargs
        assert kwargs["model"] == "kokoro-tts-2"
        assert kwargs["voice"] == "af_nova"
        assert kwargs["response_format"] == "mp3"

    def test_transcribe_returns_text(self):
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value.text = "Hello from ccsolutions."
        provider = _make_provider_with_client(mock_client)

        text = provider.transcribe(b"fake-audio-bytes")
        assert text == "Hello from ccsolutions."
        kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
        assert kwargs["model"] == DEFAULT_STT_MODEL
        assert kwargs["file"] == b"fake-audio-bytes"

    def test_tts_error_is_provider_error(self):
        mock_client = MagicMock()
        mock_client.audio.speech.create.side_effect = Exception("500 tts backend error")
        provider = _make_provider_with_client(mock_client)
        with pytest.raises(ProviderError):
            provider.text_to_speech("Hi")


# =============================================================================
# Context manager
# =============================================================================


@pytest.mark.unit
class TestLiteLLMContextManager:
    def test_close_closes_client(self):
        mock_client = MagicMock()
        provider = _make_provider_with_client(mock_client)
        _ = provider.client  # initialize
        provider.close()
        mock_client.close.assert_called_once()
        assert provider._client is None

    def test_context_manager(self):
        mock_client = MagicMock()
        mock_openai_module.OpenAI = MagicMock(return_value=mock_client)
        with LiteLLMProvider(api_key="x", base_url=TEST_BASE_URL) as provider:
            provider._client = None
            _ = provider.client
        mock_client.close.assert_called_once()
