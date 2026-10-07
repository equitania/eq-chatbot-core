"""
Unit tests for OpenAI provider.

All tests use mocked responses - no real API calls.
"""

import sys
from unittest.mock import MagicMock

import pytest

# Mock the openai module before importing provider
mock_openai_module = MagicMock()
sys.modules["openai"] = mock_openai_module

from eq_chatbot_core.providers.openai_provider import OpenAIProvider

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI chat completion response."""
    response = MagicMock()
    response.model = "gpt-4o"
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Test response"
    response.choices[0].message.tool_calls = None
    response.choices[0].finish_reason = "stop"
    response.usage = MagicMock()
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    response.model_dump.return_value = {"id": "test", "model": "gpt-4o"}
    return response


@pytest.fixture
def mock_openai_stream():
    """Create mock streaming chunks."""

    def generate_chunks():
        for content in ["Hello", " ", "World", "!"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = content
            chunk.choices[0].delta.tool_calls = None
            chunk.choices[0].finish_reason = None
            chunk.usage = None
            yield chunk

        # Final chunk with usage
        final = MagicMock()
        final.choices = [MagicMock()]
        final.choices[0].delta.content = ""
        final.choices[0].delta.tool_calls = None
        final.choices[0].finish_reason = "stop"
        final.usage = MagicMock()
        final.usage.prompt_tokens = 10
        final.usage.completion_tokens = 5
        yield final

    return generate_chunks


@pytest.fixture
def mock_models_list():
    """Create mock models list response."""
    models = MagicMock()
    models.data = [
        MagicMock(id="gpt-4o", created=1700000000, owned_by="openai"),
        MagicMock(id="gpt-4o-mini", created=1700000000, owned_by="openai"),
        MagicMock(id="gpt-3.5-turbo", created=1600000000, owned_by="openai"),
        MagicMock(id="o1", created=1700000000, owned_by="openai"),
        MagicMock(id="o1-mini", created=1700000000, owned_by="openai"),
        MagicMock(id="text-embedding-ada-002", created=1600000000, owned_by="openai"),  # Non-chat
    ]
    return models


# =============================================================================
# Provider Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestOpenAIProviderInit:
    """Test OpenAI provider initialization."""

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        # Loopback URL keeps the SSRF guard's validate_url hermetic (no DNS).
        provider = OpenAIProvider(
            api_key="sk-test-key",
            base_url="http://localhost:8080/v1",
            timeout=120.0,
            max_retries=5,
            organization="org-test",
        )

        assert provider.base_url == "http://localhost:8080/v1"
        assert provider.timeout == 120.0
        assert provider.max_retries == 5
        assert provider.organization == "org-test"

    def test_ssrf_metadata_blocked(self):
        with pytest.raises(ValueError):
            OpenAIProvider(api_key="sk-test-key", base_url="http://169.254.169.254/v1")

    def test_private_range_blocked(self):
        with pytest.raises(ValueError):
            OpenAIProvider(api_key="sk-test-key", base_url="http://10.0.0.5/v1")

    def test_non_http_scheme_blocked(self):
        with pytest.raises(ValueError):
            OpenAIProvider(api_key="sk-test-key", base_url="file:///etc/passwd")

    def test_rejected_base_url_leaves_instance_closable(self):
        """A rejected base_url must not leave _client unset (close()/__del__ safety)."""
        with pytest.raises(ValueError):
            OpenAIProvider(api_key="sk-test-key", base_url="http://169.254.169.254/v1")
        # No AttributeError may surface from garbage collection of the failed instance.

    def test_lazy_client_initialization(self):
        """Test that client is lazily initialized."""
        provider = OpenAIProvider(api_key="sk-test-key")

        # Client should not be created yet
        assert provider._client is None

    def test_client_reuses_instance(self):
        """Test that client is only created once."""
        mock_openai_class = MagicMock()
        mock_openai_module.OpenAI = mock_openai_class

        provider = OpenAIProvider(api_key="sk-test-key")
        provider._client = None  # Reset client

        # Access client multiple times
        _ = provider.client
        _ = provider.client
        _ = provider.client

        # Should only be called once
        mock_openai_class.assert_called_once()


# =============================================================================
# Chat Completion Tests
# =============================================================================


@pytest.mark.unit
class TestOpenAIChatCompletion:
    """Test chat completion functionality."""

    def test_simple_completion(self, mock_openai_response):
        """Test simple chat completion."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        provider._client = None
        response = provider.chat_completion(messages=[{"role": "user", "content": "Hello"}])

        assert response.content == "Test response"
        assert response.model == "gpt-4o"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.finish_reason == "stop"

    def test_completion_with_model(self, mock_openai_response):
        """Test completion with specific model."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o-mini",
        )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "gpt-4o-mini"

    def test_completion_with_temperature(self, mock_openai_response):
        """Temperature reaches models that accept it — and only those.

        The model matters: gpt-4.1 takes the parameter, while the current default
        (gpt-5.6) refuses it outright, so it must be omitted there. Pinning an
        explicit model keeps this test about the pass-through path even when the
        default moves to a new generation.
        """
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4.1",
            temperature=0.5,
        )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.5

    def test_completion_with_max_tokens_new_api(self, mock_openai_response):
        """Test completion with max_completion_tokens for new API models."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o",  # New API model
            max_tokens=100,
        )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs.get("max_completion_tokens") == 100
        assert "max_tokens" not in call_args.kwargs

    def test_completion_with_tools(self):
        """Test completion with tool calls."""
        # Create response with tool calls
        # Note: MagicMock's `name` parameter is special - must set as attribute
        response = MagicMock()
        response.model = "gpt-4o"
        response.choices = [MagicMock()]
        response.choices[0].message.content = ""

        # Create function mock and set name as attribute (not constructor param)
        function_mock = MagicMock()
        function_mock.name = "get_weather"
        function_mock.arguments = '{"location": "Paris"}'

        tool_call_mock = MagicMock()
        tool_call_mock.id = "call_123"
        tool_call_mock.type = "function"
        tool_call_mock.function = function_mock

        response.choices[0].message.tool_calls = [tool_call_mock]
        response.choices[0].finish_reason = "tool_calls"
        response.usage = MagicMock(prompt_tokens=20, completion_tokens=10)
        response.model_dump.return_value = {}

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        provider._client = None
        tools = [{"type": "function", "function": {"name": "get_weather"}}]

        result = provider.chat_completion(
            messages=[{"role": "user", "content": "Weather in Paris?"}],
            tools=tools,
        )

        assert result.finish_reason == "tool_calls"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["function"]["name"] == "get_weather"

    def test_completion_extra_kwargs(self, mock_openai_response):
        """Test completion passes extra kwargs."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            top_p=0.9,
            presence_penalty=0.1,
        )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs.get("top_p") == 0.9
        assert call_args.kwargs.get("presence_penalty") == 0.1

    def test_completion_gpt41_temperature_clamped(self, mock_openai_response):
        """Test GPT-4.1 clamps temperature to min 1.0 in API call."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4.1",
            temperature=0.5,
        )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.5


