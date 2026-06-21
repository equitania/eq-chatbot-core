"""Unit tests for the eq-chatbot listing-assets CLI command."""

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from eq_chatbot_core.cli import main
from eq_chatbot_core.providers.base import ImageResult, ProviderError

# Minimal PNG (1x1 pixel, valid Pillow input)
_FAKE_PNG = b"\x89PNG\r\n\x1a\n"


def _real_png_1x1() -> bytes:
    """Return a real 1x1 PNG for tests that exercise Pillow (fit_to)."""
    from PIL import Image as PILImage  # type: ignore[import]

    buf = io.BytesIO()
    PILImage.new("RGB", (64, 64), color=(0, 128, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _make_recipe(tmp_path: Path, assets: list[dict] | None = None, **extra) -> Path:
    """Write a minimal valid recipe JSON file to tmp_path and return its path."""
    recipe: dict = {
        "schema": "eq-listing-assets/v1",
        "module": "eq_test",
        "defaults": {"provider": "openai", "model": "gpt-image-1"},
        "assets": assets
        if assets is not None
        else [
            {
                "id": "icon",
                "out": "icon.png",
                "size": "1024x1024",
                "prompt": "A modern icon",
            },
            {
                "id": "banner",
                "out": "banner.png",
                "size": "1536x1024",
                "prompt": "A wide banner",
            },
        ],
    }
    recipe.update(extra)
    recipe_path = tmp_path / "listing.json"
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
    return recipe_path


def _mock_provider_returns(image_data: bytes = _FAKE_PNG):
    """Context manager: patch get_provider with a mock that returns image_data."""

    class _Context:
        def __enter__(self):
            self._patcher = patch("eq_chatbot_core.providers.get_provider")
            mock_get = self._patcher.start()
            mock_provider = MagicMock()
            mock_provider.generate_image.return_value = ImageResult(
                data=image_data,
                model="gpt-image-1",
                provider="openai",
                size="1024x1024",
                mime="image/png",
            )
            mock_get.return_value = mock_provider
            self.mock_get = mock_get
            self.mock_provider = mock_provider
            return self

        def __exit__(self, *args):
            self._patcher.stop()

    return _Context()


@pytest.mark.unit
class TestListingAssetsCommand:
    """Tests for the eq-chatbot listing-assets command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    # ─────────────────────────────────────────────
    # Happy path
    # ─────────────────────────────────────────────

    def test_successful_batch_creates_files(self, runner, tmp_path):
        """Valid recipe generates all assets in dest dir, exits 0."""
        recipe_path = _make_recipe(tmp_path)
        dest = tmp_path / "out"

        with _mock_provider_returns() as ctx:
            result = runner.invoke(
                main,
                [
                    "listing-assets",
                    "--recipe", str(recipe_path),
                    "--api-key", "sk-test",
                    "--dest", str(dest),
                ],
            )

        assert result.exit_code == 0, f"Expected exit 0:\n{result.output}"
        assert (dest / "icon.png").exists(), "icon.png not created"
        assert (dest / "banner.png").exists(), "banner.png not created"
        assert ctx.mock_provider.generate_image.call_count == 2

    def test_dest_defaults_to_recipe_directory(self, runner, tmp_path):
        """When --dest is omitted images land next to the recipe file."""
        recipe_path = _make_recipe(tmp_path)

        with _mock_provider_returns():
            result = runner.invoke(
                main,
                [
                    "listing-assets",
                    "--recipe", str(recipe_path),
                    "--api-key", "sk-test",
                ],
            )

        assert result.exit_code == 0, result.output
        assert (tmp_path / "icon.png").exists()
        assert (tmp_path / "banner.png").exists()

    def test_provider_called_once_for_batch(self, runner, tmp_path):
        """Provider is instantiated once, generate_image once per asset."""
        recipe_path = _make_recipe(tmp_path)

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.return_value = ImageResult(
                data=_FAKE_PNG, model="gpt-image-1", provider="openai"
            )
            mock_get.return_value = mock_provider

            result = runner.invoke(
                main,
                [
                    "listing-assets",
                    "--recipe", str(recipe_path),
                    "--api-key", "sk-test",
                    "--dest", str(tmp_path / "out"),
                ],
            )

        assert result.exit_code == 0
        assert mock_get.call_count == 1
        assert mock_provider.generate_image.call_count == 2

    # ─────────────────────────────────────────────
    # --dry-run
    # ─────────────────────────────────────────────

    def test_dry_run_no_api_calls(self, runner, tmp_path):
        """--dry-run lists assets without calling generate_image, exits 0."""
        recipe_path = _make_recipe(tmp_path)

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_get.return_value = mock_provider

            result = runner.invoke(
                main,
                [
                    "listing-assets",
                    "--recipe", str(recipe_path),
                    "--dry-run",
                ],
            )

        assert result.exit_code == 0, result.output
        mock_get.assert_not_called()
        mock_provider.generate_image.assert_not_called()

    def test_dry_run_lists_asset_ids(self, runner, tmp_path):
        """--dry-run output contains asset ids."""
        recipe_path = _make_recipe(tmp_path)

        result = runner.invoke(
            main,
            ["listing-assets", "--recipe", str(recipe_path), "--dry-run"],
        )

        assert result.exit_code == 0
        assert "icon" in result.output
        assert "banner" in result.output

    def test_dry_run_does_not_need_api_key(self, runner, tmp_path):
        """--dry-run works without --api-key (no provider is created)."""
        recipe_path = _make_recipe(tmp_path)

        result = runner.invoke(
            main,
            ["listing-assets", "--recipe", str(recipe_path), "--dry-run"],
        )

        assert result.exit_code == 0

    # ─────────────────────────────────────────────
    # --only filter
    # ─────────────────────────────────────────────

    def test_only_filter_generates_single_asset(self, runner, tmp_path):
        """--only icon generates only icon.png, not banner.png."""
        recipe_path = _make_recipe(tmp_path)
        dest = tmp_path / "out"

        with _mock_provider_returns() as ctx:
            result = runner.invoke(
                main,
                [
                    "listing-assets",
                    "--recipe", str(recipe_path),
                    "--api-key", "sk-test",
                    "--dest", str(dest),
                    "--only", "icon",
                ],
            )

        assert result.exit_code == 0, result.output
        assert (dest / "icon.png").exists()
        assert not (dest / "banner.png").exists()
        assert ctx.mock_provider.generate_image.call_count == 1

    def test_only_multiple_ids(self, runner, tmp_path):
        """--only with comma-separated ids filters correctly."""
        recipe_path = _make_recipe(
            tmp_path,
            assets=[
                {"id": "icon", "out": "icon.png", "size": "1024x1024", "prompt": "icon"},
                {"id": "banner", "out": "banner.png", "size": "1536x1024", "prompt": "banner"},
                {"id": "extra", "out": "extra.png", "size": "1024x1024", "prompt": "extra"},
            ],
        )
        dest = tmp_path / "out"

        with _mock_provider_returns() as ctx:
            result = runner.invoke(
                main,
                [
                    "listing-assets",
                    "--recipe", str(recipe_path),
                    "--api-key", "sk-test",
                    "--dest", str(dest),
                    "--only", "icon,extra",
                ],
            )

        assert result.exit_code == 0, result.output
        assert ctx.mock_provider.generate_image.call_count == 2
        assert (dest / "icon.png").exists()
        assert (dest / "extra.png").exists()
        assert not (dest / "banner.png").exists()

    def test_only_unknown_id_exits_nonzero(self, runner, tmp_path):
        """--only with unknown id that matches no asset raises error."""
        recipe_path = _make_recipe(tmp_path)

        result = runner.invoke(
            main,
            [
                "listing-assets",
                "--recipe", str(recipe_path),
                "--only", "nonexistent",
                "--dry-run",
            ],
        )

        assert result.exit_code != 0

    # ─────────────────────────────────────────────
    # Recipe validation errors
    # ─────────────────────────────────────────────

    def test_invalid_schema_prefix_exits_nonzero(self, runner, tmp_path):
        """Recipe with wrong schema prefix causes non-zero exit."""
        recipe_path = tmp_path / "bad.json"
        recipe_path.write_text(
            json.dumps({"schema": "something-else/v1", "assets": []}),
            encoding="utf-8",
        )

        result = runner.invoke(
            main,
            ["listing-assets", "--recipe", str(recipe_path), "--dry-run"],
        )

        assert result.exit_code != 0

    def test_missing_assets_key_exits_nonzero(self, runner, tmp_path):
        """Recipe missing 'assets' key causes non-zero exit."""
        recipe_path = tmp_path / "bad.json"
        recipe_path.write_text(
            json.dumps({"schema": "eq-listing-assets/v1", "module": "x"}),
            encoding="utf-8",
        )

        result = runner.invoke(
            main,
            ["listing-assets", "--recipe", str(recipe_path), "--dry-run"],
        )

        assert result.exit_code != 0

    def test_empty_assets_list_exits_nonzero(self, runner, tmp_path):
        """Recipe with empty 'assets' list causes non-zero exit."""
        recipe_path = _make_recipe(tmp_path, assets=[])

        result = runner.invoke(
            main,
            ["listing-assets", "--recipe", str(recipe_path), "--dry-run"],
        )

        assert result.exit_code != 0

    def test_asset_missing_required_field_exits_nonzero(self, runner, tmp_path):
        """Asset missing 'prompt' causes non-zero exit."""
        recipe_path = _make_recipe(
            tmp_path,
            assets=[{"id": "icon", "out": "icon.png"}],  # no prompt
        )

        result = runner.invoke(
            main,
            ["listing-assets", "--recipe", str(recipe_path), "--dry-run"],
        )

        assert result.exit_code != 0

    def test_invalid_json_exits_nonzero(self, runner, tmp_path):
        """Non-JSON recipe file causes non-zero exit."""
        recipe_path = tmp_path / "bad.json"
        recipe_path.write_text("not json {{{", encoding="utf-8")

        result = runner.invoke(
            main,
            ["listing-assets", "--recipe", str(recipe_path), "--dry-run"],
        )

        assert result.exit_code != 0

    # ─────────────────────────────────────────────
    # Partial failure
    # ─────────────────────────────────────────────

    def test_one_asset_fails_others_still_generated(self, runner, tmp_path):
        """When one asset raises ProviderError, remaining assets are still processed."""
        recipe_path = _make_recipe(
            tmp_path,
            assets=[
                {"id": "icon", "out": "icon.png", "size": "1024x1024", "prompt": "icon"},
                {"id": "banner", "out": "banner.png", "size": "1536x1024", "prompt": "banner"},
                {"id": "extra", "out": "extra.png", "size": "1024x1024", "prompt": "extra"},
            ],
        )
        dest = tmp_path / "out"

        def _side_effect(prompt, model, size):
            if "banner" in prompt:
                raise ProviderError("quota exceeded", provider="openai", status_code=429)
            return ImageResult(data=_FAKE_PNG, model="gpt-image-1", provider="openai")

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.side_effect = _side_effect
            mock_get.return_value = mock_provider

            result = runner.invoke(
                main,
                [
                    "listing-assets",
                    "--recipe", str(recipe_path),
                    "--api-key", "sk-test",
                    "--dest", str(dest),
                ],
            )

        # Non-zero exit because at least one asset failed
        assert result.exit_code != 0
        # The other two assets were generated
        assert (dest / "icon.png").exists()
        assert (dest / "extra.png").exists()
        assert not (dest / "banner.png").exists()

    def test_failed_asset_id_appears_in_output(self, runner, tmp_path):
        """Failed asset ID is reported in the error output."""
        recipe_path = _make_recipe(
            tmp_path,
            assets=[
                {"id": "icon", "out": "icon.png", "size": "1024x1024", "prompt": "icon"},
            ],
        )

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.side_effect = ProviderError(
                "API error", provider="openai", status_code=500
            )
            mock_get.return_value = mock_provider

            result = runner.invoke(
                main,
                [
                    "listing-assets",
                    "--recipe", str(recipe_path),
                    "--api-key", "sk-test",
                    "--dest", str(tmp_path / "out"),
                ],
            )

        assert result.exit_code != 0
        # Error message or combined output should mention 'icon'
        combined = result.output + (result.exception and str(result.exception) or "")
        assert "icon" in combined

    # ─────────────────────────────────────────────
    # --fit option (real Pillow round-trip)
    # ─────────────────────────────────────────────

    def test_fit_option_resizes_asset(self, runner, tmp_path):
        """Asset with fit field is resized via Pillow to the target dimensions."""
        real_png = _real_png_1x1()
        recipe_path = _make_recipe(
            tmp_path,
            assets=[
                {
                    "id": "icon",
                    "out": "icon.png",
                    "size": "1024x1024",
                    "fit": "32x32:cover",
                    "prompt": "icon",
                }
            ],
        )
        dest = tmp_path / "out"

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.return_value = ImageResult(
                data=real_png, model="gpt-image-1", provider="openai"
            )
            mock_get.return_value = mock_provider

            result = runner.invoke(
                main,
                [
                    "listing-assets",
                    "--recipe", str(recipe_path),
                    "--api-key", "sk-test",
                    "--dest", str(dest),
                ],
            )

        assert result.exit_code == 0, result.output
        from PIL import Image as PILImage  # type: ignore[import]

        with PILImage.open(dest / "icon.png") as img:
            assert img.size == (32, 32)

    # ─────────────────────────────────────────────
    # CLI flag overrides
    # ─────────────────────────────────────────────

    def test_cli_provider_overrides_defaults(self, runner, tmp_path):
        """--provider CLI flag overrides recipe defaults.provider."""
        recipe_path = _make_recipe(tmp_path)

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.return_value = ImageResult(
                data=_FAKE_PNG, model="any", provider="openrouter"
            )
            mock_get.return_value = mock_provider

            runner.invoke(
                main,
                [
                    "listing-assets",
                    "--recipe", str(recipe_path),
                    "--api-key", "sk-or-test",
                    "--provider", "openrouter",
                    "--dest", str(tmp_path / "out"),
                ],
            )

        call_kwargs = mock_get.call_args
        assert call_kwargs[0][0] == "openrouter"

    def test_cli_model_overrides_defaults(self, runner, tmp_path):
        """--model CLI flag overrides recipe defaults.model."""
        recipe_path = _make_recipe(tmp_path)

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.generate_image.return_value = ImageResult(
                data=_FAKE_PNG, model="dall-e-3", provider="openai"
            )
            mock_get.return_value = mock_provider

            runner.invoke(
                main,
                [
                    "listing-assets",
                    "--recipe", str(recipe_path),
                    "--api-key", "sk-test",
                    "--model", "dall-e-3",
                    "--dest", str(tmp_path / "out"),
                ],
            )

        gen_call_kwargs = mock_provider.generate_image.call_args[1]
        assert gen_call_kwargs.get("model") == "dall-e-3"

    # ─────────────────────────────────────────────
    # No API key
    # ─────────────────────────────────────────────

    def test_missing_api_key_exits_nonzero(self, runner, tmp_path):
        """Missing API key (not dry-run) causes non-zero exit."""
        recipe_path = _make_recipe(tmp_path)

        result = runner.invoke(
            main,
            ["listing-assets", "--recipe", str(recipe_path)],
        )

        assert result.exit_code != 0
