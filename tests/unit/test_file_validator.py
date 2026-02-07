"""
Unit tests for file validation module.

Tests the multi-layer file validation including extension checks,
MIME type verification, content scanning, size limits, and filename
sanitization.
"""

from unittest.mock import MagicMock, patch

import pytest

from eq_chatbot_core.security.file_validator import (
    DANGEROUS_HEADER_PATTERNS,
    DANGEROUS_TEXT_PATTERNS,
    OFFICE_MACRO_PATTERNS,
    FileTypeConfig,
    FileValidationResult,
    FileValidator,
    create_validator,
    is_magic_available,
)


# =============================================================================
# Common Fixtures and Helpers
# =============================================================================


@pytest.fixture
def validator():
    """Create a FileValidator with magic disabled (pure Python checks)."""
    return FileValidator(use_magic=False)


@pytest.fixture
def validator_with_magic():
    """Create a FileValidator with magic enabled (will only work if installed)."""
    return FileValidator(use_magic=True)


@pytest.fixture
def image_types():
    """Common image file type configurations."""
    return [
        FileTypeConfig(extension="png", mime_type="image/png", max_size_mb=5.0, supports_vision=True),
        FileTypeConfig(extension="jpg", mime_type="image/jpeg", max_size_mb=5.0, supports_vision=True),
        FileTypeConfig(extension="gif", mime_type="image/gif", max_size_mb=2.0, supports_vision=True),
        FileTypeConfig(extension="webp", mime_type="image/webp", max_size_mb=5.0, supports_vision=True),
    ]


@pytest.fixture
def document_types():
    """Common document file type configurations."""
    return [
        FileTypeConfig(extension="pdf", mime_type="application/pdf", max_size_mb=10.0, supports_document=True),
        FileTypeConfig(extension="txt", mime_type="text/plain", max_size_mb=1.0),
        FileTypeConfig(extension="csv", mime_type="text/csv", max_size_mb=5.0),
        FileTypeConfig(extension="json", mime_type="application/json", max_size_mb=2.0),
    ]


