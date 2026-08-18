"""
Unit tests for the Azure AI Foundry provider.

All tests use mocked responses - no real API calls.

Since v2.0.0 the provider drives the Azure OpenAI ``/v1`` endpoint through the
``openai`` SDK instead of the retired ``azure-ai-inference`` beta SDK, so there
is no optional-extra skip here any more: the openai module is a core dependency
and is mocked at import time, exactly like the other OpenAI-compatible providers.
"""

import sys
from unittest.mock import MagicMock

import pytest

# Mock the openai module before importing the provider.
mock_openai_module = MagicMock()
sys.modules["openai"] = mock_openai_module

from eq_chatbot_core.providers.azure_provider import AzureProvider
from eq_chatbot_core.providers.base import (
    AuthenticationError,
    ContextLengthError,
    ProviderError,
    RateLimitError,
)

# Loopback URL keeps validate_url hermetic (no DNS in unit tests).
TEST_BASE_URL = "http://localhost:8080/openai/v1/"
LEGACY_BASE_URL = "https://my-resource.services.ai.azure.com/models"


# =============================================================================
# Fixtures / helpers
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
    response.model = "gpt-4o"
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Hello from Azure."
    response.choices[0].message.tool_calls = None
    response.choices[0].finish_reason = "stop"
    response.usage = MagicMock()
    response.usage.prompt_tokens = 12
    response.usage.completion_tokens = 6
    response.model_dump.return_value = {"model": "gpt-4o"}
    return response


@pytest.fixture
def mock_stream_chunks():
    """Mock streaming chunk generator (usage arrives in the final chunk)."""

    def generate():
        for content in ["Hel", "lo", "!"]:
            chunk = MagicMock()
            chunk.usage = None
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = content
            chunk.choices[0].delta.tool_calls = None
            chunk.choices[0].finish_reason = None
            yield chunk

        final = MagicMock()
        final.usage = MagicMock()
        final.usage.prompt_tokens = 12
        final.usage.completion_tokens = 3
        final.choices = [MagicMock()]
        final.choices[0].delta.content = ""
        final.choices[0].delta.tool_calls = None
        final.choices[0].finish_reason = "stop"
        yield final

    return generate


def _active_openai_module():
    """Return the openai mock currently registered in ``sys.modules``.

    Several provider test modules install their own MagicMock under
    ``sys.modules["openai"]`` at import time, and the last module collected wins.
    Providers import ``openai`` lazily inside the ``client`` property, so patches
    must target whatever is registered at call time — not this module's own
    object, which may have been superseded during collection.
    """
    return sys.modules["openai"]


def _make_provider_with_client(mock_client) -> AzureProvider:
    """Build a provider whose openai client is the given mock."""
    _active_openai_module().OpenAI = MagicMock(return_value=mock_client)
    provider = AzureProvider(api_key="test-key", base_url=TEST_BASE_URL)
    provider._client = None  # force lazy re-creation through the mocked OpenAI()
    return provider


# =============================================================================
# Initialization
# =============================================================================


@pytest.mark.unit
class TestAzureProviderInit:
    def test_basic_init(self):
        provider = AzureProvider(api_key="test-key", base_url=TEST_BASE_URL)

        assert provider.api_key == "test-key"
        assert provider.base_url == TEST_BASE_URL
        assert provider.provider_name == "azure"
        assert provider.default_model == "gpt-4o"
        assert provider.timeout == 60.0
        assert provider.max_retries == 2

    def test_custom_params(self):
        provider = AzureProvider(
            api_key="test-key",
            base_url=TEST_BASE_URL,
            timeout=120.0,
            max_retries=5,
        )

        assert provider.timeout == 120.0
        assert provider.max_retries == 5

    def test_base_url_required(self):
        with pytest.raises(ValueError, match="base_url is required"):
            AzureProvider(api_key="test-key")

    def test_model_override(self):
        provider = AzureProvider(api_key="k", base_url=TEST_BASE_URL, model="gpt-5.2")
        assert provider.default_model == "gpt-5.2"

    def test_lazy_client(self):
        provider = AzureProvider(api_key="test-key", base_url=TEST_BASE_URL)
        assert provider._client is None

    def test_client_created_with_base_url(self):
        mock_openai_class = MagicMock()
        _active_openai_module().OpenAI = mock_openai_class

        provider = AzureProvider(api_key="test-key", base_url=TEST_BASE_URL)
        provider._client = None
        _ = provider.client

        kwargs = mock_openai_class.call_args.kwargs
        _assert_pinned_http_client(kwargs)
        assert {k: v for k, v in kwargs.items() if k != "http_client"} == {
            "api_key": "test-key",
            "base_url": TEST_BASE_URL,
            "timeout": 60.0,
            "max_retries": 2,
        }


# =============================================================================
# Migration guardrails (v2.0.0)
# =============================================================================


