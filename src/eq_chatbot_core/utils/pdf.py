"""PDF processing utilities for chatbot-core.

This module provides PDF-to-image conversion for LLM providers that
don't support native PDF processing (e.g., OpenAI, LangDock).

Requires the 'pdf' extra: pip install chatbot-core[pdf]
"""

import base64
import logging

_logger = logging.getLogger(__name__)

# Track if PyMuPDF is available
_pymupdf_available: bool | None = None

# Resource limits to bound memory/CPU when processing untrusted PDFs.
# These cap the damage from decompression bombs (tiny file -> thousands of pages)
# and extreme render requests (huge DPI -> hundreds of MB per page).
MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB raw input
MAX_PAGES_HARD = 50  # never render more pages than this, regardless of max_pages
MAX_DPI = 600  # cap render resolution


def is_pdf_conversion_available() -> bool:
    """Check if PDF conversion is available (PyMuPDF installed).

    Returns:
        bool: True if PyMuPDF is installed and functional
    """
    global _pymupdf_available
    if _pymupdf_available is None:
        try:
            import fitz  # noqa: F401

            _pymupdf_available = True
            _logger.debug("PyMuPDF (fitz) is available for PDF conversion")
        except ImportError:
            _pymupdf_available = False
            _logger.warning(
                "PyMuPDF not installed. PDF-to-image conversion unavailable. "
                "Install with: pip install chatbot-core[pdf]"
            )
    return _pymupdf_available


def pdf_to_images(
    pdf_data: bytes,
    max_pages: int = 10,
    dpi: int = 150,
    image_format: str = "png",
) -> list[tuple[bytes, str]]:
    """Convert PDF pages to images.

    Args:
        pdf_data: Raw PDF file bytes
        max_pages: Maximum number of pages to convert (default: 10)
        dpi: Resolution for rendering (default: 150, good balance of quality/size)
        image_format: Output format - 'png' or 'jpeg' (default: 'png')

    Returns:
        List of tuples: (image_bytes, mimetype)
        Empty list if conversion fails or PyMuPDF not available

    Raises:
        ValueError: If image_format is invalid or pdf_data exceeds MAX_PDF_BYTES
    """
    if not is_pdf_conversion_available():
        return []

    if image_format not in ("png", "jpeg"):
        raise ValueError(f"Unsupported image format: {image_format}. Use 'png' or 'jpeg'.")

    # Reject oversized input before handing it to the PDF parser (DoS guard).
    if len(pdf_data) > MAX_PDF_BYTES:
        raise ValueError(
            f"PDF too large: {len(pdf_data) / (1024 * 1024):.1f} MB (max: {MAX_PDF_BYTES / (1024 * 1024):.0f} MB)"
        )

    # Clamp render parameters to safe bounds (defends against decompression bombs
    # and extreme DPI requests even when callers pass large values).
    max_pages = max(1, min(max_pages, MAX_PAGES_HARD))
    dpi = max(1, min(dpi, MAX_DPI))

    try:
        import fitz

        images = []
        mimetype = f"image/{image_format}"

        # Open PDF from bytes
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        page_count = min(len(doc), max_pages)

        _logger.info(f"Converting PDF with {len(doc)} pages (processing {page_count})")

        # Calculate zoom factor from DPI (72 is the base PDF resolution)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        for page_num in range(page_count):
            try:
                page = doc[page_num]
                # Render page to pixmap (image)
                pix = page.get_pixmap(matrix=matrix, alpha=False)

                # Convert to bytes
                if image_format == "png":
                    img_bytes = pix.tobytes("png")
                else:
                    img_bytes = pix.tobytes("jpeg")

                images.append((img_bytes, mimetype))
                _logger.debug(f"Converted page {page_num + 1}/{page_count} to {image_format}")

            except Exception as e:
                _logger.error(f"Failed to convert page {page_num + 1}: {e}")
                continue

        doc.close()

        _logger.info(f"Successfully converted {len(images)} PDF pages to images")
        return images

    except Exception as e:
        _logger.error(f"PDF conversion failed: {e}")
        return []


def pdf_to_base64_images(
    pdf_data: bytes,
    max_pages: int = 10,
    dpi: int = 150,
    image_format: str = "png",
) -> list[tuple[str, str]]:
    """Convert PDF pages to base64-encoded images.

    Convenience wrapper around pdf_to_images that returns base64-encoded strings
    ready for LLM API calls.

    Args:
        pdf_data: Raw PDF file bytes
        max_pages: Maximum number of pages to convert (default: 10)
        dpi: Resolution for rendering (default: 150)
        image_format: Output format - 'png' or 'jpeg' (default: 'png')

    Returns:
        List of tuples: (base64_encoded_image, mimetype)
        Empty list if conversion fails
    """
    images = pdf_to_images(pdf_data, max_pages, dpi, image_format)
    return [(base64.b64encode(img_bytes).decode("utf-8"), mimetype) for img_bytes, mimetype in images]
