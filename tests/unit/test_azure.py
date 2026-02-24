"""
Unit tests for Azure AI provider.

All tests use mocked responses - no real API calls.
Tests cover Azure AI Foundry access with temperature constraints.
"""

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
# Fixtures
# =============================================================================


@pytest.fixture
def mock_chat_response():
    """Create a mock Azure chat completion response."""
    response = MagicMock()
    response.model = "gpt-4o"

    choice = MagicMock()
    choice.message.content = "Test response from Azure"
    choice.message.tool_calls = None
    choice.finish_reason = "stop"

    response.choices = [choice]

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    response.usage = usage

    return response


# =============================================================================
# Provider Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestAzureProviderInit:
    """Test Azure provider initialization."""

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_basic_init(self, mock_credential, mock_client_class):
        """Test basic provider initialization."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(
            api_key="test-azure-key",
            base_url="https://test.services.ai.azure.com/",
        )
        assert provider.api_key == "test-azure-key"
        assert provider.base_url == "https://test.services.ai.azure.com/"

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_custom_endpoint(self, mock_credential, mock_client_class):
        """Test initialization with custom endpoint."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        endpoint = "https://custom-resource.cognitiveservices.azure.com/"
        provider = AzureProvider(api_key="test-key", base_url=endpoint)
        assert provider.base_url == endpoint

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_missing_endpoint_raises(self, mock_credential, mock_client_class):
        """Test that missing base_url raises ValueError."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        with pytest.raises(ValueError, match="base_url is required"):
            AzureProvider(api_key="test-key")

    def test_missing_sdk_raises(self):
        """Test that missing Azure SDK raises ImportError."""
        with patch("eq_chatbot_core.providers.azure_provider._azure_available", False):
            from eq_chatbot_core.providers.azure_provider import AzureProvider

            with pytest.raises(ImportError, match="Azure AI SDK not installed"):
                AzureProvider(
                    api_key="test-key",
                    base_url="https://test.services.ai.azure.com/",
                )

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_custom_timeout(self, mock_credential, mock_client_class):
        """Test initialization with custom timeout."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(
            api_key="test-key",
            base_url="https://test.services.ai.azure.com/",
            timeout=120.0,
        )
        assert provider.timeout == 120.0


# =============================================================================
# Provider Properties Tests
# =============================================================================


@pytest.mark.unit
class TestAzureProviderProperties:
    """Test provider properties."""

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_provider_name(self, mock_credential, mock_client_class):
        """Test provider_name property."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(
            api_key="test-key",
            base_url="https://test.services.ai.azure.com/",
        )
        assert provider.provider_name == "azure"

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_default_model(self, mock_credential, mock_client_class):
        """Test default model is GPT-4o."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(
            api_key="test-key",
            base_url="https://test.services.ai.azure.com/",
        )
        assert provider.default_model == "gpt-4o"


# =============================================================================
# Temperature Constraints Tests
# =============================================================================


