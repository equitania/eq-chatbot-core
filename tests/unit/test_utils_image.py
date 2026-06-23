"""Unit tests for eq_chatbot_core.utils.image.

Requires Pillow (install with: pip install 'eq-chatbot-core[image]').
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

# Skip all tests in this module if Pillow is not installed
PIL = pytest.importorskip("PIL", reason="Pillow not installed (pip install 'eq-chatbot-core[image]')")

from PIL import Image as PILImage  # noqa: E402

from eq_chatbot_core.utils.image import fit_to, parse_size, save_png  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_png(width: int, height: int, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """Create a minimal in-memory PNG image of the given dimensions."""
    buf = io.BytesIO()
    PILImage.new("RGB", (width, height), color=color).save(buf, format="PNG")
    return buf.getvalue()


def _image_size(data: bytes) -> tuple[int, int]:
    """Return (width, height) of PNG bytes."""
    return PILImage.open(io.BytesIO(data)).size


# ---------------------------------------------------------------------------
# parse_size
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseSize:
    """Tests for parse_size()."""

    def test_basic(self):
        assert parse_size("1024x768") == (1024, 768)

    def test_square(self):
        assert parse_size("256x256") == (256, 256)

    def test_uppercase(self):
        assert parse_size("512X512") == (512, 512)

    def test_invalid_format_no_x(self):
        with pytest.raises(ValueError, match="Invalid size format"):
            parse_size("1024-768")

    def test_invalid_format_non_integer(self):
        with pytest.raises(ValueError):
            parse_size("abcxdef")

    def test_zero_dimension_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            parse_size("0x256")

    def test_negative_dimension_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            parse_size("-1x256")


# ---------------------------------------------------------------------------
# save_png
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSavePng:
    """Tests for save_png()."""

    def test_creates_file(self, tmp_path):
        data = _make_png(10, 10)
        out = save_png(data, tmp_path / "test.png")
        assert out.exists()
        assert out.read_bytes() == data

    def test_returns_resolved_path(self, tmp_path):
        data = b"\x89PNG"
        out = save_png(data, tmp_path / "img.png")
        assert out.is_absolute()

    def test_creates_parent_directories(self, tmp_path):
        data = b"\x89PNG"
        deep = tmp_path / "a" / "b" / "c" / "img.png"
        save_png(data, deep)
        assert deep.exists()

    def test_accepts_string_path(self, tmp_path):
        data = b"\x89PNG"
        out = save_png(data, str(tmp_path / "str.png"))
        assert Path(out).exists()

    def test_base_dir_allows_path_inside(self, tmp_path):
        data = b"\x89PNG"
        out = save_png(data, tmp_path / "sub" / "img.png", base_dir=tmp_path)
        assert out.exists()

    def test_base_dir_rejects_parent_traversal(self, tmp_path):
        data = b"\x89PNG"
        base = tmp_path / "assets"
        base.mkdir()
        with pytest.raises(ValueError, match="outside the base directory"):
            save_png(data, base / ".." / "escaped.png", base_dir=base)
        assert not (tmp_path / "escaped.png").exists()

    def test_base_dir_rejects_absolute_escape(self, tmp_path):
        data = b"\x89PNG"
        base = tmp_path / "assets"
        base.mkdir()
        # An absolute out_name overrides the base when joined: base / "/etc/x".
        outside = tmp_path / "outside.png"
        with pytest.raises(ValueError, match="outside the base directory"):
            save_png(data, base / str(outside), base_dir=base)
        assert not outside.exists()


# ---------------------------------------------------------------------------
# fit_to — cover mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFitToCover:
    """Tests for fit_to() with mode='cover'."""

    def test_square_to_square(self):
        src = _make_png(100, 100)
        result = fit_to(src, 50, 50, mode="cover")
        assert _image_size(result) == (50, 50)

    def test_wide_to_square(self):
        """Wide source → center-crop left/right, then resize."""
        src = _make_png(200, 100)
        result = fit_to(src, 50, 50, mode="cover")
        assert _image_size(result) == (50, 50)

    def test_tall_to_square(self):
        """Tall source → center-crop top/bottom, then resize."""
        src = _make_png(100, 200)
        result = fit_to(src, 50, 50, mode="cover")
        assert _image_size(result) == (50, 50)

    def test_cover_is_default_mode(self):
        src = _make_png(100, 100)
        result_explicit = fit_to(src, 60, 60, mode="cover")
        result_default = fit_to(src, 60, 60)
        assert result_explicit == result_default

    def test_output_is_png_bytes(self):
        src = _make_png(100, 100)
        result = fit_to(src, 50, 50, mode="cover")
        assert result[:4] == b"\x89PNG"


# ---------------------------------------------------------------------------
# fit_to — contain mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFitToContain:
    """Tests for fit_to() with mode='contain'."""

    def test_output_dimensions(self):
        src = _make_png(100, 100)
        result = fit_to(src, 200, 200, mode="contain")
        assert _image_size(result) == (200, 200)

    def test_wide_source_in_square_box(self):
        src = _make_png(200, 100)
        result = fit_to(src, 200, 200, mode="contain")
        assert _image_size(result) == (200, 200)

    def test_tall_source_in_square_box(self):
        src = _make_png(100, 200)
        result = fit_to(src, 200, 200, mode="contain")
        assert _image_size(result) == (200, 200)


# ---------------------------------------------------------------------------
# fit_to — stretch mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFitToStretch:
    """Tests for fit_to() with mode='stretch'."""

    def test_stretches_to_exact_dimensions(self):
        src = _make_png(100, 100)
        result = fit_to(src, 300, 150, mode="stretch")
        assert _image_size(result) == (300, 150)

    def test_output_is_png(self):
        src = _make_png(100, 100)
        result = fit_to(src, 64, 64, mode="stretch")
        assert result[:4] == b"\x89PNG"


# ---------------------------------------------------------------------------
# fit_to — invalid mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFitToInvalidMode:
    def test_invalid_mode_raises_value_error(self):
        src = _make_png(10, 10)
        with pytest.raises(ValueError, match="Invalid mode"):
            fit_to(src, 10, 10, mode="wrong")
