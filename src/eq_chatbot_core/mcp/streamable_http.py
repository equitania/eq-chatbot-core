"""
MCP client for the Streamable HTTP transport.

Implements the client side of the MCP specification 2025-03-26 / 2025-06-18
"Streamable HTTP" transport, which replaced the 2024-11-05 SSE transport that
:class:`eq_chatbot_core.mcp.client.MCPClient` still speaks:

- There is exactly ONE endpoint (e.g. ``https://host/mcp``). Every JSON-RPC
  message goes there as an HTTP POST; the server answers either with a plain
  ``application/json`` body or with a ``text/event-stream`` that carries the
  response as an SSE ``message`` event.
- Notifications are answered with HTTP 202 and no body.
- A server MAY assign a session (``Mcp-Session-Id`` response header on
  ``initialize``); the client then sends that header on every request and
  re-initialises once when the server reports HTTP 404 for a stale session.
  Stateless servers (e.g. the .NET SDK with ``SessionMode = Stateless``) send
  no header and the client behaves accordingly.
- After the version negotiation the client sends ``MCP-Protocol-Version`` on
  every request, as the 2025-06-18 revision asks.

Security: the endpoint goes through the same SSRF validation and DNS-rebinding
pinning as the SSE client. ``allow_private_ranges=True`` switches the
validation to LAN mode for MCP servers that live on the intranet — private and
loopback addresses become reachable, link-local / cloud-metadata targets stay
blocked.

References:
- https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
"""

import json
import logging
import threading
import time
from typing import Any, Self
from urllib.parse import urlparse

from eq_chatbot_core.mcp.client import MCPToolResult
from eq_chatbot_core.utils.secret_scrub import scrub_secrets as _scrub
from eq_chatbot_core.utils.url_validation import build_pinned_transport as _build_pinned_transport
from eq_chatbot_core.utils.url_validation import validate_url as _validate_url
from eq_chatbot_core.version import __version__

logger = logging.getLogger(__name__)

#: Protocol revision this client asks for in ``initialize``.
PROTOCOL_VERSION = "2025-06-18"

SESSION_HEADER = "Mcp-Session-Id"
PROTOCOL_HEADER = "MCP-Protocol-Version"

_MAX_ERROR_BODY = 500


