"""
Unit tests for the rate limiting module.

Tests RateLimitConfig, UsageRecord, RateLimitResult dataclasses,
check_rate_limit logic, estimate_tokens with tiktoken and fallback,
and proper storage protocol interaction.
"""

import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from eq_chatbot_core.security.rate_limit import (
    AtomicRateLimitStorage,
    RateLimitConfig,
    RateLimitResult,
    UsageRecord,
    check_rate_limit,
    enforce_rate_limit,
    estimate_tokens,
)

# =============================================================================
# Helper: Mock Storage Factory
# =============================================================================


def _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=0):
    """Create a mock storage with configurable return values."""
    storage = MagicMock()
    storage.get_minute_usage.return_value = minute_usage
    storage.get_hourly_usage.return_value = hourly_usage
    storage.get_daily_tokens.return_value = daily_tokens
    return storage


# =============================================================================
# RateLimitConfig Tests
# =============================================================================


@pytest.mark.unit
class TestRateLimitConfig:
    """Test RateLimitConfig dataclass defaults and customisation."""

    def test_default_values(self):
        """Test that default config values are correct."""
        config = RateLimitConfig()

        assert config.max_requests_per_hour == 100
        assert config.max_tokens_per_day == 100000
        assert config.max_requests_per_minute == 10

    def test_custom_values(self):
        """Test creating config with custom values."""
        config = RateLimitConfig(
            max_requests_per_hour=50,
            max_tokens_per_day=200000,
            max_requests_per_minute=5,
        )

        assert config.max_requests_per_hour == 50
        assert config.max_tokens_per_day == 200000
        assert config.max_requests_per_minute == 5

    def test_partial_custom_values(self):
        """Test overriding only some config fields."""
        config = RateLimitConfig(max_requests_per_hour=200)

        assert config.max_requests_per_hour == 200
        assert config.max_tokens_per_day == 100000  # default
        assert config.max_requests_per_minute == 10  # default

    def test_zero_limits(self):
        """Test config with zero limits (effectively disabling features)."""
        config = RateLimitConfig(
            max_requests_per_hour=0,
            max_tokens_per_day=0,
            max_requests_per_minute=0,
        )

        assert config.max_requests_per_hour == 0
        assert config.max_tokens_per_day == 0
        assert config.max_requests_per_minute == 0

    def test_very_large_limits(self):
        """Test config with very large limit values."""
        config = RateLimitConfig(
            max_requests_per_hour=1_000_000,
            max_tokens_per_day=10_000_000_000,
            max_requests_per_minute=100_000,
        )

        assert config.max_requests_per_hour == 1_000_000
        assert config.max_tokens_per_day == 10_000_000_000
        assert config.max_requests_per_minute == 100_000


# =============================================================================
# UsageRecord Tests
# =============================================================================


@pytest.mark.unit
class TestUsageRecord:
    """Test UsageRecord dataclass."""

    def test_basic_creation(self):
        """Test creating a usage record with required fields."""
        now = datetime.now(UTC)
        record = UsageRecord(
            user_id=1,
            company_id=10,
            request_count=5,
            token_count=500,
            window_start=now,
        )

        assert record.user_id == 1
        assert record.company_id == 10
        assert record.request_count == 5
        assert record.token_count == 500
        assert record.window_start == now

    def test_zero_counts(self):
        """Test usage record with zero counts."""
        now = datetime.now(UTC)
        record = UsageRecord(
            user_id=42,
            company_id=1,
            request_count=0,
            token_count=0,
            window_start=now,
        )

        assert record.request_count == 0
        assert record.token_count == 0


# =============================================================================
# RateLimitResult Tests
# =============================================================================


