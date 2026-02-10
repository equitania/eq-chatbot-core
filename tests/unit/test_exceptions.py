"""
Unit tests for provider exceptions.

Tests the exception hierarchy and error handling patterns.
"""

import pytest

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    ContextLengthError,
    ProviderError,
    RateLimitError,
)

# =============================================================================
# Base ProviderError Tests
# =============================================================================


@pytest.mark.unit
class TestProviderError:
    """Test base ProviderError class."""

    def test_basic_instantiation(self):
        """Test creating a basic provider error."""
        error = ProviderError("Something went wrong", provider="openai")

        assert str(error) == "Something went wrong"
        assert error.provider == "openai"
        assert error.status_code is None
        assert error.retry_after is None

    def test_with_status_code(self):
        """Test error with status code."""
        error = ProviderError(
            "Server error",
            provider="anthropic",
            status_code=500,
        )

        assert str(error) == "Server error"
        assert error.provider == "anthropic"
        assert error.status_code == 500
        assert error.retry_after is None

    def test_with_all_parameters(self):
        """Test error with all parameters."""
        error = ProviderError(
            "Rate limited",
            provider="openai",
            status_code=429,
            retry_after=60,
        )

        assert str(error) == "Rate limited"
        assert error.provider == "openai"
        assert error.status_code == 429
        assert error.retry_after == 60

    def test_is_exception(self):
        """Test that ProviderError is a proper exception."""
        error = ProviderError("Test error", provider="test")

        assert isinstance(error, Exception)
        assert isinstance(error, BaseException)

    def test_can_be_raised_and_caught(self):
        """Test that error can be raised and caught."""
        with pytest.raises(ProviderError) as exc_info:
            raise ProviderError("Test error", provider="test")

        assert str(exc_info.value) == "Test error"
        assert exc_info.value.provider == "test"

    def test_empty_message(self):
        """Test error with empty message."""
        error = ProviderError("", provider="local")

        assert str(error) == ""
        assert error.provider == "local"


# =============================================================================
# RateLimitError Tests
# =============================================================================


@pytest.mark.unit
class TestRateLimitError:
    """Test RateLimitError class."""

    def test_is_provider_error_subclass(self):
        """Test that RateLimitError inherits from ProviderError."""
        error = RateLimitError("Rate limited", provider="openai")

        assert isinstance(error, ProviderError)
        assert isinstance(error, RateLimitError)

    def test_typical_rate_limit(self):
        """Test typical rate limit error with retry header."""
        error = RateLimitError(
            "Rate limit exceeded. Please retry after 60 seconds.",
            provider="openai",
            status_code=429,
            retry_after=60,
        )

        assert error.status_code == 429
        assert error.retry_after == 60
        assert error.provider == "openai"

    def test_can_be_caught_as_provider_error(self):
        """Test catching RateLimitError as ProviderError."""
        with pytest.raises(ProviderError):
            raise RateLimitError("Too many requests", provider="anthropic")

    def test_can_be_caught_specifically(self):
        """Test catching RateLimitError specifically."""
        with pytest.raises(RateLimitError) as exc_info:
            raise RateLimitError(
                "Slow down",
                provider="langdock",
                status_code=429,
                retry_after=30,
            )

        assert exc_info.value.retry_after == 30


# =============================================================================
# AuthenticationError Tests
# =============================================================================


@pytest.mark.unit
class TestAuthenticationError:
    """Test AuthenticationError class."""

    def test_is_provider_error_subclass(self):
        """Test that AuthenticationError inherits from ProviderError."""
        error = AuthenticationError("Invalid API key", provider="openai")

        assert isinstance(error, ProviderError)
        assert isinstance(error, AuthenticationError)

    def test_typical_auth_error(self):
        """Test typical authentication error."""
        error = AuthenticationError(
            "Incorrect API key provided",
            provider="anthropic",
            status_code=401,
        )

        assert error.status_code == 401
        assert error.provider == "anthropic"
        assert error.retry_after is None  # Auth errors typically don't have retry

    def test_can_be_caught_as_provider_error(self):
        """Test catching AuthenticationError as ProviderError."""
        with pytest.raises(ProviderError):
            raise AuthenticationError("Bad key", provider="test")

    def test_can_be_caught_specifically(self):
        """Test catching AuthenticationError specifically."""
        with pytest.raises(AuthenticationError) as exc_info:
            raise AuthenticationError(
                "API key not found",
                provider="langdock",
                status_code=403,
            )

        assert exc_info.value.status_code == 403


# =============================================================================
# ContextLengthError Tests
# =============================================================================


