"""Unit tests for OpenRouter provider image generation.

Uses httpx mock pattern (like test_openrouter.py — no sys.modules needed,
OpenRouter uses httpx directly).
"""

import base64
from unittest.mock import MagicMock

import httpx
import pytest

from eq_chatbot_core.providers.base import ImageResult, ProviderError
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
    p = OpenRouterProvider(api_key="sk-or-test")
    mock_client = MagicMock()
    p._client = mock_client
    return p, mock_client


@pytest.mark.unit
class TestOpenRouterImageGeneration:
    """Tests for OpenRouter generate_image method."""

    def test_supports_image_generation_flag(self):
        """supports_image_generation must be True for OpenRouter."""
        assert OpenRouterProvider.supports_image_generation is True

    def test_default_image_model(self):
        """Default image model should be google/gemini-2.5-flash-image."""
        assert OpenRouterProvider.DEFAULT_IMAGE_MODEL == "google/gemini-2.5-flash-image"

    def test_generate_image_returns_image_result(self, provider):
        """Successful call returns ImageResult with decoded bytes."""
        p, mock_client = provider

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_image_response()
        mock_client.post.return_value = mock_resp

        result = p.generate_image("A sunset over the ocean")

        assert isinstance(result, ImageResult)
        assert result.data == _FAKE_PNG_BYTES
        assert result.model == "google/gemini-2.5-flash-image"
        assert result.provider == "openrouter"
        assert result.mime == "image/png"
        # size is None for OpenRouter (not controllable)
        assert result.size is None

    def test_generate_image_uses_default_model(self, provider):
        """generate_image uses DEFAULT_IMAGE_MODEL when model is None."""
        p, mock_client = provider

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_image_response()
        mock_client.post.return_value = mock_resp

        p.generate_image("Test")

        call_kwargs = mock_client.post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["model"] == "google/gemini-2.5-flash-image"

    def test_generate_image_modalities_in_payload(self, provider):
        """Payload includes modalities=['image', 'text']."""
        p, mock_client = provider

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_image_response()
        mock_client.post.return_value = mock_resp

        p.generate_image("Test")

        call_kwargs = mock_client.post.call_args[1]
        payload = call_kwargs["json"]
        assert "image" in payload["modalities"]
        assert "text" in payload["modalities"]

    def test_generate_image_prompt_in_message(self, provider):
        """User prompt is sent as a chat message."""
        p, mock_client = provider

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_image_response()
        mock_client.post.return_value = mock_resp

        p.generate_image("A beautiful landscape")

        payload = mock_client.post.call_args[1]["json"]
        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][0]["content"] == "A beautiful landscape"

    def test_generate_image_data_url_parsing(self, provider):
        """data URL is correctly parsed: mime extracted, b64 decoded."""
        p, mock_client = provider

        raw_bytes = b"SOME BINARY IMAGE"
        encoded = base64.b64encode(raw_bytes).decode()
        data_url = f"data:image/jpeg;base64,{encoded}"

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_image_response(data_url=data_url)
        mock_client.post.return_value = mock_resp

        result = p.generate_image("Test")

        assert result.data == raw_bytes
        assert result.mime == "image/jpeg"

    def test_generate_image_no_images_raises_provider_error(self, provider):
        """Empty images list in response raises ProviderError."""
        p, mock_client = provider

        # Response with no images
        response_data = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "I cannot generate images.", "images": []},
                    "finish_reason": "stop",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response_data
        mock_client.post.return_value = mock_resp

        with pytest.raises(ProviderError, match="No image returned"):
            p.generate_image("Test")

    def test_generate_image_missing_images_key_raises_provider_error(self, provider):
        """Missing 'images' key in message raises ProviderError."""
        p, mock_client = provider

        response_data = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "text only"},
                    "finish_reason": "stop",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response_data
        mock_client.post.return_value = mock_resp

        with pytest.raises(ProviderError, match="No image returned"):
            p.generate_image("Test")

    def test_generate_image_http_401_raises_authentication_error(self, provider):
        """HTTP 401 is mapped to AuthenticationError."""
        from eq_chatbot_core.providers.base import AuthenticationError

        p, mock_client = provider

        http_error = httpx.HTTPStatusError(
            "401",
            request=MagicMock(),
            response=MagicMock(
                status_code=401,
                json=MagicMock(return_value={"error": {"message": "Invalid API key"}}),
            ),
        )
        mock_client.post.side_effect = http_error

        with pytest.raises((AuthenticationError, ProviderError)):
            p.generate_image("Test")

    def test_generate_image_http_429_raises_rate_limit_error(self, provider):
        """HTTP 429 is mapped to RateLimitError."""
        from eq_chatbot_core.providers.base import RateLimitError

        p, mock_client = provider

        http_error = httpx.HTTPStatusError(
            "429",
            request=MagicMock(),
            response=MagicMock(
                status_code=429,
                json=MagicMock(return_value={"error": {"message": "Rate limit exceeded"}}),
            ),
        )
        mock_client.post.side_effect = http_error

        with pytest.raises((RateLimitError, ProviderError)):
            p.generate_image("Test")

    def test_generate_image_custom_model(self, provider):
        """Custom model is forwarded to the API."""
        p, mock_client = provider

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_image_response(model="custom/image-model")
        mock_client.post.return_value = mock_resp

        result = p.generate_image("Test", model="custom/image-model")

        assert result.model == "custom/image-model"
        payload = mock_client.post.call_args[1]["json"]
        assert payload["model"] == "custom/image-model"

    def test_generate_image_invalid_data_url_raises_error(self, provider):
        """Non-data: URL format raises ProviderError."""
        p, mock_client = provider

        response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "images": [{"type": "image_url", "image_url": {"url": "https://example.com/image.png"}}],
                    },
                    "finish_reason": "stop",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response_data
        mock_client.post.return_value = mock_resp

        with pytest.raises(ProviderError, match="Unexpected image URL format"):
            p.generate_image("Test")