class StreamableHTTPMCPClient:
    """
    MCP client using the Streamable HTTP transport (single POST endpoint).

    The public surface mirrors :class:`MCPClient` so that callers can switch
    transports without touching their code: ``connect()``, ``disconnect()``,
    ``list_tools()``, ``call_tool()``, ``get_tool_schema()``, ``close()`` and
    the context-manager protocol.
    """

    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        *,
        allow_private_ranges: bool = False,
    ):
        """
        Initialize the Streamable HTTP client.

        Args:
            url: The MCP endpoint, e.g. ``http://mcp-host:5100/mcp``. Used
                verbatim — the transport has no well-known suffix to append.
            api_key: Optional bearer token sent as ``Authorization: Bearer …``.
            timeout: Connect/read timeout per request in seconds.
            allow_private_ranges: LAN mode — permit private and loopback
                targets (an MCP server on the intranet). Link-local, reserved
                and multicast addresses remain blocked either way.

        Raises:
            ValueError: If the URL scheme is not http/https, or the URL
                resolves to a disallowed address for the chosen mode.
        """
        self._pinned_ips: dict[str, frozenset[str]] = {}
        self._pinned_lock = threading.Lock()
        ips = _validate_url(url, allow_private_ranges=allow_private_ranges)
        host = urlparse(url).hostname
        if host and ips:
            self._pinned_ips[host] = ips

        self.url = url
        self.api_key = api_key
        self.timeout = timeout
        self.allow_private_ranges = allow_private_ranges

        self._client: Any = None
        self._session_id: str | None = None
        self._protocol_version: str | None = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._initialized = False

    # ------------------------------------------------------------------ HTTP

    def _get_headers(self) -> dict[str, str]:
        """Headers for the next request — session and protocol headers included once known."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self._session_id:
            headers[SESSION_HEADER] = self._session_id
        if self._protocol_version:
            headers[PROTOCOL_HEADER] = self._protocol_version
        return headers

    @property
    def client(self) -> Any:
        """Lazy httpx2 client with the DNS-rebinding-aware transport."""
        if self._client is None:
            try:
                import httpx2
            except ImportError as e:
                raise ImportError("httpx2 package not installed. Install with: pip install httpx2") from e
            transport = _build_pinned_transport(self._pinned_ips, self._pinned_lock)
            self._client = httpx2.Client(timeout=self.timeout, transport=transport)
        return self._client

    def _capture_session(self, response: Any) -> None:
        """Remember a server-assigned session id (sent back on every later request)."""
        session_id = response.headers.get(SESSION_HEADER.lower()) or response.headers.get(SESSION_HEADER)
        if session_id and session_id != self._session_id:
            self._session_id = session_id
            logger.info("MCP server assigned a session id")

    @staticmethod
    def _error_body(response: Any) -> str:
        try:
            response.read()
            text: str = response.text
        except Exception:  # noqa: BLE001 - body is diagnostics only
            return ""
        return _scrub(text[:_MAX_ERROR_BODY])

    # ------------------------------------------------------------ JSON-RPC

    def _next_id(self) -> int:
        with self._lock:
            self._request_id += 1
            return self._request_id

    @staticmethod
    def _pick_response(payload: Any, request_id: int) -> dict[str, Any] | None:
        """Return the message answering ``request_id`` from a JSON body (single or batch)."""
        candidates = payload if isinstance(payload, list) else [payload]
        for message in candidates:
            if isinstance(message, dict) and message.get("id") == request_id:
                return message
        return None

    def _read_sse_response(self, response: Any, request_id: int) -> dict[str, Any] | None:
        """Consume an SSE stream until the response for ``request_id`` arrives.

        Server-initiated requests and notifications on the same stream are
        logged and skipped; the stream ends when the server closes it.
        """
        data_lines: list[str] = []
        for raw_line in response.iter_lines():
            line = raw_line.rstrip("\r")
            if line == "":
                if data_lines:
                    data = "\n".join(data_lines)
                    data_lines = []
                    message = self._parse_sse_data(data, request_id)
                    if message is not None:
                        return message
                continue
            if line.startswith(":"):
                continue  # comment / keep-alive
            field, _, value = line.partition(":")
            if field == "data":
                data_lines.append(value[1:] if value.startswith(" ") else value)
            # "event", "id" and "retry" carry nothing this client acts on.
        if data_lines:
            return self._parse_sse_data("\n".join(data_lines), request_id)
        return None

    def _parse_sse_data(self, data: str, request_id: int) -> dict[str, Any] | None:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse SSE message: {e}")
            return None
        message = self._pick_response(payload, request_id)
        if message is None:
            logger.debug("Ignoring server-initiated MCP message on the response stream")
        return message

    def _send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        _retry_on_stale_session: bool = True,
    ) -> dict[str, Any]:
        """
        POST a JSON-RPC request and return its ``result``.

        Raises:
            RuntimeError: On HTTP errors, JSON-RPC errors, or a stream that
                ends without the response.
            TimeoutError: If the server does not answer within ``timeout``.
        """
        request_id = self._next_id()
        request: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            request["params"] = params

        try:
            import httpx2

            timeout_errors: tuple[type[BaseException], ...] = (httpx2.TimeoutException,)
        except ImportError:  # pragma: no cover - httpx2 is a core dependency
            timeout_errors = ()

        logger.debug(f"Sending MCP request: {method}")
        stale_session = False
        message: dict[str, Any] | None = None
        try:
            with self.client.stream("POST", self.url, json=request, headers=self._get_headers()) as response:
                status = response.status_code
                if status == 404 and self._session_id:
                    stale_session = True
                elif status in (401, 403):
                    raise RuntimeError(f"MCP authentication failed: HTTP {status}")
                elif status != 200:
                    raise RuntimeError(f"MCP request failed: HTTP {status} - {self._error_body(response)}")
                else:
                    self._capture_session(response)
                    content_type = response.headers.get("content-type", "")
                    if content_type.startswith("text/event-stream"):
                        message = self._read_sse_response(response, request_id)
                    else:
                        response.read()
                        try:
                            payload = json.loads(response.text)
                        except json.JSONDecodeError as e:
                            raise RuntimeError(f"MCP server returned invalid JSON for '{method}': {e}") from e
                        message = self._pick_response(payload, request_id)
        except timeout_errors as err:
            raise TimeoutError(f"MCP request '{method}' timed out after {self.timeout}s") from err

        if stale_session:
            if not _retry_on_stale_session:
                raise RuntimeError("MCP session expired and could not be re-established")
            logger.info("MCP session expired (HTTP 404) - re-initialising")
            self._session_id = None
            self._protocol_version = None
            self._initialized = False
            self.connect()
            return self._send_request(method, params, _retry_on_stale_session=False)

        if message is None:
            raise RuntimeError(f"MCP server closed the response for '{method}' without answering")
        if "error" in message:
            error = message["error"]
            detail = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            raise RuntimeError(f"MCP error: {_scrub(detail)}")
        value: dict[str, Any] = message.get("result") or {}
        return value

    def _send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """POST a JSON-RPC notification; the server acknowledges with 202 (or 200/204)."""
        notification: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            notification["params"] = params
        response = self.client.post(self.url, json=notification, headers=self._get_headers())
        if response.status_code not in (200, 202, 204):
            raise RuntimeError(
                f"MCP notification '{method}' rejected: HTTP {response.status_code} - {self._error_body(response)}"
            )
        self._capture_session(response)

    # ----------------------------------------------------------- lifecycle

    def connect(self) -> None:
        """Run the ``initialize`` handshake once."""
        if self._initialized:
            return
        result = self._send_request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "eq-chatbot-core", "version": __version__},
            },
        )
        negotiated = result.get("protocolVersion")
        if negotiated:
            self._protocol_version = str(negotiated)
        self._send_notification("notifications/initialized")
        self._initialized = True
        logger.info(f"MCP session initialized (Streamable HTTP, protocol {self._protocol_version or 'unspecified'})")

    def disconnect(self) -> None:
        """End the session (HTTP DELETE when the server assigned one) and close the client."""
        if self._client is not None:
            if self._session_id:
                try:
                    # Servers MAY refuse client-initiated termination with 405; that is fine.
                    self._client.delete(self.url, headers=self._get_headers())
                except Exception as e:  # noqa: BLE001 - best effort, we are closing anyway
                    logger.debug(f"MCP session DELETE failed: {_scrub(str(e))}")
            self._client.close()
            self._client = None
        self._session_id = None
        self._protocol_version = None
        self._initialized = False
        logger.info("MCP client disconnected")

    def close(self) -> None:
        """Close the MCP client."""
        self.disconnect()

    def __enter__(self) -> "Self":
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # --------------------------------------------------------------- tools

    def list_tools(self) -> list[dict[str, Any]]:
        """
        Get the list of tools the server offers (follows ``nextCursor`` pagination).

        Returns:
            List of tool definitions with name, description, inputSchema —
            empty on any failure (logged).
        """
        try:
            if not self._initialized:
                self.connect()
            tools: list[dict[str, Any]] = []
            params: dict[str, Any] = {}
            while True:
                result = self._send_request("tools/list", params)
                tools.extend(result.get("tools", []))
                cursor = result.get("nextCursor")
                if not cursor:
                    break
                params = {"cursor": cursor}
            return tools
        except Exception as e:
            logger.error(f"Failed to list MCP tools: {_scrub(str(e))}")
            return []

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """
        Execute an MCP tool.

        A tool-level failure (``isError: true`` in the result) is reported as
        ``success=False`` with the server's text as ``error``; transport and
        protocol failures likewise never raise.
        """
        start_time = time.monotonic()
        try:
            if not self._initialized:
                self.connect()
            result = self._send_request("tools/call", {"name": tool_name, "arguments": arguments})
            execution_time = (time.monotonic() - start_time) * 1000
            content = self._flatten_content(result.get("content", []))
            if result.get("isError"):
                return MCPToolResult(
                    success=False,
                    content=None,
                    error=content if isinstance(content, str) else json.dumps(content),
                    execution_time_ms=execution_time,
                )
            return MCPToolResult(success=True, content=content, execution_time_ms=execution_time)
        except Exception as e:
            execution_time = (time.monotonic() - start_time) * 1000
            logger.error(f"MCP tool call failed: {_scrub(str(e))}")
            return MCPToolResult(
                success=False,
                content=None,
                error=_scrub(str(e)),
                execution_time_ms=execution_time,
            )

    @staticmethod
    def _flatten_content(content: Any) -> Any:
        """Join text content blocks into one string; leave anything else untouched."""
        if content and isinstance(content, list):
            text_content = [
                item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"
            ]
            if text_content:
                return "\n".join(text_content)
        return content

    def get_tool_schema(self, tool_name: str) -> dict[str, Any] | None:
        """Get the schema for a single tool, or ``None`` if the server does not offer it."""
        for tool in self.list_tools():
            if tool.get("name") == tool_name:
                return tool
        return None
