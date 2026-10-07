"""Unit tests for OpenRouter provider image generation.

Uses httpx mock pattern (like test_openrouter.py — no sys.modules needed,
OpenRouter uses httpx directly).
"""

import base64
from unittest.mock import MagicMock

import pytest

from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

# Minimal PNG data for testing
_FAKE_PNG_BYTES = b"\x89PNG\r\n\x1a\n"
_FAKE_PNG_B64 = base64.b64encode(_FAKE_PNG_BYTES).decode()
_FAKE_DATA_URL = f"data:image/png;base64,{_FAKE_PNG_B64}"


def _make_image_response(model: str = "google/gemini-2.5-flash-image", data_url: str = _FAKE_DATA_URL) -> dict:
    """Build a mock OpenRouter chat/completions response with image output."""
    return {
        "id": "gen-test-123",
        "model": model,
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "images": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        }
                    ],
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 0},
    }


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

    @pytest.mark.xfail(reason="stage 2: no built-in default image model", strict=False)
    def test_default_image_model(self):
        """Default image model should be google/gemini-2.5-flash-image."""
        assert OpenRouterProvider.DEFAULT_IMAGE_MODEL == "google/gemini-2.5-flash-image"
