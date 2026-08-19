"""Regression: ``is_connected`` must span both websockets APIs.

websockets < 14 exposed a boolean ``closed``; websockets >= 14 replaced it with
a ``state`` enum. The original implementation read
``not getattr(ws, "closed", True)``, so from version 14 on the missing attribute
defaulted to "closed" and the property was permanently False. Every realtime
send then raised "WebSocket is not connected" against a healthy socket, and the
defensive default turned a hard AttributeError into a silent misdiagnosis.

These tests use stand-ins for both shapes, so they hold whichever websockets
version is installed and need no network.
"""

from __future__ import annotations

import pytest

from eq_chatbot_core.realtime.websocket_client import _WS_STATE_OPEN, BaseRealtimeWebsocketClient


class _ModernSocket:
    """websockets >= 14: a `state` enum, no `closed`."""

    def __init__(self, state):
        self.state = state


class _LegacySocket:
    """websockets < 14: a boolean `closed`, no `state`."""

    def __init__(self, closed: bool):
        self.closed = closed


class _Client(BaseRealtimeWebsocketClient):
    """Minimal concrete subclass — only is_connected is under test."""

    def __init__(self):  # noqa: D107 - deliberately skips the base __init__
        self._ws = None

    async def _on_connected(self) -> None:  # pragma: no cover - never called here
        pass

    async def _on_message(self, message):  # pragma: no cover - never called here
        pass

    def _connection_error_endpoint(self) -> str:  # pragma: no cover
        return "test://endpoint"


@pytest.fixture
def client():
    return _Client()


def test_no_socket_is_not_connected(client):
    client._ws = None
    assert client.is_connected is False


@pytest.mark.skipif(_WS_STATE_OPEN is None, reason="installed websockets predates the state enum")
def test_open_state_counts_as_connected(client):
    """The bug: this returned False on every websockets >= 14."""
    client._ws = _ModernSocket(_WS_STATE_OPEN)
    assert client.is_connected is True


@pytest.mark.skipif(_WS_STATE_OPEN is None, reason="installed websockets predates the state enum")
def test_non_open_state_is_not_connected(client):
    from websockets.protocol import State

    for state in (State.CONNECTING, State.CLOSING, State.CLOSED):
        client._ws = _ModernSocket(state)
        assert client.is_connected is False, f"{state} must not count as connected"


@pytest.mark.skipif(_WS_STATE_OPEN is None, reason="legacy path only reachable without the state enum")
def test_modern_socket_without_state_attribute_is_not_connected(client):
    """A socket object exposing neither attribute must read as disconnected."""

    class _Bare:
        pass

    client._ws = _Bare()
    assert client.is_connected is False


def test_legacy_closed_attribute_still_honoured(client, monkeypatch):
    """Force the pre-14 branch and verify it reads `closed` as before."""
    monkeypatch.setattr("eq_chatbot_core.realtime.websocket_client._WS_STATE_OPEN", None, raising=False)
    client._ws = _LegacySocket(closed=False)
    assert client.is_connected is True
    client._ws = _LegacySocket(closed=True)
    assert client.is_connected is False