@pytest.mark.unit
class TestRateLimitResult:
    """Test RateLimitResult dataclass."""

    def test_allowed_result_defaults(self):
        """Test allowed result with default optional fields."""
        result = RateLimitResult(allowed=True)

        assert result.allowed is True
        assert result.reason is None
        assert result.retry_after is None
        assert result.current_usage == 0
        assert result.limit == 0

    def test_denied_result_with_details(self):
        """Test denied result with all fields populated."""
        result = RateLimitResult(
            allowed=False,
            reason="Hourly limit exceeded",
            retry_after=3600,
            current_usage=100,
            limit=100,
        )

        assert result.allowed is False
        assert result.reason == "Hourly limit exceeded"
        assert result.retry_after == 3600
        assert result.current_usage == 100
        assert result.limit == 100

    def test_result_with_custom_usage_and_limit(self):
        """Test result with custom current_usage and limit values."""
        result = RateLimitResult(
            allowed=True,
            current_usage=50,
            limit=100,
        )

        assert result.allowed is True
        assert result.current_usage == 50
        assert result.limit == 100


# =============================================================================
# check_rate_limit: Request Allowed Tests
# =============================================================================


@pytest.mark.unit
class TestCheckRateLimitAllowed:
    """Test check_rate_limit when requests are allowed."""

    def test_request_allowed_under_all_limits(self):
        """Test that a request is allowed when under all limits."""
        config = RateLimitConfig()
        storage = _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=0)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert result.allowed is True
        assert result.reason is None
        assert result.retry_after is None

    def test_request_allowed_with_moderate_usage(self):
        """Test allowed when usage is moderate but below all limits."""
        config = RateLimitConfig()
        storage = _make_storage(minute_usage=5, hourly_usage=50, daily_tokens=50000)

        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=100)

        assert result.allowed is True

    def test_allowed_result_contains_hourly_usage_and_limit(self):
        """Test that allowed result contains current hourly usage and limit."""
        config = RateLimitConfig(max_requests_per_hour=200)
        storage = _make_storage(minute_usage=3, hourly_usage=75, daily_tokens=10000)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert result.allowed is True
        assert result.current_usage == 75
        assert result.limit == 200

    def test_allowed_just_under_minute_limit(self):
        """Test allowed when minute usage is one below the limit."""
        config = RateLimitConfig(max_requests_per_minute=10)
        storage = _make_storage(minute_usage=9, hourly_usage=50, daily_tokens=1000)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert result.allowed is True

    def test_allowed_just_under_hourly_limit(self):
        """Test allowed when hourly usage is one below the limit."""
        config = RateLimitConfig(max_requests_per_hour=100)
        storage = _make_storage(minute_usage=0, hourly_usage=99, daily_tokens=1000)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert result.allowed is True

    def test_allowed_just_under_daily_token_limit(self):
        """Test allowed when daily tokens plus estimated exactly equal the limit."""
        config = RateLimitConfig(max_tokens_per_day=100000)
        # daily_tokens + estimated_tokens == 100000 exactly
        # The check is >, so exactly equal should be allowed
        storage = _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=99900)

        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=100)

        # daily_tokens (99900) + estimated_tokens (100) = 100000 which is NOT > 100000
        assert result.allowed is True

    def test_allowed_with_zero_estimated_tokens(self):
        """Test that zero estimated tokens does not affect daily check."""
        config = RateLimitConfig(max_tokens_per_day=100000)
        storage = _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=99999)

        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=0)

        assert result.allowed is True


# =============================================================================
# check_rate_limit: Burst (Per-Minute) Limit Tests
# =============================================================================


@pytest.mark.unit
class TestCheckRateLimitBurst:
    """Test check_rate_limit per-minute burst limit enforcement."""

    def test_burst_limit_exceeded(self):
        """Test denial when per-minute limit is reached."""
        config = RateLimitConfig(max_requests_per_minute=10)
        storage = _make_storage(minute_usage=10)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert result.allowed is False
        assert result.retry_after == 60
        assert result.current_usage == 10
        assert result.limit == 10
        assert "Burst limit exceeded" in result.reason
        assert "10/10" in result.reason

    def test_burst_limit_exceeded_over_limit(self):
        """Test denial when per-minute usage exceeds the limit."""
        config = RateLimitConfig(max_requests_per_minute=5)
        storage = _make_storage(minute_usage=8)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert result.allowed is False
        assert result.retry_after == 60
        assert result.current_usage == 8
        assert result.limit == 5

    def test_burst_limit_checked_first(self):
        """Test that burst limit is checked before hourly and daily limits."""
        config = RateLimitConfig(
            max_requests_per_minute=5,
            max_requests_per_hour=100,
            max_tokens_per_day=100000,
        )
        # All limits exceeded, but burst should be reported
        storage = _make_storage(minute_usage=5, hourly_usage=100, daily_tokens=200000)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert result.allowed is False
        assert "Burst limit exceeded" in result.reason
        assert result.retry_after == 60

    def test_burst_limit_zero_blocks_everything(self):
        """Test that a zero burst limit blocks all requests."""
        config = RateLimitConfig(max_requests_per_minute=0)
        storage = _make_storage(minute_usage=0)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert result.allowed is False
        assert result.retry_after == 60


