"""
Unit tests for the IONOS AI Model Hub provider (OpenAI-compatible, EU-hosted).

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
from eq_chatbot_core.providers.ionos_provider import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    IonosProvider,
)

# Loopback URL keeps validate_url hermetic when an explicit base_url is needed.
TEST_BASE_URL = "http://localhost:4000/v1"


# =============================================================================
# Fixtures
# =============================================================================


def _assert_pinned_http_client(call_kwargs):
    """The SDK client must be routed through the DNS-rebinding-aware transport."""
    http_client = call_kwargs["http_client"]
    transport = http_client._transport
    assert type(transport).__name__ == "_RevalidatingHostTransport", (
        f"expected pinned transport, got {type(transport).__name__}"
    )


@pytest.fixture
def mock_chat_response():
    """Mock chat completion response."""
    response = MagicMock()
    response.model = "meta-llama/Llama-3.3-70B-Instruct"
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Hallo aus der EU-Cloud."
    response.choices[0].message.tool_calls = None
    response.choices[0].finish_reason = "stop"
    response.usage = MagicMock()
    response.usage.prompt_tokens = 11
    response.usage.completion_tokens = 7
    response.model_dump.return_value = {"model": "meta-llama/Llama-3.3-70B-Instruct"}
    return response


@pytest.fixture
def mock_stream_chunks():
    """Mock streaming chunk generator (usage arrives in the final chunk)."""

    def generate():
        for content in ["Hal", "lo", "!"]:
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
    """Mock /v1/models response — IONOS serves Llama/Mistral models."""
    models = MagicMock()
    models.data = [
        MagicMock(id="meta-llama/Llama-3.3-70B-Instruct", created=1700000000, owned_by="ionos"),
        MagicMock(id="mistralai/Mistral-Small-24B-Instruct", created=1700000000, owned_by="ionos"),
        MagicMock(id="openGPT-X/Teuken-7B-instruct-commercial", created=1700000000, owned_by="ionos"),
    ]
    return models


@pytest.fixture(autouse=True)
def _use_ionos_openai_mock():
    """Install our openai mock for each test, then restore the prior entry.

    Other provider test modules (e.g. test_openai.py, test_litellm.py) also
    replace sys.modules["openai"] at import time, so the live entry depends on
    import order. Installing our mock per-test and restoring afterwards makes
    these tests isolation-proof in both directions.
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


def _make_provider_with_client(mock_client) -> IonosProvider:
    """Build a provider whose openai client is the given mock."""
    mock_openai_module.OpenAI = MagicMock(return_value=mock_client)
    provider = IonosProvider(api_key="test-key")
    provider._client = None  # force lazy re-creation through the mocked OpenAI()
    return provider


# =============================================================================
# Initialization
# =============================================================================


@pytest.mark.unit
class TestIonosProviderInit:
    def test_basic_init_defaults_base_url(self):
        provider = IonosProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.base_url == DEFAULT_BASE_URL
        assert provider.timeout == 60.0
        assert provider.max_retries == 2

    def test_base_url_optional(self):
        # Unlike LiteLLM, IONOS does not require an explicit base_url.
        provider = IonosProvider(api_key="test-key")
        assert provider.base_url == DEFAULT_BASE_URL

    def test_base_url_override(self):
        provider = IonosProvider(api_key="test-key", base_url=TEST_BASE_URL)
        assert provider.base_url == TEST_BASE_URL

    def test_ssrf_metadata_blocked(self):
        with pytest.raises(ValueError):
            IonosProvider(api_key="test-key", base_url="http://169.254.169.254/v1")

    def test_private_range_blocked(self):
        # IONOS is a fixed public endpoint; private ranges are rejected.
        with pytest.raises(ValueError):
            IonosProvider(api_key="test-key", base_url="http://10.0.0.5/v1")

    def test_non_http_scheme_blocked(self):
        with pytest.raises(ValueError):
            IonosProvider(api_key="test-key", base_url="file:///etc/passwd")

    def test_lazy_client(self):
        provider = IonosProvider(api_key="test-key")
        assert provider._client is None

    def test_client_created_with_default_base_url(self):
        mock_openai_class = MagicMock()
        mock_openai_module.OpenAI = mock_openai_class

        provider = IonosProvider(api_key="test-key")
        provider._client = None
        _ = provider.client

        kwargs = mock_openai_class.call_args.kwargs
        _assert_pinned_http_client(kwargs)
        assert {k: v for k, v in kwargs.items() if k != "http_client"} == {
            "api_key": "test-key",
            "base_url": DEFAULT_BASE_URL,
            "timeout": 60.0,
            "max_retries": 2,
        }