@pytest.mark.unit
class TestAzureMigrationGuardrails:
    def test_legacy_endpoint_rejected(self):
        """The retired azure-ai-inference endpoint must fail with a migration hint."""
        with pytest.raises(ValueError, match="retired Azure AI Inference endpoint"):
            AzureProvider(api_key="test-key", base_url=LEGACY_BASE_URL)

    def test_legacy_endpoint_message_names_replacement(self):
        with pytest.raises(ValueError) as exc_info:
            AzureProvider(api_key="test-key", base_url=LEGACY_BASE_URL)
        assert "openai.azure.com/openai/v1" in str(exc_info.value)

    def test_legacy_endpoint_rejected_before_dns(self):
        """Rejection must not depend on the legacy hostname resolving."""
        with pytest.raises(ValueError, match="retired Azure AI Inference endpoint"):
            AzureProvider(api_key="k", base_url="https://nonexistent-xyz.services.ai.azure.com/models")

    def test_api_version_is_deprecated_but_accepted(self):
        """Existing call sites passing api_version must keep working."""
        with pytest.warns(DeprecationWarning, match="api_version is obsolete"):
            provider = AzureProvider(
                api_key="test-key",
                base_url=TEST_BASE_URL,
                api_version="2025-04-01-preview",
            )
        assert provider.base_url == TEST_BASE_URL

    def test_no_api_version_emits_no_warning(self, recwarn):
        AzureProvider(api_key="test-key", base_url=TEST_BASE_URL)
        assert not [w for w in recwarn if issubclass(w.category, DeprecationWarning)]


# =============================================================================
# SSRF guard
# =============================================================================


@pytest.mark.unit
class TestAzureSSRFGuard:
    def test_ssrf_metadata_blocked(self):
        with pytest.raises(ValueError):
            AzureProvider(api_key="test-key", base_url="http://169.254.169.254/openai/v1/")

    def test_private_range_blocked(self):
        with pytest.raises(ValueError):
            AzureProvider(api_key="test-key", base_url="http://10.0.0.5/openai/v1/")

    def test_non_http_scheme_blocked(self):
        with pytest.raises(ValueError):
            AzureProvider(api_key="test-key", base_url="file:///etc/passwd")


# =============================================================================
# Temperature constraints and reasoning models
# =============================================================================


@pytest.mark.unit
class TestAzureReasoningModels:
    @pytest.mark.parametrize(
        "model",
        ["o1", "o1-mini", "o3", "o3-mini", "o4-mini", "codex-mini", "DeepSeek-R1", "MAI-DS-R1"],
    )
    def test_reasoning_models_detected(self, model):
        provider = AzureProvider(api_key="k", base_url=TEST_BASE_URL)
        assert provider._is_reasoning_model(model) is True

    @pytest.mark.parametrize("model", ["gpt-4o", "gpt-4.1", "gpt-5.2", "Llama-3.3-70B-Instruct"])
    def test_non_reasoning_models(self, model):
        provider = AzureProvider(api_key="k", base_url=TEST_BASE_URL)
        assert provider._is_reasoning_model(model) is False

    def test_reasoning_model_uses_max_completion_tokens(self, mock_chat_response):
        """o-series deployments reject max_tokens; they need max_completion_tokens."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}], model="o3", max_tokens=500)

        params = mock_client.chat.completions.create.call_args.kwargs
        assert params["max_completion_tokens"] == 500
        assert "max_tokens" not in params

    def test_standard_model_uses_max_tokens(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}], model="gpt-4o", max_tokens=500)

        params = mock_client.chat.completions.create.call_args.kwargs
        assert params["max_tokens"] == 500
        assert "max_completion_tokens" not in params

    def test_temperature_constraints_available(self):
        provider = AzureProvider(api_key="k", base_url=TEST_BASE_URL)
        constraints = provider._get_temperature_constraints("gpt-4o")
        assert "supports_temperature" in constraints
        assert "min" in constraints
        assert "max" in constraints


# =============================================================================
# Chat completion
# =============================================================================


@pytest.mark.unit
class TestAzureChatCompletion:
    def test_simple_completion(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        response = provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        assert response.content == "Hello from Azure."
        assert response.model == "gpt-4o"
        assert response.input_tokens == 12
        assert response.output_tokens == 6
        assert response.finish_reason == "stop"

    def test_messages_passed_as_plain_dicts(self, mock_chat_response):
        """No SDK message objects any more — the wire format is plain OpenAI dicts."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
        ]
        provider.chat_completion(messages=messages)

        sent = mock_client.chat.completions.create.call_args.kwargs["messages"]
        assert sent == messages

    def test_tools_passed_through(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        tools = [
            {
                "type": "function",
                "function": {"name": "get_weather", "description": "Weather", "parameters": {}},
            }
        ]
        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}], tools=tools)

        assert mock_client.chat.completions.create.call_args.kwargs["tools"] == tools

    def test_tool_calls_parsed(self, mock_chat_response):
        tc = MagicMock()
        tc.id = "call_1"
        tc.type = "function"
        tc.function.name = "get_weather"
        tc.function.arguments = '{"city": "Berlin"}'
        mock_chat_response.choices[0].message.tool_calls = [tc]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        response = provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "get_weather"


