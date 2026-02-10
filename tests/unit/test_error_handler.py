"""
Unit tests for the centralized error handler module.

Tests error classification, retry logic with exponential backoff and jitter,
provider fallback chains, German user messages, and logging callbacks.
"""

from unittest.mock import MagicMock, patch

import pytest

from eq_chatbot_core.services.error_handler import (
    ChatbotErrorHandler,
    ErrorCategory,
    ErrorResult,
    ErrorSeverity,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def handler():
    """Basic error handler without fallback provider function."""
    return ChatbotErrorHandler()


@pytest.fixture
def mock_provider():
    """Mock provider returned by fallback function."""
    provider = MagicMock()
    provider.provider_name = "langdock"
    return provider


@pytest.fixture
def handler_with_fallback(mock_provider):
    """Error handler with a working fallback provider function."""
    return ChatbotErrorHandler(
        get_provider_fn=lambda name: mock_provider,
    )


@pytest.fixture
def handler_with_log():
    """Error handler with a logging callback."""
    log_fn = MagicMock()
    return ChatbotErrorHandler(log_fn=log_fn), log_fn


# =============================================================================
# Error Classification Tests
# =============================================================================


@pytest.mark.unit
class TestErrorClassification:
    """Test that errors are classified into the correct type."""

    @patch("random.random", return_value=0.5)
    @patch("eq_chatbot_core.services.error_handler.time.sleep")
    def test_timeout_error_classification(self, mock_sleep, mock_random, handler):
        """Test that timeout errors are classified as 'timeout'."""
        error = Exception("Request timed out after 30s")
        result = handler.handle_llm_error(error, "openai", {})

        assert result.success is False
        assert result.error_type == "timeout"
        assert result.original_error is not None

    @patch("random.random", return_value=0.5)
    @patch("eq_chatbot_core.services.error_handler.time.sleep")
    def test_timeout_error_with_timed_out_keyword(self, mock_sleep, mock_random, handler):
        """Test that 'timed out' keyword also triggers timeout handling."""
        error = Exception("Connection timed out to server")
        result = handler.handle_llm_error(error, "anthropic", {})

        assert result.error_type == "timeout"

    def test_rate_limit_error_classification(self, handler):
        """Test that rate limit errors (429) are classified as 'rate_limit'."""
        error = Exception("Error 429: rate limit exceeded")
        result = handler.handle_llm_error(error, "openai", {})

        assert result.success is False
        assert result.error_type == "rate_limit"
        assert result.retry_after is not None

    def test_rate_limit_error_by_text(self, handler):
        """Test that 'rate limit' text triggers rate limit handling."""
        error = Exception("Rate limit reached for gpt-4o-mini")
        result = handler.handle_llm_error(error, "openai", {})

        assert result.error_type == "rate_limit"

    def test_auth_error_classification(self, handler):
        """Test that authentication errors (401) are classified as 'configuration'."""
        error = Exception("Error 401: authentication failed")
        result = handler.handle_llm_error(error, "openai", {})

        assert result.success is False
        assert result.error_type == "configuration"

    def test_auth_error_by_text(self, handler):
        """Test that 'authentication' keyword triggers auth handling."""
        error = Exception("Authentication error: invalid API key")
        result = handler.handle_llm_error(error, "anthropic", {})

        assert result.error_type == "configuration"

    def test_token_limit_error_classification(self, handler):
        """Test that token/context length errors are classified as 'token_limit'."""
        error = Exception("This model's maximum context length is 8192 tokens")
        result = handler.handle_llm_error(error, "openai", {})

        assert result.success is False
        assert result.error_type == "token_limit"

    def test_token_limit_by_token_keyword(self, handler):
        """Test that 'token' keyword triggers token limit handling."""
        error = Exception("Maximum token limit exceeded for this request")
        result = handler.handle_llm_error(error, "openai", {})

        assert result.error_type == "token_limit"

    def test_generic_error_classification(self, handler):
        """Test that unknown errors are classified as 'unknown'."""
        error = Exception("Something completely unexpected happened")
        result = handler.handle_llm_error(error, "openai", {})

        assert result.success is False
        # Without get_provider_fn, _handle_generic_error falls through
        # _try_fallback_provider returns no_fallback, then returns 'unknown'
        assert result.error_type == "unknown"


# =============================================================================
# Timeout Retry Logic Tests
# =============================================================================


@pytest.mark.unit
class TestTimeoutRetry:
    """Test timeout retry with exponential backoff and jitter."""

    @patch("random.random", return_value=0.5)
    @patch("eq_chatbot_core.services.error_handler.time.sleep")
    def test_timeout_retry_with_callback_success(self, mock_sleep, mock_random, handler):
        """Test that timeout retries using the callback and returns success."""
        retry_callback = MagicMock()
        error = Exception("Request timed out")

        result = handler.handle_llm_error(error, "openai", {}, retry_callback=retry_callback)

        assert result.success is True
        assert result.error_type == "timeout_recovered"
        retry_callback.assert_called_once()
        mock_sleep.assert_called_once()

    @patch("random.random", return_value=0.5)
    @patch("eq_chatbot_core.services.error_handler.time.sleep")
    def test_timeout_retry_exhausted_falls_back(self, mock_sleep, mock_random, handler_with_fallback):
        """Test that exhausted retries trigger fallback provider chain."""
        retry_callback = MagicMock(side_effect=Exception("Still timing out"))
        error = Exception("Request timed out")
        context = {"retry_count": 0}

        result = handler_with_fallback.handle_llm_error(error, "openai", context, retry_callback=retry_callback)

        # After 2 failed retries, should fall back to provider
        assert result.success is True
        assert result.error_type == "fallback_used"
        assert result.fallback_used is not None

    @patch("random.random", return_value=0.5)
    @patch("eq_chatbot_core.services.error_handler.time.sleep")
    def test_timeout_retry_count_increments(self, mock_sleep, mock_random, handler):
        """Test that retry_count in context increments on each retry attempt."""
        retry_callback = MagicMock(side_effect=Exception("Still failing"))
        error = Exception("Request timed out")
        context = {"retry_count": 0}

        handler.handle_llm_error(error, "openai", context, retry_callback=retry_callback)

        # _handle_timeout is called once per handle_llm_error invocation.
        # With retry_count=0, it retries once (incrementing to 1), fails,
        # then falls through to fallback without looping.
        assert context["retry_count"] == 1

    @patch("random.random", return_value=0.5)
    @patch("eq_chatbot_core.services.error_handler.time.sleep")
    def test_timeout_no_retry_when_count_exhausted(self, mock_sleep, mock_random, handler):
        """Test no retry when retry_count is already >= 2."""
        retry_callback = MagicMock()
        error = Exception("Request timed out")
        context = {"retry_count": 2}

        result = handler.handle_llm_error(error, "openai", context, retry_callback=retry_callback)

        # Should not call retry_callback since retries exhausted
        retry_callback.assert_not_called()
        mock_sleep.assert_not_called()
        assert result.success is False
        assert result.error_type == "timeout"

    @patch("random.random", return_value=0.5)
    @patch("eq_chatbot_core.services.error_handler.time.sleep")
    def test_jitter_in_timeout_retry(self, mock_sleep, mock_random, handler):
        """Test that sleep is called with jitter-adjusted wait time.

        With retry_count=0: base_wait = 2^0 = 1
        jitter = 1 * 0.25 * (2 * 0.5 - 1) = 1 * 0.25 * 0 = 0
        wait_time = 1 + 0 = 1.0
        """
        retry_callback = MagicMock()
        error = Exception("Request timed out")
        context = {"retry_count": 0}

        handler.handle_llm_error(error, "openai", context, retry_callback=retry_callback)

        # First call: base_wait=1, jitter=0 (random=0.5), total=1.0
        mock_sleep.assert_called_once_with(1.0)

    @patch("random.random", return_value=1.0)
    @patch("eq_chatbot_core.services.error_handler.time.sleep")
    def test_jitter_maximum_value(self, mock_sleep, mock_random, handler):
        """Test jitter at maximum value (random=1.0).

        With retry_count=0: base_wait = 1
        jitter = 1 * 0.25 * (2 * 1.0 - 1) = 0.25
        wait_time = 1 + 0.25 = 1.25
        """
        retry_callback = MagicMock()
        error = Exception("Request timed out")
        context = {"retry_count": 0}

        handler.handle_llm_error(error, "openai", context, retry_callback=retry_callback)

        mock_sleep.assert_called_once_with(1.25)

    @patch("random.random", return_value=0.0)
    @patch("eq_chatbot_core.services.error_handler.time.sleep")
    def test_jitter_minimum_value(self, mock_sleep, mock_random, handler):
        """Test jitter at minimum value (random=0.0).

        With retry_count=0: base_wait = 1
        jitter = 1 * 0.25 * (2 * 0.0 - 1) = -0.25
        wait_time = 1 + (-0.25) = 0.75
        """
        retry_callback = MagicMock()
        error = Exception("Request timed out")
        context = {"retry_count": 0}

        handler.handle_llm_error(error, "openai", context, retry_callback=retry_callback)

        mock_sleep.assert_called_once_with(0.75)


# =============================================================================
# Fallback Provider Chain Tests
# =============================================================================


@pytest.mark.unit
class TestFallbackProviderChain:
    """Test provider fallback chain logic."""

    def test_fallback_chain_openai_to_langdock(self):
        """Test that openai falls back to langdock first in the chain."""
        providers_tried = []

        def get_provider(name):
            providers_tried.append(name)
            provider = MagicMock()
            provider.provider_name = name
            return provider

        handler = ChatbotErrorHandler(get_provider_fn=get_provider)
        error = Exception("Something completely unexpected")

        result = handler.handle_llm_error(error, "openai", {})

        assert result.success is True
        assert result.error_type == "fallback_used"
        assert result.fallback_used == "langdock"
        assert providers_tried[0] == "langdock"

    def test_fallback_chain_skips_failing_provider(self):
        """Test that fallback chain continues when first fallback fails."""

        def get_provider(name):
            if name == "langdock":
                raise Exception("Langdock also down")
            provider = MagicMock()
            provider.provider_name = name
            return provider

        handler = ChatbotErrorHandler(get_provider_fn=get_provider)
        error = Exception("Unknown server error")

        result = handler.handle_llm_error(error, "openai", {})

        assert result.success is True
        assert result.fallback_used == "anthropic"

    def test_all_fallbacks_fail(self):
        """Test result when all fallback providers fail.

        _handle_generic_error calls _try_fallback_provider which returns
        error_type='all_fallbacks_failed'. But _handle_generic_error then
        returns its own ErrorResult with error_type='unknown'.
        """

        def get_provider(name):
            raise Exception(f"{name} is down")

        handler = ChatbotErrorHandler(get_provider_fn=get_provider)
        error = Exception("Unknown error occurred")

        result = handler.handle_llm_error(error, "openai", {})

        assert result.success is False
        assert result.error_type == "unknown"
        assert "unerwarteter Fehler" in result.user_message

    def test_no_fallback_when_get_provider_fn_is_none(self, handler):
        """Test that no fallback is attempted when get_provider_fn is None.

        _handle_generic_error checks fallback result.success, which is False.
        Then returns its own ErrorResult with error_type='unknown'.
        """
        error = Exception("Unknown server error")

        result = handler.handle_llm_error(error, "openai", {})

        assert result.success is False
        assert result.error_type == "unknown"
        assert "unerwarteter Fehler" in result.user_message

    def test_no_fallback_chain_for_unknown_provider(self):
        """Test that unknown providers have no fallback chain (empty list)."""
        get_provider = MagicMock(return_value=MagicMock())
        handler = ChatbotErrorHandler(get_provider_fn=get_provider)
        error = Exception("Unknown error")

        result = handler.handle_llm_error(error, "custom_provider", {})

        # custom_provider has no fallback chain, so no providers are tried
        assert result.success is False
        assert result.error_type == "unknown"
        get_provider.assert_not_called()

    def test_try_fallback_provider_directly_no_get_provider(self, handler):
        """Test _try_fallback_provider returns 'no_fallback' when get_provider is None."""
        result = handler._try_fallback_provider("openai", {})

        assert result.success is False
        assert result.error_type == "no_fallback"
        assert "Kein Fallback" in result.user_message

    def test_try_fallback_provider_directly_all_fail(self):
        """Test _try_fallback_provider returns 'all_fallbacks_failed' when all fail."""

        def get_provider(name):
            raise Exception(f"{name} is down")

        handler = ChatbotErrorHandler(get_provider_fn=get_provider)
        result = handler._try_fallback_provider("openai", {})

        assert result.success is False
        assert result.error_type == "all_fallbacks_failed"
        assert "nicht erreichbar" in result.user_message

    def test_fallback_chain_definitions(self):
        """Test that FALLBACK_CHAINS has expected provider entries."""
        assert "openai" in ChatbotErrorHandler.FALLBACK_CHAINS
        assert "anthropic" in ChatbotErrorHandler.FALLBACK_CHAINS
        assert "langdock" in ChatbotErrorHandler.FALLBACK_CHAINS

        assert ChatbotErrorHandler.FALLBACK_CHAINS["openai"] == ["langdock", "anthropic"]
        assert ChatbotErrorHandler.FALLBACK_CHAINS["anthropic"] == ["openai", "langdock"]
        assert ChatbotErrorHandler.FALLBACK_CHAINS["langdock"] == ["openai", "anthropic"]

    def test_fallback_provider_returns_none(self):
        """Test that a fallback returning None is skipped."""

        def get_provider(name):
            if name == "langdock":
                return None
            provider = MagicMock()
            provider.provider_name = name
            return provider

        handler = ChatbotErrorHandler(get_provider_fn=get_provider)
        error = Exception("Unknown error")

        result = handler.handle_llm_error(error, "openai", {})

        assert result.success is True
        assert result.fallback_used == "anthropic"


# =============================================================================
# Rate Limit Handling Tests
# =============================================================================


@pytest.mark.unit
class TestRateLimitHandling:
    """Test rate limit error handling and retry-after extraction."""

    def test_rate_limit_extracts_retry_after(self, handler):
        """Test that retry_after is extracted from error string."""
        error = Exception("Rate limit exceeded. Retry-After: 45 seconds")
        result = handler.handle_llm_error(error, "openai", {})

        assert result.error_type == "rate_limit"
        assert result.retry_after == 45

    def test_rate_limit_default_retry_after(self, handler):
        """Test default retry_after of 60 when not extractable."""
        error = Exception("429 rate limit exceeded")
        result = handler.handle_llm_error(error, "openai", {})

        assert result.error_type == "rate_limit"
        assert result.retry_after == 60

    def test_extract_retry_after_various_formats(self, handler):
        """Test retry-after extraction from various error message formats."""
        # Format: "retry-after: 30"
        assert handler._extract_retry_after(Exception("retry-after: 30")) == 30

        # Format: "Retry After 120"
        assert handler._extract_retry_after(Exception("Retry After 120")) == 120

        # Format: "retry_after: 15"
        assert handler._extract_retry_after(Exception("retry_after: 15")) == 15

    def test_extract_retry_after_returns_none(self, handler):
        """Test that extraction returns None when no match found."""
        result = handler._extract_retry_after(Exception("generic error message"))
        assert result is None


# =============================================================================
# German Error Messages Tests
# =============================================================================


@pytest.mark.unit
class TestGermanErrorMessages:
    """Test that user-facing error messages are in German."""

    @patch("random.random", return_value=0.5)
    @patch("eq_chatbot_core.services.error_handler.time.sleep")
    def test_timeout_message_in_german(self, mock_sleep, mock_random, handler):
        """Test that timeout error returns German user message."""
        error = Exception("Request timed out")
        result = handler.handle_llm_error(error, "openai", {})

        assert "Anfrage" in result.user_message
        assert "zu lange gedauert" in result.user_message

    def test_rate_limit_message_in_german(self, handler):
        """Test that rate limit error returns German user message."""
        error = Exception("429 rate limit exceeded")
        result = handler.handle_llm_error(error, "openai", {})

        assert "überlastet" in result.user_message
        assert "Sekunden" in result.user_message

    def test_auth_error_message_in_german(self, handler):
        """Test that auth error returns German user message."""
        error = Exception("401 authentication failed")
        result = handler.handle_llm_error(error, "openai", {})

        assert "Konfigurationsproblem" in result.user_message
        assert "Administrator" in result.user_message

    def test_token_limit_message_in_german(self, handler):
        """Test that token limit error returns German user message."""
        error = Exception("context length exceeded, too many tokens")
        result = handler.handle_llm_error(error, "openai", {})

        assert "zu lang" in result.user_message
        assert "Session" in result.user_message

    def test_generic_error_message_in_german(self, handler):
        """Test that generic error returns German user message."""
        error = Exception("Something completely unexpected happened")
        result = handler.handle_llm_error(error, "openai", {})

        assert "unerwarteter Fehler" in result.user_message


# =============================================================================
# Logging Callback Tests
# =============================================================================


@pytest.mark.unit
class TestLoggingCallback:
    """Test that the log function callback is invoked correctly."""

    def test_log_fn_called_on_rate_limit(self, handler_with_log):
        """Test that log_fn is called when rate limit error occurs."""
        handler, log_fn = handler_with_log
        error = Exception("429 rate limit exceeded")

        handler.handle_llm_error(error, "openai", {})

        log_fn.assert_called_once_with(
            "rate_limit",
            "warning",
            {"provider": "openai", "retry_after": 60},
        )

    def test_log_fn_called_on_auth_error(self, handler_with_log):
        """Test that log_fn is called when auth error occurs."""
        handler, log_fn = handler_with_log
        error = Exception("401 authentication failed")

        handler.handle_llm_error(error, "anthropic", {})

        log_fn.assert_called_once_with(
            "error",
            "critical",
            {"provider": "anthropic", "error": "authentication_failure"},
        )

    @patch("random.random", return_value=0.5)
    @patch("eq_chatbot_core.services.error_handler.time.sleep")
    def test_log_fn_not_called_on_timeout(self, mock_sleep, mock_random, handler_with_log):
        """Test that log_fn is NOT directly called in timeout handling path."""
        handler, log_fn = handler_with_log
        error = Exception("Request timed out")

        handler.handle_llm_error(error, "openai", {})

        # Timeout handler does not call _log_event directly
        log_fn.assert_not_called()

    def test_log_fn_receives_rate_limit_retry_after(self):
        """Test that log_fn receives extracted retry_after in details."""
        log_fn = MagicMock()
        handler = ChatbotErrorHandler(log_fn=log_fn)
        error = Exception("Rate limit exceeded. Retry-After: 30")

        handler.handle_llm_error(error, "openai", {})

        log_fn.assert_called_once()
        call_args = log_fn.call_args
        assert call_args[0][2]["retry_after"] == 30


# =============================================================================
# ErrorResult Dataclass Tests
# =============================================================================


@pytest.mark.unit
class TestErrorResult:
    """Test ErrorResult dataclass behavior."""

    def test_error_result_defaults(self):
        """Test ErrorResult with default optional fields."""
        result = ErrorResult(
            success=False,
            error_type="test",
            user_message="Test message",
        )

        assert result.success is False
        assert result.error_type == "test"
        assert result.user_message == "Test message"
        assert result.retry_after is None
        assert result.fallback_used is None
        assert result.original_error is None

    def test_error_result_with_all_fields(self):
        """Test ErrorResult with all fields populated."""
        result = ErrorResult(
            success=True,
            error_type="fallback_used",
            user_message="",
            retry_after=30,
            fallback_used="langdock",
            original_error="Original timeout",
        )

        assert result.success is True
        assert result.retry_after == 30
        assert result.fallback_used == "langdock"
        assert result.original_error == "Original timeout"


# =============================================================================
# Enum Tests
# =============================================================================


@pytest.mark.unit
class TestEnums:
    """Test ErrorSeverity and ErrorCategory enums."""

    def test_error_severity_values(self):
        """Test all ErrorSeverity enum values exist."""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"

    def test_error_category_values(self):
        """Test all ErrorCategory enum values exist."""
        assert ErrorCategory.LLM_PROVIDER.value == "llm_provider"
        assert ErrorCategory.VECTOR_DB.value == "vector_db"
        assert ErrorCategory.MCP_TOOL.value == "mcp_tool"
        assert ErrorCategory.UPLOAD.value == "upload"
        assert ErrorCategory.SECURITY.value == "security"
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.RATE_LIMIT.value == "rate_limit"
        assert ErrorCategory.TOKEN_LIMIT.value == "token_limit"
