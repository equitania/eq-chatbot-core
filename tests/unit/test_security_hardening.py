"""
Unit tests for the security-hardening pass.

Covers the fixes from the security review:
- secret scrubbing in logs / error surfaces (utils.secret_scrub)
- SSRF URL validation (utils.url_validation)
- retry-after clamping (services.error_handler)
- FileValidator fail-closed behaviour (security.file_validator)
- PDF resource limits (utils.pdf)
"""

import pytest

# =============================================================================
# Secret scrubbing
# =============================================================================


@pytest.mark.unit
class TestScrubSecrets:
    def test_masks_openai_key(self):
        from eq_chatbot_core.utils.secret_scrub import scrub_secrets

        out = scrub_secrets("error: invalid key sk-abc123DEF456ghi please retry")
        assert "sk-abc123DEF456ghi" not in out
        assert "***" in out

    def test_masks_provider_prefixes(self):
        from eq_chatbot_core.utils.secret_scrub import scrub_secrets

        for token in ("ld-secretvalue123", "mm-secretvalue123", "sk-or-secretvalue123", "sk-ant-secretvalue123"):
            out = scrub_secrets(f"prefix {token} suffix")
            assert token not in out
            assert "***" in out

    def test_masks_bearer_token(self):
        from eq_chatbot_core.utils.secret_scrub import scrub_secrets

        out = scrub_secrets("Authorization: Bearer eyJhbGciOiJIUzI1Ni12345")
        assert "eyJhbGciOiJIUzI1Ni12345" not in out
        assert "***" in out

    def test_masks_key_query_param(self):
        from eq_chatbot_core.utils.secret_scrub import scrub_secrets

        out = scrub_secrets("GET https://api.example.com/v1?key=AIzaSyVerySecretValue&x=1")
        assert "AIzaSyVerySecretValue" not in out
        assert "key=***" in out

    def test_masks_json_api_key(self):
        from eq_chatbot_core.utils.secret_scrub import scrub_secrets

        out = scrub_secrets('{"api_key": "sup3rs3cretvalue", "model": "gpt-4o"}')
        assert "sup3rs3cretvalue" not in out
        assert "gpt-4o" in out  # non-secret content preserved

    def test_preserves_plain_text(self):
        from eq_chatbot_core.utils.secret_scrub import scrub_secrets

        msg = "Context length exceeded: prompt has 9000 tokens, limit is 8192"
        assert scrub_secrets(msg) == msg

    def test_handles_empty(self):
        from eq_chatbot_core.utils.secret_scrub import scrub_secrets

        assert scrub_secrets("") == ""


# =============================================================================
# SSRF URL validation
# =============================================================================


@pytest.mark.unit
class TestValidateUrl:
    def test_rejects_non_http_scheme(self):
        from eq_chatbot_core.utils.url_validation import validate_url

        with pytest.raises(ValueError):
            validate_url("file:///etc/passwd")
        with pytest.raises(ValueError):
            validate_url("gopher://internal/")

    def test_rejects_missing_hostname(self):
        from eq_chatbot_core.utils.url_validation import validate_url

        with pytest.raises(ValueError):
            validate_url("http://")

    def test_strict_blocks_private_ip(self):
        from eq_chatbot_core.utils.url_validation import validate_url

        with pytest.raises(ValueError):
            validate_url("http://10.0.0.1:8080/")

    def test_strict_blocks_cloud_metadata(self):
        from eq_chatbot_core.utils.url_validation import validate_url

        with pytest.raises(ValueError):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_strict_allows_localhost(self):
        from eq_chatbot_core.utils.url_validation import validate_url

        # Should not raise; localhost is explicitly permitted.
        validate_url("http://localhost:1234/v1")
        validate_url("http://127.0.0.1:11434/v1")

    def test_lan_mode_allows_private_but_blocks_metadata(self):
        from eq_chatbot_core.utils.url_validation import validate_url

        # LAN mode: private ranges and loopback are legitimate for local servers.
        validate_url("http://10.0.0.1:1234/v1", allow_private_ranges=True)
        validate_url("http://127.0.0.1:1234/v1", allow_private_ranges=True)
        # ...but cloud-metadata / link-local stays blocked.
        with pytest.raises(ValueError):
            validate_url("http://169.254.169.254/", allow_private_ranges=True)
        # ...and non-HTTP schemes are still rejected.
        with pytest.raises(ValueError):
            validate_url("file:///etc/passwd", allow_private_ranges=True)


