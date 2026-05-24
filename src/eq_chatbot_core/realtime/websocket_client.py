"""WebSocket base class for realtime providers.

Handles connect/send/recv/close lifecycle, connection-leak protection,
exponential backoff reconnect, and error normalization across websockets 13.x–16.x.
"""

import asyncio
import json
import logging
import random
from abc import ABC, abstractmethod
from typing import Any

_websockets_available = True
try:
    import websockets
    from websockets import exceptions as ws_exceptions
except ImportError:
    _websockets_available = False
    websockets = None
    ws_exceptions = None

_logger = logging.getLogger(__name__)


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
        """Return True when the WebSocket connection is open."""
        return self._ws is not None and not getattr(self._ws, "closed", True)

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

        Override to strip API keys. Default returns self._url unchanged
        (safe only for providers that don't embed secrets in URL).
        """
        return self._url

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
            try:
                # websockets >=13 uses additional_headers; older used extra_headers
                connection = websockets.connect(
                    self._url,
                    additional_headers=self._headers,
                )
            except TypeError:
                connection = websockets.connect(
                    self._url,
                    extra_headers=self._headers,
                )
            self._ws = await connection
        except Exception as exc:
            # Cross-version HTTP status introspection (handles both legacy and new asyncio impl)
            status_code = getattr(
                getattr(exc, "response", None), "status_code", None
            ) or getattr(exc, "status_code", None)
            if status_code == 429:
                raise RealtimeRateLimitError(
                    f"Rate limited by {self._connection_error_endpoint()}",
                    retry_after=None,
                ) from exc
            raise RealtimeConnectionError(
                f"Failed to connect to {self._connection_error_endpoint()}: {exc}"
            ) from exc

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
            if ws_exceptions is not None and isinstance(
                exc, ws_exceptions.ConnectionClosed
            ):
                code = getattr(exc, "code", None) or getattr(
                    getattr(exc, "rcvd", None), "code", None
                )
                retriable = code != 1000
                raise RealtimeClosedError(
                    "WebSocket closed", code=code, retriable=retriable
                ) from exc
            raise
        result: dict[str, Any] = json.loads(raw)
        return result

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
        """
        last_exc: RealtimeConnectionError | None = None
        for attempt in range(max_attempts):
            try:
                await self.connect()
                return
            except RealtimeConnectionError as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
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
            f"Failed to connect after {max_attempts} attempts"
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
