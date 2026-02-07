"""
Error handling with provider fallback logic.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error category types."""

    LLM_PROVIDER = "llm_provider"
    VECTOR_DB = "vector_db"
    MCP_TOOL = "mcp_tool"
    UPLOAD = "upload"
    SECURITY = "security"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    TOKEN_LIMIT = "token_limit"


@dataclass
class ErrorResult:
    """Result from error handling."""

    success: bool
    """Whether recovery was successful."""

    error_type: str
    """Type of error that occurred."""

    user_message: str
    """User-friendly error message."""

    retry_after: int | None = None
    """Seconds to wait before retry (for rate limits)."""

    fallback_used: str | None = None
    """Name of fallback provider used (if any)."""

    original_error: str | None = None
    """Original error message (for logging)."""


# Default error messages (German). Override via messages parameter in constructor.
DEFAULT_ERROR_MESSAGES: dict[str, str] = {
    "timeout": "Die Anfrage hat zu lange gedauert. Bitte versuchen Sie es erneut.",
    "rate_limit": "Der Service ist momentan überlastet. Bitte versuchen Sie es in {wait_time} Sekunden erneut.",
    "auth_error": "Es gibt ein Konfigurationsproblem. Bitte kontaktieren Sie den Administrator.",
    "token_limit": (
        "Die Nachricht oder der Kontext ist zu lang. "
        "Bitte kürzen Sie Ihre Nachricht oder starten Sie eine neue Session."
    ),
    "generic_error": "Ein unerwarteter Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.",
    "no_fallback": "Kein Fallback-Provider verfügbar.",
    "all_fallbacks_failed": "Alle Dienste sind momentan nicht erreichbar.",
}


