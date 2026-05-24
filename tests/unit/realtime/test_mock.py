"""Unit tests for MockRealtimeProvider.

Tests isinstance Protocol conformance and queue-backed event flow.
"""

import pytest

from eq_chatbot_core.realtime.contracts import RealtimeAdapterContract
from eq_chatbot_core.realtime.mock import MockRealtimeProvider


@pytest.mark.unit
def test_isinstance_check() -> None:
    """MockRealtimeProvider satisfies RealtimeAdapterContract via structural typing."""
    assert isinstance(MockRealtimeProvider(), RealtimeAdapterContract)

    # Negative: a class missing iter_normalized_events should NOT satisfy it
    class _Incomplete:
        async def connect(self) -> None:
            pass

    assert not isinstance(_Incomplete(), RealtimeAdapterContract)


@pytest.mark.unit
async def test_connect_sets_connected() -> None:
    m = MockRealtimeProvider()
    await m.connect()
    assert m._connected is True


@pytest.mark.unit
async def test_close_sets_disconnected() -> None:
    m = MockRealtimeProvider()
    await m.connect()
    await m.close()
    assert m._connected is False


@pytest.mark.unit
async def test_context_manager() -> None:
    async with MockRealtimeProvider() as m:
        assert m._connected is True
    assert m._connected is False


@pytest.mark.unit
async def test_enqueue_and_iter() -> None:
    m = MockRealtimeProvider()
    m.enqueue_event({"type": "session.ready", "payload": {}})
    m.enqueue_event({"type": "response.done", "payload": {}})
    events = []
    async for ev in m.iter_normalized_events():
        events.append(ev)
    assert len(events) == 2
    assert events[0]["type"] == "session.ready"
    assert events[1]["type"] == "response.done"


@pytest.mark.unit
async def test_append_client_audio_even_ok() -> None:
    m = MockRealtimeProvider()
    await m.append_client_audio(b"\x00\x01")  # 2 bytes — even, should not raise


@pytest.mark.unit
async def test_append_client_audio_odd_raises() -> None:
    m = MockRealtimeProvider()
    with pytest.raises(ValueError, match="even-length"):
        await m.append_client_audio(b"\x00")  # 1 byte — odd, must raise
