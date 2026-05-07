"""Server lifecycle: pre-bound socket for ephemeral-port discovery, parent-PID watchdog.

The sidecar is launched by an external parent process (e.g. fr-designer) which
needs to know which port the server bound to. We pre-bind the socket ourselves
(rather than letting uvicorn bind), read ``getsockname()``, print
``LISTENING ON host=... port=...`` to stdout for the parent to scrape, then
hand the socket to uvicorn.

The parent-watchdog polls ``os.kill(parent_pid, 0)`` every few seconds. When
that fails the parent has died (crash / kill / orderly shutdown that didn't
SIGTERM us) and we shut ourselves down so we don't leak as a zombie.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket as _socket
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("eq_chatbot_core.server.lifecycle")


def _parent_alive(pid: int) -> bool:
    """Cross-platform parent-alive probe.

    POSIX: ``os.kill(pid, 0)`` returns nothing if the process exists,
    raises ``ProcessLookupError`` if not, and ``PermissionError`` if it exists
    but we're not allowed to signal it (which still means *alive*). On Windows,
    Python 3.7+ also supports ``os.kill(pid, 0)``.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours to signal
    except OSError:
        return False
    return True


async def _parent_watchdog(parent_pid: int, poll_interval: float = 5.0) -> None:
    """Polls parent PID; sends SIGTERM to self when parent dies."""
    while True:
        await asyncio.sleep(poll_interval)
        if not _parent_alive(parent_pid):
            logger.warning("Parent process %d disappeared — shutting down sidecar.", parent_pid)
            os.kill(os.getpid(), signal.SIGTERM)
            return


def _bind_listening_socket(host: str, port: int) -> _socket.socket:
    """Bind a TCP socket on (host, port). port=0 picks an ephemeral port."""
    sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    # SO_REUSEADDR helps avoid TIME_WAIT issues during repeated dev restarts.
    # Not SO_REUSEPORT (that allows multiple binders, which we explicitly don't want).
    sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    return sock


def run_server(
    app: FastAPI,
    host: str = "127.0.0.1",
    port: int = 0,
    parent_pid: int | None = None,
    log_level: str = "warning",
) -> None:
    """Bind, announce, then run uvicorn until the process is signalled.

    The parent process is expected to read ``LISTENING ON host=H port=P`` from
    stdout to discover the bound port. The line is flushed immediately.
    """
    import uvicorn

    sock = _bind_listening_socket(host, port)
    bound_host, bound_port = sock.getsockname()[:2]

    # Announce the bound address BEFORE starting uvicorn (the parent may be
    # waiting for this line on stdout to start sending requests).
    print(f"LISTENING ON host={bound_host} port={bound_port}", flush=True)

    config = uvicorn.Config(
        app,
        host=bound_host,
        port=bound_port,
        log_level=log_level,
        access_log=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    async def _serve_with_watchdog() -> None:
        if parent_pid is not None and parent_pid > 0:
            asyncio.create_task(_parent_watchdog(parent_pid))
        await server.serve(sockets=[sock])

    try:
        asyncio.run(_serve_with_watchdog())
    finally:
        try:
            sock.close()
        except OSError:
            pass
