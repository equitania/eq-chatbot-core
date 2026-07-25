"""
Unit tests for Mammouth AI provider.

All tests use mocked responses - no real API calls.
Tests cover 30+ model access through unified API with temperature constraints.
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
    """Create a mock Mammouth chat completion response."""
    return {
        "id": "chatcmpl-123",
        "model": "gpt-4o",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Test response from Mammouth",
                    "tool_calls": None,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
        },
    }


@pytest.fixture
def mock_models_response():
    """Create a mock Mammouth models list response."""
    return [
        {
            "id": "gpt-4o",
            "name": "GPT-4o",
            "max_input_tokens": 128000,
            "max_output_tokens": 16384,
            "input_price": 2.5,
            "output_price": 10.0,
        },
        {
            "id": "claude-sonnet-4-5",
            "name": "Claude Sonnet 4.5",
            "max_input_tokens": 200000,
            "max_output_tokens": 8192,
            "input_price": 3.0,
            "output_price": 15.0,
        },
        {
            "id": "o3",
            "name": "O3",
            "max_input_tokens": 200000,
            "max_output_tokens": 100000,
            "input_price": 10.0,
            "output_price": 40.0,
        },
        {
            "id": "gpt-4.1",
            "name": "GPT-4.1",
            "max_input_tokens": 1048576,
            "max_output_tokens": 32768,
            "input_price": 2.0,
            "output_price": 8.0,
        },
    ]


# =============================================================================
# Provider Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthProviderInit:
    """Test Mammouth provider initialization."""

    def test_basic_init(self):
        """Test basic provider initialization."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider.api_key == "mm-test-key"
            assert provider.base_url == "https://api.mammouth.ai/v1"

    def test_init_with_custom_base_url(self):
        """Test initialization with custom base URL."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            custom_url = "http://localhost:4000/v1"
            provider = MammouthProvider(api_key="mm-test-key", base_url=custom_url)
            assert provider.base_url == custom_url

    def test_init_with_timeout(self):
        """Test initialization with custom timeout."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key", timeout=120.0)
            assert provider.timeout == 120.0


# =============================================================================
# Provider Properties Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthProviderProperties:
    """Test provider properties."""

    def test_provider_name(self):
        """Test provider_name property."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider.provider_name == "mammouth"

    def test_default_model(self):
        """Test default model is GPT-4o."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider.default_model == "gpt-4o"


# =============================================================================
# Temperature Constraints Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthTemperatureConstraints:
    """Test temperature constraint handling - critical for newer OpenAI models."""

    def test_reasoning_model_no_temperature(self):
        """Test reasoning models (o1, o3, o4) return None for temperature."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("o1", 0.7) is None
            assert provider._clamp_temperature("o3", 0.5) is None
            assert provider._clamp_temperature("o4-mini", 0.3) is None

    def test_gpt5_temperature_passthrough(self):
        """Test GPT-5.x models pass through temperature (min=0.0)."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            # Temperature within range should pass through (min=0.0)
            assert provider._clamp_temperature("gpt-5.2-chat", 0.3) == 0.3
            assert provider._clamp_temperature("gpt-5.1-chat", 0.7) == 0.7
            assert provider._clamp_temperature("gpt-5-mini", 0.0) == 0.0

    def test_gpt41_temperature_passthrough(self):
        """Test GPT-4.1 models pass through temperature (min=0.0)."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("gpt-4.1", 0.5) == 0.5
            assert provider._clamp_temperature("gpt-4.1-mini", 0.7) == 0.7
            assert provider._clamp_temperature("gpt-4.1-nano", 0.0) == 0.0

    def test_gpt41_valid_temperature_passes_through(self):
        """Test GPT-4.1 models pass through valid temperatures."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("gpt-4.1", 1.0) == 1.0
            assert provider._clamp_temperature("gpt-4.1", 1.5) == 1.5
            assert provider._clamp_temperature("gpt-4.1", 2.0) == 2.0

    def test_legacy_model_passthrough(self):
        """Test legacy models (gpt-4o) pass through any valid temperature."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("gpt-4o", 0.0) == 0.0
            assert provider._clamp_temperature("gpt-4o", 0.7) == 0.7
            assert provider._clamp_temperature("gpt-4o", 2.0) == 2.0

    def test_claude_max_temperature_clamped(self):
        """Test Claude models clamp temperature to max 1.0."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("claude-sonnet-4-5", 1.5) == 1.0
            assert provider._clamp_temperature("claude-opus-4-5", 2.0) == 1.0
            # Valid range should pass through
            assert provider._clamp_temperature("claude-sonnet-4-5", 0.5) == 0.5

    def test_unknown_model_uses_defaults(self):
        """Test unknown models use default constraints (0.0-2.0)."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("some-unknown-model", 0.0) == 0.0
            assert provider._clamp_temperature("some-unknown-model", 1.5) == 1.5
            assert provider._clamp_temperature("some-unknown-model", 2.0) == 2.0

    def test_constraints_in_list_models(self, mock_models_response):
        """Test list_models returns temperature constraints per model."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_models_response
            mock_response.raise_for_status = MagicMock()
            mock_httpx.get.return_value = mock_response

            provider = MammouthProvider(api_key="mm-test-key")

            models = provider.list_models()

            # GPT-4o: supports temperature 0.0-2.0
            gpt4o = next(m for m in models if m["id"] == "gpt-4o")
            assert gpt4o["supports_temperature"] is True
            assert gpt4o["min_temperature"] == 0.0
            assert gpt4o["max_temperature"] == 2.0

            # O3: reasoning model, no temperature
            o3 = next(m for m in models if m["id"] == "o3")
            assert o3["supports_temperature"] is False
            assert o3["supports_reasoning"] is True

            # GPT-4.1: min temperature 0.0
            gpt41 = next(m for m in models if m["id"] == "gpt-4.1")
            assert gpt41["supports_temperature"] is True
            assert gpt41["min_temperature"] == 0.0
            assert gpt41["max_temperature"] == 2.0


