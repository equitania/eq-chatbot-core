"""
Rate limiting logic for API requests.

This module provides the logic for rate limiting.
The actual storage is handled by Odoo models.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol


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
    now = datetime.now(timezone.utc)

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
