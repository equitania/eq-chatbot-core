"""
Unit tests for LocalLLMProvider.

Tests the unified provider for local LLM servers (LM Studio, Ollama)
using mocked HTTP responses.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    ContextLengthError,
    ProviderError,
    RateLimitError,
)
from eq_chatbot_core.providers.local_provider import LocalLLMProvider


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_chat_response():
    """Mock successful chat completion response."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "phi-2",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 12,
            "total_tokens": 22,
        },
    }


@pytest.fixture
def mock_models_response():
    """Mock models list response."""
    return {
        "object": "list",
        "data": [
            {
                "id": "phi-2",
                "object": "model",
                "owned_by": "local",
                "created": 1677652288,
            },
            {
                "id": "mistral-7b",
                "object": "model",
                "owned_by": "local",
                "context_length": 8192,
            },
        ],
    }


# =============================================================================
# Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestLocalLLMProviderInit:
    """Test LocalLLMProvider initialization."""

    def test_default_initialization(self):
        """Test provider initializes with default values."""
        provider = LocalLLMProvider()

        assert provider.api_key == "not-used"
        assert provider.base_url == LocalLLMProvider.LM_STUDIO_URL
        assert provider.timeout == LocalLLMProvider.DEFAULT_TIMEOUT
        assert provider.provider_name == "local"
        assert provider.default_model == "local-model"

    def test_custom_base_url(self):
        """Test provider with custom base URL."""
        custom_url = "http://custom-server:8080/v1"
        provider = LocalLLMProvider(base_url=custom_url)

        assert provider.base_url == custom_url

    def test_ollama_url(self):
        """Test provider configured for Ollama."""
        provider = LocalLLMProvider(base_url=LocalLLMProvider.OLLAMA_URL)

        assert provider.base_url == "http://localhost:11434/v1"
        assert provider._get_server_type() == "ollama"

    def test_lm_studio_url(self):
        """Test provider configured for LM Studio."""
        provider = LocalLLMProvider(base_url=LocalLLMProvider.LM_STUDIO_URL)

        assert provider.base_url == "http://localhost:1234/v1"
        assert provider._get_server_type() == "lm_studio"

    def test_custom_timeout(self):
        """Test provider with custom timeout."""
        provider = LocalLLMProvider(timeout=300.0)

        assert provider.timeout == 300.0

    def test_custom_api_key(self):
        """Test provider with custom API key (some servers may require it)."""
        provider = LocalLLMProvider(api_key="custom-key")

        assert provider.api_key == "custom-key"


# =============================================================================
# Chat Completion Tests
# =============================================================================


