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

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    ContextLengthError,
    ProviderError,
    RateLimitError,
)
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

    def test_basic_init(self):
        """Test basic provider initialization."""
        provider = OpenAIProvider(api_key="sk-test-key")

        assert provider.api_key == "sk-test-key"
        assert provider.provider_name == "openai"
        assert provider.default_model == "gpt-4o"
        assert provider.timeout == 60.0
        assert provider.max_retries == 2
        assert provider.organization is None

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

    def test_client_property_creates_client(self):
        """Test that accessing client creates the OpenAI instance."""
        mock_openai_class = MagicMock()
        mock_openai_module.OpenAI = mock_openai_class

        provider = OpenAIProvider(api_key="sk-test-key")
        provider._client = None  # Reset client

        # Access client
        _ = provider.client

        mock_openai_class.assert_called_once_with(
            api_key="sk-test-key",
            base_url=OpenAIProvider.DEFAULT_BASE_URL,
            timeout=60.0,
            max_retries=2,
            organization=None,
        )

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


@pytest.fixture
def setup_openai_mock():
    """Setup mock client for tests."""
    mock_client = MagicMock()
    mock_openai_module.OpenAI.return_value = mock_client
    return mock_client


@pytest.mark.unit
class TestOpenAIChatCompletion:
    """Test chat completion functionality."""

    def test_simple_completion(self, mock_openai_response):
        """Test simple chat completion."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
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

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o-mini",
        )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "gpt-4o-mini"

    def test_completion_with_temperature(self, mock_openai_response):
        """Test completion with custom temperature."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.5,
        )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.5

    def test_completion_with_max_tokens_legacy(self, mock_openai_response):
        """Test completion with max_tokens for legacy models."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4-turbo",  # Legacy model
            max_tokens=100,
        )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs.get("max_tokens") == 100
        assert "max_completion_tokens" not in call_args.kwargs

    def test_completion_with_max_tokens_new_api(self, mock_openai_response):
        """Test completion with max_completion_tokens for new API models."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
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

        provider = OpenAIProvider(api_key="sk-test")
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

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            top_p=0.9,
            presence_penalty=0.1,
        )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs.get("top_p") == 0.9
        assert call_args.kwargs.get("presence_penalty") == 0.1

    def test_completion_reasoning_model_no_temperature(self, mock_openai_response):
        """Test reasoning models (o1/o3/o4) don't receive temperature in API call."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="o3",
            temperature=0.7,
        )

        call_args = mock_client.chat.completions.create.call_args
        assert "temperature" not in call_args.kwargs

    def test_completion_gpt41_temperature_clamped(self, mock_openai_response):
        """Test GPT-4.1 clamps temperature to min 1.0 in API call."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
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

        provider = OpenAIProvider(api_key="sk-test")
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

        provider = OpenAIProvider(api_key="sk-test")
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

        provider = OpenAIProvider(api_key="sk-test")
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

    def test_stream_tool_calls(self):
        """Test streaming with tool calls."""

        def stream_with_tools():
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = ""

            # Create function mock with name as attribute (not constructor param)
            function_mock = MagicMock()
            function_mock.name = "test_func"
            function_mock.arguments = '{"a": 1}'

            tool_call_mock = MagicMock()
            tool_call_mock.index = 0
            tool_call_mock.id = "call_123"
            tool_call_mock.function = function_mock

            chunk.choices[0].delta.tool_calls = [tool_call_mock]
            chunk.choices[0].finish_reason = "tool_calls"
            chunk.usage = None
            yield chunk

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = stream_with_tools()
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Hello"}],
                tools=[{"type": "function", "function": {"name": "test_func"}}],
            )
        )

        assert len(chunks) == 1
        assert chunks[0].tool_call_delta is not None
        assert chunks[0].tool_call_delta["function"]["name"] == "test_func"


# =============================================================================
# List Models Tests
# =============================================================================