# =============================================================================
# Stream Completion Tests
# =============================================================================


@pytest.mark.unit
class TestOpenAIStreamCompletion:
    """Test streaming completion functionality."""

    def test_stream_completion(self, mock_openai_stream):
        """Test streaming completion."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_stream()
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        provider._client = None
        chunks = list(provider.stream_completion(messages=[{"role": "user", "content": "Hello"}]))

        # Should have content chunks + final chunk
        assert len(chunks) >= 1

        # Combine content
        full_content = "".join(c.content for c in chunks if c.content)
        assert full_content == "Hello World!"

        # Last chunk should be final
        final_chunks = [c for c in chunks if c.is_final]
        assert len(final_chunks) == 1
        assert final_chunks[0].finish_reason == "stop"

    def test_stream_includes_usage(self, mock_openai_stream):
        """Test streaming includes usage on final chunk."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_stream()
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        provider._client = None
        chunks = list(provider.stream_completion(messages=[{"role": "user", "content": "Hello"}]))

        final_chunk = [c for c in chunks if c.is_final][0]
        assert final_chunk.input_tokens == 10
        assert final_chunk.output_tokens == 5

    def test_stream_with_max_tokens(self, mock_openai_stream):
        """Test streaming with max_tokens parameter."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_stream()
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        provider._client = None
        list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
                max_tokens=50,
            )
        )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs.get("max_completion_tokens") == 50
        assert call_args.kwargs["stream"] is True


# =============================================================================
# List Models Tests
# =============================================================================


@pytest.mark.unit
class TestOpenAIListModels:
    """Test list_models functionality."""

    def test_list_models_sorted(self, mock_models_list):
        """Test that models are sorted by ID."""
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_models_list
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        provider._client = None
        models = provider.list_models()

        model_ids = [m["id"] for m in models]
        assert model_ids == sorted(model_ids)


# =============================================================================
# Provider Properties Tests
# =============================================================================


@pytest.mark.unit
class TestOpenAIProviderProperties:
    """Test provider properties and repr."""

    def test_provider_name(self):
        """Test provider_name property."""
        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        assert provider.provider_name == "openai"

    def test_default_base_url(self):
        """Test default base URL constant."""
        assert OpenAIProvider.DEFAULT_BASE_URL == "https://api.openai.com/v1"

    def test_repr(self):
        """Test string representation."""
        provider = OpenAIProvider(api_key="sk-test", model="test-model")
        repr_str = repr(provider)
        assert "OpenAIProvider" in repr_str
        assert "openai" in repr_str
