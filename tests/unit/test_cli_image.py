"""Unit tests for the eq-chatbot image CLI command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from eq_chatbot_core.cli import main
from eq_chatbot_core.providers.base import ImageResult, ProviderError

# Minimal valid PNG header (8 bytes) for testing
_FAKE_PNG = b"\x89PNG\r\n\x1a\n"


@pytest.mark.unit
class TestImageCommand:
    """Tests for the eq-chatbot image command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_image_result(self):
        return ImageResult(
            data=_FAKE_PNG,
            model="gpt-image-1",
            provider="openai",
            size="1024x1024",
            mime="image/png",
        )

    def _invoke(self, runner, args, *, tmp_path=None):
        """Helper to invoke with optional tmp output path."""
        return runner.invoke(main, args)

    def test_successful_generation(self, runner, mock_image_result, tmp_path):
        """Successful generation writes image file and exits 0."""
        out_file = str(tmp_path / "out.png")

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.return_value = mock_image_result
            mock_get.return_value = mock_provider

            result = runner.invoke(
                main,
                [
                    "image",
                    "-p",
                    "openai",
                    "-k",
                    "sk-test",
                    "--prompt",
                    "A sunset over the ocean",
                    "-o",
                    out_file,
                ],
            )

        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"
        assert Path(out_file).exists(), "Output file was not created"
        assert Path(out_file).read_bytes() == _FAKE_PNG

    def test_output_message_contains_path(self, runner, mock_image_result, tmp_path):
        """Success output mentions the saved file path."""
        out_file = str(tmp_path / "image.png")

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.return_value = mock_image_result
            mock_get.return_value = mock_provider

            result = runner.invoke(
                main,
                ["image", "-p", "openai", "-k", "sk-test", "--prompt", "Test", "-o", out_file],
            )

        assert result.exit_code == 0
        assert "image.png" in result.output or "Image saved" in result.output

    def test_provider_error_exits_nonzero(self, runner, tmp_path):
        """ProviderError from generate_image causes non-zero exit."""
        out_file = str(tmp_path / "fail.png")

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.side_effect = ProviderError(
                "API quota exceeded", provider="openai", status_code=429
            )
            mock_get.return_value = mock_provider

            result = runner.invoke(
                main,
                ["image", "-p", "openai", "-k", "sk-test", "--prompt", "Test", "-o", out_file],
            )

        assert result.exit_code != 0

    def test_missing_prompt_exits_nonzero(self, runner):
        """Missing both --prompt and --prompt-file causes non-zero exit."""
        result = runner.invoke(main, ["image", "-p", "openai", "-k", "sk-test"])
        assert result.exit_code != 0

    def test_missing_api_key_exits_nonzero(self, runner, monkeypatch):
        """Missing API key causes non-zero exit."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        result = runner.invoke(main, ["image", "-p", "openai", "--prompt", "Test"])
        assert result.exit_code != 0

    def test_prompt_file(self, runner, mock_image_result, tmp_path):
        """--prompt-file reads prompt from file."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("A cat in space")
        out_file = str(tmp_path / "out.png")

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.return_value = mock_image_result
            mock_get.return_value = mock_provider

            result = runner.invoke(
                main,
                [
                    "image",
                    "-p",
                    "openai",
                    "-k",
                    "sk-test",
                    "--prompt-file",
                    str(prompt_file),
                    "-o",
                    out_file,
                ],
            )

        assert result.exit_code == 0
        # Verify the provider was called with the file contents
        call_args = mock_provider.generate_image.call_args
        assert call_args[0][0] == "A cat in space"

    def test_custom_model_forwarded(self, runner, mock_image_result, tmp_path):
        """--model option is forwarded to generate_image."""
        out_file = str(tmp_path / "out.png")

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.return_value = mock_image_result
            mock_get.return_value = mock_provider

            runner.invoke(
                main,
                [
                    "image",
                    "-p",
                    "openai",
                    "-k",
                    "sk-test",
                    "--prompt",
                    "Test",
                    "--model",
                    "dall-e-3",
                    "-o",
                    out_file,
                ],
            )

        call_kwargs = mock_provider.generate_image.call_args[1]
        assert call_kwargs.get("model") == "dall-e-3"

    def test_openrouter_provider_accepted(self, runner, tmp_path):
        """openrouter is a valid provider choice for image command."""
        out_file = str(tmp_path / "out.png")
        image_result = ImageResult(data=_FAKE_PNG, model="google/gemini-2.5-flash-image", provider="openrouter")

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.return_value = image_result
            mock_get.return_value = mock_provider

            result = runner.invoke(
                main,
                ["image", "-p", "openrouter", "-k", "sk-or-test", "--prompt", "Test", "-o", out_file],
            )

        assert result.exit_code == 0

    def test_fit_option_resizes_image(self, runner, tmp_path):
        """--fit option applies fit_to transformation."""
        import io

        from PIL import Image as PILImage  # type: ignore[import]

        # Create a real 100x100 PNG for the mock result
        buf = io.BytesIO()
        PILImage.new("RGB", (100, 100), color=(255, 0, 0)).save(buf, format="PNG")
        real_png = buf.getvalue()

        image_result = ImageResult(data=real_png, model="gpt-image-1", provider="openai")
        out_file = str(tmp_path / "fitted.png")

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.return_value = image_result
            mock_get.return_value = mock_provider

            result = runner.invoke(
                main,
                [
                    "image",
                    "-p",
                    "openai",
                    "-k",
                    "sk-test",
                    "--prompt",
                    "Test",
                    "--fit",
                    "50x50:cover",
                    "-o",
                    out_file,
                ],
            )

        assert result.exit_code == 0, result.output
        # Verify output is 50x50
        with PILImage.open(out_file) as img:
            assert img.size == (50, 50)
