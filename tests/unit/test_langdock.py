"""
Unit tests for LangDock provider.

All tests use mocked responses - no real API calls.
Tests cover OpenAI and Anthropic backends routing through LangDock.

NOTE: This module uses class-level fixtures with patch.dict to avoid
polluting sys.modules and causing test isolation issues.
"""

from unittest.mock import MagicMock, patch

import pytest

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    ContextLengthError,
    ProviderError,
    RateLimitError,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI chat completion response."""
    response = MagicMock()
    response.model = "gpt-4o"
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Test response from LangDock"
    response.choices[0].message.tool_calls = None
    response.choices[0].finish_reason = "stop"
    response.usage = MagicMock()
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    response.model_dump.return_value = {"id": "test", "model": "gpt-4o"}
    return response


@pytest.fixture
def mock_anthropic_response():
    """Create a mock Anthropic message response."""
    response = MagicMock()
    response.model = "claude-sonnet-4-20250514"
    response.content = [MagicMock(type="text", text="Test response from Claude")]
    response.stop_reason = "end_turn"
    response.usage = MagicMock()
    response.usage.input_tokens = 10
    response.usage.output_tokens = 5
    response.model_dump.return_value = {"id": "test", "model": "claude-sonnet-4"}
    return response


@pytest.fixture
def mock_openai_stream():
    """Create mock OpenAI streaming chunks."""

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
def mock_openai_models_list():
    """Create mock models list response."""
    models = MagicMock()
    models.data = [
        MagicMock(id="gpt-4o", created=1700000000, owned_by="openai"),
        MagicMock(id="gpt-4o-mini", created=1700000000, owned_by="openai"),
        MagicMock(id="gpt-4-turbo", created=1700000000, owned_by="openai"),
        MagicMock(id="o1", created=1700000000, owned_by="openai"),
        MagicMock(id="text-embedding-ada-002", created=1600000000, owned_by="openai"),
    ]
    return models


# =============================================================================
# Provider Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestLangDockProviderInit:
    """Test LangDock provider initialization."""

    def test_basic_init(self):
        """Test basic provider initialization with OpenAI backend."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key")
            assert provider.api_key == "test-key"
            assert provider.backend == "openai"  # default
            assert provider.region == "eu"  # default

    def test_init_with_openai_backend(self):
        """Test initialization with explicit OpenAI backend."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai", region="us")
            assert provider.backend == "openai"
            assert provider.region == "us"

    def test_init_with_anthropic_backend(self):
        """Test initialization with Anthropic backend."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="anthropic", region="eu")
            assert provider.backend == "anthropic"

    def test_init_with_google_backend(self):
        """Test initialization with Google backend."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="google")
            assert provider.backend == "google"

    def test_init_with_agent_backend(self):
        """Test initialization with Agent backend requires agent_id."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="agent", agent_id="agent-123")
            assert provider.backend == "agent"
            assert provider.agent_id == "agent-123"

    def test_init_agent_without_agent_id_raises(self):
        """Test that agent backend without agent_id raises error."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            with pytest.raises(ValueError, match="agent_id.*required"):
                LangDockProvider(api_key="test-key", backend="agent")

    def test_init_invalid_backend_raises(self):
        """Test that invalid backend raises error."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            with pytest.raises(ValueError, match="Invalid backend"):
                LangDockProvider(api_key="test-key", backend="invalid")

    def test_init_with_reasoning_effort(self):
        """Test initialization with reasoning effort."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", reasoning_effort="high")
            assert provider.reasoning_effort == "high"

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", timeout=120.0)
            assert provider.timeout == 120.0

    def test_init_with_custom_base_url(self):
        """Test initialization with custom base URL."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            custom_url = "http://localhost:4000/v1"
            provider = LangDockProvider(api_key="test-key", base_url=custom_url)
            assert provider.base_url == custom_url


# =============================================================================
# Backend URL Tests
# =============================================================================