@pytest.mark.unit
class TestContextLengthError:
    """Test ContextLengthError class."""

    def test_is_provider_error_subclass(self):
        """Test that ContextLengthError inherits from ProviderError."""
        error = ContextLengthError("Context too long", provider="openai")

        assert isinstance(error, ProviderError)
        assert isinstance(error, ContextLengthError)

    def test_typical_context_error(self):
        """Test typical context length error."""
        error = ContextLengthError(
            "This model's maximum context length is 8192 tokens",
            provider="openai",
            status_code=400,
        )

        assert error.status_code == 400
        assert error.provider == "openai"

    def test_can_be_caught_as_provider_error(self):
        """Test catching ContextLengthError as ProviderError."""
        with pytest.raises(ProviderError):
            raise ContextLengthError("Too long", provider="test")

    def test_can_be_caught_specifically(self):
        """Test catching ContextLengthError specifically."""
        with pytest.raises(ContextLengthError) as exc_info:
            raise ContextLengthError(
                "Max tokens exceeded",
                provider="anthropic",
                status_code=400,
            )

        assert exc_info.value.provider == "anthropic"


# =============================================================================
# Exception Hierarchy Tests
# =============================================================================


@pytest.mark.unit
class TestExceptionHierarchy:
    """Test exception hierarchy and discrimination."""

    def test_exception_types_are_distinct(self):
        """Test that exception types are distinct."""
        provider_error = ProviderError("Test", provider="test")
        rate_limit = RateLimitError("Test", provider="test")
        auth_error = AuthenticationError("Test", provider="test")
        context_error = ContextLengthError("Test", provider="test")

        # Each is its own type
        assert type(provider_error) is ProviderError
        assert type(rate_limit) is RateLimitError
        assert type(auth_error) is AuthenticationError
        assert type(context_error) is ContextLengthError

    def test_can_discriminate_exception_types(self):
        """Test handling different exception types differently."""
        errors = [
            RateLimitError("Rate limited", provider="test", retry_after=60),
            AuthenticationError("Bad key", provider="test", status_code=401),
            ContextLengthError("Too long", provider="test", status_code=400),
            ProviderError("Generic error", provider="test", status_code=500),
        ]

        results = []
        for error in errors:
            if isinstance(error, RateLimitError):
                results.append(f"retry_after:{error.retry_after}")
            elif isinstance(error, AuthenticationError):
                results.append("needs_new_key")
            elif isinstance(error, ContextLengthError):
                results.append("truncate_context")
            elif isinstance(error, ProviderError):
                results.append("generic_error")

        assert results == [
            "retry_after:60",
            "needs_new_key",
            "truncate_context",
            "generic_error",
        ]

    def test_order_of_exception_catching(self):
        """Test that specific exceptions should be caught before generic."""

        def handle_error(error: ProviderError) -> str:
            # Correct order: specific exceptions first
            if isinstance(error, RateLimitError):
                return "rate_limit"
            elif isinstance(error, AuthenticationError):
                return "auth"
            elif isinstance(error, ContextLengthError):
                return "context"
            else:
                return "provider"

        assert handle_error(RateLimitError("x", provider="t")) == "rate_limit"
        assert handle_error(AuthenticationError("x", provider="t")) == "auth"
        assert handle_error(ContextLengthError("x", provider="t")) == "context"
        assert handle_error(ProviderError("x", provider="t")) == "provider"


# =============================================================================
# Error Attributes Tests
# =============================================================================


@pytest.mark.unit
class TestErrorAttributes:
    """Test error attribute handling."""

    def test_provider_attribute_types(self):
        """Test that provider attribute accepts different types."""
        errors = [
            ProviderError("test", provider="openai"),
            ProviderError("test", provider="anthropic"),
            ProviderError("test", provider="local"),
            ProviderError("test", provider="langdock"),
        ]

        providers = [e.provider for e in errors]
        assert providers == ["openai", "anthropic", "local", "langdock"]

    def test_status_code_common_values(self):
        """Test common HTTP status codes."""
        errors = [
            ProviderError("Bad request", provider="t", status_code=400),
            AuthenticationError("Unauthorized", provider="t", status_code=401),
            ProviderError("Forbidden", provider="t", status_code=403),
            ProviderError("Not found", provider="t", status_code=404),
            RateLimitError("Rate limited", provider="t", status_code=429),
            ProviderError("Server error", provider="t", status_code=500),
            ProviderError("Service unavailable", provider="t", status_code=503),
        ]

        status_codes = [e.status_code for e in errors]
        assert status_codes == [400, 401, 403, 404, 429, 500, 503]

    def test_retry_after_values(self):
        """Test various retry_after values."""
        errors = [
            RateLimitError("test", provider="t", retry_after=1),
            RateLimitError("test", provider="t", retry_after=60),
            RateLimitError("test", provider="t", retry_after=3600),
            RateLimitError("test", provider="t", retry_after=None),
        ]

        retry_values = [e.retry_after for e in errors]
        assert retry_values == [1, 60, 3600, None]

    def test_error_message_preserves_details(self):
        """Test that error messages preserve details."""
        detailed_message = (
            "Error code: 429 - {'error': {'message': 'Rate limit exceeded. "
            "You are sending requests too quickly.', 'type': 'rate_limit_error'}}"
        )

        error = RateLimitError(
            detailed_message,
            provider="openai",
            status_code=429,
            retry_after=20,
        )

        assert "Rate limit exceeded" in str(error)
        assert "rate_limit_error" in str(error)