# =============================================================================
# Reasoning Model Detection Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthReasoningModels:
    """Test reasoning model detection."""

    def test_o1_is_reasoning_model(self):
        """Test o1 models are detected as reasoning."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider._is_reasoning_model("o1") is True
            assert provider._is_reasoning_model("o1-mini") is True
            assert provider._is_reasoning_model("o1-preview") is True

    def test_o3_is_reasoning_model(self):
        """Test o3 models are detected as reasoning."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider._is_reasoning_model("o3") is True
            assert provider._is_reasoning_model("o3-mini") is True

    def test_o4_is_reasoning_model(self):
        """Test o4 models are detected as reasoning."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider._is_reasoning_model("o4-mini") is True

    def test_gpt_not_reasoning_model(self):
        """Test GPT models are not reasoning models."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider._is_reasoning_model("gpt-4o") is False
            assert provider._is_reasoning_model("gpt-4.1") is False
            assert provider._is_reasoning_model("gpt-5.2-chat") is False

    def test_claude_not_reasoning_model(self):
        """Test Claude models are not reasoning models."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider._is_reasoning_model("claude-sonnet-4-5") is False
            assert provider._is_reasoning_model("claude-opus-4-5") is False


# =============================================================================
# Chat Completion Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthChatCompletion:
    """Test chat completion functionality."""

    def test_simple_completion(self, mock_chat_response):
        """Test simple chat completion."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_chat_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = MammouthProvider(api_key="mm-test-key")
            provider._client = mock_client

            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
            )

            assert response.content == "Test response from Mammouth"
            assert response.model == "gpt-4o"
            assert response.input_tokens == 10
            assert response.output_tokens == 5

    def test_completion_temperature_clamped_for_gpt41(self, mock_chat_response):
        """Test temperature is clamped to 1.0 for GPT-4.1 models."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_chat_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = MammouthProvider(api_key="mm-test-key")
            provider._client = mock_client

            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4.1",
                temperature=0.3,  # Within range (min=0.0), passes through
            )

            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert payload.get("temperature") == 0.3

    def test_completion_no_temperature_for_reasoning(self, mock_chat_response):
        """Test reasoning models don't receive temperature."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_chat_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = MammouthProvider(api_key="mm-test-key")
            provider._client = mock_client

            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="o1",
                temperature=0.7,
            )

            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert "temperature" not in payload

    def test_completion_with_max_tokens(self, mock_chat_response):
        """Test completion with max_tokens."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_chat_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = MammouthProvider(api_key="mm-test-key")
            provider._client = mock_client

            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
                max_tokens=100,
            )

            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert payload.get("max_tokens") == 100

    def test_completion_with_tools(self, mock_chat_response):
        """Test completion with tools."""
        mock_chat_response = dict(mock_chat_response)
        mock_chat_response["choices"][0]["message"]["tool_calls"] = [
            {
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"location": "Paris"}',
                },
            }
        ]
        mock_chat_response["choices"][0]["finish_reason"] = "tool_calls"

        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_chat_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = MammouthProvider(api_key="mm-test-key")
            provider._client = mock_client

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
# Stream Completion Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthStreamCompletion:
    """Test streaming completion functionality."""

    def test_basic_streaming(self):
        """Test basic SSE streaming."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            # Simulate SSE stream lines
            sse_lines = [
                'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}',
                'data: {"choices":[{"delta":{"content":" world"},"finish_reason":null}]}',
                'data: {"choices":[{"delta":{"content":""},"finish_reason":"stop"}],'
                '"usage":{"prompt_tokens":5,"completion_tokens":2}}',
                "data: [DONE]",
            ]

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.iter_lines.return_value = iter(sse_lines)

            mock_client = MagicMock()
            mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
            mock_client.stream.return_value.__exit__ = MagicMock(return_value=False)
            mock_httpx.Client.return_value = mock_client

            provider = MammouthProvider(api_key="mm-test-key")
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

    def test_streaming_temperature_clamped(self):
        """Test streaming also clamps temperature for GPT-4.1 models."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            sse_lines = [
                'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}',
                "data: [DONE]",
            ]

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.iter_lines.return_value = iter(sse_lines)

            mock_client = MagicMock()
            mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
            mock_client.stream.return_value.__exit__ = MagicMock(return_value=False)
            mock_httpx.Client.return_value = mock_client

            provider = MammouthProvider(api_key="mm-test-key")
            provider._client = mock_client

            list(
                provider.stream_completion(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="gpt-4.1",
                    temperature=0.5,
                )
            )

            call_args = mock_client.stream.call_args
            payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert payload.get("temperature") == 0.5


# =============================================================================
# List Models Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthListModels:
    """Test list models functionality."""

    def test_list_models_returns_all(self, mock_models_response):
        """Test list_models returns all available models."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_models_response
            mock_response.raise_for_status = MagicMock()
            mock_httpx.get.return_value = mock_response

            provider = MammouthProvider(api_key="mm-test-key")

            models = provider.list_models()

            assert len(models) == 4
            model_ids = [m["id"] for m in models]
            assert "gpt-4o" in model_ids
            assert "claude-sonnet-4-5" in model_ids
            assert "o3" in model_ids
            assert "gpt-4.1" in model_ids

    def test_list_models_includes_metadata(self, mock_models_response):
        """Test list_models includes model metadata."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_models_response
            mock_response.raise_for_status = MagicMock()
            mock_httpx.get.return_value = mock_response

            provider = MammouthProvider(api_key="mm-test-key")

            models = provider.list_models()

            gpt4o = next(m for m in models if m["id"] == "gpt-4o")
            assert gpt4o["name"] == "GPT-4o"
            assert gpt4o["context_length"] == 128000
            assert gpt4o["provider"] == "mammouth"
            assert gpt4o["max_output_tokens"] == 16384

    def test_list_models_includes_pricing(self, mock_models_response):
        """Test list_models includes pricing information."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_models_response
            mock_response.raise_for_status = MagicMock()
            mock_httpx.get.return_value = mock_response

            provider = MammouthProvider(api_key="mm-test-key")

            models = provider.list_models()

            gpt4o = next(m for m in models if m["id"] == "gpt-4o")
            assert gpt4o["input_cost_per_million"] == 2.5
            assert gpt4o["output_cost_per_million"] == 10.0

    def test_list_models_sorted(self, mock_models_response):
        """Test list_models returns sorted by ID."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_models_response
            mock_response.raise_for_status = MagicMock()
            mock_httpx.get.return_value = mock_response

            provider = MammouthProvider(api_key="mm-test-key")

            models = provider.list_models()

            model_ids = [m["id"] for m in models]
            assert model_ids == sorted(model_ids)


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthErrorHandling:
    """Test error handling and mapping."""

    def test_error_scrubs_secret(self):
        """Provider errors must not leak API keys into the message."""
        from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

        provider = MammouthProvider(api_key="mm-test-key")
        err = provider._handle_error(Exception("500 error for key sk-leakedsecret12345"))
        assert "sk-leakedsecret12345" not in str(err)

    def test_rate_limit_error(self):
        """Test rate limit error is properly mapped."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.json.return_value = {"error": {"message": "Rate limit exceeded"}}

            import httpx

            mock_httpx.HTTPStatusError = httpx.HTTPStatusError

            mock_error = httpx.HTTPStatusError(
                "Rate limit exceeded",
                request=MagicMock(),
                response=mock_response,
            )

            mock_client = MagicMock()
            mock_client.post.side_effect = mock_error
            mock_httpx.Client.return_value = mock_client

            provider = MammouthProvider(api_key="mm-test-key")
            provider._client = mock_client

            with pytest.raises(RateLimitError):
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello"}],
                    model="gpt-4o",
                )

    def test_authentication_error(self):
        """Test authentication error is properly mapped."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.json.return_value = {"error": {"message": "Invalid API key"}}

            import httpx

            mock_httpx.HTTPStatusError = httpx.HTTPStatusError

            mock_error = httpx.HTTPStatusError(
                "Unauthorized",
                request=MagicMock(),
                response=mock_response,
            )

            mock_client = MagicMock()
            mock_client.post.side_effect = mock_error
            mock_httpx.Client.return_value = mock_client

            provider = MammouthProvider(api_key="invalid-key")
            provider._client = mock_client

            with pytest.raises(AuthenticationError):
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello"}],
                    model="gpt-4o",
                )

    def test_overloaded_error(self):
        """Test 503 overloaded error is properly mapped."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.json.return_value = {"error": {"message": "Service overloaded"}}

            import httpx

            mock_httpx.HTTPStatusError = httpx.HTTPStatusError

            mock_error = httpx.HTTPStatusError(
                "Service Unavailable",
                request=MagicMock(),
                response=mock_response,
            )

            mock_client = MagicMock()
            mock_client.post.side_effect = mock_error
            mock_httpx.Client.return_value = mock_client

            provider = MammouthProvider(api_key="mm-test-key")
            provider._client = mock_client

            with pytest.raises(OverloadedError):
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello"}],
                    model="gpt-4o",
                )

    def test_context_length_error(self):
        """Test context length error is properly mapped."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.json.return_value = {"error": {"message": "Maximum context length exceeded"}}

            import httpx

            mock_httpx.HTTPStatusError = httpx.HTTPStatusError

            mock_error = httpx.HTTPStatusError(
                "Bad Request",
                request=MagicMock(),
                response=mock_response,
            )

            mock_client = MagicMock()
            mock_client.post.side_effect = mock_error
            mock_httpx.Client.return_value = mock_client

            provider = MammouthProvider(api_key="mm-test-key")
            provider._client = mock_client

            with pytest.raises(ContextLengthError):
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello"}],
                    model="gpt-4o",
                )

    def test_generic_error(self):
        """Test generic errors are wrapped as ProviderError."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx.Client") as mock_client_class:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_client = MagicMock()
            mock_client.post.side_effect = Exception("Network error")
            mock_client_class.return_value = mock_client

            provider = MammouthProvider(api_key="mm-test-key")

            with pytest.raises(ProviderError):
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello"}],
                    model="gpt-4o",
                )


