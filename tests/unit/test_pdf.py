"""Tests for utils/pdf.py — PDF-to-image conversion and its resource guards.

These build real PDFs with PyMuPDF and convert them for real; the point of the
module is the rendering and the DoS bounds around it, and a mocked fitz would
verify neither.
"""

import base64

import pytest

from eq_chatbot_core.utils.pdf import (
    MAX_DPI,
    MAX_PAGES_HARD,
    MAX_PDF_BYTES,
    is_pdf_conversion_available,
    pdf_to_base64_images,
    pdf_to_images,
)

pytestmark = pytest.mark.unit

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed ([pdf] extra)")


def _make_pdf(pages: int = 1) -> bytes:
    """Build a minimal multi-page PDF in memory."""
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"page {i + 1}")
    data: bytes = doc.tobytes()
    doc.close()
    return data


class TestAvailability:
    def test_available_when_pymupdf_installed(self):
        assert is_pdf_conversion_available() is True


class TestConversion:
    def test_single_page_returns_one_png(self):
        images = pdf_to_images(_make_pdf(1))

        assert len(images) == 1
        img_bytes, mimetype = images[0]
        assert mimetype == "image/png"
        assert img_bytes.startswith(b"\x89PNG\r\n\x1a\n"), "expected a real PNG signature"

    def test_jpeg_format_selected(self):
        images = pdf_to_images(_make_pdf(1), image_format="jpeg")

        assert len(images) == 1
        img_bytes, mimetype = images[0]
        assert mimetype == "image/jpeg"
        assert img_bytes.startswith(b"\xff\xd8\xff"), "expected a real JPEG signature"

    def test_all_pages_converted(self):
        images = pdf_to_images(_make_pdf(3))

        assert len(images) == 3

    def test_max_pages_truncates(self):
        images = pdf_to_images(_make_pdf(5), max_pages=2)

        assert len(images) == 2

    def test_higher_dpi_produces_larger_image(self):
        low = pdf_to_images(_make_pdf(1), dpi=72)[0][0]
        high = pdf_to_images(_make_pdf(1), dpi=300)[0][0]

        assert len(high) > len(low)

    def test_corrupt_pdf_returns_empty_list_instead_of_raising(self):
        """Callers treat an unconvertible document as 'no images', not an error."""
        assert pdf_to_images(b"this is not a PDF at all") == []


class TestInputValidation:
    def test_invalid_format_rejected(self):
        with pytest.raises(ValueError, match="Unsupported image format"):
            pdf_to_images(_make_pdf(1), image_format="gif")

    def test_oversized_input_rejected(self):
        oversized = b"%PDF-1.4" + b"\x00" * MAX_PDF_BYTES

        with pytest.raises(ValueError, match="PDF too large"):
            pdf_to_images(oversized)


class TestResourceClamping:
    """max_pages and dpi are clamped, so a hostile caller cannot demand unbounded work."""

    def test_page_count_clamped_to_hard_limit(self):
        pdf = _make_pdf(MAX_PAGES_HARD + 5)

        images = pdf_to_images(pdf, max_pages=10_000)

        assert len(images) == MAX_PAGES_HARD

    def test_zero_max_pages_still_renders_one_page(self):
        """Clamped up to 1 rather than silently returning nothing."""
        assert len(pdf_to_images(_make_pdf(2), max_pages=0)) == 1

    def test_excessive_dpi_clamped(self):
        """A 10000-dpi request must render like MAX_DPI, not allocate for 10000."""
        capped = pdf_to_images(_make_pdf(1), dpi=MAX_DPI)[0][0]
        absurd = pdf_to_images(_make_pdf(1), dpi=10_000)[0][0]

        assert len(absurd) == len(capped)

    def test_zero_dpi_clamped_to_minimum(self):
        assert len(pdf_to_images(_make_pdf(1), dpi=0)) == 1


class TestBase64Wrapper:
    def test_returns_decodable_base64(self):
        results = pdf_to_base64_images(_make_pdf(1))

        assert len(results) == 1
        encoded, mimetype = results[0]
        assert mimetype == "image/png"
        assert base64.b64decode(encoded).startswith(b"\x89PNG\r\n\x1a\n")

    def test_matches_raw_conversion(self):
        raw = pdf_to_images(_make_pdf(2))
        encoded = pdf_to_base64_images(_make_pdf(2))

        assert len(encoded) == len(raw)
        assert base64.b64decode(encoded[0][0]) == raw[0][0]

    def test_corrupt_pdf_returns_empty_list(self):
        assert pdf_to_base64_images(b"not a pdf") == []
