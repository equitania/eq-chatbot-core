"""
Unit tests for Anthropic provider.

All tests use mocked responses - no real API calls.
"""

import sys
from unittest.mock import MagicMock

import pytest

# Mock the anthropic module before importing provider
mock_anthropic_module = MagicMock()
sys.modules["anthropic"] = mock_anthropic_module

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    ContextLengthError,
    ProviderError,
    RateLimitError,
)
from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_anthropic_response():
    """Create a mock Anthropic message response."""
    response = MagicMock()
    response.model = "claude-sonnet-4-20250514"
    response.content = [MagicMock(type="text", text="Test response")]
    response.usage = MagicMock(input_tokens=10, output_tokens=5)
    response.stop_reason = "end_turn"
    response.model_dump.return_value = {"id": "test", "model": "claude-sonnet-4-20250514"}
    return response


@pytest.fixture
def mock_anthropic_stream():
    """Create mock streaming events."""

    class StreamContext:
        def __init__(self):
            self.events = []
            # Message start with input tokens
            msg_start = MagicMock()
            msg_start.type = "message_start"
            msg_start.message = MagicMock()
            msg_start.message.usage = MagicMock(input_tokens=10)
            self.events.append(msg_start)

            # Content deltas
            for text in ["Hello", " ", "World", "!"]:
                delta = MagicMock()
                delta.type = "content_block_delta"
                delta.delta = MagicMock(text=text)
                self.events.append(delta)

            # Message delta with output tokens
            msg_delta = MagicMock()
            msg_delta.type = "message_delta"
            msg_delta.usage = MagicMock(output_tokens=5)
            self.events.append(msg_delta)

            # Message stop
            msg_stop = MagicMock()
            msg_stop.type = "message_stop"
            self.events.append(msg_stop)

        def __enter__(self):
            return iter(self.events)

        def __exit__(self, *args):
            pass

    return StreamContext


@pytest.fixture
def mock_models_list():
    """Create mock models list response."""
    models = MagicMock()
    models.data = [
        MagicMock(id="claude-sonnet-4-20250514", display_name="Claude 4 Sonnet", created_at="2025-05-14"),
        MagicMock(id="claude-3-5-sonnet-20241022", display_name="Claude 3.5 Sonnet", created_at="2024-10-22"),
        MagicMock(id="claude-3-5-haiku-20241022", display_name="Claude 3.5 Haiku", created_at="2024-10-22"),
        MagicMock(id="claude-3-opus-20240229", display_name="Claude 3 Opus", created_at="2024-02-29"),
    ]
    return models


# =============================================================================
# Provider Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestAnthropicProviderInit:
    """Test Anthropic provider initialization."""

    def test_basic_init(self):
        """Test basic provider initialization."""
        provider = AnthropicProvider(api_key="sk-ant-test-key")

        assert provider.api_key == "sk-ant-test-key"
        assert provider.provider_name == "anthropic"
        assert provider.default_model == "claude-sonnet-4-20250514"
        assert provider.timeout == 60.0
        assert provider.max_retries == 2

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        provider = AnthropicProvider(
            api_key="sk-ant-test-key",
            base_url="https://custom.anthropic.com",
            timeout=120.0,
            max_retries=5,
        )

        assert provider.base_url == "https://custom.anthropic.com"
        assert provider.timeout == 120.0
        assert provider.max_retries == 5

    def test_lazy_client_initialization(self):
        """Test that client is lazily initialized."""
        provider = AnthropicProvider(api_key="sk-ant-test-key")
        assert provider._client is None

    def test_client_property_creates_client(self):
        """Test that accessing client creates the Anthropic instance."""
        mock_anthropic_class = MagicMock()
        mock_anthropic_module.Anthropic = mock_anthropic_class

        provider = AnthropicProvider(api_key="sk-ant-test-key")
        provider._client = None

        _ = provider.client

        mock_anthropic_class.assert_called_once_with(
            api_key="sk-ant-test-key",
            base_url=AnthropicProvider.DEFAULT_BASE_URL,
            timeout=60.0,
            max_retries=2,
        )

    def test_client_reuses_instance(self):
        """Test that client is only created once."""
        mock_anthropic_class = MagicMock()
        mock_anthropic_module.Anthropic = mock_anthropic_class

        provider = AnthropicProvider(api_key="sk-ant-test-key")
        provider._client = None

        _ = provider.client
        _ = provider.client
        _ = provider.client

        mock_anthropic_class.assert_called_once()