# =============================================================================
# Context Manager Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthContextManager:
    """Test context manager functionality."""

    def test_close_client(self):
        """Test close() properly closes the HTTP client."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_client = MagicMock()
            mock_httpx.Client.return_value = mock_client

            provider = MammouthProvider(api_key="mm-test-key")
            provider._client = mock_client

            provider.close()

            mock_client.close.assert_called_once()
            assert provider._client is None

    def test_context_manager(self):
        """Test context manager protocol."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx") as mock_httpx:
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            mock_client = MagicMock()
            mock_httpx.Client.return_value = mock_client

            with MammouthProvider(api_key="mm-test-key") as provider:
                provider._client = mock_client
                assert provider is not None

            mock_client.close.assert_called()


# =============================================================================
# Factory Integration Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthFactoryIntegration:
    """Test integration with provider factory."""

    def test_get_provider_returns_mammouth(self):
        """Test get_provider returns MammouthProvider."""
        with patch("eq_chatbot_core.providers.mammouth_provider.httpx"):
            from eq_chatbot_core.providers import get_provider
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = get_provider("mammouth", api_key="mm-test-key")

            assert isinstance(provider, MammouthProvider)
            assert provider.provider_name == "mammouth"


# =============================================================================
# SSRF Guard (v1.17.2)
# =============================================================================


@pytest.mark.unit
class TestMammouthSSRFGuard:
    """A caller-supplied base_url must pass validate_url; the default is exempt."""

    def test_cloud_metadata_endpoint_rejected(self):
        from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

        with pytest.raises(ValueError):
            MammouthProvider(api_key="mm-test-key", base_url="http://169.254.169.254/v1")

    def test_non_http_scheme_rejected(self):
        from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

        with pytest.raises(ValueError):
            MammouthProvider(api_key="mm-test-key", base_url="ftp://localhost/v1")

    def test_localhost_base_url_accepted(self):
        from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

        provider = MammouthProvider(api_key="mm-test-key", base_url="http://localhost:4000/v1")
        assert provider.base_url == "http://localhost:4000/v1"

    def test_default_base_url_skips_validation(self):
        from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

        provider = MammouthProvider(api_key="mm-test-key")
        assert provider.base_url == MammouthProvider.DEFAULT_BASE_URL