# =============================================================================
# check_rate_limit: Hourly Limit Tests
# =============================================================================


@pytest.mark.unit
class TestCheckRateLimitHourly:
    """Test check_rate_limit hourly request limit enforcement."""

    def test_hourly_limit_exceeded(self):
        """Test denial when hourly limit is reached."""
        config = RateLimitConfig(max_requests_per_hour=100)
        storage = _make_storage(minute_usage=0, hourly_usage=100)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert result.allowed is False
        assert result.retry_after == 3600
        assert result.current_usage == 100
        assert result.limit == 100
        assert "Hourly limit exceeded" in result.reason
        assert "100/100" in result.reason

    def test_hourly_limit_exceeded_over_limit(self):
        """Test denial when hourly usage exceeds the limit."""
        config = RateLimitConfig(max_requests_per_hour=50)
        storage = _make_storage(minute_usage=0, hourly_usage=75)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert result.allowed is False
        assert result.retry_after == 3600
        assert result.current_usage == 75
        assert result.limit == 50

    def test_hourly_limit_checked_after_burst(self):
        """Test that hourly limit is checked after burst passes."""
        config = RateLimitConfig(
            max_requests_per_minute=10,
            max_requests_per_hour=50,
        )
        # Burst OK, hourly exceeded
        storage = _make_storage(minute_usage=5, hourly_usage=50)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert result.allowed is False
        assert "Hourly limit exceeded" in result.reason
        assert result.retry_after == 3600

    def test_hourly_limit_zero_blocks_after_burst(self):
        """Test that a zero hourly limit blocks when burst is also zero."""
        config = RateLimitConfig(
            max_requests_per_minute=10,
            max_requests_per_hour=0,
        )
        storage = _make_storage(minute_usage=0, hourly_usage=0)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert result.allowed is False
        assert result.retry_after == 3600


# =============================================================================
# check_rate_limit: Daily Token Limit Tests
# =============================================================================


@pytest.mark.unit
class TestCheckRateLimitDaily:
    """Test check_rate_limit daily token limit enforcement."""

    def test_daily_token_limit_exceeded(self):
        """Test denial when daily token limit is exceeded."""
        config = RateLimitConfig(max_tokens_per_day=100000)
        storage = _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=90000)

        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=20000)

        assert result.allowed is False
        assert "Daily token limit exceeded" in result.reason
        assert "90000/100000" in result.reason
        assert result.current_usage == 90000
        assert result.limit == 100000

    def test_daily_limit_retry_after_seconds_until_midnight(self):
        """Test that retry_after for daily limit is seconds until UTC midnight."""
        config = RateLimitConfig(max_tokens_per_day=1000)
        storage = _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=900)

        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=200)

        assert result.allowed is False
        assert result.retry_after is not None
        # retry_after should be positive and at most 86400 seconds (24h)
        assert 0 < result.retry_after <= 86400

    def test_daily_limit_with_only_estimated_tokens_exceeding(self):
        """Test denial when current usage is zero but estimated exceeds limit."""
        config = RateLimitConfig(max_tokens_per_day=100)
        storage = _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=0)

        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=101)

        assert result.allowed is False
        assert "Daily token limit exceeded" in result.reason

    def test_daily_limit_checked_last(self):
        """Test that daily limit is only checked when burst and hourly pass."""
        config = RateLimitConfig(
            max_requests_per_minute=10,
            max_requests_per_hour=100,
            max_tokens_per_day=1000,
        )
        # Burst and hourly OK, daily exceeded
        storage = _make_storage(minute_usage=5, hourly_usage=50, daily_tokens=900)

        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=200)

        assert result.allowed is False
        assert "Daily token limit exceeded" in result.reason

    def test_daily_limit_exact_boundary_allowed(self):
        """Test that daily_tokens + estimated_tokens == limit is allowed."""
        config = RateLimitConfig(max_tokens_per_day=1000)
        storage = _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=800)

        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=200)

        # 800 + 200 = 1000 which is NOT > 1000, so allowed
        assert result.allowed is True

    def test_daily_limit_one_over_boundary_denied(self):
        """Test that daily_tokens + estimated_tokens == limit + 1 is denied."""
        config = RateLimitConfig(max_tokens_per_day=1000)
        storage = _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=800)

        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=201)

        # 800 + 201 = 1001 which is > 1000, so denied
        assert result.allowed is False


