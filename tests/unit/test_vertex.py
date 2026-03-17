"""
Unit tests for Google Vertex AI provider.

All tests use mocked responses - no real API calls.
Tests cover Vertex AI access via google-genai SDK with temperature constraints.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    ContextLengthError,
    OverloadedError,
    ProviderError,
    RateLimitError,
)

# =============================================================================
# Helper to create a provider with mocked SDK
# =============================================================================


def _make_provider(**kwargs):
    """Create a VertexProvider with mocked google-genai SDK."""
    import eq_chatbot_core.providers.vertex_provider as vp

    # Temporarily enable the availability flag (SDK is not installed in test env)
    original = vp._google_available
    vp._google_available = True
    try:
        from eq_chatbot_core.providers.vertex_provider import VertexProvider

        defaults = {"project": "test-project", "location": "europe-west1"}
        defaults.update(kwargs)
        return VertexProvider(**defaults)
    finally:
        vp._google_available = original


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_generate_response():
    """Create a mock google-genai generate_content response."""
    response = MagicMock()

    # Candidate with text content
    part = MagicMock()
    part.text = "Test response from Vertex AI"
    part.function_call = None

    candidate = MagicMock()
    candidate.content.parts = [part]
    candidate.finish_reason = "STOP"

    response.candidates = [candidate]

    # Usage metadata
    usage = MagicMock()
    usage.prompt_token_count = 10
    usage.candidates_token_count = 5
    response.usage_metadata = usage

    return response


@pytest.fixture
def mock_stream_chunks():
    """Create mock streaming chunks."""
    chunk1 = MagicMock()
    part1 = MagicMock()
    part1.text = "Hello "
    part1.function_call = None
    candidate1 = MagicMock()
    candidate1.content.parts = [part1]
    candidate1.finish_reason = None
    chunk1.candidates = [candidate1]
    chunk1.usage_metadata = None

    chunk2 = MagicMock()
    part2 = MagicMock()
    part2.text = "World!"
    part2.function_call = None
    candidate2 = MagicMock()
    candidate2.content.parts = [part2]
    candidate2.finish_reason = "STOP"
    usage2 = MagicMock()
    usage2.prompt_token_count = 8
    usage2.candidates_token_count = 4
    chunk2.candidates = [candidate2]
    chunk2.usage_metadata = usage2

    return [chunk1, chunk2]


# =============================================================================
# Provider Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestVertexProviderInit:
    """Test Vertex provider initialization."""

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_basic_init(self, mock_genai):
        """Test basic provider initialization."""
        provider = _make_provider()
        assert provider._project == "test-project"
        assert provider._location == "europe-west1"

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_custom_location(self, mock_genai):
        """Test initialization with custom location."""
        provider = _make_provider(location="europe-west3")
        assert provider._location == "europe-west3"

    @patch("eq_chatbot_core.providers.vertex_provider._google_available", True)
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_missing_project_raises(self, mock_genai):
        """Test that missing project raises ValueError."""
        from eq_chatbot_core.providers.vertex_provider import VertexProvider

        with pytest.raises(ValueError, match="project is required"):
            VertexProvider()

    def test_missing_sdk_raises(self):
        """Test that missing google-genai SDK raises ImportError."""
        with patch("eq_chatbot_core.providers.vertex_provider._google_available", False):
            from eq_chatbot_core.providers.vertex_provider import VertexProvider

            with pytest.raises(ImportError, match="Google Gen AI SDK not installed"):
                VertexProvider(project="test-project")

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_custom_timeout(self, mock_genai):
        """Test initialization with custom timeout."""
        provider = _make_provider(timeout=120.0)
        assert provider.timeout == 120.0

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_api_key_ignored(self, mock_genai):
        """Test that api_key is accepted but not used for auth."""
        provider = _make_provider(api_key="some-key")
        assert provider.api_key == "some-key"

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_api_key_defaults_to_not_used(self, mock_genai):
        """Test that empty api_key defaults to 'not-used'."""
        provider = _make_provider()
        assert provider.api_key == "not-used"


# =============================================================================
# Provider Properties Tests
# =============================================================================


@pytest.mark.unit
class TestVertexProviderProperties:
    """Test provider properties."""

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_provider_name(self, mock_genai):
        """Test provider_name property."""
        provider = _make_provider()
        assert provider.provider_name == "vertex"

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_default_model(self, mock_genai):
        """Test default model is gemini-2.5-flash."""
        provider = _make_provider()
        assert provider.default_model == "gemini-2.5-flash"


# =============================================================================
# Lazy Client Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestVertexClientInit:
    """Test lazy client initialization."""

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_client_lazy_init(self, mock_genai):
        """Test that client is lazily initialized."""
        provider = _make_provider()
        assert provider._client is None

        _ = provider.client

        mock_genai.Client.assert_called_once_with(
            vertexai=True,
            project="test-project",
            location="europe-west1",
        )

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_client_reused(self, mock_genai):
        """Test that client is reused on subsequent access."""
        provider = _make_provider()
        client1 = provider.client
        client2 = provider.client
        assert client1 is client2
        mock_genai.Client.assert_called_once()


# =============================================================================
# Temperature Constraints Tests
# =============================================================================


@pytest.mark.unit
class TestVertexTemperatureConstraints:
    """Test temperature constraints for Gemini models."""

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_gemini_temperature_range(self, mock_genai):
        """Test Gemini models have 0.0-2.0 temperature range."""
        provider = _make_provider()
        constraints = provider._get_temperature_constraints("gemini-2.5-flash")
        assert constraints["min"] == 0.0
        assert constraints["max"] == 2.0
        assert constraints["supports_temperature"] is True

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_gemini_temperature_passthrough(self, mock_genai):
        """Test temperature within range passes through."""
        provider = _make_provider()
        result = provider._clamp_temperature("gemini-2.5-flash", 0.7)
        assert result == 0.7

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_gemini_temperature_clamp_high(self, mock_genai):
        """Test temperature above max is clamped."""
        provider = _make_provider()
        result = provider._clamp_temperature("gemini-2.5-flash", 2.5)
        assert result == 2.0

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_gemini_temperature_zero(self, mock_genai):
        """Test zero temperature is valid for Gemini."""
        provider = _make_provider()
        result = provider._clamp_temperature("gemini-2.5-flash", 0.0)
        assert result == 0.0


# =============================================================================
# Message Conversion Tests
# =============================================================================


@pytest.mark.unit
class TestVertexMessageConversion:
    """Test message format conversion."""

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    @patch("eq_chatbot_core.providers.vertex_provider.types")
    def test_system_message_extraction(self, mock_types, mock_genai):
        """Test system messages are extracted to system_instruction."""
        provider = _make_provider()
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        system_instruction, contents = provider._convert_messages(messages)
        assert system_instruction == "You are a helpful assistant."
        assert len(contents) == 1  # Only the user message

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    @patch("eq_chatbot_core.providers.vertex_provider.types")
    def test_multiple_system_messages(self, mock_types, mock_genai):
        """Test multiple system messages are joined."""
        provider = _make_provider()
        messages = [
            {"role": "system", "content": "Rule 1"},
            {"role": "system", "content": "Rule 2"},
            {"role": "user", "content": "Hi"},
        ]
        system_instruction, contents = provider._convert_messages(messages)
        assert system_instruction == "Rule 1\n\nRule 2"

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    @patch("eq_chatbot_core.providers.vertex_provider.types")
    def test_assistant_role_mapped_to_model(self, mock_types, mock_genai):
        """Test 'assistant' role is mapped to 'model' for google-genai."""
        provider = _make_provider()
        messages = [{"role": "assistant", "content": "I can help you."}]
        system_instruction, contents = provider._convert_messages(messages)
        assert system_instruction is None
        mock_types.Content.assert_called_with(
            role="model",
            parts=[mock_types.Part.from_text(text="I can help you.")],
        )

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    @patch("eq_chatbot_core.providers.vertex_provider.types")
    def test_user_message(self, mock_types, mock_genai):
        """Test user messages are converted correctly."""
        provider = _make_provider()
        messages = [{"role": "user", "content": "Hello"}]
        provider._convert_messages(messages)
        mock_types.Content.assert_called_with(
            role="user",
            parts=[mock_types.Part.from_text(text="Hello")],
        )

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    @patch("eq_chatbot_core.providers.vertex_provider.types")
    def test_tool_message_conversion(self, mock_types, mock_genai):
        """Test tool response messages are converted to function response parts."""
        provider = _make_provider()
        messages = [
            {
                "role": "tool",
                "tool_call_id": "call_abc123",
                "name": "get_weather",
                "content": '{"temperature": 20, "unit": "celsius"}',
            }
        ]
        system_instruction, contents = provider._convert_messages(messages)
        assert system_instruction is None
        assert len(contents) == 1
        mock_types.Part.from_function_response.assert_called_once_with(
            name="get_weather",
            response={"temperature": 20, "unit": "celsius"},
        )

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    @patch("eq_chatbot_core.providers.vertex_provider.types")
    def test_tool_message_invalid_json(self, mock_types, mock_genai):
        """Test tool message with invalid JSON falls back to string result."""
        provider = _make_provider()
        messages = [
            {
                "role": "tool",
                "tool_call_id": "call_xyz",
                "name": "search",
                "content": "plain text result",
            }
        ]
        provider._convert_messages(messages)
        mock_types.Part.from_function_response.assert_called_once_with(
            name="search",
            response={"result": "plain text result"},
        )

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    @patch("eq_chatbot_core.providers.vertex_provider.types")
    def test_no_system_message(self, mock_types, mock_genai):
        """Test no system instruction when no system messages present."""
        provider = _make_provider()
        messages = [{"role": "user", "content": "Hello"}]
        system_instruction, _ = provider._convert_messages(messages)
        assert system_instruction is None


# =============================================================================
# Chat Completion Tests
# =============================================================================


@pytest.mark.unit
class TestVertexChatCompletion:
    """Test chat completion functionality."""

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_simple_completion(self, mock_genai, mock_types, mock_generate_response):
        """Test simple chat completion."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_generate_response
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert response.content == "Test response from Vertex AI"
        assert response.model == "gemini-2.5-flash"
        assert response.input_tokens == 10
        assert response.output_tokens == 5

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_completion_with_custom_model(self, mock_genai, mock_types, mock_generate_response):
        """Test completion with custom model."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_generate_response
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="gemini-2.5-pro",
        )

        assert response.model == "gemini-2.5-pro"
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs["model"] == "gemini-2.5-pro"

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_completion_with_max_tokens(self, mock_genai, mock_types, mock_generate_response):
        """Test completion with max_tokens parameter."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_generate_response
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=100,
        )

        # Verify GenerateContentConfig was called with max_output_tokens
        mock_types.GenerateContentConfig.assert_called_once()
        config_kwargs = mock_types.GenerateContentConfig.call_args.kwargs
        assert config_kwargs["max_output_tokens"] == 100

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_completion_with_tools(self, mock_genai, mock_types, mock_generate_response):
        """Test completion with tool definitions."""
        # Setup function call response
        fn_call = MagicMock()
        fn_call.name = "get_weather"
        fn_call.args = {"location": "Berlin"}

        part = MagicMock()
        part.text = None
        part.function_call = fn_call

        mock_generate_response.candidates[0].content.parts = [part]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_generate_response
        mock_genai.Client.return_value = mock_client

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a location",
                    "parameters": {"type": "object", "properties": {"location": {"type": "string"}}},
                },
            }
        ]

        provider = _make_provider()
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Weather in Berlin?"}],
            tools=tools,
        )

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["type"] == "function"
        assert response.tool_calls[0]["function"]["name"] == "get_weather"
        args = json.loads(response.tool_calls[0]["function"]["arguments"])
        assert args["location"] == "Berlin"

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_completion_finish_reason_stop(self, mock_genai, mock_types, mock_generate_response):
        """Test finish reason mapping for STOP."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_generate_response
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert response.finish_reason == "stop"

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_completion_empty_candidates(self, mock_genai, mock_types):
        """Test handling of empty candidates."""
        mock_response = MagicMock()
        mock_response.candidates = []
        mock_response.usage_metadata = None

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert response.content == ""
        assert response.tool_calls == []


# =============================================================================
# Stream Completion Tests
# =============================================================================


@pytest.mark.unit
class TestVertexStreamCompletion:
    """Test streaming completion functionality."""

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_basic_streaming(self, mock_genai, mock_types, mock_stream_chunks):
        """Test basic streaming response."""
        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = iter(mock_stream_chunks)
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Hello"}],
            )
        )

        assert len(chunks) == 2
        assert chunks[0].content == "Hello "
        assert chunks[0].is_final is False
        assert chunks[1].content == "World!"
        assert chunks[1].is_final is True
        assert chunks[1].finish_reason == "stop"
        assert chunks[1].input_tokens == 8
        assert chunks[1].output_tokens == 4

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_streaming_with_tool_calls(self, mock_genai, mock_types):
        """Test streaming with function call chunks."""
        # Create chunk with function call
        fn_call = MagicMock()
        fn_call.name = "get_weather"
        fn_call.args = {"city": "Berlin"}

        part = MagicMock()
        part.text = None
        part.function_call = fn_call

        chunk = MagicMock()
        candidate = MagicMock()
        candidate.content.parts = [part]
        candidate.finish_reason = "FUNCTION_CALL"
        chunk.candidates = [candidate]
        usage = MagicMock()
        usage.prompt_token_count = 5
        usage.candidates_token_count = 3
        chunk.usage_metadata = usage

        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = iter([chunk])
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Weather?"}],
            )
        )

        assert len(chunks) == 1
        assert chunks[0].is_final is True
        assert chunks[0].tool_calls is not None
        assert len(chunks[0].tool_calls) == 1
        assert chunks[0].tool_calls[0]["function"]["name"] == "get_weather"


# =============================================================================
# List Models Tests
# =============================================================================


@pytest.mark.unit
class TestVertexListModels:
    """Test model listing."""

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_list_models_returns_known_models(self, mock_genai):
        """Test that list_models returns static catalog."""
        provider = _make_provider()
        models = provider.list_models()

        assert len(models) == 4
        model_ids = [m["id"] for m in models]
        assert "gemini-2.5-flash" in model_ids
        assert "gemini-2.5-pro" in model_ids
        assert "gemini-2.0-flash" in model_ids
        assert "gemini-2.0-flash-lite" in model_ids

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_list_models_sorted(self, mock_genai):
        """Test that models are sorted by ID."""
        provider = _make_provider()
        models = provider.list_models()
        ids = [m["id"] for m in models]
        assert ids == sorted(ids)

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_list_models_metadata(self, mock_genai):
        """Test that models include correct metadata."""
        provider = _make_provider()
        models = provider.list_models()

        flash_model = next(m for m in models if m["id"] == "gemini-2.5-flash")
        assert flash_model["provider"] == "vertex"
        assert flash_model["context_length"] == 1048576
        assert flash_model["max_output_tokens"] == 65536
        assert flash_model["supports_vision"] is True
        assert flash_model["supports_tools"] is True
        assert flash_model["supports_streaming"] is True
        assert flash_model["supports_temperature"] is True
        assert flash_model["min_temperature"] == 0.0
        assert flash_model["max_temperature"] == 2.0


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestVertexErrorHandling:
    """Test error handling and mapping."""

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_rate_limit_error(self, mock_genai, mock_types):
        """Test 429 error maps to RateLimitError."""
        error = Exception("429 Resource Exhausted")
        error.code = 429  # type: ignore[attr-defined]

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = error
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        with pytest.raises(RateLimitError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_auth_error(self, mock_genai, mock_types):
        """Test 403 error maps to AuthenticationError."""
        error = Exception("403 Permission denied")
        error.code = 403  # type: ignore[attr-defined]

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = error
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        with pytest.raises(AuthenticationError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_overloaded_error(self, mock_genai, mock_types):
        """Test 503 error maps to OverloadedError."""
        error = Exception("503 Service Unavailable")
        error.code = 503  # type: ignore[attr-defined]

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = error
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        with pytest.raises(OverloadedError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_context_length_error(self, mock_genai, mock_types):
        """Test context length error detection."""
        error = Exception("400 context window exceeded, token limit reached")

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = error
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        with pytest.raises(ContextLengthError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_generic_error(self, mock_genai, mock_types):
        """Test generic exceptions map to ProviderError."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("Something went wrong")
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        with pytest.raises(ProviderError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_resource_exhausted_error(self, mock_genai, mock_types):
        """Test 'resource exhausted' in message maps to RateLimitError."""
        error = Exception("Resource exhausted: quota exceeded")

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = error
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        with pytest.raises(RateLimitError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    @patch("eq_chatbot_core.providers.vertex_provider.types")
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_unauthenticated_error(self, mock_genai, mock_types):
        """Test 'unauthenticated' in message maps to AuthenticationError."""
        error = Exception("Request had invalid authentication credentials: unauthenticated")

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = error
        mock_genai.Client.return_value = mock_client

        provider = _make_provider()
        with pytest.raises(AuthenticationError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])


# =============================================================================
# Context Manager Tests
# =============================================================================


@pytest.mark.unit
class TestVertexContextManager:
    """Test context manager protocol."""

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_close(self, mock_genai):
        """Test close() resets client."""
        provider = _make_provider()
        _ = provider.client  # Initialize client
        assert provider._client is not None

        provider.close()
        assert provider._client is None

    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_context_manager(self, mock_genai):
        """Test with-statement support."""
        with _make_provider() as provider:
            assert provider.provider_name == "vertex"
        assert provider._client is None


# =============================================================================
# Factory Integration Tests
# =============================================================================


@pytest.mark.unit
class TestVertexFactoryIntegration:
    """Test factory function integration."""

    @patch("eq_chatbot_core.providers.vertex_provider._google_available", True)
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_get_provider_vertex(self, mock_genai):
        """Test get_provider('vertex') returns VertexProvider."""
        from eq_chatbot_core.providers import get_provider
        from eq_chatbot_core.providers.vertex_provider import VertexProvider

        provider = get_provider("vertex", project="test-project")
        assert isinstance(provider, VertexProvider)
        assert provider.provider_name == "vertex"

    @patch("eq_chatbot_core.providers.vertex_provider._google_available", True)
    @patch("eq_chatbot_core.providers.vertex_provider.genai")
    def test_get_provider_vertex_no_api_key_needed(self, mock_genai):
        """Test that vertex provider works without api_key."""
        from eq_chatbot_core.providers import get_provider

        provider = get_provider("vertex", project="my-project")
        assert provider.api_key == "not-used"
