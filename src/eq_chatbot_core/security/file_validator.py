"""
File validation utilities for secure file uploads.

Provides multi-layer validation including:
- Extension validation against whitelist
- MIME type verification
- Content scanning for dangerous patterns
- File size validation
- Filename sanitization
"""

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

# Try to import python-magic for MIME detection
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False


@dataclass
class FileValidationResult:
    """Result of file validation."""

    is_valid: bool
    error_message: Optional[str] = None
    detected_mime: Optional[str] = None
    sanitized_filename: Optional[str] = None


@dataclass
class FileTypeConfig:
    """Configuration for an allowed file type."""

    extension: str
    mime_type: str
    max_size_mb: float = 10.0
    scan_content: bool = True
    supports_vision: bool = False
    supports_document: bool = False


# Dangerous byte patterns at file START (header-based detection)
# These patterns must appear at the very beginning of the file
DANGEROUS_HEADER_PATTERNS = [
    b"MZ",           # DOS/Windows PE executable
    b"\x7fELF",      # Linux ELF binary
    b"#!/",          # Shebang (shell scripts)
    b"<?php",        # PHP script
    b"<%",           # ASP/JSP
]

# Dangerous patterns anywhere in file (for text-based threats)
# These are checked only for text-like content, not binary formats
DANGEROUS_TEXT_PATTERNS = [
    b"<script",      # JavaScript in HTML
    b"<SCRIPT",      # JavaScript (uppercase)
    b"javascript:",  # JavaScript URL scheme
    b"vbscript:",    # VBScript URL scheme
]

# Patterns specific to Office documents (VBA macros)
# Only vbaProject patterns - these indicate actual macro content
OFFICE_MACRO_PATTERNS = [
    b"vbaProject.bin",   # VBA project binary (standard location)
    b"xl/vbaProject",    # Excel VBA path
    b"word/vbaProject",  # Word VBA path
    b"ppt/vbaProject",   # PowerPoint VBA path
]