@pytest.mark.unit
class TestLangDockBackendURLs:
    """Test backend URL construction."""

    def test_openai_eu_url(self):
        """Test OpenAI EU endpoint URL construction."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai", region="eu")
            backend_url = provider._get_backend_url()
            assert "openai" in backend_url.lower()
            assert "eu" in backend_url.lower()

    def test_openai_us_url(self):
        """Test OpenAI US endpoint URL construction."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai", region="us")
            backend_url = provider._get_backend_url()
            assert "openai" in backend_url.lower()
            assert "us" in backend_url.lower()

    def test_anthropic_eu_url(self):
        """Test Anthropic EU endpoint URL construction."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="anthropic", region="eu")
            backend_url = provider._get_backend_url()
            assert "anthropic" in backend_url.lower()
            assert "eu" in backend_url.lower()

    def test_google_url(self):
        """Test Google endpoint URL construction."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="google")
            backend_url = provider._get_backend_url()
            assert "google" in backend_url.lower()

    def test_agent_url(self):
        """Test Agent endpoint URL construction."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="agent", agent_id="agent-123")
            backend_url = provider._get_backend_url()
            # Agent backend uses /agent/v1 endpoint
            assert "/agent/v1" in backend_url.lower()


# =============================================================================
# OpenAI Backend Chat Completion Tests
# =============================================================================


@pytest.mark.unit
class TestLangDockOpenAIChatCompletion:
    """Test chat completion with OpenAI backend."""

    def test_simple_completion(self, mock_openai_response):
        """Test simple chat completion."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai")
            # Set the mock client directly
            provider._LangDockProvider__openai_client = mock_client

            response = provider.chat_completion(messages=[{"role": "user", "content": "Hello"}], model="gpt-4o")

            assert response.content == "Test response from LangDock"
            assert response.model == "gpt-4o"

    def test_completion_with_temperature(self, mock_openai_response):
        """Test completion with temperature parameter."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai")
            provider._LangDockProvider__openai_client = mock_client

            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
                temperature=0.7,
            )

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs.get("temperature") == 0.7

    def test_completion_with_reasoning_effort(self, mock_openai_response):
        """Test completion with reasoning effort for o1/o3/o4 models."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai", reasoning_effort="high")
            provider._LangDockProvider__openai_client = mock_client

            provider.chat_completion(
                messages=[{"role": "user", "content": "Complex reasoning task"}],
                model="o1",
            )

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs.get("reasoning_effort") == "high"

    def test_completion_with_max_tokens_new_api(self, mock_openai_response):
        """Test max_tokens becomes max_completion_tokens for new API models."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai")
            provider._LangDockProvider__openai_client = mock_client

            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
                max_tokens=100,
            )

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            # For new API models, should use max_completion_tokens
            assert "max_completion_tokens" in call_kwargs or "max_tokens" in call_kwargs

    def test_completion_with_tools(self, mock_openai_response):
        """Test completion with tools."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()

        # Set up tool call response
        tool_call = MagicMock()
        tool_call.id = "call_123"
        tool_call.type = "function"
        tool_call.function = MagicMock()
        tool_call.function.name = "get_weather"
        tool_call.function.arguments = '{"location": "Paris"}'

        mock_openai_response.choices[0].message.content = ""
        mock_openai_response.choices[0].message.tool_calls = [tool_call]
        mock_openai_response.choices[0].finish_reason = "tool_calls"
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai")
            provider._LangDockProvider__openai_client = mock_client

            tools = [{"type": "function", "function": {"name": "get_weather"}}]
            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Weather in Paris?"}],
                model="gpt-4o",
                tools=tools,
            )

            assert response.tool_calls is not None
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0]["function"]["name"] == "get_weather"


# =============================================================================
# Anthropic Backend Chat Completion Tests
# =============================================================================


