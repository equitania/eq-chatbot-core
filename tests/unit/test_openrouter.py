"""
Unit tests for OpenRouter provider.

All tests use mocked responses - no real API calls.
Tests cover 400+ model access through unified API.
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
def mock_chat_response():
    """Create a mock OpenRouter chat completion response."""
    return {
        "id": "gen-123",
        "model": "openai/gpt-4o",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Test response from OpenRouter",
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
    """Create a mock OpenRouter models list response."""
    return {
        "data": [
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4o",
                "context_length": 128000,
                "supported_parameters": ["temperature", "max_tokens", "tools"],
                "input_modalities": ["text", "image"],
                "pricing": {"prompt": "0.000005", "completion": "0.000015"},
            },
            {
                "id": "anthropic/claude-3.5-sonnet",
                "name": "Claude 3.5 Sonnet",
                "context_length": 200000,
                "supported_parameters": ["temperature", "max_tokens"],
                "input_modalities": ["text", "image"],
                "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            },
            {
                "id": "openai/o1",
                "name": "O1",
                "context_length": 200000,
                "supported_parameters": ["max_tokens"],  # No temperature
                "input_modalities": ["text"],
                "pricing": {"prompt": "0.000015", "completion": "0.00006"},
            },
            {
                "id": "meta-llama/llama-3.1-70b-instruct",
                "name": "Llama 3.1 70B",
                "context_length": 131072,
                "supported_parameters": ["temperature", "max_tokens"],
                "input_modalities": ["text"],
                "pricing": {"prompt": "0.00000035", "completion": "0.0000004"},
            },
        ]
    }


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx2.Client."""
    mock = MagicMock()
    return mock


# =============================================================================
# Provider Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestOpenRouterProviderInit:
    """Test OpenRouter provider initialization."""

    def test_basic_init(self):
        """Test basic provider initialization."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            assert provider.api_key == "sk-or-test-key"
            assert provider.base_url == "https://openrouter.ai/api/v1"

    def test_init_with_custom_base_url(self):
        """Test initialization with custom base URL."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            custom_url = "http://localhost:4000/v1"
            provider = OpenRouterProvider(api_key="sk-or-test-key", base_url=custom_url)
            assert provider.base_url == custom_url

    def test_init_with_site_info(self):
        """Test initialization with site URL and name for rankings."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(
                api_key="sk-or-test-key",
                site_url="https://example.com",
                site_name="My App",
            )
            assert provider.site_url == "https://example.com"
            assert provider.site_name == "My App"

    def test_init_with_timeout(self):
        """Test initialization with custom timeout."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key", timeout=120.0)
            assert provider.timeout == 120.0


# =============================================================================
# Provider Properties Tests
# =============================================================================


@pytest.mark.unit
class TestOpenRouterProviderProperties:
    """Test provider properties."""

    def test_provider_name(self):
        """Test provider_name property."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            assert provider.provider_name == "openrouter"

    def test_default_model(self):
        """Test default model is OpenAI GPT-4o via OpenRouter."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            assert provider.default_model == "openai/gpt-4o"


# =============================================================================
# Reasoning Model Detection Tests
# =============================================================================


@pytest.mark.unit
class TestOpenRouterReasoningModels:
    """Test reasoning model detection."""

    def test_o1_is_reasoning_model(self):
        """Test o1 models are detected as reasoning."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            assert provider._is_reasoning_model("openai/o1") is True
            assert provider._is_reasoning_model("openai/o1-mini") is True
            assert provider._is_reasoning_model("openai/o1-preview") is True

    def test_o3_is_reasoning_model(self):
        """Test o3 models are detected as reasoning."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            assert provider._is_reasoning_model("openai/o3") is True
            assert provider._is_reasoning_model("openai/o3-mini") is True

    def test_o4_is_reasoning_model(self):
        """Test o4 models are detected as reasoning."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            assert provider._is_reasoning_model("openai/o4-mini") is True

    def test_gpt_not_reasoning_model(self):
        """Test GPT models are not reasoning models."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            assert provider._is_reasoning_model("openai/gpt-4o") is False
            assert provider._is_reasoning_model("openai/gpt-4-turbo") is False

    def test_claude_not_reasoning_model(self):
        """Test Claude models are not reasoning models."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            assert provider._is_reasoning_model("anthropic/claude-3.5-sonnet") is False

    def test_llama_not_reasoning_model(self):
        """Test Llama models are not reasoning models."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            assert provider._is_reasoning_model("meta-llama/llama-3.1-70b-instruct") is False