# =============================================================================
# check_rate_limit: Storage Interaction Tests
# =============================================================================


@pytest.mark.unit
class TestCheckRateLimitStorageInteraction:
    """Test that check_rate_limit properly interacts with the storage protocol."""

    def test_storage_get_minute_usage_called(self):
        """Test that get_minute_usage is called with correct arguments."""
        config = RateLimitConfig()
        storage = _make_storage()

        check_rate_limit(user_id=42, config=config, storage=storage)

        storage.get_minute_usage.assert_called_once()
        args = storage.get_minute_usage.call_args
        assert args[0][0] == 42  # user_id
        assert isinstance(args[0][1], datetime)  # since timestamp

    def test_storage_get_hourly_usage_called(self):
        """Test that get_hourly_usage is called with correct arguments."""
        config = RateLimitConfig()
        storage = _make_storage()

        check_rate_limit(user_id=7, config=config, storage=storage)

        storage.get_hourly_usage.assert_called_once()
        args = storage.get_hourly_usage.call_args
        assert args[0][0] == 7  # user_id
        assert isinstance(args[0][1], datetime)  # since timestamp

    def test_storage_get_daily_tokens_called(self):
        """Test that get_daily_tokens is called with correct arguments."""
        config = RateLimitConfig()
        storage = _make_storage()

        check_rate_limit(user_id=3, config=config, storage=storage)

        storage.get_daily_tokens.assert_called_once()
        args = storage.get_daily_tokens.call_args
        assert args[0][0] == 3  # user_id
        # The since timestamp should be midnight UTC
        since = args[0][1]
        assert isinstance(since, datetime)
        assert since.hour == 0
        assert since.minute == 0
        assert since.second == 0
        assert since.microsecond == 0

    def test_storage_not_called_past_burst_denial(self):
        """Test that hourly/daily storage is not queried when burst is denied."""
        config = RateLimitConfig(max_requests_per_minute=5)
        storage = _make_storage(minute_usage=5)

        check_rate_limit(user_id=1, config=config, storage=storage)

        storage.get_minute_usage.assert_called_once()
        storage.get_hourly_usage.assert_not_called()
        storage.get_daily_tokens.assert_not_called()

    def test_storage_daily_not_called_past_hourly_denial(self):
        """Test that daily storage is not queried when hourly is denied."""
        config = RateLimitConfig(max_requests_per_hour=10)
        storage = _make_storage(minute_usage=0, hourly_usage=10)

        check_rate_limit(user_id=1, config=config, storage=storage)

        storage.get_minute_usage.assert_called_once()
        storage.get_hourly_usage.assert_called_once()
        storage.get_daily_tokens.assert_not_called()

    def test_all_storage_methods_called_when_all_pass(self):
        """Test that all storage methods are called when all checks pass."""
        config = RateLimitConfig()
        storage = _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=0)

        check_rate_limit(user_id=1, config=config, storage=storage)

        storage.get_minute_usage.assert_called_once()
        storage.get_hourly_usage.assert_called_once()
        storage.get_daily_tokens.assert_called_once()

    def test_record_usage_is_not_called(self):
        """Test that check_rate_limit does not call record_usage (it only checks)."""
        config = RateLimitConfig()
        storage = _make_storage()

        check_rate_limit(user_id=1, config=config, storage=storage)

        storage.record_usage.assert_not_called()


# =============================================================================
# check_rate_limit: Priority / Order Tests
# =============================================================================


