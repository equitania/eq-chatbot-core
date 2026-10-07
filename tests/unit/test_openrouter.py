"""
Unit tests for OpenRouter provider.

All tests use mocked responses - no real API calls.
Tests cover 400+ model access through unified API.
"""

from unittest.mock import MagicMock

import pytest

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


# =============================================================================
# Provider Properties Tests
# =============================================================================


# =============================================================================
# Reasoning Model Detection Tests
# =============================================================================


# =============================================================================
# Chat Completion Tests
# =============================================================================


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


# =============================================================================
# List Models Tests
# =============================================================================


# =============================================================================
# Model Constraints Tests
# =============================================================================


# =============================================================================
# Error Handling Tests
# =============================================================================


# =============================================================================
# Context Manager Tests
# =============================================================================


# =============================================================================
# Factory Integration Tests
# =============================================================================


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