class ChatbotErrorHandler:
    """
    Centralized error handling with retry and fallback logic.

    Handles:
    - LLM provider errors (timeout, rate limit, auth)
    - Provider fallback chains
    - User-friendly error messages (configurable language)
    """

    # Fallback chains by provider
    FALLBACK_CHAINS = {
        "openai": ["langdock", "anthropic"],
        "anthropic": ["openai", "langdock"],
        "langdock": ["openai", "anthropic"],
    }

    def __init__(
        self,
        get_provider_fn: Callable[[str], Any] | None = None,
        log_fn: Callable[[str, str, dict], None] | None = None,
        messages: dict[str, str] | None = None,
    ):
        """
        Initialize error handler.

        Args:
            get_provider_fn: Function to get provider by name
            log_fn: Function to log errors (event_type, severity, details)
            messages: Custom error messages (overrides defaults per key)
        """
        self.get_provider = get_provider_fn
        self.log_fn = log_fn
        self.messages = {**DEFAULT_ERROR_MESSAGES, **(messages or {})}

    def handle_llm_error(
        self,
        error: Exception,
        provider: str,
        context: dict[str, Any],
        retry_callback: Callable[[dict], Any] | None = None,
    ) -> ErrorResult:
        """
        Handle LLM provider errors with retry and fallback.

        Args:
            error: The exception that occurred
            provider: Name of the provider that failed
            context: Request context (messages, model, etc.)
            retry_callback: Function to retry the request

        Returns:
            ErrorResult with handling outcome
        """
        error_str = str(error).lower()

        # Classify and handle error
        if "timeout" in error_str or "timed out" in error_str:
            return self._handle_timeout(error, provider, context, retry_callback)

        if "rate limit" in error_str or "429" in error_str:
            return self._handle_rate_limit(error, provider)

        if "authentication" in error_str or "401" in error_str:
            return self._handle_auth_error(error, provider)

        if "context length" in error_str or "token" in error_str:
            return self._handle_token_limit(error)

        return self._handle_generic_error(error, provider, context)

    def _handle_timeout(
        self,
        error: Exception,
        provider: str,
        context: dict[str, Any],
        retry_callback: Callable[[dict], Any] | None,
    ) -> ErrorResult:
        """Handle timeout with exponential backoff retry and jitter."""
        import random

        retry_count = context.get("retry_count", 0)

        if retry_count < 2 and retry_callback:
            base_wait = 2**retry_count  # 1s, 2s
            # Add jitter (±25%) to prevent thundering herd
            jitter = base_wait * 0.25 * (2 * random.random() - 1)
            wait_time = base_wait + jitter
            logger.warning(f"LLM timeout, retry {retry_count + 1}/2 after {wait_time:.1f}s")
            time.sleep(wait_time)

            context["retry_count"] = retry_count + 1

            try:
                retry_callback(context)
                return ErrorResult(
                    success=True,
                    error_type="timeout_recovered",
                    user_message="",
                )
            except Exception as retry_err:
                logger.debug("Retry callback failed, falling through to fallback: %s", retry_err)

        # Try fallback provider
        fallback_result = self._try_fallback_provider(provider, context)
        if fallback_result.success:
            return fallback_result

        return ErrorResult(
            success=False,
            error_type="timeout",
            user_message=self.messages["timeout"],
            original_error=str(error),
        )

    def _handle_rate_limit(
        self,
        error: Exception,
        provider: str,
    ) -> ErrorResult:
        """Handle rate limit errors."""
        wait_time = self._extract_retry_after(error) or 60

        self._log_event(
            "rate_limit",
            "warning",
            {
                "provider": provider,
                "retry_after": wait_time,
            },
        )

        return ErrorResult(
            success=False,
            error_type="rate_limit",
            user_message=self.messages["rate_limit"].format(wait_time=wait_time),
            retry_after=wait_time,
            original_error=str(error),
        )

    def _handle_auth_error(
        self,
        error: Exception,
        provider: str,
    ) -> ErrorResult:
        """Handle authentication errors."""
        self._log_event(
            "error",
            "critical",
            {
                "provider": provider,
                "error": "authentication_failure",
            },
        )

        return ErrorResult(
            success=False,
            error_type="configuration",
            user_message=self.messages["auth_error"],
            original_error=str(error),
        )

    def _handle_token_limit(self, error: Exception) -> ErrorResult:
        """Handle context length exceeded."""
        return ErrorResult(
            success=False,
            error_type="token_limit",
            user_message=self.messages["token_limit"],
            original_error=str(error),
        )

    def _handle_generic_error(
        self,
        error: Exception,
        provider: str,
        context: dict[str, Any],
    ) -> ErrorResult:
        """Handle unknown errors with fallback."""
        logger.error(f"Generic LLM error from {provider}: {error}")

        fallback_result = self._try_fallback_provider(provider, context)
        if fallback_result.success:
            return fallback_result

        return ErrorResult(
            success=False,
            error_type="unknown",
            user_message=self.messages["generic_error"],
            original_error=str(error),
        )

    def _try_fallback_provider(
        self,
        failed_provider: str,
        context: dict[str, Any],
    ) -> ErrorResult:
        """Try alternative providers from fallback chain."""
        if not self.get_provider:
            return ErrorResult(
                success=False,
                error_type="no_fallback",
                user_message=self.messages["no_fallback"],
            )

        fallbacks = self.FALLBACK_CHAINS.get(failed_provider, [])

        for fallback_name in fallbacks:
            try:
                provider = self.get_provider(fallback_name)
                if provider:
                    logger.info(f"Falling back to {fallback_name}")
                    return ErrorResult(
                        success=True,
                        error_type="fallback_used",
                        user_message="",
                        fallback_used=fallback_name,
                    )
            except Exception as e:
                logger.warning(f"Fallback to {fallback_name} failed: {e}")
                continue

        return ErrorResult(
            success=False,
            error_type="all_fallbacks_failed",
            user_message=self.messages["all_fallbacks_failed"],
        )

    def _extract_retry_after(self, error: Exception) -> int | None:
        """Extract retry-after seconds from error response."""
        import re

        error_str = str(error)
        match = re.search(r"retry.after[:\s]+(\d+)", error_str, re.IGNORECASE)

        if match:
            return int(match.group(1))

        return None

    def _log_event(
        self,
        event_type: str,
        severity: str,
        details: dict[str, Any],
    ) -> None:
        """Log event via callback if available."""
        if self.log_fn:
            self.log_fn(event_type, severity, details)
        else:
            logger.log(
                logging.WARNING if severity in ("warning", "high") else logging.INFO,
                f"[{event_type}] {details}",
            )