@pytest.mark.unit
class TestLocalLLMProviderChatCompletion:
    """Test chat completion functionality."""

    def test_chat_completion_success(self, mock_chat_response):
        """Test successful chat completion."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_chat_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Hello!"}],
            )

            assert response.content == "Hello! How can I help you today?"
            assert response.model == "phi-2"
            assert response.input_tokens == 10
            assert response.output_tokens == 12
            assert response.finish_reason == "stop"

    def test_chat_completion_with_model(self, mock_chat_response):
        """Test chat completion with specific model."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_chat_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello!"}],
                model="mistral-7b",
            )

            # Verify model was passed in payload
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["model"] == "mistral-7b"

    def test_chat_completion_with_temperature(self, mock_chat_response):
        """Test chat completion with custom temperature."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_chat_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello!"}],
                temperature=0.5,
            )

            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["temperature"] == 0.5

    def test_chat_completion_with_max_tokens(self, mock_chat_response):
        """Test chat completion with max_tokens."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_chat_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            provider.chat_completion(
                messages=[{"role": "user", "content": "Hello!"}],
                max_tokens=100,
            )

            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["max_tokens"] == 100

    def test_chat_completion_no_usage(self):
        """Test chat completion when server doesn't return usage stats."""
        response_data = {
            "id": "test",
            "model": "local-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            # No usage field
        }

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Hello!"}],
            )

            assert response.content == "Hello!"
            assert response.input_tokens == 0
            assert response.output_tokens == 0

    def test_chat_completion_with_tool_calls(self):
        """Test chat completion with tool calls in response."""
        response_data = {
            "id": "test",
            "model": "local-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"location": "Berlin"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            response = provider.chat_completion(
                messages=[{"role": "user", "content": "What's the weather?"}],
            )

            assert len(response.tool_calls) == 1
            assert response.tool_calls[0]["function"]["name"] == "get_weather"


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestLocalLLMProviderErrors:
    """Test error handling."""

    def test_connection_error(self):
        """Test handling of connection errors."""
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            with pytest.raises(ProviderError) as exc_info:
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello!"}],
                )

            assert "Cannot connect to local LLM server" in str(exc_info.value)

    def test_timeout_error(self):
        """Test handling of timeout errors."""
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timeout")

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            with pytest.raises(ProviderError) as exc_info:
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello!"}],
                )

            assert "timed out" in str(exc_info.value)

    def test_authentication_error(self):
        """Test handling of 401 authentication errors."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401

        mock_client = MagicMock()
        error = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_response)
        mock_client.post.side_effect = error

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            with pytest.raises(AuthenticationError) as exc_info:
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello!"}],
                )

            assert exc_info.value.status_code == 401

    def test_rate_limit_error(self):
        """Test handling of 429 rate limit errors."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "60"}

        mock_client = MagicMock()
        error = httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=mock_response)
        mock_client.post.side_effect = error

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            with pytest.raises(RateLimitError) as exc_info:
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello!"}],
                )

            assert exc_info.value.status_code == 429
            assert exc_info.value.retry_after == 60

    def test_context_length_error(self):
        """Test handling of context length exceeded errors."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400

        mock_client = MagicMock()
        error = httpx.HTTPStatusError(
            "context length exceeded: maximum 4096 tokens",
            request=MagicMock(),
            response=mock_response,
        )
        mock_client.post.side_effect = error

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            with pytest.raises(ContextLengthError) as exc_info:
                provider.chat_completion(
                    messages=[{"role": "user", "content": "Hello!"}],
                )

            assert exc_info.value.status_code == 400


# =============================================================================
# Streaming Tests
# =============================================================================


@pytest.mark.unit
class TestLocalLLMProviderStreaming:
    """Test streaming completion functionality."""

    def test_stream_completion_success(self):
        """Test successful streaming completion."""
        # Mock SSE response lines
        sse_lines = [
            'data: {"id":"1","choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"id":"1","choices":[{"delta":{"content":" world"}}]}',
            'data: {"id":"1","choices":[{"delta":{},"finish_reason":"stop"}]}',
            "data: [DONE]",
        ]

        mock_stream_response = MagicMock()
        mock_stream_response.iter_lines.return_value = iter(sse_lines)
        mock_stream_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.stream.return_value.__enter__.return_value = mock_stream_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            chunks = list(
                provider.stream_completion(
                    messages=[{"role": "user", "content": "Hello!"}],
                )
            )

            # Should have 4 chunks: "Hello", " world", finish, and final [DONE]
            assert len(chunks) >= 3
            assert chunks[0].content == "Hello"
            assert chunks[1].content == " world"

    def test_stream_completion_handles_done_marker(self):
        """Test that [DONE] marker properly terminates stream."""
        sse_lines = [
            'data: {"id":"1","choices":[{"delta":{"content":"Test"}}]}',
            "data: [DONE]",
        ]

        mock_stream_response = MagicMock()
        mock_stream_response.iter_lines.return_value = iter(sse_lines)
        mock_stream_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.stream.return_value.__enter__.return_value = mock_stream_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            chunks = list(
                provider.stream_completion(
                    messages=[{"role": "user", "content": "Hello!"}],
                )
            )

            # Last chunk should be marked as final
            final_chunks = [c for c in chunks if c.is_final]
            assert len(final_chunks) >= 1

    def test_stream_completion_skips_empty_lines(self):
        """Test that empty lines are skipped in stream."""
        sse_lines = [
            "",
            'data: {"id":"1","choices":[{"delta":{"content":"Test"}}]}',
            "",
            "data: [DONE]",
        ]

        mock_stream_response = MagicMock()
        mock_stream_response.iter_lines.return_value = iter(sse_lines)
        mock_stream_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.stream.return_value.__enter__.return_value = mock_stream_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            chunks = list(
                provider.stream_completion(
                    messages=[{"role": "user", "content": "Hello!"}],
                )
            )

            content_chunks = [c for c in chunks if c.content]
            assert len(content_chunks) >= 1
            assert content_chunks[0].content == "Test"

    def test_stream_completion_connection_error(self):
        """Test streaming handles connection errors."""
        mock_client = MagicMock()
        mock_client.stream.side_effect = httpx.ConnectError("Connection refused")

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            with pytest.raises(ProviderError) as exc_info:
                list(
                    provider.stream_completion(
                        messages=[{"role": "user", "content": "Hello!"}],
                    )
                )

            assert "Cannot connect" in str(exc_info.value)


# =============================================================================
# List Models Tests
# =============================================================================


@pytest.mark.unit
class TestLocalLLMProviderListModels:
    """Test model listing functionality."""

    def test_list_models_success(self, mock_models_response):
        """Test successful model listing."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_models_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            models = provider.list_models()

            assert len(models) == 2
            assert models[0]["id"] == "phi-2"
            assert models[1]["id"] == "mistral-7b"

    def test_list_models_with_context_length(self, mock_models_response):
        """Test model listing includes context length when available."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_models_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            models = provider.list_models()

            # Second model has context_length
            assert models[1]["context_length"] == 8192

    def test_list_models_connection_error(self):
        """Test model listing handles connection errors."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            with pytest.raises(ProviderError) as exc_info:
                provider.list_models()

            assert "Cannot connect" in str(exc_info.value)

    def test_list_models_empty_response(self):
        """Test model listing handles empty response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"object": "list", "data": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            models = provider.list_models()

            assert models == []


# =============================================================================
# Server Availability Tests
# =============================================================================


@pytest.mark.unit
class TestLocalLLMProviderAvailability:
    """Test server availability checking."""

    def test_is_server_available_true(self):
        """Test server availability returns True when server responds."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            assert provider.is_server_available() is True

    def test_is_server_available_false_connection_error(self):
        """Test server availability returns False on connection error."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            assert provider.is_server_available() is False

    def test_is_server_available_false_timeout(self):
        """Test server availability returns False on timeout."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            assert provider.is_server_available() is False

    def test_is_server_available_false_http_error(self):
        """Test server availability returns False on HTTP error."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        with patch("eq_chatbot_core.providers.local_provider.httpx.Client", return_value=mock_client):
            provider = LocalLLMProvider(api_key="not-used", base_url="http://localhost:1234/v1")

            assert provider.is_server_available() is False


# =============================================================================
# Client Management Tests
# =============================================================================


@pytest.mark.unit
class TestLocalLLMProviderClient:
    """Test HTTP client management."""

    def test_client_lazy_initialization(self):
        """Test that client is lazily initialized."""
        provider = LocalLLMProvider()

        # Client should not be created yet
        assert provider._client is None

        # Accessing client property should create it
        with patch("eq_chatbot_core.providers.local_provider.httpx.Client") as mock_client_class:
            mock_client_class.return_value = MagicMock()
            _ = provider.client

            mock_client_class.assert_called_once()

    def test_client_reuses_instance(self):
        """Test that client is reused across calls."""
        with patch("eq_chatbot_core.providers.local_provider.httpx.Client") as mock_client_class:
            mock_instance = MagicMock()
            mock_client_class.return_value = mock_instance

            provider = LocalLLMProvider()

            client1 = provider.client
            client2 = provider.client

            # Should only create client once
            assert mock_client_class.call_count == 1
            assert client1 is client2

    def test_client_includes_auth_header(self):
        """Test that client includes authorization header."""
        with patch("eq_chatbot_core.providers.local_provider.httpx.Client") as mock_client_class:
            mock_client_class.return_value = MagicMock()

            provider = LocalLLMProvider(api_key="test-key")
            _ = provider.client

            call_kwargs = mock_client_class.call_args[1]
            assert "Authorization" in call_kwargs["headers"]
            assert call_kwargs["headers"]["Authorization"] == "Bearer test-key"