@pytest.mark.unit
class TestAzureTemperatureConstraints:
    """Test temperature constraint handling."""

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_reasoning_model_no_temperature(self, mock_credential, mock_client_class):
        """Test reasoning models (o1, o3, o4) return None for temperature."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")

        assert provider._clamp_temperature("o1", 0.7) is None
        assert provider._clamp_temperature("o3", 0.5) is None
        assert provider._clamp_temperature("o4-mini", 0.3) is None

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_gpt41_temperature_passthrough(self, mock_credential, mock_client_class):
        """Test GPT-4.1 models pass through temperature (min=0.0)."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")

        assert provider._clamp_temperature("gpt-4.1", 0.5) == 0.5
        assert provider._clamp_temperature("gpt-4.1-mini", 0.7) == 0.7
        assert provider._clamp_temperature("gpt-4.1-nano", 0.0) == 0.0

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_legacy_model_passthrough(self, mock_credential, mock_client_class):
        """Test legacy models (gpt-4o) pass through any valid temperature."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")

        assert provider._clamp_temperature("gpt-4o", 0.0) == 0.0
        assert provider._clamp_temperature("gpt-4o", 0.7) == 0.7
        assert provider._clamp_temperature("gpt-4o", 2.0) == 2.0

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_claude_max_temperature_clamped(self, mock_credential, mock_client_class):
        """Test Claude models clamp temperature to max 1.0."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")

        assert provider._clamp_temperature("claude-sonnet-4-5", 1.5) == 1.0
        assert provider._clamp_temperature("claude-sonnet-4-5", 0.5) == 0.5

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_unknown_model_uses_defaults(self, mock_credential, mock_client_class):
        """Test unknown models use default constraints (0.0-2.0)."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")

        assert provider._clamp_temperature("some-unknown-model", 0.0) == 0.0
        assert provider._clamp_temperature("some-unknown-model", 1.5) == 1.5
        assert provider._clamp_temperature("some-unknown-model", 2.0) == 2.0


# =============================================================================
# Reasoning Model Detection Tests
# =============================================================================


@pytest.mark.unit
class TestAzureReasoningModels:
    """Test reasoning model detection."""

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_o1_o3_o4_detected(self, mock_credential, mock_client_class):
        """Test o1/o3/o4 models are detected as reasoning."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        assert provider._is_reasoning_model("o1") is True
        assert provider._is_reasoning_model("o1-mini") is True
        assert provider._is_reasoning_model("o3") is True
        assert provider._is_reasoning_model("o3-mini") is True
        assert provider._is_reasoning_model("o4-mini") is True

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_gpt_claude_not_detected(self, mock_credential, mock_client_class):
        """Test GPT and Claude models are not reasoning models."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        assert provider._is_reasoning_model("gpt-4o") is False
        assert provider._is_reasoning_model("gpt-4.1") is False
        assert provider._is_reasoning_model("claude-sonnet-4-5") is False


# =============================================================================
# Message Conversion Tests
# =============================================================================


@pytest.mark.unit
class TestAzureMessageConversion:
    """Test message dict to Azure SDK type conversion."""

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_system_message(self, mock_credential, mock_client_class):
        """Test system message conversion."""
        from azure.ai.inference.models import SystemMessage

        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        result = provider._convert_messages([{"role": "system", "content": "You are helpful."}])
        assert len(result) == 1
        assert isinstance(result[0], SystemMessage)

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_user_message(self, mock_credential, mock_client_class):
        """Test user message conversion."""
        from azure.ai.inference.models import UserMessage

        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        result = provider._convert_messages([{"role": "user", "content": "Hello"}])
        assert len(result) == 1
        assert isinstance(result[0], UserMessage)

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_assistant_message(self, mock_credential, mock_client_class):
        """Test assistant message conversion."""
        from azure.ai.inference.models import AssistantMessage

        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        result = provider._convert_messages([{"role": "assistant", "content": "Hi there!"}])
        assert len(result) == 1
        assert isinstance(result[0], AssistantMessage)

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_tool_message(self, mock_credential, mock_client_class):
        """Test tool message conversion."""
        from azure.ai.inference.models import ToolMessage

        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        result = provider._convert_messages(
            [{"role": "tool", "content": '{"temp": 20}', "tool_call_id": "call_123"}]
        )
        assert len(result) == 1
        assert isinstance(result[0], ToolMessage)

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_unknown_role_fallback(self, mock_credential, mock_client_class):
        """Test unknown role falls back to user message."""
        from azure.ai.inference.models import UserMessage

        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        result = provider._convert_messages([{"role": "unknown", "content": "test"}])
        assert len(result) == 1
        assert isinstance(result[0], UserMessage)


# =============================================================================
# Chat Completion Tests
# =============================================================================


@pytest.mark.unit
class TestAzureChatCompletion:
    """Test chat completion functionality."""

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_simple_completion(self, mock_credential, mock_client_class, mock_chat_response):
        """Test simple chat completion."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        mock_client = MagicMock()
        mock_client.complete.return_value = mock_chat_response
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o",
        )

        assert response.content == "Test response from Azure"
        assert response.model == "gpt-4o"
        assert response.input_tokens == 10
        assert response.output_tokens == 5

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_completion_temperature_passthrough_gpt41(self, mock_credential, mock_client_class, mock_chat_response):
        """Test temperature passes through for GPT-4.1 models (min=0.0)."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        mock_client = MagicMock()
        mock_client.complete.return_value = mock_chat_response
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4.1",
            temperature=0.3,
        )

        call_kwargs = mock_client.complete.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.3

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_completion_no_temperature_reasoning(self, mock_credential, mock_client_class, mock_chat_response):
        """Test reasoning models don't receive temperature."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        mock_client = MagicMock()
        mock_client.complete.return_value = mock_chat_response
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="o1",
            temperature=0.7,
        )

        call_kwargs = mock_client.complete.call_args.kwargs
        assert "temperature" not in call_kwargs

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_completion_with_max_tokens(self, mock_credential, mock_client_class, mock_chat_response):
        """Test completion with max_tokens."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        mock_client = MagicMock()
        mock_client.complete.return_value = mock_chat_response
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o",
            max_tokens=100,
        )

        call_kwargs = mock_client.complete.call_args.kwargs
        assert call_kwargs.get("max_tokens") == 100

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_completion_with_tools(self, mock_credential, mock_client_class):
        """Test completion with tools."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        # Build mock response with tool calls
        function_mock = MagicMock()
        function_mock.name = "get_weather"
        function_mock.arguments = '{"location": "Paris"}'

        tool_call_mock = MagicMock()
        tool_call_mock.id = "call_123"
        tool_call_mock.type = "function"
        tool_call_mock.function = function_mock

        response = MagicMock()
        response.model = "gpt-4o"
        response.choices = [MagicMock()]
        response.choices[0].message.content = ""
        response.choices[0].message.tool_calls = [tool_call_mock]
        response.choices[0].finish_reason = "tool_calls"
        response.usage.prompt_tokens = 10
        response.usage.completion_tokens = 5

        mock_client = MagicMock()
        mock_client.complete.return_value = response
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]
        result = provider.chat_completion(
            messages=[{"role": "user", "content": "Weather in Paris?"}],
            model="gpt-4o",
            tools=tools,
        )

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["function"]["name"] == "get_weather"