# =============================================================================
# Streaming
# =============================================================================


@pytest.mark.unit
class TestAzureStreamCompletion:
    def test_stream_yields_content_then_final(self, mock_stream_chunks):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_stream_chunks()
        provider = _make_provider_with_client(mock_client)

        chunks = list(provider.stream_completion(messages=[{"role": "user", "content": "Hi"}]))

        assert "".join(c.content for c in chunks if not c.is_final) == "Hello!"
        assert chunks[-1].is_final is True
        assert chunks[-1].finish_reason == "stop"
        assert chunks[-1].input_tokens == 12
        assert chunks[-1].output_tokens == 3

    def test_stream_requests_usage(self, mock_stream_chunks):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_stream_chunks()
        provider = _make_provider_with_client(mock_client)

        list(provider.stream_completion(messages=[{"role": "user", "content": "Hi"}]))

        params = mock_client.chat.completions.create.call_args.kwargs
        assert params["stream"] is True
        assert params["stream_options"] == {"include_usage": True}


# =============================================================================
# Model catalog
# =============================================================================


@pytest.mark.unit
class TestAzureListModels:
    def test_returns_static_catalog(self):
        provider = AzureProvider(api_key="k", base_url=TEST_BASE_URL)
        models = provider.list_models()

        assert len(models) == len(AzureProvider.KNOWN_MODELS)
        ids = [m["id"] for m in models]
        assert ids == sorted(ids)

    def test_catalog_covers_openai_and_foundry_models(self):
        provider = AzureProvider(api_key="k", base_url=TEST_BASE_URL)
        ids = {m["id"] for m in provider.list_models()}

        # Azure OpenAI models
        assert "gpt-4o" in ids
        assert "o3" in ids
        # Foundry models from other providers stay reachable via the /v1 endpoint
        assert "DeepSeek-R1" in ids
        assert "Llama-3.3-70B-Instruct" in ids
        assert "Mistral-Large-3" in ids

    def test_entries_carry_metadata(self):
        provider = AzureProvider(api_key="k", base_url=TEST_BASE_URL)
        entry = next(m for m in provider.list_models() if m["id"] == "o3")

        assert entry["provider"] == "azure"
        assert entry["supports_reasoning"] is True
        assert entry["supports_streaming"] is True
        assert entry["context_length"] == 200000

    def test_does_not_call_the_api(self):
        """The catalog is static — no /v1/models round-trip."""
        mock_client = MagicMock()
        provider = _make_provider_with_client(mock_client)

        provider.list_models()

        mock_client.models.list.assert_not_called()


# =============================================================================
# Error handling
# =============================================================================


@pytest.mark.unit
class TestAzureErrorHandling:
    def _provider_raising(self, exc: Exception) -> AzureProvider:
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
        """Provider errors must not leak API keys into the message."""
        provider = self._provider_raising(Exception("500 error for key sk-leakedsecret12345"))
        with pytest.raises(ProviderError) as exc_info:
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])
        assert "sk-leakedsecret12345" not in str(exc_info.value)


# =============================================================================
# Context manager
# =============================================================================


@pytest.mark.unit
class TestAzureContextManager:
    def test_close_closes_client(self):
        mock_client = MagicMock()
        provider = _make_provider_with_client(mock_client)
        _ = provider.client

        provider.close()

        mock_client.close.assert_called_once()
        assert provider._client is None

    def test_context_manager(self):
        mock_client = MagicMock()
        provider = _make_provider_with_client(mock_client)

        with provider as p:
            assert p is provider
            _ = p.client

        mock_client.close.assert_called_once()

    def test_close_without_client_is_safe(self):
        provider = AzureProvider(api_key="k", base_url=TEST_BASE_URL)
        provider.close()  # must not raise

    def test_rejected_base_url_leaves_instance_closable(self):
        """A rejected base_url must not leave _client unset (close()/__del__ safety)."""
        with pytest.raises(ValueError):
            AzureProvider(api_key="k", base_url="http://169.254.169.254/openai/v1/")


# =============================================================================
# Factory integration
# =============================================================================


@pytest.mark.unit
class TestAzureFactoryIntegration:
    def test_factory_returns_azure_provider(self):
        from eq_chatbot_core.providers import get_provider

        provider = get_provider("azure", api_key="test-key", base_url=TEST_BASE_URL)

        assert isinstance(provider, AzureProvider)
        assert provider.provider_name == "azure"

    def test_factory_rejects_legacy_endpoint(self):
        from eq_chatbot_core.providers import get_provider

        with pytest.raises(ValueError, match="retired Azure AI Inference endpoint"):
            get_provider("azure", api_key="test-key", base_url=LEGACY_BASE_URL)