# =============================================================================
# Chat Completion Tests
# =============================================================================


@pytest.mark.unit
class TestOpenRouterChatCompletion:
    """Test chat completion functionality."""

    def test_simple_completion(self, mock_chat_response):
        """Test simple chat completion."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_chat_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="openai/gpt-4o",
            )

            assert response.content == "Test response from OpenRouter"
            assert response.model == "openai/gpt-4o"
            assert response.input_tokens == 10
            assert response.output_tokens == 5

    def test_completion_with_temperature(self, mock_chat_response):
        """Test completion includes temperature for non-reasoning models."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_chat_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="openai/gpt-4o",
                temperature=0.7,
            )

            # Check that temperature was included in payload
            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert payload.get("temperature") == 0.7

    def test_completion_without_temperature_for_reasoning(self, mock_chat_response):
        """Test reasoning models don't receive temperature."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_chat_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="openai/o1",
                temperature=0.7,  # Should be ignored for reasoning models
            )

            # Check that temperature was NOT included in payload
            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert "temperature" not in payload

    def test_completion_with_max_tokens(self, mock_chat_response):
        """Test completion with max_tokens."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_chat_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="openai/gpt-4o",
                max_tokens=100,
            )

            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert payload.get("max_tokens") == 100

    def test_completion_with_tools(self, mock_chat_response):
        """Test completion with tools."""
        # Modify response to include tool calls
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

        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_chat_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            tools = [{"type": "function", "function": {"name": "get_weather"}}]
            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Weather in Paris?"}],
                model="openai/gpt-4o",
                tools=tools,
            )

            assert response.tool_calls is not None
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0]["function"]["name"] == "get_weather"


# =============================================================================
# Stream Completion Tests
# =============================================================================


def _build_stream_response(lines: list[str]) -> MagicMock:
    """
    Build a mock response object that mimics httpx2.Client.stream(...) context manager.

    The provider uses `with self.client.stream("POST", ...) as response:` and then
    iterates `response.iter_lines()`. We mock both __enter__/__exit__ and iter_lines.
    """
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_lines.return_value = iter(lines)

    # client.stream(...) returns a context manager; mock it.
    stream_cm = MagicMock()
    stream_cm.__enter__ = MagicMock(return_value=mock_response)
    stream_cm.__exit__ = MagicMock(return_value=False)
    return stream_cm