@pytest.mark.unit
class TestOpenAIListModels:
    """Test list_models functionality."""

    def test_list_models_filters_chat_models(self, mock_models_list):
        """Test that list_models filters for chat-capable models only."""
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_models_list
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None
        models = provider.list_models()

        # Should not include embedding model
        model_ids = [m["id"] for m in models]
        assert "text-embedding-ada-002" not in model_ids

        # Should include chat models
        assert "gpt-4o" in model_ids
        assert "gpt-4o-mini" in model_ids
        assert "gpt-3.5-turbo" in model_ids
        assert "o1" in model_ids

    def test_list_models_includes_constraints(self, mock_models_list):
        """Test that models include constraint information."""
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_models_list
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None
        models = provider.list_models()

        # Find gpt-4o model
        gpt4o = next(m for m in models if m["id"] == "gpt-4o")
        assert gpt4o["supports_temperature"] is True
        assert gpt4o["supports_vision"] is True
        assert gpt4o["provider"] == "openai"

        # Find o1 model - reasoning model
        o1 = next(m for m in models if m["id"] == "o1")
        assert o1["supports_temperature"] is False
        assert o1["supports_reasoning"] is True

    def test_list_models_sorted(self, mock_models_list):
        """Test that models are sorted by ID."""
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_models_list
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None
        models = provider.list_models()

        model_ids = [m["id"] for m in models]
        assert model_ids == sorted(model_ids)


# =============================================================================
# Model API Detection Tests
# =============================================================================


@pytest.mark.unit
class TestOpenAIModelAPIDetection:
    """Test detection of model API versions."""

    def test_new_api_models_detected(self):
        """Test that new API models are correctly detected."""
        provider = OpenAIProvider(api_key="sk-test")

        assert provider._uses_new_token_api("gpt-4o") is True
        assert provider._uses_new_token_api("gpt-4o-mini") is True
        assert provider._uses_new_token_api("o1") is True
        assert provider._uses_new_token_api("o1-mini") is True
        assert provider._uses_new_token_api("o3") is True
        assert provider._uses_new_token_api("o3-mini") is True
        assert provider._uses_new_token_api("gpt-5") is True

    def test_legacy_api_models_detected(self):
        """Test that legacy API models are correctly detected."""
        provider = OpenAIProvider(api_key="sk-test")

        assert provider._uses_new_token_api("gpt-4-turbo") is False
        assert provider._uses_new_token_api("gpt-4") is False
        assert provider._uses_new_token_api("gpt-3.5-turbo") is False

    def test_case_insensitive_detection(self):
        """Test case insensitivity in model detection."""
        provider = OpenAIProvider(api_key="sk-test")

        assert provider._uses_new_token_api("GPT-4O") is True
        assert provider._uses_new_token_api("GPT-4O-MINI") is True
        assert provider._uses_new_token_api("O1") is True


# =============================================================================
# Model Constraints Tests
# =============================================================================