@pytest.mark.unit
class TestLocalProviderBaseUrl:
    def test_rejects_metadata_base_url(self):
        from eq_chatbot_core.providers.local_provider import LocalLLMProvider

        with pytest.raises(ValueError):
            LocalLLMProvider(base_url="http://169.254.169.254/v1")

    def test_accepts_localhost_default(self):
        from eq_chatbot_core.providers.local_provider import LocalLLMProvider

        provider = LocalLLMProvider()  # defaults to localhost LM Studio URL
        assert provider.base_url.startswith("http://localhost")


# =============================================================================
# retry-after clamping
# =============================================================================


@pytest.mark.unit
class TestRetryAfterCap:
    def test_caps_huge_retry_after(self):
        from eq_chatbot_core.services.error_handler import MAX_RETRY_AFTER, ChatbotErrorHandler

        handler = ChatbotErrorHandler()
        value = handler._extract_retry_after(Exception("Rate limited. retry-after: 99999999"))
        assert value == MAX_RETRY_AFTER

    def test_passes_reasonable_value(self):
        from eq_chatbot_core.services.error_handler import ChatbotErrorHandler

        handler = ChatbotErrorHandler()
        assert handler._extract_retry_after(Exception("retry-after: 30")) == 30

    def test_returns_none_when_absent(self):
        from eq_chatbot_core.services.error_handler import ChatbotErrorHandler

        handler = ChatbotErrorHandler()
        assert handler._extract_retry_after(Exception("some other error")) is None

    def test_rate_limit_result_scrubs_key(self):
        from eq_chatbot_core.services.error_handler import ChatbotErrorHandler

        handler = ChatbotErrorHandler()
        result = handler.handle_llm_error(
            Exception("429 rate limit for key sk-leakedsecret12345"),
            provider="openai",
            context={},
        )
        assert "sk-leakedsecret12345" not in (result.original_error or "")


# =============================================================================
# FileValidator fail-closed
# =============================================================================


@pytest.mark.unit
class TestFileValidatorFailClosed:
    def test_mime_verified_true_with_magic(self):
        from eq_chatbot_core.security.file_validator import FileTypeConfig, FileValidator

        validator = FileValidator(use_magic=True)
        # A real PNG header so puremagic detects image/png.
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        config = FileTypeConfig(extension="png", mime_type="image/png", scan_content=False)
        result = validator.validate("logo.png", png, [config])
        assert result.is_valid is True
        assert result.mime_verified is True

    def test_mime_not_verified_when_magic_disabled(self):
        from eq_chatbot_core.security.file_validator import FileTypeConfig, FileValidator

        validator = FileValidator(use_magic=False)
        config = FileTypeConfig(extension="png", mime_type="image/png", scan_content=False)
        # Content does NOT match the extension, but without magic it cannot be detected.
        result = validator.validate("evil.png", b"GIF89a-not-a-png", [config])
        assert result.is_valid is True
        assert result.mime_verified is False  # degradation surfaced to caller

    def test_require_magic_raises_when_unavailable(self, monkeypatch):
        import eq_chatbot_core.security.file_validator as fv

        monkeypatch.setattr(fv, "MAGIC_AVAILABLE", False)
        with pytest.raises(RuntimeError):
            fv.FileValidator(require_magic=True)


# =============================================================================
# PDF resource limits
# =============================================================================


@pytest.mark.unit
class TestPdfLimits:
    def test_oversized_pdf_raises(self, monkeypatch):
        import eq_chatbot_core.utils.pdf as pdf

        if not pdf.is_pdf_conversion_available():
            pytest.skip("pymupdf not installed")

        monkeypatch.setattr(pdf, "MAX_PDF_BYTES", 16)
        with pytest.raises(ValueError):
            pdf.pdf_to_images(b"%PDF-1.4 padding-data-that-exceeds-limit", max_pages=1)

    def test_invalid_format_raises(self):
        from eq_chatbot_core.utils.pdf import is_pdf_conversion_available, pdf_to_images

        if not is_pdf_conversion_available():
            pytest.skip("pymupdf not installed")

        with pytest.raises(ValueError):
            pdf_to_images(b"%PDF-1.4", image_format="bmp")