@pytest.mark.unit
class TestCheckRateLimitPriority:
    """Test the order of limit checks in check_rate_limit."""

    def test_burst_takes_priority_over_hourly(self):
        """Test burst denial even when hourly is also exceeded."""
        config = RateLimitConfig(
            max_requests_per_minute=5,
            max_requests_per_hour=50,
        )
        storage = _make_storage(minute_usage=5, hourly_usage=50)

        result = check_rate_limit(user_id=1, config=config, storage=storage)

        assert "Burst limit" in result.reason
        assert result.retry_after == 60

    def test_hourly_takes_priority_over_daily(self):
        """Test hourly denial even when daily is also exceeded."""
        config = RateLimitConfig(
            max_requests_per_minute=10,
            max_requests_per_hour=50,
            max_tokens_per_day=1000,
        )
        storage = _make_storage(minute_usage=5, hourly_usage=50, daily_tokens=2000)

        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=100)

        assert "Hourly limit" in result.reason
        assert result.retry_after == 3600


# =============================================================================
# check_rate_limit: Edge Cases
# =============================================================================


@pytest.mark.unit
class TestCheckRateLimitEdgeCases:
    """Test edge cases for check_rate_limit."""

    def test_user_id_zero(self):
        """Test rate limiting with user_id zero."""
        config = RateLimitConfig()
        storage = _make_storage()

        result = check_rate_limit(user_id=0, config=config, storage=storage)

        assert result.allowed is True
        storage.get_minute_usage.assert_called_once()
        assert storage.get_minute_usage.call_args[0][0] == 0

    def test_large_estimated_tokens(self):
        """Test with very large estimated token count."""
        config = RateLimitConfig(max_tokens_per_day=100000)
        storage = _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=0)

        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=999999)

        assert result.allowed is False

    def test_negative_estimated_tokens_still_works(self):
        """Test that negative estimated tokens does not cause errors."""
        config = RateLimitConfig(max_tokens_per_day=100000)
        storage = _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=99999)

        # Negative estimated tokens would reduce the sum below daily limit
        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=-100)

        assert result.allowed is True

    def test_multiple_users_use_separate_calls(self):
        """Test that different user IDs result in separate storage calls."""
        config = RateLimitConfig()
        storage = _make_storage()

        check_rate_limit(user_id=1, config=config, storage=storage)
        check_rate_limit(user_id=2, config=config, storage=storage)

        # get_minute_usage should have been called twice with different user IDs
        calls = storage.get_minute_usage.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == 1
        assert calls[1][0][0] == 2


# =============================================================================
# estimate_tokens: With tiktoken Tests
# =============================================================================


@pytest.mark.unit
class TestEstimateTokensWithTiktoken:
    """Test estimate_tokens when tiktoken is available."""

    def test_basic_text_estimation(self):
        """Test token estimation for simple text."""
        count = estimate_tokens("Hello, world!")

        # tiktoken should return a positive integer
        assert isinstance(count, int)
        assert count > 0

    def test_empty_string(self):
        """Test token estimation for empty string."""
        count = estimate_tokens("")

        assert count == 0

    def test_long_text(self):
        """Test that longer text produces more tokens."""
        short_text = "Hello"
        long_text = "Hello " * 100

        short_count = estimate_tokens(short_text)
        long_count = estimate_tokens(long_text)

        assert long_count > short_count

    def test_default_model_is_gpt4(self):
        """Test that the default model parameter is gpt-4."""
        # Both calls should produce the same result with cl100k_base encoding
        count_default = estimate_tokens("Test text")
        count_gpt4 = estimate_tokens("Test text", model="gpt-4")

        assert count_default == count_gpt4

    def test_different_model_names(self):
        """Test estimation with various model names."""
        text = "Sample text for estimation"

        # All these should use cl100k_base and produce the same count
        count_gpt4 = estimate_tokens(text, model="gpt-4")
        count_gpt4o = estimate_tokens(text, model="gpt-4o")
        count_gpt4_turbo = estimate_tokens(text, model="gpt-4-turbo")

        assert count_gpt4 == count_gpt4o
        assert count_gpt4 == count_gpt4_turbo

    def test_unknown_model_uses_default_encoding(self):
        """Test that unknown model names fall back to cl100k_base."""
        text = "Sample text for encoding test"

        count_known = estimate_tokens(text, model="gpt-4")
        count_unknown = estimate_tokens(text, model="unknown-model-xyz")

        # Both should use cl100k_base
        assert count_known == count_unknown

    def test_claude_model_approximation(self):
        """Test that claude model uses cl100k_base approximation."""
        text = "Test for Claude model"

        count_claude = estimate_tokens(text, model="claude")
        count_gpt4 = estimate_tokens(text, model="gpt-4")

        assert count_claude == count_gpt4

    def test_unicode_text(self):
        """Test token estimation with Unicode characters."""
        text = "Hallo Welt! Umlaute: aou scharfes s"

        count = estimate_tokens(text)

        assert isinstance(count, int)
        assert count > 0

    def test_multiline_text(self):
        """Test token estimation with multiline text."""
        text = "Line 1\nLine 2\nLine 3\n"

        count = estimate_tokens(text)

        assert isinstance(count, int)
        assert count > 0


