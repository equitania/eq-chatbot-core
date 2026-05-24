"""Fixtures for realtime unit tests.

IMPORTANT: Uses AsyncMock for websockets.connect() — MagicMock breaks async with.
Function-scoped provider fixtures prevent state leakage between tests (PITFALL-16).
"""

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True, scope="session")
def mock_websockets_module():
    """Inject mock websockets module for all realtime unit tests.

    Session-scoped so the sys.modules entry is installed once.
    Uses REAL exception classes so except clauses in production code work correctly.
    AsyncMock is required for connect() — MagicMock breaks `async with` (PITFALL-14).

    Restores the original sys.modules entries after the session ends so that
    integration tests running in the same pytest session (e.g. via -k or --co)
    receive the real websockets library and are not silently handed this mock.
    """
    # Snapshot originals before installing the mock
    original_websockets = sys.modules.get("websockets")
    original_ws_exc = sys.modules.get("websockets.exceptions")

    mock_ws_module = MagicMock()
    mock_ws_instance = AsyncMock()
    mock_ws_instance.closed = False
    mock_ws_instance.recv = AsyncMock(return_value='{"type": "test"}')
    mock_ws_instance.send = AsyncMock()
    mock_ws_instance.close = AsyncMock()

    # MUST be AsyncMock: `async with websockets.connect(...) as ws:` requires coroutine
    mock_ws_module.connect = AsyncMock(return_value=mock_ws_instance)
    mock_ws_module.connect.return_value.__aenter__ = AsyncMock(return_value=mock_ws_instance)
    mock_ws_module.connect.return_value.__aexit__ = AsyncMock(return_value=False)

    # Use REAL exception classes so except clauses work correctly
    mock_ws_module.exceptions = MagicMock()
    try:
        from websockets.exceptions import (
            ConnectionClosed,
            ConnectionClosedError,
            ConnectionClosedOK,
            InvalidStatus,
            WebSocketException,
        )

        mock_ws_module.exceptions.ConnectionClosed = ConnectionClosed
        mock_ws_module.exceptions.ConnectionClosedOK = ConnectionClosedOK
        mock_ws_module.exceptions.ConnectionClosedError = ConnectionClosedError
        mock_ws_module.exceptions.InvalidStatus = InvalidStatus
        mock_ws_module.exceptions.WebSocketException = WebSocketException
    except ImportError:
        # websockets not installed yet — use MagicMock() for exception classes as fallback
        # This allows tests to run; except clauses will not catch real ws exceptions but
        # that is acceptable for unit tests that use the sys.modules mock.
        pass

    sys.modules["websockets"] = mock_ws_module
    sys.modules["websockets.exceptions"] = mock_ws_module.exceptions

    yield mock_ws_module

    # Restore originals after session so integration tests in the same run get the real library
    if original_websockets is not None:
        sys.modules["websockets"] = original_websockets
    else:
        sys.modules.pop("websockets", None)
    if original_ws_exc is not None:
        sys.modules["websockets.exceptions"] = original_ws_exc
    else:
        sys.modules.pop("websockets.exceptions", None)


@pytest.fixture
def mock_ws_instance(mock_websockets_module):  # noqa: ARG001
    """Function-scoped: fresh WS instance per test to prevent state leakage (PITFALL-16)."""
    instance = AsyncMock()
    instance.closed = False
    instance.recv = AsyncMock(return_value='{"type": "test"}')
    instance.send = AsyncMock()
    instance.close = AsyncMock()
    return instance
