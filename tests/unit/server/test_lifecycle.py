"""Tests for server/lifecycle.py — port announcement and parent-PID watchdog.

The sockets bound here are real ephemeral sockets; only uvicorn's serve loop is
substituted, since actually serving would block the test run.
"""

import asyncio
import os
import signal
import socket as _socket
from unittest.mock import patch

import pytest

from eq_chatbot_core.server.lifecycle import (
    _bind_listening_socket,
    _parent_alive,
    _parent_watchdog,
    run_server,
)

pytestmark = pytest.mark.unit


class TestParentAlive:
    def test_own_process_is_alive(self):
        assert _parent_alive(os.getpid()) is True

    def test_zero_and_negative_pids_rejected(self):
        """PID 0 and negatives address process *groups* for os.kill — never a parent."""
        assert _parent_alive(0) is False
        assert _parent_alive(-1) is False

    def test_missing_process_is_not_alive(self):
        with patch("os.kill", side_effect=ProcessLookupError):
            assert _parent_alive(12345) is False

    def test_permission_error_counts_as_alive(self):
        """EPERM means the process exists, we just may not signal it."""
        with patch("os.kill", side_effect=PermissionError):
            assert _parent_alive(12345) is True

    def test_other_oserror_counts_as_dead(self):
        with patch("os.kill", side_effect=OSError("unexpected")):
            assert _parent_alive(12345) is False


class TestBindListeningSocket:
    def test_port_zero_binds_ephemeral_port(self):
        sock = _bind_listening_socket("127.0.0.1", 0)
        try:
            host, port = sock.getsockname()[:2]
            assert host == "127.0.0.1"
            assert port > 0
        finally:
            sock.close()

    def test_reuseaddr_is_set(self):
        sock = _bind_listening_socket("127.0.0.1", 0)
        try:
            assert sock.getsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR) != 0
        finally:
            sock.close()

    def test_reuseport_is_not_set(self):
        """SO_REUSEPORT would let a second process bind the same port — not wanted."""
        if not hasattr(_socket, "SO_REUSEPORT"):
            pytest.skip("SO_REUSEPORT not available on this platform")

        sock = _bind_listening_socket("127.0.0.1", 0)
        try:
            assert sock.getsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEPORT) == 0
        finally:
            sock.close()


class TestParentWatchdog:
    async def test_signals_self_when_parent_disappears(self):
        sent = []

        with patch("eq_chatbot_core.server.lifecycle._parent_alive", return_value=False):
            with patch("os.kill", side_effect=lambda pid, sig: sent.append((pid, sig))):
                await _parent_watchdog(4242, poll_interval=0.01)

        assert sent == [(os.getpid(), signal.SIGTERM)]

    async def test_keeps_polling_while_parent_lives(self):
        """The watchdog must not fire on a living parent."""
        with patch("eq_chatbot_core.server.lifecycle._parent_alive", return_value=True):
            with patch("os.kill") as mock_kill:
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(_parent_watchdog(4242, poll_interval=0.01), timeout=0.08)

        mock_kill.assert_not_called()


class TestRunServer:
    def _patched_uvicorn(self, served):
        """Replace uvicorn.Server.serve with a no-op that records the socket."""

        async def _fake_serve(self, sockets=None):
            served.append(sockets)

        return patch("uvicorn.Server.serve", _fake_serve)

    def test_announces_bound_port_on_stdout(self, capsys):
        served = []
        with self._patched_uvicorn(served):
            run_server(app=None, host="127.0.0.1", port=0)

        out = capsys.readouterr().out.strip()
        assert out.startswith("LISTENING ON host=127.0.0.1 port=")
        announced = int(out.rsplit("port=", 1)[1])
        assert announced > 0

    def test_prebound_socket_is_handed_to_uvicorn(self):
        """uvicorn must serve the socket we bound, so the announced port is the real one."""
        served = []
        with self._patched_uvicorn(served):
            run_server(app=None, host="127.0.0.1", port=0)

        assert len(served) == 1
        assert served[0] is not None and len(served[0]) == 1

    def test_socket_is_closed_after_serving(self, capsys):
        served = []
        with self._patched_uvicorn(served):
            run_server(app=None, host="127.0.0.1", port=0)

        sock = served[0][0]
        with pytest.raises(OSError):
            sock.getsockname()

    def test_socket_closed_even_when_serve_raises(self):
        served = []

        async def _boom(self, sockets=None):
            served.append(sockets)
            raise RuntimeError("serve failed")

        with patch("uvicorn.Server.serve", _boom):
            with pytest.raises(RuntimeError, match="serve failed"):
                run_server(app=None, host="127.0.0.1", port=0)

        with pytest.raises(OSError):
            served[0][0].getsockname()

    def test_watchdog_started_only_with_parent_pid(self):
        served = []
        with self._patched_uvicorn(served):
            with patch("eq_chatbot_core.server.lifecycle._parent_watchdog") as mock_wd:
                run_server(app=None, host="127.0.0.1", port=0)
                mock_wd.assert_not_called()

                run_server(app=None, host="127.0.0.1", port=0, parent_pid=0)
                mock_wd.assert_not_called()