# =============================================================================
# estimate_tokens: Fallback Tests (tiktoken unavailable)
# =============================================================================


@pytest.mark.unit
class TestEstimateTokensFallback:
    """Test estimate_tokens fallback when tiktoken is not available."""

    def test_fallback_uses_char_count_divided_by_four(self):
        """Test that fallback estimates tokens as len(text) // 4."""
        with patch.dict(sys.modules, {"tiktoken": None}):
            # Force ImportError by making tiktoken raise on import
            with patch("builtins.__import__", side_effect=_import_raiser("tiktoken")):
                count = estimate_tokens("abcdefgh")  # 8 chars -> 8 // 4 = 2

                assert count == 2

    def test_fallback_empty_string(self):
        """Test fallback with empty string returns 0."""
        with patch.dict(sys.modules, {"tiktoken": None}):
            with patch("builtins.__import__", side_effect=_import_raiser("tiktoken")):
                count = estimate_tokens("")

                assert count == 0

    def test_fallback_short_string(self):
        """Test fallback with string shorter than 4 chars returns 0."""
        with patch.dict(sys.modules, {"tiktoken": None}):
            with patch("builtins.__import__", side_effect=_import_raiser("tiktoken")):
                count = estimate_tokens("abc")  # 3 chars -> 3 // 4 = 0

                assert count == 0

    def test_fallback_known_length(self):
        """Test fallback with a string of known length."""
        text = "a" * 100  # 100 chars -> 100 // 4 = 25
        with patch.dict(sys.modules, {"tiktoken": None}):
            with patch("builtins.__import__", side_effect=_import_raiser("tiktoken")):
                count = estimate_tokens(text)

                assert count == 25

    def test_fallback_ignores_model_parameter(self):
        """Test that fallback produces the same result regardless of model."""
        text = "a" * 40  # 40 chars -> 10 tokens
        with patch.dict(sys.modules, {"tiktoken": None}):
            with patch("builtins.__import__", side_effect=_import_raiser("tiktoken")):
                count_gpt4 = estimate_tokens(text, model="gpt-4")
                count_claude = estimate_tokens(text, model="claude")
                count_unknown = estimate_tokens(text, model="xyz")

                assert count_gpt4 == count_claude == count_unknown == 10


# =============================================================================
# Integration-style Tests (combining multiple features)
# =============================================================================


