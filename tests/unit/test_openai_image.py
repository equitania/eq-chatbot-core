"""Unit tests for OpenAI provider image generation.

Client is injected directly via _client attribute — no sys.modules patching
needed because generate_image accesses self.client (the lazy property) and
we bypass it by setting _client before the call.
"""

import base64
import sys
from unittest.mock import MagicMock

import pytest

# The openai module is already mocked by test_openai.py when running in the
# same session. If we're running alone, we need to mock it ourselves so the
# lazy import inside OpenAIProvider does not fail.
if "openai" not in sys.modules:
    sys.modules["openai"] = MagicMock()

from eq_chatbot_core.providers.base import (  # noqa: E402
    ImageResult,
    ProviderError,
    RateLimitError,
)
from eq_chatbot_core.providers.openai_provider import OpenAIProvider  # noqa: E402

# Minimal valid PNG header bytes used as fake image data
_FAKE_PNG_BYTES = b"\x89PNG\r\n\x1a\n"
_FAKE_PNG_B64 = base64.b64encode(_FAKE_PNG_BYTES).decode()


@pytest.fixture
def provider():
    """OpenAI provider with injected mock client."""
    p = OpenAIProvider(api_key="sk-test")
    mock_client = MagicMock()
    p._client = mock_client
    return p, mock_client


@pytest.mark.unit
class TestOpenAIImageGeneration:
    """Tests for OpenAI generate_image method."""

    def test_supports_image_generation_flag(self):
        """supports_image_generation must be True for OpenAI."""
        assert OpenAIProvider.supports_image_generation is True

    def test_default_image_model(self):
        """Default image model should be gpt-image-1."""
        assert OpenAIProvider.DEFAULT_IMAGE_MODEL == "gpt-image-1"

    def test_generate_image_returns_image_result(self, provider):
        """Successful call returns ImageResult with decoded bytes."""
        p, mock_client = provider

        # Mock images.generate response
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock()]
        mock_resp.data[0].b64_json = _FAKE_PNG_B64
        mock_client.images.generate.return_value = mock_resp

        result = p.generate_image("A sunset over the ocean")

        assert isinstance(result, ImageResult)
        assert result.data == _FAKE_PNG_BYTES
        assert result.model == "gpt-image-1"
        assert result.provider == "openai"
        assert result.size == "1024x1024"
        assert result.mime == "image/png"

    def test_generate_image_uses_default_model(self, provider):
        """generate_image uses gpt-image-1 when model is None."""
        p, mock_client = provider

        mock_resp = MagicMock()
        mock_resp.data = [MagicMock()]
        mock_resp.data[0].b64_json = _FAKE_PNG_B64
        mock_client.images.generate.return_value = mock_resp

        p.generate_image("Test prompt")

        call_kwargs = mock_client.images.generate.call_args[1]
        assert call_kwargs["model"] == "gpt-image-1"

    def test_generate_image_no_response_format_for_gpt_image_1(self, provider):
        """gpt-image-1 must NOT receive response_format parameter."""
        p, mock_client = provider

        mock_resp = MagicMock()
        mock_resp.data = [MagicMock()]
        mock_resp.data[0].b64_json = _FAKE_PNG_B64
        mock_client.images.generate.return_value = mock_resp

        p.generate_image("Test", model="gpt-image-1")

        call_kwargs = mock_client.images.generate.call_args[1]
        assert "response_format" not in call_kwargs

    def test_generate_image_sends_response_format_for_dalle3(self, provider):
        """dall-e-3 should receive response_format='b64_json'."""
        p, mock_client = provider

        mock_resp = MagicMock()
        mock_resp.data = [MagicMock()]
        mock_resp.data[0].b64_json = _FAKE_PNG_B64
        mock_client.images.generate.return_value = mock_resp

        p.generate_image("Test", model="dall-e-3")

        call_kwargs = mock_client.images.generate.call_args[1]
        assert call_kwargs.get("response_format") == "b64_json"

    def test_generate_image_custom_size(self, provider):
        """Custom size is forwarded to the API call."""
        p, mock_client = provider

        mock_resp = MagicMock()
        mock_resp.data = [MagicMock()]
        mock_resp.data[0].b64_json = _FAKE_PNG_B64
        mock_client.images.generate.return_value = mock_resp

        result = p.generate_image("Test", size="1024x1536")

        call_kwargs = mock_client.images.generate.call_args[1]
        assert call_kwargs["size"] == "1024x1536"
        assert result.size == "1024x1536"

    def test_generate_image_custom_model(self, provider):
        """Custom model is used instead of the default."""
        p, mock_client = provider

        mock_resp = MagicMock()
        mock_resp.data = [MagicMock()]
        mock_resp.data[0].b64_json = _FAKE_PNG_B64
        mock_client.images.generate.return_value = mock_resp

        result = p.generate_image("Test", model="dall-e-3")

        assert result.model == "dall-e-3"

    def test_generate_image_base64_decoding(self, provider):
        """Image bytes are correctly base64-decoded from the API response."""
        p, mock_client = provider

        raw_bytes = b"FAKE IMAGE BINARY DATA"
        encoded = base64.b64encode(raw_bytes).decode()

        mock_resp = MagicMock()
        mock_resp.data = [MagicMock()]
        mock_resp.data[0].b64_json = encoded
        mock_client.images.generate.return_value = mock_resp

        result = p.generate_image("Test")

        assert result.data == raw_bytes

    def test_generate_image_authentication_error(self, provider):
        """Authentication errors are mapped to AuthenticationError."""
        p, mock_client = provider

        mock_client.images.generate.side_effect = Exception("401 authentication failed")

        with pytest.raises(ProviderError):
            p.generate_image("Test")

    def test_generate_image_rate_limit_error(self, provider):
        """Rate limit errors are mapped to RateLimitError."""
        p, mock_client = provider

        mock_client.images.generate.side_effect = Exception("rate limit exceeded 429")

        with pytest.raises((RateLimitError, ProviderError)):
            p.generate_image("Test")

    def test_generate_image_forwards_n_1(self, provider):
        """API call always requests n=1 image."""
        p, mock_client = provider

        mock_resp = MagicMock()
        mock_resp.data = [MagicMock()]
        mock_resp.data[0].b64_json = _FAKE_PNG_B64
        mock_client.images.generate.return_value = mock_resp

        p.generate_image("Test")

        call_kwargs = mock_client.images.generate.call_args[1]
        assert call_kwargs["n"] == 1