@pytest.mark.unit
class TestOpenAIModelConstraints:
    """Test model constraint detection."""

    def test_reasoning_model_constraints(self):
        """Test constraints for reasoning models (O1, O3, O4)."""
        provider = OpenAIProvider(api_key="sk-test")

        for model in ["o1", "o1-mini", "o3", "o3-mini", "o4-mini"]:
            constraints = provider._get_model_constraints(model)
            assert constraints["supports_temperature"] is False
            assert constraints["min_temperature"] == 1.0
            assert constraints["max_temperature"] == 1.0
            assert constraints["supports_reasoning"] is True

    def test_gpt_model_constraints(self):
        """Test constraints for standard GPT models."""
        provider = OpenAIProvider(api_key="sk-test")

        for model in ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]:
            constraints = provider._get_model_constraints(model)
            assert constraints["supports_temperature"] is True
            assert constraints["min_temperature"] == 0.0
            assert constraints["max_temperature"] == 2.0
            assert constraints["supports_reasoning"] is False

    def test_vision_support_detection(self):
        """Test vision capability detection."""
        provider = OpenAIProvider(api_key="sk-test")

        # Models with vision
        assert provider._get_model_constraints("gpt-4o")["supports_vision"] is True
        assert provider._get_model_constraints("gpt-4-turbo")["supports_vision"] is True
        assert provider._get_model_constraints("o1")["supports_vision"] is True

        # Models without vision
        assert provider._get_model_constraints("gpt-3.5-turbo")["supports_vision"] is False

    def test_context_length_detection(self):
        """Test context length detection for models."""
        provider = OpenAIProvider(api_key="sk-test")

        assert provider._get_model_constraints("gpt-4o")["context_length"] == 128000
        assert provider._get_model_constraints("gpt-4")["context_length"] == 8192
        assert provider._get_model_constraints("gpt-3.5-turbo")["context_length"] == 16385
        assert provider._get_model_constraints("o1")["context_length"] == 200000


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestOpenAIErrorHandling:
    """Test error handling in OpenAI provider."""

    def test_error_scrubs_secret(self):
        """Provider errors must not leak API keys into the message."""
        provider = OpenAIProvider(api_key="sk-test")
        err = provider._handle_error(Exception("500 error for key sk-leakedsecret12345"))
        assert "sk-leakedsecret12345" not in str(err)

    def test_rate_limit_error(self):
        """Test handling of rate limit errors."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Error code: 429 - Rate limit exceeded")
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None

        with pytest.raises(RateLimitError) as exc_info:
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        assert exc_info.value.status_code == 429
        assert exc_info.value.provider == "openai"

    def test_authentication_error(self):
        """Test handling of authentication errors."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Error code: 401 - Authentication failed")
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-invalid")
        provider._client = None

        with pytest.raises(AuthenticationError) as exc_info:
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        assert exc_info.value.status_code == 401
        assert exc_info.value.provider == "openai"

    def test_context_length_error(self):
        """Test handling of context length errors."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception(
            "This model's maximum context length is 8192 tokens"
        )
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None

        with pytest.raises(ContextLengthError) as exc_info:
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        assert exc_info.value.provider == "openai"

    def test_generic_error(self):
        """Test handling of generic errors."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Unknown server error")
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None

        with pytest.raises(ProviderError) as exc_info:
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        assert exc_info.value.provider == "openai"
        # Should not be a specific subtype
        assert type(exc_info.value) is ProviderError

    def test_stream_error_handling(self):
        """Test error handling during streaming."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Stream error")
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")
        provider._client = None

        with pytest.raises(ProviderError):
            list(provider.stream_completion(messages=[{"role": "user", "content": "Hi"}]))

    def test_list_models_error_handling(self):
        """Test error handling in list_models."""
        mock_client = MagicMock()
        mock_client.models.list.side_effect = Exception("Error code: 401")
        mock_openai_module.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-invalid")
        provider._client = None

        with pytest.raises(AuthenticationError):
            provider.list_models()


# =============================================================================
# Provider Properties Tests
# =============================================================================


@pytest.mark.unit
class TestOpenAIProviderProperties:
    """Test provider properties and repr."""

    def test_provider_name(self):
        """Test provider_name property."""
        provider = OpenAIProvider(api_key="sk-test")
        assert provider.provider_name == "openai"

    def test_default_model(self):
        """Test default_model property."""
        provider = OpenAIProvider(api_key="sk-test")
        assert provider.default_model == "gpt-4o"

    def test_default_base_url(self):
        """Test default base URL constant."""
        assert OpenAIProvider.DEFAULT_BASE_URL == "https://api.openai.com/v1"

    def test_repr(self):
        """Test string representation."""
        provider = OpenAIProvider(api_key="sk-test")
        repr_str = repr(provider)
        assert "OpenAIProvider" in repr_str
        assert "openai" in repr_str

    def test_chat_model_prefixes(self):
        """Test chat model prefix constants."""
        assert "gpt-4" in OpenAIProvider.CHAT_MODEL_PREFIXES
        assert "o1" in OpenAIProvider.CHAT_MODEL_PREFIXES
        assert "o3" in OpenAIProvider.CHAT_MODEL_PREFIXES

    def test_reasoning_model_no_temperature(self):
        """Test reasoning models skip temperature via shared constraints module."""
        from eq_chatbot_core.providers.temperature_constraints import clamp_temperature

        assert clamp_temperature("o1", 0.7) is None
        assert clamp_temperature("o3", 0.5) is None
        assert clamp_temperature("o4-mini", 0.3) is None

    def test_gpt41_temperature_passthrough(self):
        """Test GPT-4.1 models pass through temperature (min=0.0)."""
        from eq_chatbot_core.providers.temperature_constraints import clamp_temperature

        assert clamp_temperature("gpt-4.1", 0.5) == 0.5
        assert clamp_temperature("gpt-4.1-mini", 0.7) == 0.7
        assert clamp_temperature("gpt-4.1", 1.5) == 1.5  # In range, passthrough
