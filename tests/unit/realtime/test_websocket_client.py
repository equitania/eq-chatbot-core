"""Unit tests for BaseRealtimeWebsocketClient — backoff, error hierarchy, context manager.

No real network calls.
"""

from unittest.mock import patch

import pytest

from eq_chatbot_core.realtime.websocket_client import (
    BaseRealtimeWebsocketClient,
    RealtimeClientError,
    RealtimeClosedError,
    RealtimeConnectionError,
    RealtimeProtocolError,
    RealtimeRateLimitError,
)

# ---------------------------------------------------------------------------
# Concrete test subclass
# ---------------------------------------------------------------------------


class ConcreteTestClient(BaseRealtimeWebsocketClient):
    """Minimal concrete subclass for testing BaseRealtimeWebsocketClient."""

    async def _on_connected(self) -> None:
        pass

    async def _on_message(self, raw: str) -> None:
        pass

    def _connection_error_endpoint(self) -> str:
        return "ws://test-endpoint"


# ---------------------------------------------------------------------------
# Backoff tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_connect_with_backoff_3_failures_then_success() -> None:
    """3 failures then success; asserts asyncio.sleep called 3 times with correct delays."""
    attempt_count = 0

    async def mock_connect(self_inner: ConcreteTestClient) -> None:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 4:
            raise RealtimeConnectionError("transient failure")

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    client = ConcreteTestClient(url="ws://test")

    with (
        patch.object(type(client), "connect", mock_connect),
        patch("eq_chatbot_core.realtime.websocket_client.asyncio.sleep", fake_sleep),
        patch("eq_chatbot_core.realtime.websocket_client.random.uniform", return_value=0.0),
    ):
        await client.connect_with_backoff(max_attempts=5, base_delay_s=1.0)

    assert attempt_count == 4
    assert len(sleep_calls) == 3
    assert sleep_calls[0] == pytest.approx(1.0)  # base * 2^0 + jitter(0) = 1.0
    assert sleep_calls[1] == pytest.approx(2.0)  # base * 2^1 + jitter(0) = 2.0
    assert sleep_calls[2] == pytest.approx(4.0)  # base * 2^2 + jitter(0) = 4.0


@pytest.mark.unit
async def test_connect_with_backoff_all_failures_raises() -> None:
    """All max_attempts fail — RealtimeConnectionError is raised after exhausting retries."""
    client = ConcreteTestClient(url="ws://test")

    with pytest.raises(RealtimeConnectionError):
        # base_delay_s=0.0 keeps delays trivially small without patching sleep
        await client.connect_with_backoff(max_attempts=5, base_delay_s=0.0)


# ---------------------------------------------------------------------------
# Error field tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_realtime_closed_error_fields() -> None:
    """RealtimeClosedError exposes code and retriable fields correctly."""
    err = RealtimeClosedError("closed by server", code=1006, retriable=True)
    assert err.code == 1006
    assert err.retriable is True
    assert str(err) == "closed by server"

    err_normal = RealtimeClosedError("normal", code=1000, retriable=False)
    assert err_normal.code == 1000
    assert err_normal.retriable is False


@pytest.mark.unit
def test_realtime_rate_limit_error() -> None:
    """RealtimeRateLimitError exposes retry_after field."""
    err = RealtimeRateLimitError("rate limited", retry_after=30.0)
    assert err.retry_after == 30.0

    err_no_retry = RealtimeRateLimitError("rate limited")
    assert err_no_retry.retry_after is None


# ---------------------------------------------------------------------------
# Error hierarchy tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_error_hierarchy() -> None:
    """All realtime error types are subclasses of RealtimeClientError."""
    assert issubclass(RealtimeConnectionError, Exception)
    assert issubclass(RealtimeClosedError, Exception)
    assert issubclass(RealtimeRateLimitError, Exception)
    assert issubclass(RealtimeProtocolError, Exception)

    assert issubclass(RealtimeConnectionError, RealtimeClientError)
    assert issubclass(RealtimeClosedError, RealtimeClientError)
    assert issubclass(RealtimeRateLimitError, RealtimeClientError)
    assert issubclass(RealtimeProtocolError, RealtimeClientError)


@pytest.mark.unit
def test_base_class_is_abstract() -> None:
    """BaseRealtimeWebsocketClient has the required abstract methods."""
    assert "_on_connected" in BaseRealtimeWebsocketClient.__abstractmethods__
    assert "_on_message" in BaseRealtimeWebsocketClient.__abstractmethods__
    assert "_connection_error_endpoint" in BaseRealtimeWebsocketClient.__abstractmethods__