# =============================================================================
# Stream Completion Tests
# =============================================================================


@pytest.mark.unit
class TestAzureStreamCompletion:
    """Test streaming completion functionality."""

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_basic_streaming(self, mock_credential, mock_client_class):
        """Test basic streaming."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        # Create stream chunks
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"
        chunk1.choices[0].delta.tool_calls = None
        chunk1.choices[0].finish_reason = None
        chunk1.usage = None

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " world"
        chunk2.choices[0].delta.tool_calls = None
        chunk2.choices[0].finish_reason = None
        chunk2.usage = None

        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta.content = ""
        chunk3.choices[0].delta.tool_calls = None
        chunk3.choices[0].finish_reason = "stop"
        chunk3.usage = MagicMock()
        chunk3.usage.prompt_tokens = 5
        chunk3.usage.completion_tokens = 2

        mock_client = MagicMock()
        mock_client.complete.return_value = iter([chunk1, chunk2, chunk3])
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Hi"}],
                model="gpt-4o",
            )
        )

        assert len(chunks) == 3
        assert chunks[0].content == "Hello"
        assert chunks[0].is_final is False
        assert chunks[1].content == " world"
        assert chunks[2].is_final is True
        assert chunks[2].input_tokens == 5
        assert chunks[2].output_tokens == 2

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_streaming_temperature_passthrough_gpt41(self, mock_credential, mock_client_class):
        """Test streaming passes through temperature for GPT-4.1 models (min=0.0)."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "ok"
        chunk.choices[0].delta.tool_calls = None
        chunk.choices[0].finish_reason = "stop"
        chunk.usage = None

        mock_client = MagicMock()
        mock_client.complete.return_value = iter([chunk])
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Hi"}],
                model="gpt-4.1",
                temperature=0.5,
            )
        )

        call_kwargs = mock_client.complete.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.5


# =============================================================================
# List Models Tests
# =============================================================================