@pytest.mark.unit
class TestOpenRouterStreamCompletion:
    """Test SSE streaming chat completion."""

    def test_simple_stream(self):
        """Test that streaming yields content chunks and a terminal chunk."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            sse_lines = [
                'data: {"choices":[{"delta":{"content":"Hel"}}]}',
                'data: {"choices":[{"delta":{"content":"lo"}}]}',
                'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
                '"usage":{"prompt_tokens":3,"completion_tokens":2}}',
                "data: [DONE]",
            ]
            stream_cm = _build_stream_response(sse_lines)

            mock_client = MagicMock()
            mock_client.stream.return_value = stream_cm
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            chunks = list(
                provider.stream_completion(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="openai/gpt-4o",
                )
            )

            assert len(chunks) == 3
            # Concatenated content
            full = "".join(c.content for c in chunks if c.content)
            assert full == "Hello"

    def test_stream_skips_sse_comment_lines(self):
        """SSE comment / keep-alive lines (': OPENROUTER PROCESSING') must be ignored,
        not parsed as JSON — no 'Failed to parse SSE chunk' warning, content intact."""
        with (
            patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx,
            patch("eq_chatbot_core.providers.openrouter_provider._logger") as mock_logger,
        ):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            sse_lines = [
                ": OPENROUTER PROCESSING",
                'data: {"choices":[{"delta":{"content":"Hel"}}]}',
                ": OPENROUTER PROCESSING",
                'data: {"choices":[{"delta":{"content":"lo"}}]}',
                'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
                '"usage":{"prompt_tokens":3,"completion_tokens":2}}',
                "data: [DONE]",
            ]
            stream_cm = _build_stream_response(sse_lines)

            mock_client = MagicMock()
            mock_client.stream.return_value = stream_cm
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            chunks = list(
                provider.stream_completion(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="openai/gpt-4o",
                )
            )

            # Comment lines skipped → content still parses, no spurious warning.
            full = "".join(c.content for c in chunks if c.content)
            assert full == "Hello"
            mock_logger.warning.assert_not_called()

    def test_stream_finish_reason_propagates(self):
        """Final chunk must carry finish_reason and is_final=True."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            sse_lines = [
                'data: {"choices":[{"delta":{"content":"x"}}]}',
                'data: {"choices":[{"delta":{},"finish_reason":"length"}],'
                '"usage":{"prompt_tokens":1,"completion_tokens":1}}',
                "data: [DONE]",
            ]
            stream_cm = _build_stream_response(sse_lines)

            mock_client = MagicMock()
            mock_client.stream.return_value = stream_cm
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            chunks = list(
                provider.stream_completion(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="openai/gpt-4o",
                    max_tokens=1,
                )
            )

            final = chunks[-1]
            assert final.is_final is True
            assert final.finish_reason == "length"
            assert final.input_tokens == 1
            assert final.output_tokens == 1

    def test_stream_accumulates_tool_calls(self):
        """Tool-call deltas across chunks must be accumulated into the final chunk."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            sse_lines = [
                # First tool-call delta: id + name
                'data: {"choices":[{"delta":{"tool_calls":['
                '{"index":0,"id":"call_abc","function":{"name":"get_weather","arguments":""}}]}}]}',
                # Second delta: arguments fragment 1
                'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"loc\\":"}}]}}]}',
                # Third delta: arguments fragment 2
                'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"Paris\\"}"}}]}}]}',
                # Final chunk
                'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}],'
                '"usage":{"prompt_tokens":5,"completion_tokens":7}}',
                "data: [DONE]",
            ]
            stream_cm = _build_stream_response(sse_lines)

            mock_client = MagicMock()
            mock_client.stream.return_value = stream_cm
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            chunks = list(
                provider.stream_completion(
                    messages=[{"role": "user", "content": "Weather?"}],
                    model="openai/gpt-4o",
                    tools=[{"type": "function", "function": {"name": "get_weather"}}],
                )
            )

            final = chunks[-1]
            assert final.is_final is True
            assert final.tool_calls is not None
            assert len(final.tool_calls) == 1
            tc = final.tool_calls[0]
            assert tc["id"] == "call_abc"
            assert tc["function"]["name"] == "get_weather"
            assert tc["function"]["arguments"] == '{"loc":"Paris"}'


# =============================================================================
# List Models Tests
# =============================================================================


@pytest.mark.unit
class TestOpenRouterListModels:
    """Test list models functionality."""

    def test_list_models_returns_all(self, mock_models_response):
        """Test list_models returns all available models."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_models_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            models = provider.list_models()

            assert len(models) == 4
            model_ids = [m["id"] for m in models]
            assert "openai/gpt-4o" in model_ids
            assert "anthropic/claude-3.5-sonnet" in model_ids
            assert "openai/o1" in model_ids

    def test_list_models_includes_metadata(self, mock_models_response):
        """Test list_models includes model metadata."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_models_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            models = provider.list_models()

            # Find GPT-4o
            gpt4o = next(m for m in models if m["id"] == "openai/gpt-4o")
            assert gpt4o["name"] == "GPT-4o"
            assert gpt4o["context_length"] == 128000
            assert gpt4o["provider"] == "openrouter"

    def test_list_models_includes_constraints(self, mock_models_response):
        """Test list_models includes temperature and capability constraints."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_models_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            models = provider.list_models()

            # GPT-4o should support temperature
            gpt4o = next(m for m in models if m["id"] == "openai/gpt-4o")
            assert gpt4o["supports_temperature"] is True
            assert gpt4o["supports_vision"] is True  # Has image in input_modalities

            # O1 should NOT support temperature (reasoning model)
            o1 = next(m for m in models if m["id"] == "openai/o1")
            assert o1["supports_temperature"] is False
            assert o1["supports_vision"] is False

    def test_list_models_includes_pricing(self, mock_models_response):
        """Test list_models includes pricing information."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_response = MagicMock()
            mock_response.json.return_value = mock_models_response
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            models = provider.list_models()

            gpt4o = next(m for m in models if m["id"] == "openai/gpt-4o")
            assert gpt4o["input_cost_per_token"] == 0.000005
            assert gpt4o["output_cost_per_token"] == 0.000015


# =============================================================================
# Model Constraints Tests
# =============================================================================


@pytest.mark.unit
class TestOpenRouterModelConstraints:
    """Test model constraints extraction."""

    def test_regular_model_constraints(self):
        """Test regular model has temperature support."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")

            model_data = {
                "id": "openai/gpt-4o",
                "supported_parameters": ["temperature", "max_tokens"],
                "input_modalities": ["text", "image"],
            }

            constraints = provider._get_model_constraints(model_data)

            assert constraints["supports_temperature"] is True
            assert constraints["supports_vision"] is True
            assert constraints["min_temperature"] == 0.0
            assert constraints["max_temperature"] == 2.0

    def test_reasoning_model_constraints(self):
        """Test reasoning model has no temperature support."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")

            model_data = {
                "id": "openai/o1",
                "supported_parameters": ["max_tokens"],
                "input_modalities": ["text"],
            }

            constraints = provider._get_model_constraints(model_data)

            assert constraints["supports_temperature"] is False
            assert constraints["supports_reasoning"] is True
            assert constraints["min_temperature"] == 1.0
            assert constraints["max_temperature"] == 1.0

    def test_pricing_extraction(self):
        """Test pricing extraction from model data."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")

            model_data = {
                "pricing": {
                    "prompt": "0.000005",
                    "completion": "0.000015",
                    "image": "0.001",
                }
            }

            pricing = provider._extract_pricing(model_data)

            assert pricing["input_cost_per_token"] == 0.000005
            assert pricing["output_cost_per_token"] == 0.000015
            assert pricing["image_cost_per_token"] == 0.001

    def test_pricing_with_missing_values(self):
        """Test pricing extraction handles missing values."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider(api_key="sk-or-test-key")

            model_data = {"pricing": {}}

            pricing = provider._extract_pricing(model_data)

            assert pricing["input_cost_per_token"] is None
            assert pricing["output_cost_per_token"] is None


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestOpenRouterErrorHandling:
    """Test error handling and mapping."""

    def test_error_scrubs_secret(self):
        """Provider errors must not leak API keys into the message."""
        from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider(api_key="sk-or-test")
        err = provider._handle_error(Exception("500 error for key sk-leakedsecret12345"))
        assert "sk-leakedsecret12345" not in str(err)

    def test_rate_limit_error(self):
        """Test rate limit error is properly mapped."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            # Create mock HTTP 429 error
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.json.return_value = {"error": {"message": "Rate limit exceeded"}}

            import httpx2

            mock_httpx.HTTPStatusError = httpx2.HTTPStatusError

            mock_error = httpx2.HTTPStatusError(
                "Rate limit exceeded",
                request=MagicMock(),
                response=mock_response,
            )

            mock_client = MagicMock()
            mock_client.post.side_effect = mock_error
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            with pytest.raises(RateLimitError):
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello"}],
                    model="openai/gpt-4o",
                )

    def test_authentication_error(self):
        """Test authentication error is properly mapped."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.json.return_value = {"error": {"message": "Invalid API key"}}

            import httpx2

            mock_httpx.HTTPStatusError = httpx2.HTTPStatusError

            mock_error = httpx2.HTTPStatusError(
                "Unauthorized",
                request=MagicMock(),
                response=mock_response,
            )

            mock_client = MagicMock()
            mock_client.post.side_effect = mock_error
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="invalid-key")
            provider._client = mock_client

            with pytest.raises(AuthenticationError):
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello"}],
                    model="openai/gpt-4o",
                )

    def test_context_length_error(self):
        """HTTP 400 with 'context' in message must map to ContextLengthError."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": {"message": "This model's maximum context length is 8192 tokens."}
            }

            import httpx2

            mock_httpx.HTTPStatusError = httpx2.HTTPStatusError

            mock_error = httpx2.HTTPStatusError(
                "Bad Request",
                request=MagicMock(),
                response=mock_response,
            )

            mock_client = MagicMock()
            mock_client.post.side_effect = mock_error
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            with pytest.raises(ContextLengthError):
                provider.chat_completion(
                    messages=[{"role": "user", "content": "x" * 100000}],
                    model="openai/gpt-4o",
                )

    def test_generic_error(self):
        """Test generic errors are wrapped as ProviderError."""
        # Only patch httpx2.Client, not the entire httpx module
        # This preserves httpx2.HTTPStatusError as a real exception class
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2.Client") as mock_client_class:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_client = MagicMock()
            mock_client.post.side_effect = Exception("Network error")
            mock_client_class.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")

            with pytest.raises(ProviderError):
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello"}],
                    model="openai/gpt-4o",
                )


