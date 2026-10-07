"""
Unit tests for LocalLLMProvider.

Tests the unified provider for local LLM servers (LM Studio, Ollama)
using mocked HTTP responses.
"""

import pytest

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


# =============================================================================
# Error Handling Tests
# =============================================================================


# =============================================================================
# Streaming Tests
# =============================================================================


# =============================================================================
# List Models Tests
# =============================================================================


# =============================================================================
# Server Availability Tests
# =============================================================================


# =============================================================================
# Client Management Tests
# =============================================================================