@pytest.mark.unit
class TestCheckRateLimitIntegration:
    """Integration-style tests combining check_rate_limit with estimate_tokens."""

    def test_full_workflow_allowed(self):
        """Test a complete workflow where the request is allowed."""
        config = RateLimitConfig(
            max_requests_per_minute=10,
            max_requests_per_hour=100,
            max_tokens_per_day=100000,
        )
        storage = _make_storage(minute_usage=3, hourly_usage=40, daily_tokens=50000)

        estimated = estimate_tokens("A simple user message for the chatbot.")
        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=estimated)

        assert result.allowed is True
        assert result.current_usage == 40
        assert result.limit == 100

    def test_full_workflow_denied_by_tokens(self):
        """Test a workflow where the daily token limit causes denial."""
        config = RateLimitConfig(max_tokens_per_day=100)
        storage = _make_storage(minute_usage=0, hourly_usage=0, daily_tokens=95)

        # Even a small message estimate could push us over
        estimated = estimate_tokens("This is a longer message with enough text to exceed the remaining budget.")
        result = check_rate_limit(user_id=1, config=config, storage=storage, estimated_tokens=estimated)

        assert result.allowed is False
        assert "Daily token limit exceeded" in result.reason

    def test_consecutive_checks_accumulate(self):
        """Test that storage accurately reflects increasing usage across checks."""
        config = RateLimitConfig(max_requests_per_minute=3)

        # Simulate increasing minute usage across calls
        for minute_usage in range(4):
            storage = _make_storage(minute_usage=minute_usage)
            result = check_rate_limit(user_id=1, config=config, storage=storage)

            if minute_usage < 3:
                assert result.allowed is True
            else:
                assert result.allowed is False
                assert "Burst limit exceeded" in result.reason


# =============================================================================
# Helper for tiktoken Import Mock
# =============================================================================


def _import_raiser(blocked_module):
    """Return an import function that raises ImportError for a specific module."""
    original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def _custom_import(name, *args, **kwargs):
        if name == blocked_module:
            raise ImportError(f"Mocked: No module named '{blocked_module}'")
        return original_import(name, *args, **kwargs)

    return _custom_import


# =============================================================================
# enforce_rate_limit: atomic vs. non-atomic check+record
# =============================================================================


class _AtomicStorage:
    """Storage satisfying AtomicRateLimitStorage — records the atomic call."""

    def __init__(self, result):
        self._result = result
        self.calls = []

    def get_minute_usage(self, user_id, since):  # pragma: no cover - unused
        return 0

    def get_hourly_usage(self, user_id, since):  # pragma: no cover - unused
        return 0

    def get_daily_tokens(self, user_id, since):  # pragma: no cover - unused
        return 0

    def record_usage(self, user_id, company_id, tokens):  # pragma: no cover - unused
        raise AssertionError("atomic path must not call record_usage separately")

    def check_and_record(self, user_id, company_id, config, estimated_tokens):
        self.calls.append((user_id, company_id, estimated_tokens))
        return self._result


@pytest.mark.unit
class TestEnforceRateLimit:
    """Test the atomic-preferring enforce_rate_limit entry point."""

    def test_atomic_storage_is_recognized_by_protocol(self):
        storage = _AtomicStorage(RateLimitResult(allowed=True))
        assert isinstance(storage, AtomicRateLimitStorage)

    def test_plain_storage_without_method_is_not_atomic(self):
        class _PlainStorage:
            def get_minute_usage(self, user_id, since):
                return 0

            def get_hourly_usage(self, user_id, since):
                return 0

            def get_daily_tokens(self, user_id, since):
                return 0

            def record_usage(self, user_id, company_id, tokens):
                pass

        assert not isinstance(_PlainStorage(), AtomicRateLimitStorage)

    def test_prefers_atomic_check_and_record(self):
        expected = RateLimitResult(allowed=True, current_usage=3, limit=100)
        storage = _AtomicStorage(expected)

        result = enforce_rate_limit(
            user_id=7, company_id=2, config=RateLimitConfig(), storage=storage, estimated_tokens=42
        )

        assert result is expected
        assert storage.calls == [(7, 2, 42)]

    def test_non_atomic_records_usage_when_allowed(self):
        storage = _make_storage()
        # Plain MagicMock would auto-create check_and_record; remove it so the
        # storage does NOT satisfy the atomic protocol.
        del storage.check_and_record

        result = enforce_rate_limit(
            user_id=1, company_id=1, config=RateLimitConfig(), storage=storage, estimated_tokens=10
        )

        assert result.allowed is True
        storage.record_usage.assert_called_once_with(1, 1, 10)

    def test_non_atomic_does_not_record_when_denied(self):
        storage = _make_storage(minute_usage=999)
        del storage.check_and_record

        result = enforce_rate_limit(
            user_id=1, company_id=1, config=RateLimitConfig(max_requests_per_minute=5), storage=storage
        )

        assert result.allowed is False
        storage.record_usage.assert_not_called()