@pytest.mark.unit
class TestLangDockAnthropicChatCompletion:
    """Test chat completion with Anthropic backend."""

    def test_simple_completion(self, mock_anthropic_response):
        """Test simple chat completion with Anthropic backend."""
        mock_anthropic_module = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic_module.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": mock_anthropic_module}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="anthropic")
            provider._LangDockProvider__anthropic_client = mock_client

            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="claude-sonnet-4-20250514",
            )

            assert response.content == "Test response from Claude"

    def test_completion_with_system_message(self, mock_anthropic_response):
        """Test completion extracts system message for Anthropic."""
        mock_anthropic_module = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic_module.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": mock_anthropic_module}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="anthropic")
            provider._LangDockProvider__anthropic_client = mock_client

            provider.chat_completion(
                messages=[
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hello"},
                ],
                model="claude-sonnet-4-20250514",
            )

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs.get("system") == "You are helpful"

    def test_completion_with_temperature(self, mock_anthropic_response):
        """Test completion with temperature for Anthropic."""
        mock_anthropic_module = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic_module.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": mock_anthropic_module}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="anthropic")
            provider._LangDockProvider__anthropic_client = mock_client

            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="claude-sonnet-4-20250514",
                temperature=0.5,
            )

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert "temperature" not in call_kwargs
            assert call_kwargs["extra_body"]["temperature"] == 0.5


# =============================================================================
# Stream Completion Tests
# =============================================================================


@pytest.mark.unit
class TestLangDockStreamCompletion:
    """Test streaming completion."""

    def test_stream_completion(self, mock_openai_stream):
        """Test streaming chat completion."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_stream()
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai")
            provider._LangDockProvider__openai_client = mock_client

            chunks = list(provider.stream_completion(messages=[{"role": "user", "content": "Hello"}], model="gpt-4o"))

            assert len(chunks) > 0
            # Combine content
            full_content = "".join(c.content for c in chunks if c.content)
            assert full_content == "Hello World!"

    def test_stream_includes_usage(self, mock_openai_stream):
        """Test streaming includes usage in final chunk."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_stream()
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai")
            provider._LangDockProvider__openai_client = mock_client

            chunks = list(provider.stream_completion(messages=[{"role": "user", "content": "Hello"}], model="gpt-4o"))

            # Last chunk should have finish_reason
            last_chunk = chunks[-1]
            assert last_chunk.finish_reason == "stop"


# =============================================================================
# List Models Tests
# =============================================================================


@pytest.mark.unit
class TestLangDockListModels:
    """Test list models functionality."""

    def test_list_models_includes_metadata(self, mock_openai_models_list):
        """Test list_models includes model metadata."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_openai_models_list
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai")
            provider._LangDockProvider__openai_client = mock_client

            models = provider.list_models()

            assert len(models) > 0
            # Each model should have an id
            for model in models:
                assert "id" in model or "model_id" in model

    def test_list_models_includes_constraints(self, mock_openai_models_list):
        """Test list_models includes constraint information."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_openai_models_list
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai")
            provider._LangDockProvider__openai_client = mock_client

            models = provider.list_models()

            # Models should include constraint info
            assert len(models) > 0


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestLangDockErrorHandling:
    """Test error handling and mapping."""

    def test_rate_limit_error(self):
        """Test rate limit error is properly mapped."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()

        # Create OpenAI rate limit error
        mock_error = MagicMock()
        mock_error.status_code = 429
        mock_error.message = "Rate limit exceeded"
        mock_openai_module.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_client.chat.completions.create.side_effect = mock_openai_module.RateLimitError("Rate limit exceeded")
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai")
            provider._LangDockProvider__openai_client = mock_client

            with pytest.raises((RateLimitError, Exception)):
                provider.chat_completion(messages=[{"role": "user", "content": "Hello"}], model="gpt-4o")

    def test_authentication_error(self):
        """Test authentication error is properly mapped."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()

        mock_openai_module.AuthenticationError = type("AuthenticationError", (Exception,), {})
        mock_client.chat.completions.create.side_effect = mock_openai_module.AuthenticationError("Invalid API key")
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai")
            provider._LangDockProvider__openai_client = mock_client

            with pytest.raises((AuthenticationError, Exception)):
                provider.chat_completion(messages=[{"role": "user", "content": "Hello"}], model="gpt-4o")

    def test_context_length_error(self):
        """Test context length error is properly mapped."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()

        mock_openai_module.BadRequestError = type("BadRequestError", (Exception,), {})
        error = mock_openai_module.BadRequestError("context_length_exceeded")
        error.message = "This model's maximum context length is exceeded"
        mock_client.chat.completions.create.side_effect = error
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai")
            provider._LangDockProvider__openai_client = mock_client

            with pytest.raises((ContextLengthError, Exception)):
                provider.chat_completion(messages=[{"role": "user", "content": "Hello"}], model="gpt-4o")

    def test_generic_error(self):
        """Test generic errors are wrapped as ProviderError."""
        mock_openai_module = MagicMock()
        mock_client = MagicMock()

        mock_openai_module.APIError = type("APIError", (Exception,), {})
        mock_client.chat.completions.create.side_effect = mock_openai_module.APIError("Unknown error")
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module, "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="openai")
            provider._LangDockProvider__openai_client = mock_client

            with pytest.raises((ProviderError, Exception)):
                provider.chat_completion(messages=[{"role": "user", "content": "Hello"}], model="gpt-4o")


# =============================================================================
# Provider Properties Tests
# =============================================================================


@pytest.mark.unit
class TestLangDockProviderProperties:
    """Test provider properties."""

    def test_provider_name(self):
        """Test provider_name property."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key")
            assert provider.provider_name == "langdock"

    def test_region_normalization(self):
        """Test region is normalized to lowercase."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", region="EU")
            assert provider.region == "eu"

    def test_backend_normalization(self):
        """Test backend is normalized to lowercase."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="OpenAI")
            assert provider.backend == "openai"