# =============================================================================
# System Prompt Extraction Tests
# =============================================================================


@pytest.mark.unit
class TestSystemPromptExtraction:
    """Test system prompt extraction from messages."""

    def test_extract_single_system_prompt(self):
        """Test extracting single system prompt."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]

        system, filtered = provider._extract_system_prompt(messages)

        assert system == "You are helpful."
        assert len(filtered) == 1
        assert filtered[0]["role"] == "user"

    def test_extract_multiple_system_prompts(self):
        """Test concatenating multiple system prompts."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Hello"},
        ]

        system, filtered = provider._extract_system_prompt(messages)

        assert "You are helpful." in system
        assert "Be concise." in system
        assert len(filtered) == 1

    def test_no_system_prompt(self):
        """Test when no system prompt exists."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]

        system, filtered = provider._extract_system_prompt(messages)

        assert system is None
        assert len(filtered) == 2


# =============================================================================
# Tool Conversion Tests
# =============================================================================


@pytest.mark.unit
class TestToolConversion:
    """Test OpenAI-style to Anthropic tool conversion."""

    def test_convert_single_tool(self):
        """Test converting a single tool."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                    },
                },
            }
        ]

        converted = provider._convert_tools_to_anthropic(tools)

        assert len(converted) == 1
        assert converted[0]["name"] == "get_weather"
        assert converted[0]["description"] == "Get weather for a city"
        assert "input_schema" in converted[0]

    def test_convert_multiple_tools(self):
        """Test converting multiple tools."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        tools = [
            {"type": "function", "function": {"name": "tool1", "description": "First tool"}},
            {"type": "function", "function": {"name": "tool2", "description": "Second tool"}},
        ]

        converted = provider._convert_tools_to_anthropic(tools)

        assert len(converted) == 2
        assert converted[0]["name"] == "tool1"
        assert converted[1]["name"] == "tool2"

    def test_convert_none_tools(self):
        """Test that None tools returns None."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        assert provider._convert_tools_to_anthropic(None) is None

    def test_convert_empty_tools(self):
        """Test that empty tools returns None."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        assert provider._convert_tools_to_anthropic([]) is None


# =============================================================================
# Chat Completion Tests
# =============================================================================


@pytest.mark.unit
class TestAnthropicChatCompletion:
    """Test chat completion functionality."""

    def test_simple_completion(self, mock_anthropic_response):
        """Test simple chat completion."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        response = provider.chat_completion(messages=[{"role": "user", "content": "Hello"}])

        assert response.content == "Test response"
        assert response.model == "claude-sonnet-4-20250514"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.finish_reason == "end_turn"

    def test_completion_with_system_prompt(self, mock_anthropic_response):
        """Test completion with system prompt."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        provider.chat_completion(
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ]
        )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["system"] == "You are helpful."
        # System message should be filtered out
        assert len(call_args.kwargs["messages"]) == 1

    def test_completion_with_model(self, mock_anthropic_response):
        """Test completion with specific model."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="claude-3-5-haiku-20241022",
        )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-3-5-haiku-20241022"

    def test_completion_with_temperature(self, mock_anthropic_response):
        """Test completion with temperature."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.5,
        )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["temperature"] == 0.5

    def test_completion_no_temp_for_opus3(self, mock_anthropic_response):
        """Test that temperature is not sent for claude-3-opus."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="claude-3-opus-20240229",
            temperature=0.5,  # Should be ignored
        )

        call_args = mock_client.messages.create.call_args
        assert "temperature" not in call_args.kwargs

    def test_completion_with_max_tokens(self, mock_anthropic_response):
        """Test completion with max_tokens."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=100,
        )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["max_tokens"] == 100

    def test_completion_default_max_tokens(self, mock_anthropic_response):
        """Test completion uses default max_tokens."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
        )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["max_tokens"] == 4096

    def test_completion_with_tools(self):
        """Test completion with tool calls."""
        # Create response with tool use
        # Note: MagicMock's `name` parameter is special - must set as attribute
        response = MagicMock()
        response.model = "claude-sonnet-4-20250514"

        # Create tool_use mock with name as attribute (not constructor param)
        tool_use_mock = MagicMock()
        tool_use_mock.type = "tool_use"
        tool_use_mock.id = "tool_123"
        tool_use_mock.name = "get_weather"
        tool_use_mock.input = {"location": "Paris"}

        response.content = [tool_use_mock]
        response.usage = MagicMock(input_tokens=20, output_tokens=10)
        response.stop_reason = "tool_use"
        response.model_dump.return_value = {}

        mock_client = MagicMock()
        mock_client.messages.create.return_value = response
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        tools = [{"type": "function", "function": {"name": "get_weather"}}]

        result = provider.chat_completion(
            messages=[{"role": "user", "content": "Weather in Paris?"}],
            tools=tools,
        )

        assert result.finish_reason == "tool_use"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["function"]["name"] == "get_weather"

    def test_completion_mixed_content(self):
        """Test completion with mixed text and tool content."""
        response = MagicMock()
        response.model = "claude-sonnet-4-20250514"
        response.content = [
            MagicMock(type="text", text="Let me check. "),
            MagicMock(type="text", text="Here is the result."),
        ]
        response.usage = MagicMock(input_tokens=10, output_tokens=8)
        response.stop_reason = "end_turn"
        response.model_dump.return_value = {}

        mock_client = MagicMock()
        mock_client.messages.create.return_value = response
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        result = provider.chat_completion(messages=[{"role": "user", "content": "Test"}])

        assert result.content == "Let me check. Here is the result."


