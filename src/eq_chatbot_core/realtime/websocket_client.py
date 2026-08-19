"""WebSocket base class for realtime providers.

Handles connect/send/recv/close lifecycle, connection-leak protection,
exponential backoff reconnect, and error normalization across websockets 13.x–16.x.
"""

import asyncio
import inspect
import json
import logging
import random
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

# Annotated as Any because the optional-import fallback rebinds both names to
# None: without the annotation the module type and None are incompatible, and
# every attribute access on them (e.g. websockets.connect) is checked against a
# module type the [realtime] extra may not have installed at all.
websockets: Any
ws_exceptions: Any

_websockets_available = True
try:
    import websockets
    from websockets import exceptions as ws_exceptions
except ImportError:
    _websockets_available = False
    websockets = None
    ws_exceptions = None

_logger = logging.getLogger(__name__)

# Detect which header kwarg websockets.connect accepts — done once at import time
# to avoid exception-as-control-flow inside connect() (PITFALL: TypeError from the
# fallback arm would be silently wrapped as RealtimeConnectionError, hiding the real cause).
# websockets >=13 uses additional_headers; older versions used extra_headers.
_CONNECT_HEADERS_KWARG: str = "extra_headers"
if websockets is not None:
    try:
        _sig = inspect.signature(websockets.connect)
        if "additional_headers" in _sig.parameters:
            _CONNECT_HEADERS_KWARG = "additional_headers"
    except (ValueError, TypeError):
        pass  # If signature introspection fails, fall back to extra_headers

# websockets >= 14 dropped the boolean `closed` attribute in favour of a `state`
# enum. Resolve the OPEN sentinel once at import; None means the installed
# version still exposes `closed`.
_WS_STATE_OPEN = None
if websockets is not None:
    try:
        from websockets.protocol import State as _WsState

        _WS_STATE_OPEN = _WsState.OPEN
    except ImportError:
        pass  # websockets < 14 — the legacy `closed` attribute applies


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class RealtimeClientError(Exception):
    """Base exception for all realtime client errors."""


class RealtimeConnectionError(RealtimeClientError):
    """Raised when a connection attempt fails or a network error occurs."""


