"""Unit tests for services/document_extractor.py.

The plain-text path is dependency-free and always tested; rich-format paths
are exercised only when markitdown is installed (docs extra).
"""

import pytest

from eq_chatbot_core.services.document_extractor import (
    MAX_DOC_BYTES,
    ExtractionResult,
    extract_markdown,
    is_document_extraction_available,
    supported_extensions,
)


class TestPlainTextExtraction:
    def test_markdown_passthrough(self):
        result = extract_markdown(b"# Title\n\nBody text.", "notes.md")
        assert isinstance(result, ExtractionResult)
        assert result.markdown == "# Title\n\nBody text."
        assert result.images == []
        assert result.warnings == []

    def test_txt_passthrough(self):
        result = extract_markdown("Umlaute: äöüß".encode(), "notes.txt")
        assert "äöüß" in result.markdown

    def test_latin1_fallback_warns(self):
        result = extract_markdown("Größe".encode("latin-1"), "legacy.txt")
        assert result.markdown
        assert any("Latin-1" in w for w in result.warnings)


class TestGuards:
    def test_too_large_rejected(self):
        with pytest.raises(ValueError, match="too large"):
            extract_markdown(b"x", "a.md", max_bytes=0)

    def test_default_limit_constant(self):
        assert MAX_DOC_BYTES == 50 * 1024 * 1024

    def test_unsupported_extension_rejected(self):
        with pytest.raises(ValueError, match="Unsupported"):
            extract_markdown(b"data", "malware.exe")

    def test_non_bytes_rejected(self):
        with pytest.raises(ValueError, match="bytes"):
            extract_markdown("not bytes", "a.md")

    def test_supported_extensions_always_include_plain_text(self):
        exts = supported_extensions()
        assert ".md" in exts
        assert ".txt" in exts


class TestRichFormats:
    def test_missing_markitdown_yields_warning_not_crash(self, monkeypatch):
        import eq_chatbot_core.services.document_extractor as mod

        monkeypatch.setattr(mod, "_markitdown_available", False)
        result = extract_markdown(b"%PDF-1.4 fake", "doc.pdf")
        assert result.markdown == ""
        assert any("markitdown" in w for w in result.warnings)

    @pytest.mark.skipif(
        not is_document_extraction_available(),
        reason="markitdown not installed (docs extra)",
    )
    def test_html_extraction(self):
        html = b"<html><body><h1>Hello</h1><p>World</p></body></html>"
        result = extract_markdown(html, "page.html")
        assert "Hello" in result.markdown
        assert "World" in result.markdown