class FileValidator:
    """Multi-layer file validation for secure uploads."""

    def __init__(self, use_magic: bool = True):
        """Initialize the validator.

        Args:
            use_magic: Whether to use python-magic for MIME detection.
                       Falls back to extension-based detection if unavailable.
        """
        self.use_magic = use_magic and MAGIC_AVAILABLE

    def validate(
        self,
        filename: str,
        content: bytes,
        allowed_types: list[FileTypeConfig],
    ) -> FileValidationResult:
        """Validate a file against security requirements.

        Performs 5-layer validation:
        1. Extension check against whitelist
        2. MIME type verification
        3. Content scanning for dangerous patterns
        4. Size validation
        5. Filename sanitization

        Args:
            filename: Original filename
            content: File content as bytes
            allowed_types: List of allowed file type configurations

        Returns:
            FileValidationResult with validation status and details
        """
        # Layer 1: Extension validation
        ext_result = self._validate_extension(filename, allowed_types)
        if not ext_result[0]:
            return FileValidationResult(
                is_valid=False,
                error_message=ext_result[1],
            )

        file_config = ext_result[2]

        # Layer 2: MIME type verification
        mime_result = self._validate_mime_type(content, file_config)
        if not mime_result[0]:
            return FileValidationResult(
                is_valid=False,
                error_message=mime_result[1],
                detected_mime=mime_result[2],
            )

        # Layer 3: Content scanning
        if file_config.scan_content:
            scan_result = self._scan_content(content, file_config)
            if not scan_result[0]:
                return FileValidationResult(
                    is_valid=False,
                    error_message=scan_result[1],
                )

        # Layer 4: Size validation
        size_result = self._validate_size(content, file_config)
        if not size_result[0]:
            return FileValidationResult(
                is_valid=False,
                error_message=size_result[1],
            )

        # Layer 5: Filename sanitization
        sanitized = self.sanitize_filename(filename)

        return FileValidationResult(
            is_valid=True,
            detected_mime=file_config.mime_type,
            sanitized_filename=sanitized,
        )

    def _validate_extension(
        self,
        filename: str,
        allowed_types: list[FileTypeConfig],
    ) -> tuple[bool, Optional[str], Optional[FileTypeConfig]]:
        """Validate file extension against whitelist.

        Returns:
            Tuple of (is_valid, error_message, matching_config)
        """
        ext = self._get_extension(filename)
        if not ext:
            return False, "File has no extension", None

        for config in allowed_types:
            if config.extension.lower() == ext:
                return True, None, config

        allowed_exts = ", ".join(f".{c.extension}" for c in allowed_types)
        return False, f"Extension '.{ext}' not allowed. Allowed: {allowed_exts}", None

    def _validate_mime_type(
        self,
        content: bytes,
        config: FileTypeConfig,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Verify actual MIME type matches expected.

        Returns:
            Tuple of (is_valid, error_message, detected_mime)
        """
        if not self.use_magic:
            # Skip MIME verification if magic is not available
            return True, None, config.mime_type

        detected = magic.from_buffer(content, mime=True)

        # Allow some flexibility for related MIME types
        if detected == config.mime_type:
            return True, None, detected

        # Handle common variations
        mime_aliases = {
            "text/plain": ["text/csv", "application/csv"],
            "image/jpeg": ["image/jpg"],
            "application/xml": ["text/xml"],
            "application/json": ["text/json"],
        }

        expected = config.mime_type
        if expected in mime_aliases and detected in mime_aliases[expected]:
            return True, None, detected

        # Reverse check
        for primary, aliases in mime_aliases.items():
            if expected in aliases and detected == primary:
                return True, None, detected

        return (
            False,
            f"MIME type mismatch: expected '{config.mime_type}', detected '{detected}'",
            detected,
        )

    def _scan_content(
        self,
        content: bytes,
        config: FileTypeConfig,
    ) -> tuple[bool, Optional[str]]:
        """Scan file content for dangerous patterns.

        Uses different scanning strategies based on file type:
        - Header patterns: Check first bytes for executable signatures
        - Text patterns: Only check in text-based files
        - Office patterns: Check for VBA macros in Office documents

        Returns:
            Tuple of (is_safe, error_message)
        """
        # Layer 1: Check dangerous header patterns at file START only
        # These are binary signatures that indicate executable files
        for pattern in DANGEROUS_HEADER_PATTERNS:
            if content.startswith(pattern):
                return False, "File contains executable content (header detected)"

        # Layer 2: For text-based files, check for script injection patterns
        # Only apply to text MIME types to avoid false positives in binary files
        if config.mime_type.startswith("text/") or config.extension in ("html", "htm", "xml", "svg"):
            content_lower = content.lower()
            for pattern in DANGEROUS_TEXT_PATTERNS:
                if pattern in content_lower:
                    return False, "File contains potentially dangerous script content"

            # Check for null bytes in text files (potential binary injection)
            if b"\x00" in content:
                return False, "Text file contains binary data"

        # Layer 3: Check for VBA macros in Office documents
        # Office Open XML files (.docx, .xlsx, .pptx) are ZIP archives
        if config.extension in ("docx", "xlsx", "pptx"):
            for pattern in OFFICE_MACRO_PATTERNS:
                if pattern in content:
                    return False, "Office document contains macros (not allowed)"

        return True, None

    def _validate_size(
        self,
        content: bytes,
        config: FileTypeConfig,
    ) -> tuple[bool, Optional[str]]:
        """Validate file size against limit.

        Returns:
            Tuple of (is_valid, error_message)
        """
        size_mb = len(content) / (1024 * 1024)

        if size_mb > config.max_size_mb:
            return (
                False,
                f"File too large: {size_mb:.2f} MB (max: {config.max_size_mb} MB)",
            )

        return True, None

    def _get_extension(self, filename: str) -> str:
        """Extract and normalize file extension."""
        if not filename or "." not in filename:
            return ""
        return filename.rsplit(".", 1)[-1].lower()

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and injection.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for storage
        """
        if not filename:
            return "unnamed_file"

        # Normalize unicode characters
        filename = unicodedata.normalize("NFKD", filename)

        # Remove path components (prevent path traversal)
        filename = os.path.basename(filename)

        # Remove null bytes
        filename = filename.replace("\x00", "")

        # Remove dangerous characters
        # Keep: alphanumeric, dots, dashes, underscores, spaces
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)

        # Prevent hidden files (starting with dot)
        filename = filename.lstrip(".")

        # Split name and extension
        if "." in filename:
            name, ext = filename.rsplit(".", 1)
        else:
            name, ext = filename, ""

        # Limit name length
        max_name_length = 200
        if len(name) > max_name_length:
            name = name[:max_name_length]

        # Ensure we have a valid name
        if not name:
            name = "file"

        # Rebuild filename
        if ext:
            return f"{name}.{ext}"
        return name


def create_validator(use_magic: bool = True) -> FileValidator:
    """Factory function to create a FileValidator instance.

    Args:
        use_magic: Whether to use python-magic for MIME detection

    Returns:
        Configured FileValidator instance
    """
    return FileValidator(use_magic=use_magic)


def is_magic_available() -> bool:
    """Check if python-magic is available for MIME detection."""
    return MAGIC_AVAILABLE
