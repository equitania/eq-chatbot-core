"""HTTP server mode for eq_chatbot_core (optional, requires the ``[server]`` extra).

Exposes the LLM provider abstraction over a localhost HTTP API with bearer-token
auth and SSE streaming. Designed to be run as a sidecar by external apps that
can't easily import Python directly (e.g. fr-designer Avalonia desktop app
spawning a frozen sidecar binary).

Usage from Python::

    from eq_chatbot_core.server import create_app, run_server
    app = create_app(auth_token="<random-32-byte-token>")
    run_server(app, host="127.0.0.1", port=0, parent_pid=os.getppid())

Usage from the CLI::

    eq-chatbot serve --port 0 --auth-token-fd 0 --parent-pid 1234 < token.txt
"""

from __future__ import annotations


def create_app(auth_token: str):  # type: ignore[no-untyped-def]
    """Lazy proxy to the real factory so importing the package without the
    ``[server]`` extra installed only fails when the server is actually used.

    Pure imports of ``eq_chatbot_core`` (CLI, providers, RAG, MCP) MUST keep
    working without ``fastapi`` / ``uvicorn`` / ``sse-starlette`` on disk.
    """
    from eq_chatbot_core.server.app import create_app as _create_app

    return _create_app(auth_token)


def run_server(app, **kwargs):  # type: ignore[no-untyped-def]
    """Lazy proxy to :func:`eq_chatbot_core.server.lifecycle.run_server`."""
    from eq_chatbot_core.server.lifecycle import run_server as _run_server

    return _run_server(app, **kwargs)


__all__ = ["create_app", "run_server"]