@pytest.fixture
def office_types():
    """Office document file type configurations."""
    return [
        FileTypeConfig(extension="docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", max_size_mb=10.0),
        FileTypeConfig(extension="xlsx", mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", max_size_mb=10.0),
        FileTypeConfig(extension="pptx", mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", max_size_mb=20.0),
    ]


@pytest.fixture
def text_types():
    """Text-based file type configurations including HTML/XML."""
    return [
        FileTypeConfig(extension="txt", mime_type="text/plain", max_size_mb=1.0),
        FileTypeConfig(extension="html", mime_type="text/html", max_size_mb=1.0),
        FileTypeConfig(extension="xml", mime_type="application/xml", max_size_mb=2.0),
        FileTypeConfig(extension="svg", mime_type="image/svg+xml", max_size_mb=1.0),
        FileTypeConfig(extension="csv", mime_type="text/csv", max_size_mb=5.0),
    ]


@pytest.fixture
def all_types(image_types, document_types, office_types):
    """Combined list of all file type configurations."""
    return image_types + document_types + office_types


def make_content(size_mb: float) -> bytes:
    """Create content of approximately the given size in MB."""
    return b"\x00" * int(size_mb * 1024 * 1024)


# =============================================================================
# FileTypeConfig Dataclass Tests
# =============================================================================


@pytest.mark.unit
class TestFileTypeConfig:
    """Test FileTypeConfig dataclass."""

    def test_default_values(self):
        """Test FileTypeConfig has correct defaults."""
        config = FileTypeConfig(extension="txt", mime_type="text/plain")

        assert config.extension == "txt"
        assert config.mime_type == "text/plain"
        assert config.max_size_mb == 10.0
        assert config.scan_content is True
        assert config.supports_vision is False
        assert config.supports_document is False

    def test_custom_values(self):
        """Test FileTypeConfig with custom values."""
        config = FileTypeConfig(
            extension="png",
            mime_type="image/png",
            max_size_mb=5.0,
            scan_content=False,
            supports_vision=True,
            supports_document=False,
        )

        assert config.extension == "png"
        assert config.mime_type == "image/png"
        assert config.max_size_mb == 5.0
        assert config.scan_content is False
        assert config.supports_vision is True

    def test_document_config(self):
        """Test FileTypeConfig for document types."""
        config = FileTypeConfig(
            extension="pdf",
            mime_type="application/pdf",
            max_size_mb=20.0,
            supports_document=True,
        )

        assert config.supports_document is True
        assert config.supports_vision is False
        assert config.max_size_mb == 20.0


# =============================================================================
# FileValidationResult Dataclass Tests
# =============================================================================


@pytest.mark.unit
class TestFileValidationResult:
    """Test FileValidationResult dataclass."""

    def test_valid_result(self):
        """Test a valid validation result."""
        result = FileValidationResult(
            is_valid=True,
            detected_mime="image/png",
            sanitized_filename="test.png",
        )

        assert result.is_valid is True
        assert result.error_message is None
        assert result.detected_mime == "image/png"
        assert result.sanitized_filename == "test.png"

    def test_invalid_result(self):
        """Test an invalid validation result."""
        result = FileValidationResult(
            is_valid=False,
            error_message="Extension not allowed",
        )

        assert result.is_valid is False
        assert result.error_message == "Extension not allowed"
        assert result.detected_mime is None
        assert result.sanitized_filename is None

    def test_default_none_values(self):
        """Test that optional fields default to None."""
        result = FileValidationResult(is_valid=True)

        assert result.error_message is None
        assert result.detected_mime is None
        assert result.sanitized_filename is None


# =============================================================================
# Layer 1: Extension Validation Tests
# =============================================================================


@pytest.mark.unit
class TestExtensionValidation:
    """Test extension-based file validation (Layer 1)."""

    def test_valid_png_extension(self, validator, image_types):
        """Test that .png files pass extension check."""
        result = validator.validate("photo.png", b"\x89PNG\r\n\x1a\n", image_types)

        assert result.is_valid is True

    def test_valid_jpg_extension(self, validator, image_types):
        """Test that .jpg files pass extension check."""
        result = validator.validate("photo.jpg", b"\xff\xd8\xff\xe0", image_types)

        assert result.is_valid is True

    def test_valid_pdf_extension(self, validator, document_types):
        """Test that .pdf files pass extension check."""
        result = validator.validate("document.pdf", b"%PDF-1.4 test content", document_types)

        assert result.is_valid is True

    def test_case_insensitive_extension(self, validator, image_types):
        """Test that extension matching is case-insensitive."""
        result = validator.validate("photo.PNG", b"\x89PNG\r\n\x1a\n", image_types)

        assert result.is_valid is True

    def test_uppercase_extension(self, validator, image_types):
        """Test uppercase extension is accepted."""
        result = validator.validate("photo.JPG", b"\xff\xd8\xff\xe0", image_types)

        assert result.is_valid is True

    def test_mixed_case_extension(self, validator, document_types):
        """Test mixed case extension is accepted."""
        result = validator.validate("data.Csv", b"a,b,c\n1,2,3\n", document_types)

        assert result.is_valid is True

    def test_invalid_extension_exe(self, validator, image_types):
        """Test that .exe files are rejected."""
        result = validator.validate("malware.exe", b"MZ\x90\x00", image_types)

        assert result.is_valid is False
        assert "not allowed" in result.error_message
        assert ".exe" in result.error_message

    def test_invalid_extension_php(self, validator, image_types):
        """Test that .php files are rejected."""
        result = validator.validate("shell.php", b"<?php echo 'pwned'; ?>", image_types)

        assert result.is_valid is False
        assert ".php" in result.error_message

    def test_invalid_extension_sh(self, validator, document_types):
        """Test that .sh files are rejected."""
        result = validator.validate("script.sh", b"#!/bin/bash\nrm -rf /", document_types)

        assert result.is_valid is False

    def test_double_extension_attack(self, validator, image_types):
        """Test that double-extension attack is handled (uses last extension)."""
        result = validator.validate("photo.exe.png", b"\x89PNG\r\n\x1a\n", image_types)

        # Should pass because last extension is .png
        assert result.is_valid is True

    def test_no_extension(self, validator, image_types):
        """Test that files without extension are rejected."""
        result = validator.validate("noextension", b"some data", image_types)

        assert result.is_valid is False
        assert "no extension" in result.error_message.lower()

    def test_empty_filename(self, validator, image_types):
        """Test that empty filename is rejected."""
        result = validator.validate("", b"some data", image_types)

        assert result.is_valid is False

    def test_dot_only_filename(self, validator, image_types):
        """Test that '.' only filename is rejected."""
        result = validator.validate(".", b"some data", image_types)

        assert result.is_valid is False

    def test_allowed_extensions_listed_in_error(self, validator, image_types):
        """Test that error message lists allowed extensions."""
        result = validator.validate("data.exe", b"MZ", image_types)

        assert result.is_valid is False
        assert ".png" in result.error_message
        assert ".jpg" in result.error_message


# =============================================================================
# Layer 2: MIME Type Validation Tests
# =============================================================================


@pytest.mark.unit
class TestMimeTypeValidation:
    """Test MIME type validation (Layer 2)."""

    def test_magic_disabled_skips_mime_check(self, validator, image_types):
        """Test that MIME check is skipped when magic is disabled."""
        # With use_magic=False, any content passes MIME validation
        result = validator.validate("photo.png", b"not actually a PNG", image_types)

        assert result.is_valid is True
        assert result.detected_mime == "image/png"

    def test_magic_enabled_detects_mismatch(self, image_types):
        """Test MIME mismatch detection when magic is available."""
        mock_magic = MagicMock()
        mock_magic.from_buffer.return_value = "application/pdf"

        with patch("eq_chatbot_core.security.file_validator.magic", mock_magic, create=True):
            with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
                validator = FileValidator(use_magic=True)
                result = validator.validate("fake.png", b"%PDF-1.4 content", image_types)

        assert result.is_valid is False
        assert "MIME type mismatch" in result.error_message
        assert "image/png" in result.error_message
        assert result.detected_mime == "application/pdf"

    def test_magic_enabled_accepts_match(self, image_types):
        """Test that matching MIME type passes when magic is available."""
        mock_magic = MagicMock()
        mock_magic.from_buffer.return_value = "image/png"

        with patch("eq_chatbot_core.security.file_validator.magic", mock_magic, create=True):
            with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
                validator = FileValidator(use_magic=True)
                result = validator.validate("photo.png", b"\x89PNG\r\n\x1a\n", image_types)

        assert result.is_valid is True

    def test_csv_alias_text_csv_accepts_application_csv(self, document_types):
        """Test that text/csv accepts application/csv alias."""
        mock_magic = MagicMock()
        mock_magic.from_buffer.return_value = "application/csv"

        with patch("eq_chatbot_core.security.file_validator.magic", mock_magic, create=True):
            with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
                validator = FileValidator(use_magic=True)
                result = validator.validate("data.csv", b"a,b,c\n1,2,3", document_types)

        assert result.is_valid is True

    def test_text_plain_accepts_application_csv(self, document_types):
        """Test that text/plain accepts application/csv (CSV detected as plain text)."""
        mock_magic = MagicMock()
        mock_magic.from_buffer.return_value = "application/csv"

        with patch("eq_chatbot_core.security.file_validator.magic", mock_magic, create=True):
            with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
                validator = FileValidator(use_magic=True)
                result = validator.validate("data.txt", b"a,b,c\n1,2,3", document_types)

        assert result.is_valid is True

    def test_jpeg_alias_accepts_image_jpg(self, image_types):
        """Test that image/jpeg accepts image/jpg alias."""
        mock_magic = MagicMock()
        mock_magic.from_buffer.return_value = "image/jpg"

        with patch("eq_chatbot_core.security.file_validator.magic", mock_magic, create=True):
            with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
                validator = FileValidator(use_magic=True)
                result = validator.validate("photo.jpg", b"\xff\xd8\xff", image_types)

        assert result.is_valid is True

    def test_json_alias_accepts_text_json(self, document_types):
        """Test that application/json accepts text/json alias."""
        mock_magic = MagicMock()
        mock_magic.from_buffer.return_value = "text/json"

        with patch("eq_chatbot_core.security.file_validator.magic", mock_magic, create=True):
            with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
                validator = FileValidator(use_magic=True)
                result = validator.validate("data.json", b'{"key": "value"}', document_types)

        assert result.is_valid is True

    def test_reverse_alias_application_csv_detected_as_text_csv(self, document_types):
        """Test reverse alias: text/plain config accepts text/csv via reverse lookup.

        The alias map has 'text/plain': ['application/csv']. When expected is
        'application/csv' (an alias) and detected is 'text/plain' (a primary),
        the reverse check finds the match.
        """
        mock_magic = MagicMock()
        mock_magic.from_buffer.return_value = "text/csv"

        # Create a type where expected MIME is application/csv (which is an alias)
        types = [FileTypeConfig(extension="csv", mime_type="application/csv", max_size_mb=5.0)]

        with patch("eq_chatbot_core.security.file_validator.magic", mock_magic, create=True):
            with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
                validator = FileValidator(use_magic=True)
                # Expected: application/csv, Detected: text/csv
                # Reverse check: text/csv is a primary key with alias ['application/csv']
                # application/csv is in that alias list -> match
                result = validator.validate("data.csv", b"a,b,c\n1,2,3", types)

        assert result.is_valid is True

    def test_csv_detected_as_text_plain_rejected(self, document_types):
        """Test that text/csv config rejects text/plain detection (no alias match).

        text/csv aliases are ['application/csv']. text/plain is NOT in that list,
        so it should be rejected as a MIME mismatch.
        """
        mock_magic = MagicMock()
        mock_magic.from_buffer.return_value = "text/plain"

        with patch("eq_chatbot_core.security.file_validator.magic", mock_magic, create=True):
            with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
                validator = FileValidator(use_magic=True)
                result = validator.validate("data.csv", b"a,b,c\n1,2,3", document_types)

        assert result.is_valid is False
        assert "MIME type mismatch" in result.error_message

    def test_xml_alias_removed_for_security(self, text_types):
        """SECURITY TEST: Verify that application/xml no longer accepts text/xml alias.

        The old mapping 'application/xml': ['text/xml'] was removed to prevent
        cross-type confusion attacks (e.g., HTML served as XML).
        """
        mock_magic = MagicMock()
        mock_magic.from_buffer.return_value = "text/xml"

        with patch("eq_chatbot_core.security.file_validator.magic", mock_magic, create=True):
            with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
                validator = FileValidator(use_magic=True)
                result = validator.validate("data.xml", b"<root><item/></root>", text_types)

        assert result.is_valid is False
        assert "MIME type mismatch" in result.error_message
        assert result.detected_mime == "text/xml"

    def test_completely_wrong_mime_rejected(self, image_types):
        """Test that completely mismatched MIME types are rejected."""
        mock_magic = MagicMock()
        mock_magic.from_buffer.return_value = "text/html"

        with patch("eq_chatbot_core.security.file_validator.magic", mock_magic, create=True):
            with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
                validator = FileValidator(use_magic=True)
                result = validator.validate("image.png", b"<html>not an image</html>", image_types)

        assert result.is_valid is False
        assert "MIME type mismatch" in result.error_message


# =============================================================================
# Layer 3: Content Scanning Tests
# =============================================================================


@pytest.mark.unit
class TestContentScanning:
    """Test dangerous content detection (Layer 3)."""

    # --- Dangerous header patterns ---

    def test_mz_header_detected(self, validator, document_types):
        """Test that MZ (Windows executable) header is detected."""
        content = b"MZ\x90\x00\x03\x00\x00\x00"
        result = validator.validate("document.pdf", content, document_types)

        assert result.is_valid is False
        assert "executable" in result.error_message.lower()

    def test_elf_header_detected(self, validator, document_types):
        """Test that ELF (Linux binary) header is detected."""
        content = b"\x7fELF\x02\x01\x01\x00"
        result = validator.validate("document.pdf", content, document_types)

        assert result.is_valid is False
        assert "executable" in result.error_message.lower()

    def test_shebang_header_detected(self, validator, document_types):
        """Test that shebang (#!/) header is detected."""
        content = b"#!/bin/bash\nrm -rf /\n"
        result = validator.validate("data.txt", content, document_types)

        assert result.is_valid is False
        assert "executable" in result.error_message.lower()

    def test_php_header_detected(self, validator, document_types):
        """Test that PHP script header is detected."""
        content = b"<?php\necho shell_exec($_GET['cmd']);\n?>"
        result = validator.validate("data.txt", content, document_types)

        assert result.is_valid is False
        assert "executable" in result.error_message.lower()

    def test_asp_header_detected(self, validator, document_types):
        """Test that ASP/JSP header (<%...) is detected."""
        content = b"<%@ Page Language=\"C#\" %>\n<script runat=\"server\">"
        result = validator.validate("data.txt", content, document_types)

        assert result.is_valid is False
        assert "executable" in result.error_message.lower()

    # --- Dangerous text patterns (only checked in text-like files) ---

    def test_script_tag_detected_in_text(self, validator, text_types):
        """Test that <script> tags are detected in text files."""
        content = b"Hello world <script>alert('xss')</script>"
        result = validator.validate("page.html", content, text_types)

        assert result.is_valid is False
        assert "script" in result.error_message.lower()

    def test_script_tag_uppercase_detected(self, validator, text_types):
        """Test that uppercase <SCRIPT> tags are detected."""
        content = b"Hello <SCRIPT>alert('xss')</SCRIPT>"
        result = validator.validate("page.html", content, text_types)

        assert result.is_valid is False

    def test_javascript_url_detected_in_text(self, validator, text_types):
        """Test that javascript: URLs are detected in text files."""
        content = b'<a href="javascript:alert(1)">click</a>'
        result = validator.validate("page.html", content, text_types)

        assert result.is_valid is False
        assert "script" in result.error_message.lower()

    def test_vbscript_url_detected_in_text(self, validator, text_types):
        """Test that vbscript: URLs are detected in text files."""
        content = b'<a href="vbscript:MsgBox(1)">click</a>'
        result = validator.validate("page.html", content, text_types)

        assert result.is_valid is False

    def test_script_in_svg_detected(self, validator, text_types):
        """Test that scripts in SVG files are detected."""
        content = b'<svg><script>alert("xss")</script></svg>'
        result = validator.validate("image.svg", content, text_types)

        assert result.is_valid is False

    def test_script_in_xml_detected(self, validator, text_types):
        """Test that scripts in XML files are detected."""
        content = b'<?xml version="1.0"?><data><script>evil()</script></data>'
        result = validator.validate("data.xml", content, text_types)

        assert result.is_valid is False

    def test_null_bytes_in_text_detected(self, validator, text_types):
        """Test that null bytes in text files are detected (binary injection)."""
        content = b"Normal text\x00hidden binary\x00data"
        result = validator.validate("data.txt", content, text_types)

        assert result.is_valid is False
        assert "binary" in result.error_message.lower()

    def test_script_not_checked_in_binary_files(self, validator, image_types):
        """Test that script patterns are NOT checked in binary file types."""
        # Binary content that happens to contain <script pattern
        content = b"\x89PNG\r\n\x1a\n" + b"<script>" + b"\x00" * 100
        result = validator.validate("photo.png", content, image_types)

        # Should pass because binary files skip text pattern checks
        assert result.is_valid is True

    def test_clean_text_file_passes(self, validator, text_types):
        """Test that clean text content passes scanning."""
        content = b"This is a perfectly normal text file.\nWith multiple lines.\n"
        result = validator.validate("readme.txt", content, text_types)

        assert result.is_valid is True

    def test_clean_csv_passes(self, validator, text_types):
        """Test that clean CSV content passes scanning."""
        content = b"name,age,city\nAlice,30,Berlin\nBob,25,Munich\n"
        result = validator.validate("data.csv", content, text_types)

        assert result.is_valid is True

    # --- Office macro detection ---

    def test_vba_project_bin_detected_in_docx(self, validator, office_types):
        """Test that vbaProject.bin is detected in DOCX files."""
        content = b"PK\x03\x04" + b"\x00" * 50 + b"vbaProject.bin" + b"\x00" * 50
        result = validator.validate("document.docx", content, office_types)

        assert result.is_valid is False
        assert "macro" in result.error_message.lower()

    def test_excel_vba_path_detected(self, validator, office_types):
        """Test that xl/vbaProject path is detected in XLSX files."""
        content = b"PK\x03\x04" + b"\x00" * 50 + b"xl/vbaProject" + b"\x00" * 50
        result = validator.validate("spreadsheet.xlsx", content, office_types)

        assert result.is_valid is False
        assert "macro" in result.error_message.lower()

    def test_word_vba_path_detected(self, validator, office_types):
        """Test that word/vbaProject path is detected in DOCX files."""
        content = b"PK\x03\x04" + b"\x00" * 50 + b"word/vbaProject" + b"\x00" * 50
        result = validator.validate("document.docx", content, office_types)

        assert result.is_valid is False

    def test_ppt_vba_path_detected(self, validator, office_types):
        """Test that ppt/vbaProject path is detected in PPTX files."""
        content = b"PK\x03\x04" + b"\x00" * 50 + b"ppt/vbaProject" + b"\x00" * 50
        result = validator.validate("presentation.pptx", content, office_types)

        assert result.is_valid is False

    def test_clean_office_file_passes(self, validator, office_types):
        """Test that clean Office files (no macros) pass scanning."""
        content = b"PK\x03\x04" + b"\x00" * 100 + b"[Content_Types].xml" + b"\x00" * 100
        result = validator.validate("document.docx", content, office_types)

        assert result.is_valid is True

    def test_scan_content_disabled_skips_check(self):
        """Test that scan_content=False skips content scanning."""
        validator = FileValidator(use_magic=False)
        types = [FileTypeConfig(extension="bin", mime_type="application/octet-stream", scan_content=False)]

        # Executable header should be ignored when scan_content=False
        content = b"MZ\x90\x00\x03\x00\x00\x00"
        result = validator.validate("data.bin", content, types)

        assert result.is_valid is True


# =============================================================================
# Layer 4: File Size Validation Tests
# =============================================================================


@pytest.mark.unit
class TestSizeValidation:
    """Test file size validation (Layer 4)."""

    def test_file_within_size_limit(self, validator):
        """Test that a file within the size limit passes."""
        types = [FileTypeConfig(extension="txt", mime_type="text/plain", max_size_mb=1.0)]
        content = b"A" * (512 * 1024)  # 0.5 MB

        result = validator.validate("small.txt", content, types)

        assert result.is_valid is True

    def test_file_exceeds_size_limit(self, validator):
        """Test that a file exceeding the size limit is rejected."""
        types = [FileTypeConfig(extension="txt", mime_type="text/plain", max_size_mb=0.001)]
        content = b"A" * (2 * 1024)  # ~2 KB, limit is ~1 KB

        result = validator.validate("large.txt", content, types)

        assert result.is_valid is False
        assert "too large" in result.error_message.lower()
        assert "max:" in result.error_message.lower()

    def test_file_exactly_at_size_limit(self, validator):
        """Test that a file at exactly the size limit passes."""
        types = [FileTypeConfig(extension="txt", mime_type="text/plain", max_size_mb=1.0)]
        content = b"A" * (1024 * 1024)  # Exactly 1 MB

        result = validator.validate("exact.txt", content, types)

        assert result.is_valid is True

    def test_empty_file_passes_size_check(self, validator):
        """Test that an empty file passes size validation."""
        types = [FileTypeConfig(extension="txt", mime_type="text/plain", max_size_mb=1.0)]

        result = validator.validate("empty.txt", b"", types)

        assert result.is_valid is True

    def test_different_limits_per_type(self, validator):
        """Test that different file types have different size limits."""
        types = [
            FileTypeConfig(extension="txt", mime_type="text/plain", max_size_mb=0.001),
            FileTypeConfig(extension="pdf", mime_type="application/pdf", max_size_mb=10.0),
        ]
        content = b"A" * (5 * 1024)  # ~5 KB

        # txt has 0.001 MB (~1KB) limit - should fail
        result_txt = validator.validate("data.txt", content, types)
        assert result_txt.is_valid is False

        # pdf has 10 MB limit - should pass
        result_pdf = validator.validate("data.pdf", content, types)
        assert result_pdf.is_valid is True

    def test_large_image_rejected(self, validator, image_types):
        """Test that an image exceeding the limit is rejected."""
        # image_types have 5.0 MB limit for png
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * (6 * 1024 * 1024)  # ~6 MB

        result = validator.validate("huge.png", content, image_types)

        assert result.is_valid is False
        assert "too large" in result.error_message.lower()


# =============================================================================
# Layer 5: Filename Sanitization Tests
# =============================================================================


@pytest.mark.unit
class TestFilenameSanitization:
    """Test filename sanitization (Layer 5) and sanitize_filename method."""

    def test_normal_filename_unchanged(self, validator):
        """Test that normal filenames are not modified."""
        sanitized = validator.sanitize_filename("document.pdf")
        assert sanitized == "document.pdf"

    def test_path_traversal_prevented(self, validator):
        """Test that path traversal sequences are removed."""
        sanitized = validator.sanitize_filename("../../../etc/passwd")
        assert ".." not in sanitized
        assert "/" not in sanitized
        assert sanitized == "passwd"

    def test_windows_path_traversal_prevented(self, validator):
        """Test that Windows-style path traversal characters are sanitized.

        Note: On POSIX systems, backslash is not a path separator, so
        os.path.basename does not split on it. However, the dangerous
        character replacement (backslash is in the regex) sanitizes it.
        """
        sanitized = validator.sanitize_filename("..\\..\\windows\\system32\\cmd.exe")
        # Backslashes are replaced by the dangerous character regex
        assert "\\" not in sanitized

    def test_absolute_path_stripped(self, validator):
        """Test that absolute paths are stripped to basename."""
        sanitized = validator.sanitize_filename("/usr/local/bin/script.sh")
        assert sanitized == "script.sh"

    def test_null_bytes_removed(self, validator):
        """Test that null bytes are removed from filename."""
        sanitized = validator.sanitize_filename("file\x00.txt")
        assert "\x00" not in sanitized
        assert sanitized == "file.txt"

    def test_hidden_file_dot_stripped(self, validator):
        """Test that leading dots are stripped (prevent hidden files)."""
        sanitized = validator.sanitize_filename(".htaccess")
        assert not sanitized.startswith(".")
        assert sanitized == "htaccess"

    def test_multiple_leading_dots_stripped(self, validator):
        """Test that multiple leading dots are all stripped."""
        sanitized = validator.sanitize_filename("...hidden.txt")
        assert not sanitized.startswith(".")
        assert sanitized == "hidden.txt"

    def test_unicode_normalized(self, validator):
        """Test that unicode characters are normalized."""
        # NFKD normalization decomposes characters
        sanitized = validator.sanitize_filename("caf\u00e9.txt")
        # After NFKD normalization, e-acute becomes e + combining accent
        assert "txt" in sanitized

    def test_dangerous_characters_replaced(self, validator):
        """Test that dangerous characters are replaced with underscores."""
        sanitized = validator.sanitize_filename('file<>:"/\\|?*.txt')
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert ":" not in sanitized
        assert '"' not in sanitized
        assert "|" not in sanitized
        assert "?" not in sanitized
        assert "*" not in sanitized
        assert sanitized.endswith(".txt")

    def test_control_characters_replaced(self, validator):
        """Test that control characters (0x00-0x1f) are replaced."""
        sanitized = validator.sanitize_filename("file\x01\x02\x03.txt")
        assert "\x01" not in sanitized
        assert "\x02" not in sanitized
        assert "\x03" not in sanitized

    def test_long_filename_truncated(self, validator):
        """Test that very long filenames are truncated."""
        long_name = "a" * 300 + ".pdf"
        sanitized = validator.sanitize_filename(long_name)

        # Name part should be max 200 characters
        name_part = sanitized.rsplit(".", 1)[0]
        assert len(name_part) <= 200
        assert sanitized.endswith(".pdf")

    def test_exactly_200_char_name_not_truncated(self, validator):
        """Test that a filename at exactly 200 chars is not truncated."""
        name = "a" * 200 + ".txt"
        sanitized = validator.sanitize_filename(name)

        name_part = sanitized.rsplit(".", 1)[0]
        assert len(name_part) == 200

    def test_empty_filename_returns_unnamed(self, validator):
        """Test that empty filename returns 'unnamed_file'."""
        sanitized = validator.sanitize_filename("")
        assert sanitized == "unnamed_file"

    def test_none_like_empty_filename(self, validator):
        """Test that empty string gives fallback name."""
        sanitized = validator.sanitize_filename("")
        assert sanitized == "unnamed_file"

    def test_only_dots_and_slashes(self, validator):
        """Test filename with only dots and path separators."""
        sanitized = validator.sanitize_filename("../../..")
        # After basename and dot stripping, should get fallback name
        assert sanitized == "file"

    def test_filename_with_spaces_preserved(self, validator):
        """Test that spaces in filenames are preserved."""
        sanitized = validator.sanitize_filename("my document file.pdf")
        assert " " in sanitized
        assert sanitized == "my document file.pdf"

    def test_filename_with_dashes_and_underscores(self, validator):
        """Test that dashes and underscores are preserved."""
        sanitized = validator.sanitize_filename("my-file_name-2024.txt")
        assert sanitized == "my-file_name-2024.txt"

    def test_sanitized_filename_in_validation_result(self, validator, document_types):
        """Test that sanitized filename appears in validation result."""
        result = validator.validate("../../../evil.pdf", b"%PDF-1.4 content", document_types)

        assert result.is_valid is True
        assert result.sanitized_filename is not None
        assert ".." not in result.sanitized_filename
        assert result.sanitized_filename == "evil.pdf"

    def test_no_extension_after_sanitization(self, validator):
        """Test file that loses extension during sanitization still works."""
        sanitized = validator.sanitize_filename("justdots...")
        # After stripping leading dots from basename, we get "justdots..."
        # The basename is "justdots...", dots stripped from start only
        assert sanitized  # Should return something non-empty


# =============================================================================
# Full Validation Pipeline Tests
# =============================================================================


@pytest.mark.unit
class TestFullValidationPipeline:
    """Test the complete 5-layer validation pipeline."""

    def test_valid_png_full_pipeline(self, validator, image_types):
        """Test that a valid PNG passes all layers."""
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = validator.validate("photo.png", content, image_types)

        assert result.is_valid is True
        assert result.detected_mime == "image/png"
        assert result.sanitized_filename == "photo.png"
        assert result.error_message is None

    def test_valid_pdf_full_pipeline(self, validator, document_types):
        """Test that a valid PDF passes all layers."""
        content = b"%PDF-1.4 " + b"\x00" * 100
        result = validator.validate("report.pdf", content, document_types)

        assert result.is_valid is True
        assert result.detected_mime == "application/pdf"
        assert result.sanitized_filename == "report.pdf"

    def test_valid_csv_full_pipeline(self, validator, document_types):
        """Test that a valid CSV passes all layers."""
        content = b"id,name,value\n1,Alice,100\n2,Bob,200\n"
        result = validator.validate("data.csv", content, document_types)

        assert result.is_valid is True
        assert result.sanitized_filename == "data.csv"

    def test_invalid_extension_stops_early(self, validator, image_types):
        """Test that invalid extension stops validation at Layer 1."""
        result = validator.validate("virus.exe", b"safe content", image_types)

        assert result.is_valid is False
        assert "not allowed" in result.error_message
        # Should not have MIME info since it stopped at extension check
        assert result.detected_mime is None

    def test_dangerous_content_stops_at_layer_3(self, validator, document_types):
        """Test that dangerous content is caught at Layer 3."""
        content = b"MZ\x90\x00" + b"\x00" * 100
        result = validator.validate("data.pdf", content, document_types)

        assert result.is_valid is False
        assert "executable" in result.error_message.lower()

    def test_oversized_file_stops_at_layer_4(self, validator):
        """Test that oversized file is caught at Layer 4."""
        types = [FileTypeConfig(extension="txt", mime_type="text/plain", max_size_mb=0.001)]
        content = b"A" * (100 * 1024)  # 100 KB, limit ~1 KB

        result = validator.validate("big.txt", content, types)

        assert result.is_valid is False
        assert "too large" in result.error_message.lower()

    def test_valid_file_with_path_traversal_sanitized(self, validator, document_types):
        """Test that valid file content with bad filename is sanitized."""
        content = b"Normal text content here"
        result = validator.validate("../../etc/data.txt", content, document_types)

        assert result.is_valid is True
        assert result.sanitized_filename == "data.txt"

    def test_empty_content_passes_validation(self, validator, document_types):
        """Test that empty content passes all validation layers."""
        result = validator.validate("empty.txt", b"", document_types)

        assert result.is_valid is True

    def test_json_content_passes(self, validator, document_types):
        """Test that valid JSON content passes all layers."""
        content = b'{"users": [{"name": "test"}]}'
        result = validator.validate("config.json", content, document_types)

        assert result.is_valid is True
        assert result.sanitized_filename == "config.json"


# =============================================================================
# Edge Cases Tests
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_allowed_types_list(self, validator):
        """Test validation with empty allowed types list."""
        result = validator.validate("file.txt", b"content", [])

        assert result.is_valid is False
        assert "no extension" in result.error_message.lower() or "not allowed" in result.error_message.lower()

    def test_single_allowed_type(self, validator):
        """Test validation with only one allowed type."""
        types = [FileTypeConfig(extension="txt", mime_type="text/plain")]
        result = validator.validate("file.txt", b"content", types)

        assert result.is_valid is True

    def test_very_small_size_limit(self, validator):
        """Test with extremely small size limit."""
        types = [FileTypeConfig(extension="txt", mime_type="text/plain", max_size_mb=0.000001)]

        result = validator.validate("tiny.txt", b"hello", types)

        assert result.is_valid is False

    def test_zero_size_limit_rejects_any_content(self, validator):
        """Test that zero size limit rejects any non-empty content."""
        types = [FileTypeConfig(extension="txt", mime_type="text/plain", max_size_mb=0.0)]

        result = validator.validate("file.txt", b"a", types)

        assert result.is_valid is False

    def test_content_with_all_header_patterns_at_non_start(self, validator, document_types):
        """Test that header patterns not at start of file are ignored."""
        # MZ pattern embedded in middle of file, not at start
        content = b"SAFE CONTENT " + b"MZ\x90\x00" + b" MORE CONTENT"
        result = validator.validate("data.pdf", content, document_types)

        assert result.is_valid is True

    def test_filename_with_multiple_extensions(self, validator, image_types):
        """Test filename with multiple dots - uses last extension."""
        result = validator.validate("photo.backup.2024.png", b"\x89PNG", image_types)

        assert result.is_valid is True

    def test_filename_with_unicode_characters(self, validator, document_types):
        """Test filename with international characters."""
        result = validator.validate("Bericht_2024_Ubersicht.pdf", b"%PDF-1.4", document_types)

        assert result.is_valid is True
        assert result.sanitized_filename is not None

    def test_binary_content_in_pdf(self, validator, document_types):
        """Test that binary content in PDF (expected behavior) passes."""
        content = b"%PDF-1.4" + bytes(range(256)) * 10
        result = validator.validate("binary.pdf", content, document_types)

        assert result.is_valid is True

    def test_all_dangerous_header_patterns_defined(self):
        """Test that all expected dangerous header patterns are defined."""
        assert b"MZ" in DANGEROUS_HEADER_PATTERNS
        assert b"\x7fELF" in DANGEROUS_HEADER_PATTERNS
        assert b"#!/" in DANGEROUS_HEADER_PATTERNS
        assert b"<?php" in DANGEROUS_HEADER_PATTERNS
        assert b"<%" in DANGEROUS_HEADER_PATTERNS

    def test_all_dangerous_text_patterns_defined(self):
        """Test that all expected dangerous text patterns are defined."""
        assert b"<script" in DANGEROUS_TEXT_PATTERNS
        assert b"<SCRIPT" in DANGEROUS_TEXT_PATTERNS
        assert b"javascript:" in DANGEROUS_TEXT_PATTERNS
        assert b"vbscript:" in DANGEROUS_TEXT_PATTERNS

    def test_all_office_macro_patterns_defined(self):
        """Test that all expected office macro patterns are defined."""
        assert b"vbaProject.bin" in OFFICE_MACRO_PATTERNS
        assert b"xl/vbaProject" in OFFICE_MACRO_PATTERNS
        assert b"word/vbaProject" in OFFICE_MACRO_PATTERNS
        assert b"ppt/vbaProject" in OFFICE_MACRO_PATTERNS


# =============================================================================
# Factory Function and Utility Tests
# =============================================================================


@pytest.mark.unit
class TestFactoryAndUtilities:
    """Test factory function and utility functions."""

    def test_create_validator_default(self):
        """Test create_validator factory with defaults."""
        validator = create_validator()

        assert isinstance(validator, FileValidator)

    def test_create_validator_magic_disabled(self):
        """Test create_validator with magic explicitly disabled."""
        validator = create_validator(use_magic=False)

        assert isinstance(validator, FileValidator)
        assert validator.use_magic is False

    def test_create_validator_magic_enabled_no_module(self):
        """Test create_validator with magic requested but not available."""
        with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", False):
            validator = create_validator(use_magic=True)

            assert isinstance(validator, FileValidator)
            assert validator.use_magic is False  # Falls back to False

    def test_create_validator_magic_enabled_with_module(self):
        """Test create_validator with magic available and requested."""
        with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
            validator = create_validator(use_magic=True)

            assert isinstance(validator, FileValidator)
            assert validator.use_magic is True

    def test_is_magic_available_returns_bool(self):
        """Test that is_magic_available returns a boolean."""
        result = is_magic_available()

        assert isinstance(result, bool)

    def test_is_magic_available_reflects_import(self):
        """Test that is_magic_available reflects the module import state."""
        with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
            assert is_magic_available() is True

        with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", False):
            assert is_magic_available() is False

    def test_validator_use_magic_false_when_not_available(self):
        """Test that use_magic=True falls back to False when magic not installed."""
        with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", False):
            validator = FileValidator(use_magic=True)
            assert validator.use_magic is False

    def test_validator_use_magic_true_when_available(self):
        """Test that use_magic=True stays True when magic is installed."""
        with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
            validator = FileValidator(use_magic=True)
            assert validator.use_magic is True

    def test_validator_use_magic_false_explicit(self):
        """Test that use_magic=False stays False regardless of availability."""
        with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
            validator = FileValidator(use_magic=False)
            assert validator.use_magic is False


# =============================================================================
# Security-Specific Tests
# =============================================================================


@pytest.mark.unit
class TestSecurityScenarios:
    """Test specific security attack scenarios."""

    def test_polyglot_pdf_executable_rejected(self, validator, document_types):
        """Test that a file starting with MZ (polyglot PDF/EXE) is rejected."""
        content = b"MZ" + b"\x00" * 50 + b"%PDF-1.4" + b"\x00" * 100
        result = validator.validate("tricky.pdf", content, document_types)

        assert result.is_valid is False
        assert "executable" in result.error_message.lower()

    def test_null_byte_injection_in_filename(self, validator, document_types):
        """Test that null byte in filename is handled safely."""
        result = validator.validate("file.pdf\x00.exe", b"%PDF-1.4", document_types)

        # File extension after null byte should not be used
        if result.is_valid:
            assert "\x00" not in result.sanitized_filename

    def test_extension_mismatch_without_magic(self, validator):
        """Test that without magic, extension alone determines file type acceptance."""
        types = [FileTypeConfig(extension="pdf", mime_type="application/pdf")]

        # File claims to be PDF but content is an ELF binary
        content = b"\x7fELF\x02\x01\x01"
        result = validator.validate("fake.pdf", content, types)

        # Extension passes, but content scan catches the ELF header
        assert result.is_valid is False
        assert "executable" in result.error_message.lower()

    def test_html_disguised_as_text_with_script(self, validator, text_types):
        """Test that HTML with scripts in a .txt file is caught."""
        content = b"Looks like plain text\n<script>document.cookie</script>\n"
        result = validator.validate("notes.txt", content, text_types)

        assert result.is_valid is False

    def test_macro_in_xlsx_with_vba_content(self, validator, office_types):
        """Test that XLSX files with VBA macro content are rejected."""
        content = b"PK\x03\x04" + b"xl/vbaProject" + b"\x00" * 200
        result = validator.validate("budget.xlsx", content, office_types)

        assert result.is_valid is False
        assert "macro" in result.error_message.lower()

    def test_directory_traversal_in_validation(self, validator, document_types):
        """Test that path traversal in filename is sanitized in full pipeline."""
        content = b"Safe content for testing"
        result = validator.validate(
            "../../../../../tmp/evil.txt",
            content,
            document_types,
        )

        assert result.is_valid is True
        assert ".." not in result.sanitized_filename
        assert "/" not in result.sanitized_filename

    def test_xml_alias_security_with_html_content(self):
        """SECURITY TEST: Verify that text/xml detected content cannot pass as application/xml.

        This prevents an attacker from serving HTML content (detected as text/xml)
        and having it accepted as application/xml, which could lead to XSS.
        """
        mock_magic = MagicMock()
        mock_magic.from_buffer.return_value = "text/xml"

        text_types = [
            FileTypeConfig(extension="xml", mime_type="application/xml", max_size_mb=2.0),
        ]

        with patch("eq_chatbot_core.security.file_validator.magic", mock_magic, create=True):
            with patch("eq_chatbot_core.security.file_validator.MAGIC_AVAILABLE", True):
                validator = FileValidator(use_magic=True)
                content = b'<?xml version="1.0"?><html><body>XSS attempt</body></html>'
                result = validator.validate("data.xml", content, text_types)

        assert result.is_valid is False
        assert "MIME type mismatch" in result.error_message

    def test_case_sensitivity_in_dangerous_patterns(self, validator, text_types):
        """Test that script detection handles mixed case through lowering."""
        # The content scanner lowercases content for text files
        content = b"<ScRiPt>alert(1)</sCrIpT>"
        result = validator.validate("page.html", content, text_types)

        assert result.is_valid is False