# =============================================================================
# Context Manager Tests
# =============================================================================


@pytest.mark.unit
class TestOpenRouterContextManager:
    """Test context manager functionality."""

    def test_close_client(self):
        """Test close() properly closes the HTTP client."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_client = MagicMock()
            mock_httpx.Client.return_value = mock_client

            provider = OpenRouterProvider(api_key="sk-or-test-key")
            provider._client = mock_client

            provider.close()

            mock_client.close.assert_called_once()
            assert provider._client is None

    def test_context_manager(self):
        """Test context manager protocol."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2") as mock_httpx:
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            mock_client = MagicMock()
            mock_httpx.Client.return_value = mock_client

            with OpenRouterProvider(api_key="sk-or-test-key") as provider:
                provider._client = mock_client
                assert provider is not None

            # After exiting context, close should be called
            mock_client.close.assert_called()


# =============================================================================
# Factory Integration Tests
# =============================================================================


@pytest.mark.unit
class TestOpenRouterFactoryIntegration:
    """Test integration with provider factory."""

    def test_get_provider_returns_openrouter(self):
        """Test get_provider returns OpenRouterProvider."""
        with patch("eq_chatbot_core.providers.openrouter_provider.httpx2"):
            from eq_chatbot_core.providers import get_provider
            from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

            provider = get_provider("openrouter", api_key="sk-or-test-key")

            assert isinstance(provider, OpenRouterProvider)
            assert provider.provider_name == "openrouter"


# =============================================================================
# SSRF Guard (v1.17.2)
# =============================================================================


@pytest.mark.unit
class TestOpenRouterSSRFGuard:
    """A caller-supplied base_url must pass validate_url; the default is exempt."""

    def test_cloud_metadata_endpoint_rejected(self):
        from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

        with pytest.raises(ValueError):
            OpenRouterProvider(api_key="sk-or-test-key", base_url="http://169.254.169.254/v1")

    def test_non_http_scheme_rejected(self):
        from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

        with pytest.raises(ValueError):
            OpenRouterProvider(api_key="sk-or-test-key", base_url="ftp://localhost/v1")

    def test_localhost_base_url_accepted(self):
        from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider(api_key="sk-or-test-key", base_url="http://localhost:4000/v1")
        assert provider.base_url == "http://localhost:4000/v1"

    def test_default_base_url_skips_validation(self):
        from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider(api_key="sk-or-test-key")
        assert provider.base_url == OpenRouterProvider.DEFAULT_BASE_URL
