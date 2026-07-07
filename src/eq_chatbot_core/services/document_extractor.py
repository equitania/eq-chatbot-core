"""Document-to-Markdown extraction for knowledge ingestion.

This module converts uploaded office documents (PDF, DOCX, PPTX, XLSX, ODT,
Markdown, plain text) into Markdown so downstream consumers (e.g. the Odoo
``eq_knowledge_ai`` module) can feed them through an LLM restructuring step
and store them as knowledge-base articles.

Requires the 'docs' extra for rich formats: pip install eq-chatbot-core[docs]
Plain ``.md``/``.txt`` extraction works without any optional dependency.

Design notes (mirrors utils/pdf.py):

* optional imports are guarded — :func:`is_document_extraction_available`
  reports whether rich formats work, nothing raises at import time,
* hard resource limits bound memory/CPU when processing untrusted uploads,
* embedded images are returned as raw blobs so the caller decides where to
  store them (Odoo creates ``ir.attachment`` records and rewrites links).
"""

import io
import logging
import os
from dataclasses import dataclass, field

_logger = logging.getLogger(__name__)

# Track optional-dependency availability (resolved lazily, cached).
_markitdown_available: bool | None = None
_pymupdf_available: bool | None = None

# Resource limits to bound memory/CPU when processing untrusted documents.
MAX_DOC_BYTES = 50 * 1024 * 1024  # 50 MB raw input
MAX_IMAGES = 50  # never extract more embedded images than this
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # skip embedded images larger than 10 MB

# Formats extractable without optional dependencies.
PLAIN_TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
# Formats handled by markitdown (requires the 'docs' extra).
MARKITDOWN_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".csv"}
SUPPORTED_EXTENSIONS = PLAIN_TEXT_EXTENSIONS | MARKITDOWN_EXTENSIONS

_IMAGE_MIME_BY_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