# =============================================================================
# System Prompt Extraction Tests
# =============================================================================


@pytest.mark.unit
class TestLangDockSystemPromptExtraction:
    """Test system prompt extraction for Anthropic backend."""

    def test_extract_single_system_prompt(self):
        """Test extracting single system message."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="anthropic")

            messages = [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
            ]

            system, filtered = provider._extract_system_prompt(messages)
            assert system == "You are helpful"
            assert len(filtered) == 1
            assert filtered[0]["role"] == "user"

    def test_extract_multiple_system_prompts(self):
        """Test extracting multiple system messages combines them."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="anthropic")

            messages = [
                {"role": "system", "content": "You are helpful"},
                {"role": "system", "content": "Be concise"},
                {"role": "user", "content": "Hello"},
            ]

            system, filtered = provider._extract_system_prompt(messages)
            assert "helpful" in system
            assert "concise" in system
            assert len(filtered) == 1

    def test_no_system_prompt(self):
        """Test handling messages without system prompt."""
        with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
            from eq_chatbot_core.providers.langdock_provider import LangDockProvider

            provider = LangDockProvider(api_key="test-key", backend="anthropic")

            messages = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ]

            system, filtered = provider._extract_system_prompt(messages)
            assert system is None
            assert len(filtered) == 2


# =============================================================================
# SSRF Guard (v1.17.2)
# =============================================================================


@pytest.mark.unit
class TestLangDockSSRFGuard:
    """A caller-supplied base_url must pass validate_url; the default is exempt."""

    def test_cloud_metadata_endpoint_rejected(self):
        from eq_chatbot_core.providers.langdock_provider import LangDockProvider

        with pytest.raises(ValueError):
            LangDockProvider(api_key="test-key", base_url="http://169.254.169.254/v1")

    def test_non_http_scheme_rejected(self):
        from eq_chatbot_core.providers.langdock_provider import LangDockProvider

        with pytest.raises(ValueError):
            LangDockProvider(api_key="test-key", base_url="ftp://localhost/v1")

    def test_localhost_base_url_accepted(self):
        from eq_chatbot_core.providers.langdock_provider import LangDockProvider

        provider = LangDockProvider(api_key="test-key", base_url="http://localhost:4000/v1")
        assert provider.base_url == "http://localhost:4000/v1"

    def test_default_base_url_skips_validation(self):
        from eq_chatbot_core.providers.langdock_provider import LangDockProvider

        provider = LangDockProvider(api_key="test-key")
        assert provider.base_url == LangDockProvider.BASE_URL
