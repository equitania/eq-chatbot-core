"""
Rate limiting logic for API requests.

This module provides the logic for rate limiting.
The actual storage is handled by Odoo models.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

_logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    max_requests_per_hour: int = 100
    """Maximum requests per user per hour."""

    max_tokens_per_day: int = 100000
    """Maximum tokens per user per day."""

    max_requests_per_minute: int = 10
    """Maximum requests per user per minute (burst limit)."""


@dataclass
class UsageRecord:
    """Record of API usage for rate limiting."""

    user_id: int
    company_id: int
    request_count: int
    token_count: int
    window_start: datetime


class RateLimitStorage(Protocol):
    """
    Protocol for rate limit storage backends.

    Implemented by Odoo models (chatbot.rate.limit).

    Atomicity (IMPORTANT): :func:`check_rate_limit` reads usage counters but does
    NOT record usage — the caller invokes :meth:`record_usage` afterwards. These
    two steps are not atomic, so under concurrent requests for the same user every
    request can read the same pre-increment counter, all pass the check, and all
    record separately, overshooting the limit. Backends that must enforce the
    limit strictly should serialize check+record per user (e.g. a
    ``SELECT ... FOR UPDATE`` row lock) and/or implement the atomic
    :class:`AtomicRateLimitStorage` protocol, which :func:`enforce_rate_limit`
    uses when available.
    """

    def get_hourly_usage(self, user_id: int, since: datetime) -> int:
        """Get request count in the last hour."""
        ...

    def get_daily_tokens(self, user_id: int, since: datetime) -> int:
        """Get token count since midnight."""
        ...

    def get_minute_usage(self, user_id: int, since: datetime) -> int:
        """Get request count in the last minute."""
        ...

    def record_usage(self, user_id: int, company_id: int, tokens: int) -> None:
        """Record a new request with token count."""
        ...


@runtime_checkable
class AtomicRateLimitStorage(Protocol):
    """Optional storage protocol for race-free rate limiting.

    A backend implementing ``check_and_record`` performs the limit check and the
    usage write in a single atomic operation (e.g. inside one locked DB
    transaction), closing the TOCTOU window described on
    :class:`RateLimitStorage`. :func:`enforce_rate_limit` prefers this path when
    the supplied storage satisfies it.
    """

    def check_and_record(
        self,
        user_id: int,
        company_id: int,
        config: "RateLimitConfig",
        estimated_tokens: int,
    ) -> "RateLimitResult":
        """Atomically check limits and, if allowed, record the usage."""
        ...


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    """Whether the request is allowed."""

    reason: str | None = None
    """Reason for denial (if not allowed)."""

    retry_after: int | None = None
    """Seconds to wait before retrying (if not allowed)."""

    current_usage: int = 0
    """Current usage count for the relevant limit."""

    limit: int = 0
    """The limit that was checked."""


def check_rate_limit(
    user_id: int,
    config: RateLimitConfig,
    storage: RateLimitStorage,
    estimated_tokens: int = 0,
) -> RateLimitResult:
    """
    Check if a request is within rate limits.

    Args:
        user_id: The user making the request
        config: Rate limit configuration
        storage: Storage backend for usage data
        estimated_tokens: Estimated tokens for this request

    Returns:
        RateLimitResult with allowed status and details
    """
    now = datetime.now(UTC)

    # Check per-minute burst limit
    minute_ago = now - timedelta(minutes=1)
    minute_usage = storage.get_minute_usage(user_id, minute_ago)

    if minute_usage >= config.max_requests_per_minute:
        return RateLimitResult(
            allowed=False,
            reason=f"Burst limit exceeded: {minute_usage}/{config.max_requests_per_minute} requests per minute",
            retry_after=60,
            current_usage=minute_usage,
            limit=config.max_requests_per_minute,
        )

    # Check hourly request limit
    hour_ago = now - timedelta(hours=1)
    hourly_usage = storage.get_hourly_usage(user_id, hour_ago)

    if hourly_usage >= config.max_requests_per_hour:
        return RateLimitResult(
            allowed=False,
            reason=f"Hourly limit exceeded: {hourly_usage}/{config.max_requests_per_hour} requests per hour",
            retry_after=3600,
            current_usage=hourly_usage,
            limit=config.max_requests_per_hour,
        )

    # Check daily token limit
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    daily_tokens = storage.get_daily_tokens(user_id, day_start)

    if daily_tokens + estimated_tokens > config.max_tokens_per_day:
        # Calculate seconds until midnight
        tomorrow = day_start + timedelta(days=1)
        seconds_until_reset = int((tomorrow - now).total_seconds())

        return RateLimitResult(
            allowed=False,
            reason=f"Daily token limit exceeded: {daily_tokens}/{config.max_tokens_per_day} tokens",
            retry_after=seconds_until_reset,
            current_usage=daily_tokens,
            limit=config.max_tokens_per_day,
        )

    return RateLimitResult(
        allowed=True,
        current_usage=hourly_usage,
        limit=config.max_requests_per_hour,
    )


def enforce_rate_limit(
    user_id: int,
    company_id: int,
    config: RateLimitConfig,
    storage: RateLimitStorage,
    estimated_tokens: int = 0,
) -> RateLimitResult:
    """Check the rate limit and record usage if allowed, in one call.

    Prefers an atomic backend: if ``storage`` implements
    :class:`AtomicRateLimitStorage`, the check and the usage write happen
    race-free inside the backend. Otherwise it falls back to a non-atomic
    ``check`` followed by ``record_usage`` and logs that the TOCTOU window
    applies — concurrent requests for the same user may overshoot the limit
    unless the backend serializes them itself (see :class:`RateLimitStorage`).

    Args:
        user_id: The user making the request.
        company_id: The user's company (recorded with the usage).
        config: Rate limit configuration.
        storage: Storage backend for usage data.
        estimated_tokens: Estimated tokens for this request.

    Returns:
        RateLimitResult with allowed status and details. Usage is recorded only
        when ``allowed`` is True.
    """
    if isinstance(storage, AtomicRateLimitStorage):
        return storage.check_and_record(user_id, company_id, config, estimated_tokens)

    _logger.debug(
        "Rate limit enforced via non-atomic check+record for user %s; "
        "concurrent requests may overshoot the limit. Implement "
        "AtomicRateLimitStorage for strict enforcement.",
        user_id,
    )
    result = check_rate_limit(user_id, config, storage, estimated_tokens)
    if result.allowed:
        storage.record_usage(user_id, company_id, estimated_tokens)
    return result


def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Estimate token count for text.

    Uses tiktoken for accurate estimation.

    Args:
        text: Text to estimate
        model: Model name (for tokenizer selection)

    Returns:
        Estimated token count
    """
    try:
        import tiktoken

        # Map models to encodings
        encoding_map = {
            "gpt-4": "cl100k_base",
            "gpt-4o": "cl100k_base",
            "gpt-4-turbo": "cl100k_base",
            "claude": "cl100k_base",  # Approximation
        }

        # Default to cl100k_base
        encoding_name = encoding_map.get(model.split("-")[0], "cl100k_base")
        encoding = tiktoken.get_encoding(encoding_name)

        return len(encoding.encode(text))

    except ImportError:
        # Fallback: rough estimate (4 chars per token)
        return len(text) // 4