@dataclass
class ExtractionResult:
    """Result of a document-to-Markdown extraction.

    Attributes:
        markdown: Extracted Markdown text ("" if nothing could be extracted).
        images: Embedded images as ``(bytes, mimetype)`` tuples (PDF only for
            now; other rich formats return an empty list plus a warning).
        warnings: Human-readable, non-fatal issues encountered on the way.
    """

    markdown: str = ""
    images: list[tuple[bytes, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def is_document_extraction_available() -> bool:
    """Check whether rich-format extraction is available (markitdown installed).

    Plain ``.md``/``.txt`` extraction always works; this flag only gates
    PDF/DOCX/PPTX/XLSX/ODT/HTML/CSV support.

    Returns:
        bool: True if markitdown is installed and importable.
    """
    global _markitdown_available
    if _markitdown_available is None:
        try:
            import markitdown  # noqa: F401

            _markitdown_available = True
            _logger.debug("markitdown is available for document extraction")
        except ImportError:
            _markitdown_available = False
            _logger.warning(
                "markitdown not installed. Rich document extraction unavailable. "
                "Install with: pip install eq-chatbot-core[docs]"
            )
    return _markitdown_available


def _is_pymupdf_available() -> bool:
    """PyMuPDF availability (used for embedded-image extraction from PDFs)."""
    global _pymupdf_available
    if _pymupdf_available is None:
        try:
            import fitz  # noqa: F401

            _pymupdf_available = True
        except ImportError:
            _pymupdf_available = False
    return _pymupdf_available


def supported_extensions() -> set[str]:
    """Extensions the extractor can currently handle (given installed extras)."""
    if is_document_extraction_available():
        return set(SUPPORTED_EXTENSIONS)
    return set(PLAIN_TEXT_EXTENSIONS)


def extract_markdown(file_bytes: bytes, filename: str, max_bytes: int = MAX_DOC_BYTES) -> ExtractionResult:
    """Convert an uploaded document into Markdown.

    Args:
        file_bytes: Raw document bytes.
        filename: Original filename — the extension selects the extraction path.
        max_bytes: Reject inputs larger than this (DoS guard).

    Returns:
        ExtractionResult: Markdown + embedded images + warnings. On failure the
        markdown is "" and the reason lands in ``warnings`` (callers surface it
        to the user); only invalid *arguments* raise.

    Raises:
        ValueError: If ``file_bytes`` exceeds ``max_bytes`` or the extension is
            unsupported — programmer/caller errors, not content problems.
    """
    if not isinstance(file_bytes, (bytes, bytearray)):
        raise ValueError("file_bytes must be bytes")
    if len(file_bytes) > max_bytes:
        raise ValueError(f"Document too large: {len(file_bytes)} bytes (max {max_bytes})")
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported document type: '{ext or filename}'")

    if ext in PLAIN_TEXT_EXTENSIONS:
        return _extract_plain_text(bytes(file_bytes))

    result = _extract_with_markitdown(bytes(file_bytes), ext)
    if ext == ".pdf":
        _append_pdf_images(bytes(file_bytes), result)
    elif result.markdown:
        result.warnings.append(f"Embedded images are not extracted from {ext} files yet.")
    return result


def _extract_plain_text(file_bytes: bytes) -> ExtractionResult:
    """Markdown/plain-text passthrough (dependency-free)."""
    try:
        return ExtractionResult(markdown=file_bytes.decode("utf-8"))
    except UnicodeDecodeError:
        try:
            return ExtractionResult(
                markdown=file_bytes.decode("latin-1"),
                warnings=["File was not valid UTF-8; decoded as Latin-1."],
            )
        except Exception:  # pragma: no cover - latin-1 decodes any byte string
            return ExtractionResult(warnings=["Could not decode text file."])


def _extract_with_markitdown(file_bytes: bytes, ext: str) -> ExtractionResult:
    """Rich-format extraction via markitdown (requires the 'docs' extra)."""
    if not is_document_extraction_available():
        return ExtractionResult(
            warnings=[
                "markitdown is not installed — rich document extraction is unavailable. Install eq-chatbot-core[docs]."
            ]
        )
    try:
        from markitdown import MarkItDown

        converter = MarkItDown(enable_plugins=False)
        try:
            # markitdown >= 0.1.x routes format detection through StreamInfo.
            from markitdown import StreamInfo

            converted = converter.convert_stream(io.BytesIO(file_bytes), stream_info=StreamInfo(extension=ext))
        except ImportError:
            # Older releases accept the extension as a keyword argument.
            converted = converter.convert_stream(io.BytesIO(file_bytes), file_extension=ext)
        markdown = (getattr(converted, "text_content", "") or "").strip()
        if not markdown:
            return ExtractionResult(warnings=["The document contained no extractable text."])
        return ExtractionResult(markdown=markdown)
    except Exception as err:  # noqa: BLE001 - any converter failure is a content problem
        _logger.warning("document extraction failed for %s: %s", ext, err)
        return ExtractionResult(warnings=[f"Extraction failed: {err}"])


def _append_pdf_images(file_bytes: bytes, result: ExtractionResult) -> None:
    """Collect embedded images from a PDF (best effort, capped)."""
    if not result.markdown:
        return
    if not _is_pymupdf_available():
        result.warnings.append("PyMuPDF not installed — embedded PDF images were not extracted.")
        return
    try:
        import fitz

        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            seen_xrefs = set()
            for page in doc:
                for image_info in page.get_images(full=True):
                    xref = image_info[0]
                    if xref in seen_xrefs:
                        continue
                    seen_xrefs.add(xref)
                    if len(result.images) >= MAX_IMAGES:
                        result.warnings.append(f"Image limit reached ({MAX_IMAGES}); remaining images skipped.")
                        return
                    extracted = doc.extract_image(xref)
                    blob = extracted.get("image") or b""
                    if not blob or len(blob) > MAX_IMAGE_BYTES:
                        continue
                    mimetype = _IMAGE_MIME_BY_EXT.get((extracted.get("ext") or "").lower())
                    if mimetype:
                        result.images.append((blob, mimetype))
    except Exception as err:  # noqa: BLE001 - image extraction is best effort
        _logger.warning("PDF image extraction failed: %s", err)
        result.warnings.append(f"Embedded PDF images could not be extracted: {err}")