# =============================================================================
# Stream Completion Tests
# =============================================================================


@pytest.mark.unit
class TestAnthropicStreamCompletion:
    """Test streaming completion functionality."""

    def test_stream_completion(self, mock_anthropic_stream):
        """Test streaming completion."""
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_anthropic_stream()
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        chunks = list(provider.stream_completion(messages=[{"role": "user", "content": "Hello"}]))

        # Should have content chunks + final
        assert len(chunks) >= 1

        # Combine content
        full_content = "".join(c.content for c in chunks if c.content)
        assert full_content == "Hello World!"

        # Last chunk should be final
        final_chunks = [c for c in chunks if c.is_final]
        assert len(final_chunks) == 1
        assert final_chunks[0].finish_reason == "end_turn"

    def test_stream_includes_usage(self, mock_anthropic_stream):
        """Test streaming includes usage on final chunk."""
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_anthropic_stream()
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        chunks = list(provider.stream_completion(messages=[{"role": "user", "content": "Hello"}]))

        final_chunk = [c for c in chunks if c.is_final][0]
        assert final_chunk.input_tokens == 10
        assert final_chunk.output_tokens == 5

    def test_stream_with_system_prompt(self, mock_anthropic_stream):
        """Test streaming with system prompt."""
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_anthropic_stream()
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        list(
            provider.stream_completion(
                messages=[
                    {"role": "system", "content": "Be helpful"},
                    {"role": "user", "content": "Hello"},
                ]
            )
        )

        call_args = mock_client.messages.stream.call_args
        assert call_args.kwargs["system"] == "Be helpful"


# =============================================================================
# List Models Tests
# =============================================================================


@pytest.mark.unit
class TestAnthropicListModels:
    """Test list_models functionality."""

    def test_list_models(self, mock_models_list):
        """Test listing models from API."""
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_models_list
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        models = provider.list_models()

        assert len(models) == 4
        model_ids = [m["id"] for m in models]
        assert "claude-sonnet-4-20250514" in model_ids
        assert "claude-3-5-sonnet-20241022" in model_ids

    def test_list_models_includes_constraints(self, mock_models_list):
        """Test that models include constraint information."""
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_models_list
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        models = provider.list_models()

        sonnet4 = next(m for m in models if m["id"] == "claude-sonnet-4-20250514")
        assert sonnet4["supports_temperature"] is True
        assert sonnet4["supports_vision"] is True
        assert sonnet4["provider"] == "anthropic"
        assert sonnet4["max_temperature"] == 1.0

    def test_list_models_sorted_by_date(self, mock_models_list):
        """Test that models are sorted by creation date (newest first)."""
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_models_list
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None
        models = provider.list_models()

        # First model should be newest (2025-05-14)
        assert models[0]["id"] == "claude-sonnet-4-20250514"


# =============================================================================
# Model Constraints Tests
# =============================================================================