# =============================================================================
# Exception String Representation Tests
# =============================================================================


@pytest.mark.unit
class TestExceptionStringRepresentation:
    """Test exception string representations."""

    def test_str_method(self):
        """Test __str__ method returns message."""
        error = ProviderError("Custom error message", provider="test")
        assert str(error) == "Custom error message"

    def test_repr_method(self):
        """Test __repr__ method."""
        error = ProviderError("Test error", provider="openai")
        # Default Exception repr includes message
        assert "Test error" in repr(error)

    def test_exception_in_f_string(self):
        """Test using exception in f-strings."""
        error = ProviderError("API Error", provider="anthropic")
        message = f"Provider error: {error}"
        assert message == "Provider error: API Error"

    def test_exception_args(self):
        """Test exception args attribute."""
        error = ProviderError("Error message", provider="test")
        assert error.args == ("Error message",)


# =============================================================================
# Exception Chaining Tests
# =============================================================================


@pytest.mark.unit
class TestExceptionChaining:
    """Test exception chaining patterns."""

    def test_exception_cause(self):
        """Test setting exception cause."""
        original = ValueError("Original error")
        try:
            raise ProviderError("Wrapped error", provider="test") from original
        except ProviderError as e:
            assert e.__cause__ is original

    def test_exception_context(self):
        """Test exception context in nested try blocks."""
        try:
            try:
                raise ValueError("Inner error")
            except ValueError:
                raise ProviderError("Outer error", provider="test")
        except ProviderError as e:
            assert e.__context__ is not None
            assert isinstance(e.__context__, ValueError)

    def test_suppress_context(self):
        """Test suppressing exception context."""
        try:
            try:
                raise ValueError("Inner")
            except ValueError:
                raise ProviderError("Outer", provider="test") from None
        except ProviderError as e:
            assert e.__suppress_context__ is True


# =============================================================================
# Real-World Error Scenario Tests
# =============================================================================


@pytest.mark.unit
class TestRealWorldScenarios:
    """Test real-world error handling scenarios."""

    def test_openai_rate_limit_response(self):
        """Test handling OpenAI-style rate limit error."""
        error = RateLimitError(
            "Rate limit reached for gpt-4o-mini in organization org-xxx "
            "on tokens per min. Limit: 60000, Used: 59500, Requested: 1000.",
            provider="openai",
            status_code=429,
            retry_after=20,
        )

        assert error.status_code == 429
        assert error.retry_after == 20
        assert "gpt-4o-mini" in str(error)

    def test_anthropic_auth_error(self):
        """Test handling Anthropic-style authentication error."""
        error = AuthenticationError(
            "invalid x-api-key",
            provider="anthropic",
            status_code=401,
        )

        assert error.status_code == 401
        assert "x-api-key" in str(error)

    def test_context_length_with_token_counts(self):
        """Test context length error with token information."""
        error = ContextLengthError(
            "This model's maximum context length is 128000 tokens. However, your messages resulted in 130000 tokens.",
            provider="openai",
            status_code=400,
        )

        assert "128000" in str(error)
        assert "130000" in str(error)

    def test_local_provider_connection_error(self):
        """Test local provider connection error."""
        error = ProviderError(
            "Connection refused. Is the local LLM server running?",
            provider="local",
            status_code=None,  # No HTTP status for connection errors
        )

        assert error.provider == "local"
        assert error.status_code is None

    def test_retry_logic_based_on_error_type(self):
        """Test implementing retry logic based on error types."""

        def should_retry(error: ProviderError, attempt: int) -> bool:
            """Determine if request should be retried."""
            if attempt >= 3:
                return False

            # Don't retry auth errors
            if isinstance(error, AuthenticationError):
                return False

            # Retry rate limits with backoff
            if isinstance(error, RateLimitError):
                return True

            # Retry 5xx errors
            if error.status_code and 500 <= error.status_code < 600:
                return True

            return False

        # Test cases
        assert should_retry(RateLimitError("x", provider="t"), 1) is True
        assert should_retry(RateLimitError("x", provider="t"), 3) is False
        assert should_retry(AuthenticationError("x", provider="t"), 1) is False
        assert should_retry(ProviderError("x", provider="t", status_code=500), 1) is True
        assert should_retry(ProviderError("x", provider="t", status_code=400), 1) is False