@pytest.mark.unit
class TestAzureListModels:
    """Test list models functionality."""

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_list_models_returns_all(self, mock_credential, mock_client_class):
        """Test list_models returns all known models."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")

        models = provider.list_models()

        assert len(models) > 0
        model_ids = [m["id"] for m in models]
        assert "gpt-4o" in model_ids
        assert "gpt-4.1" in model_ids
        assert "o3" in model_ids

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_list_models_includes_metadata(self, mock_credential, mock_client_class):
        """Test list_models includes model metadata."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")

        models = provider.list_models()

        gpt4o = next(m for m in models if m["id"] == "gpt-4o")
        assert gpt4o["name"] == "GPT-4o"
        assert gpt4o["context_length"] == 128000
        assert gpt4o["provider"] == "azure"

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_list_models_sorted(self, mock_credential, mock_client_class):
        """Test list_models returns sorted by ID."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")

        models = provider.list_models()
        model_ids = [m["id"] for m in models]
        assert model_ids == sorted(model_ids)

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_list_models_temperature_constraints(self, mock_credential, mock_client_class):
        """Test list_models includes correct temperature constraints."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")

        models = provider.list_models()

        # GPT-4o: 0.0-2.0
        gpt4o = next(m for m in models if m["id"] == "gpt-4o")
        assert gpt4o["supports_temperature"] is True
        assert gpt4o["min_temperature"] == 0.0
        assert gpt4o["max_temperature"] == 2.0

        # O3: reasoning model, no temperature
        o3 = next(m for m in models if m["id"] == "o3")
        assert o3["supports_temperature"] is False
        assert o3["supports_reasoning"] is True

        # GPT-4.1: min 0.0
        gpt41 = next(m for m in models if m["id"] == "gpt-4.1")
        assert gpt41["supports_temperature"] is True
        assert gpt41["min_temperature"] == 0.0


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestAzureErrorHandling:
    """Test error handling and mapping."""

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_rate_limit_429(self, mock_credential, mock_client_class):
        """Test rate limit error is properly mapped."""
        from azure.core.exceptions import HttpResponseError

        from eq_chatbot_core.providers.azure_provider import AzureProvider

        mock_client = MagicMock()
        error = HttpResponseError(message="Rate limit exceeded")
        error.status_code = 429
        mock_client.complete.side_effect = error
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        with pytest.raises(RateLimitError):
            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
            )

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_auth_401(self, mock_credential, mock_client_class):
        """Test authentication error via ClientAuthenticationError."""
        from azure.core.exceptions import ClientAuthenticationError

        from eq_chatbot_core.providers.azure_provider import AzureProvider

        mock_client = MagicMock()
        error = ClientAuthenticationError(message="Invalid API key")
        mock_client.complete.side_effect = error
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="invalid-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        with pytest.raises(AuthenticationError):
            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
            )

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_overloaded_503(self, mock_credential, mock_client_class):
        """Test 503 overloaded error is properly mapped."""
        from azure.core.exceptions import HttpResponseError

        from eq_chatbot_core.providers.azure_provider import AzureProvider

        mock_client = MagicMock()
        error = HttpResponseError(message="Service overloaded")
        error.status_code = 503
        mock_client.complete.side_effect = error
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        with pytest.raises(OverloadedError):
            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
            )

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_context_length_400(self, mock_credential, mock_client_class):
        """Test context length error is properly mapped."""
        from azure.core.exceptions import HttpResponseError

        from eq_chatbot_core.providers.azure_provider import AzureProvider

        mock_client = MagicMock()
        error = HttpResponseError(message="Maximum context length exceeded")
        error.status_code = 400
        mock_client.complete.side_effect = error
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        with pytest.raises(ContextLengthError):
            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
            )

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_generic_error(self, mock_credential, mock_client_class):
        """Test generic errors are wrapped as ProviderError."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        mock_client = MagicMock()
        mock_client.complete.side_effect = Exception("Network error")
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        with pytest.raises(ProviderError):
            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
            )


# =============================================================================
# Context Manager Tests
# =============================================================================


@pytest.mark.unit
class TestAzureContextManager:
    """Test context manager functionality."""

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_close_client(self, mock_credential, mock_client_class):
        """Test close() properly closes the client."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/")
        provider._client = mock_client

        provider.close()

        mock_client.close.assert_called_once()
        assert provider._client is None

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_context_manager(self, mock_credential, mock_client_class):
        """Test context manager protocol."""
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with AzureProvider(api_key="test-key", base_url="https://test.ai.azure.com/") as provider:
            provider._client = mock_client
            assert provider is not None

        mock_client.close.assert_called()


# =============================================================================
# Factory Integration Tests
# =============================================================================


@pytest.mark.unit
class TestAzureFactoryIntegration:
    """Test integration with provider factory."""

    @patch("eq_chatbot_core.providers.azure_provider.ChatCompletionsClient")
    @patch("eq_chatbot_core.providers.azure_provider.AzureKeyCredential")
    def test_get_provider_returns_azure(self, mock_credential, mock_client_class):
        """Test get_provider returns AzureProvider."""
        from eq_chatbot_core.providers import get_provider
        from eq_chatbot_core.providers.azure_provider import AzureProvider

        provider = get_provider(
            "azure",
            api_key="test-azure-key",
            base_url="https://test.services.ai.azure.com/",
        )

        assert isinstance(provider, AzureProvider)
        assert provider.provider_name == "azure"
