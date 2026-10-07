"""Unit tests for OpenRouter provider image generation.

Uses httpx mock pattern (like test_openrouter.py — no sys.modules needed,
OpenRouter uses httpx directly).
"""

from unittest.mock import MagicMock

import pytest

from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider


@pytest.fixture
def provider():
    """OpenRouter provider with injected mock httpx client."""
    p = OpenRouterProvider(api_key="sk-or-test", image_model="img-model")
    mock_client = MagicMock()
    p._client = mock_client
    return p, mock_client


@pytest.mark.unit
class TestOpenRouterImageGeneration:
    """Tests for OpenRouter generate_image method."""

    def test_supports_image_generation_flag(self):
        """supports_image_generation must be True for OpenRouter."""
        assert OpenRouterProvider.supports_image_generation is True