@pytest.mark.unit
class TestIonosProviderProperties:
    def test_provider_name(self):
        provider = IonosProvider(api_key="x")
        assert provider.provider_name == "ionos"

    def test_default_model_fallback(self):
        provider = IonosProvider(api_key="x")
        assert provider.default_model == DEFAULT_MODEL

    def test_default_model_override(self):
        provider = IonosProvider(api_key="x", model="mistralai/Mistral-Small-24B-Instruct")
        assert provider.default_model == "mistralai/Mistral-Small-24B-Instruct"


# =============================================================================
# Chat completion
# =============================================================================


@pytest.mark.unit
class TestIonosChatCompletion:
    def test_simple_completion(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        response = provider.chat_completion(messages=[{"role": "user", "content": "Sag Hallo"}])

        assert response.content == "Hallo aus der EU-Cloud."
        assert response.model == "meta-llama/Llama-3.3-70B-Instruct"
        assert response.input_tokens == 11
        assert response.output_tokens == 7
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
            model="mistralai/Mistral-Small-24B-Instruct",
            max_tokens=128,
        )
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "mistralai/Mistral-Small-24B-Instruct"
        assert kwargs["max_tokens"] == 128

    def test_tools_passed_through(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]
        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}], tools=tools)
        assert mock_client.chat.completions.create.call_args.kwargs["tools"] == tools

    def test_temperature_clamped(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        # Llama supports 0.0-2.0; a normal value passes through unchanged.
        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}], temperature=0.5)
        assert mock_client.chat.completions.create.call_args.kwargs["temperature"] == 0.5

    def test_tool_calls_parsed(self):
        tool_call = MagicMock()
        tool_call.id = "call_1"
        tool_call.type = "function"
        tool_call.function.name = "get_weather"
        tool_call.function.arguments = '{"city": "Berlin"}'

        resp = MagicMock()
        resp.model = "meta-llama/Llama-3.3-70B-Instruct"
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
class TestIonosStreamCompletion:
    def test_basic_stream(self, mock_stream_chunks):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_stream_chunks()
        provider = _make_provider_with_client(mock_client)

        chunks = list(provider.stream_completion(messages=[{"role": "user", "content": "Hi"}]))
        full = "".join(c.content for c in chunks if c.content)
        assert full == "Hallo!"
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
class TestIonosListModels:
    def test_returns_all_models_unfiltered(self, mock_models_list):
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_models_list
        provider = _make_provider_with_client(mock_client)

        models = provider.list_models()
        ids = [m["id"] for m in models]
        assert "meta-llama/Llama-3.3-70B-Instruct" in ids
        assert "openGPT-X/Teuken-7B-instruct-commercial" in ids
        assert all(m["provider"] == "ionos" for m in models)


# =============================================================================
# Error handling
# =============================================================================


@pytest.mark.unit
class TestIonosErrorHandling:
    def _provider_raising(self, exc: Exception) -> IonosProvider:
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
# Context manager
# =============================================================================


@pytest.mark.unit
class TestIonosContextManager:
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
        with IonosProvider(api_key="x") as provider:
            provider._client = None
            _ = provider.client
        mock_client.close.assert_called_once()