@pytest.mark.unit
class TestAnthropicModelConstraints:
    """Test model constraint detection."""

    def test_sonnet4_constraints(self):
        """Test constraints for Claude 4 Sonnet."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        constraints = provider._get_model_constraints("claude-sonnet-4-20250514")

        assert constraints["supports_temperature"] is True
        assert constraints["supports_vision"] is True
        assert constraints["max_output_tokens"] == 16384
        assert constraints["context_length"] == 200000

    def test_opus4_constraints(self):
        """Test constraints for Claude 4 Opus."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        constraints = provider._get_model_constraints("claude-opus-4-5-20251101")

        assert constraints["supports_temperature"] is True
        assert constraints["supports_vision"] is True
        assert constraints["max_output_tokens"] == 16384

    def test_opus3_constraints(self):
        """Test constraints for Claude 3 Opus (no temperature)."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        constraints = provider._get_model_constraints("claude-3-opus-20240229")

        assert constraints["supports_temperature"] is False
        assert constraints["supports_vision"] is True

    def test_haiku_constraints(self):
        """Test constraints for Claude 3.5 Haiku."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        constraints = provider._get_model_constraints("claude-3-5-haiku-20241022")

        assert constraints["supports_temperature"] is True
        assert constraints["supports_vision"] is True
        assert constraints["max_output_tokens"] == 8192

    def test_temperature_range(self):
        """Test Anthropic temperature range."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        constraints = provider._get_model_constraints("claude-sonnet-4-20250514")

        assert constraints["min_temperature"] == 0.0
        assert constraints["max_temperature"] == 1.0  # Anthropic max is 1.0


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestAnthropicErrorHandling:
    """Test error handling in Anthropic provider."""

    def test_rate_limit_error(self):
        """Test handling of rate limit errors."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Error code: 429 - Rate limit exceeded")
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None

        with pytest.raises(RateLimitError) as exc_info:
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        assert exc_info.value.status_code == 429
        assert exc_info.value.provider == "anthropic"

    def test_authentication_error(self):
        """Test handling of authentication errors."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Error code: 401 - Authentication failed")
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-invalid")
        provider._client = None

        with pytest.raises(AuthenticationError) as exc_info:
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        assert exc_info.value.status_code == 401
        assert exc_info.value.provider == "anthropic"

    def test_context_length_error(self):
        """Test handling of context length errors."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("prompt is too long: 250000 tokens > 200000 maximum")
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None

        with pytest.raises(ContextLengthError) as exc_info:
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        assert exc_info.value.provider == "anthropic"

    def test_generic_error(self):
        """Test handling of generic errors."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Unknown error")
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None

        with pytest.raises(ProviderError) as exc_info:
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        assert exc_info.value.provider == "anthropic"
        assert type(exc_info.value) is ProviderError

    def test_stream_error_handling(self):
        """Test error handling during streaming."""
        mock_client = MagicMock()
        mock_client.messages.stream.side_effect = Exception("Stream error")
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-test")
        provider._client = None

        with pytest.raises(ProviderError):
            list(provider.stream_completion(messages=[{"role": "user", "content": "Hi"}]))

    def test_list_models_error_handling(self):
        """Test error handling in list_models."""
        mock_client = MagicMock()
        mock_client.models.list.side_effect = Exception("Error code: 401")
        mock_anthropic_module.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="sk-ant-invalid")
        provider._client = None

        with pytest.raises(AuthenticationError):
            provider.list_models()


# =============================================================================
# Provider Properties Tests
# =============================================================================


@pytest.mark.unit
class TestAnthropicProviderProperties:
    """Test provider properties and constants."""

    def test_provider_name(self):
        """Test provider_name property."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        assert provider.provider_name == "anthropic"

    def test_default_model(self):
        """Test default_model property."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        assert provider.default_model == "claude-sonnet-4-20250514"

    def test_default_base_url(self):
        """Test default base URL constant."""
        assert AnthropicProvider.DEFAULT_BASE_URL == "https://api.anthropic.com"

    def test_no_temperature_models(self):
        """Test NO_TEMPERATURE_MODELS constant."""
        assert "claude-3-opus" in AnthropicProvider.NO_TEMPERATURE_MODELS

    def test_repr(self):
        """Test string representation."""
        provider = AnthropicProvider(api_key="sk-ant-test")
        repr_str = repr(provider)
        assert "AnthropicProvider" in repr_str
        assert "anthropic" in repr_str