class RealtimeClosedError(RealtimeClientError):
    """Raised when the WebSocket connection is closed or disconnected.

    Attributes:
        code: WebSocket close code (1000=normal, 1006=abnormal). retriable: True when code != 1000.
    """

    def __init__(
        self,
        message: str,
        code: int | None = None,
        retriable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retriable = retriable


class RealtimeRateLimitError(RealtimeClientError):
    """Raised when the provider returns HTTP 429 during the WebSocket handshake.

    Attributes:
        retry_after: Seconds to wait before retrying, if provided by the server.
    """

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RealtimeProtocolError(RealtimeClientError):
    """Raised when a malformed or unexpected frame is received."""


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class BaseRealtimeWebsocketClient(ABC):
    """WebSocket base class for realtime providers.

    Handles connect/send/recv/close lifecycle, connection-leak protection,
    exponential backoff reconnect, and error normalization across websockets 13.x–16.x.
    """

    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self._url = url
        self._headers = headers or {}
        self._ws: Any = None

    @property
    def is_connected(self) -> bool:
        """Return True when the WebSocket connection is open.

        Spans both websockets APIs: < 14 exposes a boolean ``closed``, >= 14
        replaced it with a ``state`` enum. The previous implementation read
        ``getattr(ws, "closed", True)``, so on any version from 14 on the
        missing attribute defaulted to "closed" and this property was
        permanently False — every send raised "WebSocket is not connected"
        against a perfectly healthy socket, and the default masked it as a
        connection problem instead of surfacing an AttributeError.
        """
        ws = self._ws
        if ws is None:
            return False
        if _WS_STATE_OPEN is not None:
            return getattr(ws, "state", None) is _WS_STATE_OPEN
        return not getattr(ws, "closed", True)

    @abstractmethod
    async def _on_connected(self) -> None:
        """Called after WebSocket handshake completes. Raise to abort — connect() will call close()."""
        ...

    @abstractmethod
    async def _on_message(self, raw: str) -> None:
        """Called for each received text frame."""
        ...

    @abstractmethod
    def _connection_error_endpoint(self) -> str:
        """Return a REDACTED URL string safe for error messages and logs.

        You MUST override this and strip API keys before returning.
        Raise NotImplementedError if called directly — no safe default exists,
        because URLs may embed secrets (e.g. ?api_key=sk-...).
        """
        raise NotImplementedError("_connection_error_endpoint must be overridden to redact secrets from URL")

    async def connect(self) -> None:
        """Open the WebSocket connection and invoke _on_connected().

        Idempotent: does nothing if already connected.
        Raises RealtimeRateLimitError on HTTP 429 from the WS handshake.
        Raises RealtimeConnectionError on any other connection failure.
        Calls close() if _on_connected() raises (PITFALL-04: connection-leak protection).
        """
        if self.is_connected:
            return

        try:
            # Use the header kwarg detected at import time (_CONNECT_HEADERS_KWARG).
            # Avoids exception-as-control-flow: if `extra_headers` fallback also raised
            # TypeError, it would be silently wrapped as RealtimeConnectionError.
            self._ws = await websockets.connect(
                self._url,
                **{_CONNECT_HEADERS_KWARG: self._headers},
            )
        except Exception as exc:
            # Cross-version HTTP status introspection (handles both legacy and new asyncio impl)
            status_code = getattr(getattr(exc, "response", None), "status_code", None) or getattr(
                exc, "status_code", None
            )
            if status_code == 429:
                raise RealtimeRateLimitError(
                    f"Rate limited by {self._connection_error_endpoint()}",
                    retry_after=None,
                ) from exc
            raise RealtimeConnectionError(f"Failed to connect to {self._connection_error_endpoint()}: {exc}") from exc

        try:
            await self._on_connected()
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        """Close the WebSocket connection. Idempotent — safe to call when already closed."""
        if self._ws is None:
            return
        try:
            await self._ws.close()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._ws = None

    async def send_json(self, data: dict[str, Any]) -> None:
        """Serialize *data* as JSON and send it as a text frame.

        Raises RealtimeConnectionError if not connected.
        """
        if not self.is_connected:
            raise RealtimeConnectionError("Cannot send: WebSocket is not connected")
        await self._ws.send(json.dumps(data))

    async def recv_json(self) -> dict[str, Any]:
        """Receive the next text frame and deserialize it as JSON.

        Raises RealtimeClosedError when the connection is closed mid-receive.
        """
        try:
            raw: Any = await self._ws.recv()
        except Exception as exc:
            # Map ws_exceptions.ConnectionClosed → RealtimeClosedError
            if ws_exceptions is not None and isinstance(exc, ws_exceptions.ConnectionClosed):
                code = getattr(exc, "code", None) or getattr(getattr(exc, "rcvd", None), "code", None)
                retriable = code != 1000
                raise RealtimeClosedError("WebSocket closed", code=code, retriable=retriable) from exc
            raise
        result: dict[str, Any] = json.loads(raw)
        return result

    async def iter_events(self) -> AsyncIterator[dict[str, Any]]:
        """Yield parsed JSON frames from the WebSocket until the connection closes.

        This is the primary event-consumption API for production event loops.
        `_on_message` is the low-level callback used by subclasses that prefer
        push-style processing; `iter_events` is preferred for pull-style consumers.

        Raises RealtimeClosedError when the connection closes.
        """
        while True:
            yield await self.recv_json()

    async def connect_with_backoff(
        self,
        max_attempts: int = 5,
        base_delay_s: float = 1.0,
        max_delay_s: float = 30.0,
    ) -> None:
        """Connect with truncated exponential backoff and jitter.

        Formula: delay = min(base * 2**attempt + random.uniform(0, 1), max_delay)
        Deterministic in tests: patch asyncio.sleep and random.uniform.

        Raises RealtimeConnectionError after *max_attempts* failed attempts.
        RealtimeRateLimitError is also retried — when retry_after is provided by
        the server, that delay is used (capped at max_delay_s); otherwise the
        standard exponential backoff applies.
        """
        last_exc: RealtimeClientError | None = None
        for attempt in range(max_attempts):
            try:
                await self.connect()
                return
            except (RealtimeConnectionError, RealtimeRateLimitError) as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    if isinstance(exc, RealtimeRateLimitError) and exc.retry_after is not None:
                        delay = min(exc.retry_after, max_delay_s)
                    else:
                        delay = min(
                            base_delay_s * (2**attempt) + random.uniform(0, 1),
                            max_delay_s,
                        )
                    _logger.warning(
                        "Realtime connect attempt %d/%d failed, retrying in %.1fs: %s",
                        attempt + 1,
                        max_attempts,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
        raise RealtimeConnectionError(
            f"Failed to connect after {max_attempts} attempts (last error: RealtimeRateLimitError)"
            if isinstance(last_exc, RealtimeRateLimitError)
            else f"Failed to connect after {max_attempts} attempts"
        ) from last_exc

    async def __aenter__(self) -> "BaseRealtimeWebsocketClient":
        """Connect and return self."""
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Close the connection on context exit."""
        await self.close()


__all__ = [
    "BaseRealtimeWebsocketClient",
    "RealtimeClientError",
    "RealtimeConnectionError",
    "RealtimeClosedError",
    "RealtimeRateLimitError",
    "RealtimeProtocolError",
]
