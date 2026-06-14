"""
MCP client implementations for tool execution.

Supports both SSE (HTTP) and stdio (subprocess) transport modes.
Implements the MCP specification 2024-11-05.

SSE Transport:
- Connect to /sse endpoint to establish SSE connection
- Server sends 'endpoint' event with POST URL for requests
- Client sends JSON-RPC requests via POST
- Server sends JSON-RPC responses via SSE 'message' events

References:
- https://modelcontextprotocol.io/specification/2024-11-05/basic/transports
"""

import asyncio
import json
import logging
import os
import queue
import re
import shutil
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from eq_chatbot_core.utils.url_validation import validate_url as _validate_url
from eq_chatbot_core.version import __version__

logger = logging.getLogger(__name__)

# Allowed commands for StdioMCPClient subprocess execution.
# Only these binaries are permitted to prevent arbitrary command execution.
ALLOWED_STDIO_COMMANDS = frozenset(
    {
        "python",
        "python3",
        "python3.10",
        "python3.11",
        "python3.12",
        "python3.13",
        "node",
        "npx",
        "uvx",
        "uv",
    }
)

# Shell metacharacters that are not allowed in stdio args
_SHELL_META_RE = re.compile(r"[;|&`$(){}!\n\r]")


def _build_pinned_transport(pinned_ips: dict[str, frozenset[str]], lock: threading.Lock) -> Any:
    """Build an httpx HTTPTransport that re-checks DNS resolution against pinned IPs.

    Mitigates DNS rebinding attacks: at validation time the URL's hostname is
    resolved to a set of public IPs; at request time the transport re-resolves
    and rejects the connection if the resolution diverges from that set.

    Note: A small TOCTOU window remains between this check and httpx's actual
    socket connect call. For complete protection, deploy network-level egress
    filtering against private/reserved IP ranges.

    Args:
        pinned_ips: Shared mapping of hostname -> frozenset of allowed IPs.
                    Updated by the caller as new endpoints are validated.
        lock: Lock guarding concurrent updates to pinned_ips.

    Returns:
        Subclass of httpx.HTTPTransport.
    """
    import httpx

    class _PinnedHostTransport(httpx.HTTPTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            host = request.url.host
            with lock:
                pinned = pinned_ips.get(host)
            if pinned:
                try:
                    infos = socket.getaddrinfo(host, None)
                except socket.gaierror as e:
                    raise httpx.ConnectError(f"DNS resolution failed for {host}: {e}") from e
                current = frozenset(str(info[4][0]) for info in infos)
                rogue = current - pinned
                if rogue:
                    raise httpx.ConnectError(
                        f"DNS rebinding detected: {host} now resolves to {sorted(rogue)}, "
                        f"expected subset of pinned set {sorted(pinned)}."
                    )
            return super().handle_request(request)

    return _PinnedHostTransport()


def _validate_stdio_command(command: str, args: list[str] | None = None) -> None:
    """Validate command and args for StdioMCPClient.

    Both the literal command basename AND the PATH-resolved binary's basename are
    checked against the whitelist, so a non-whitelisted alias cannot slip through
    by resolving to an allowed name (or vice versa).

    PATH trust model: this guard restricts *which runtime names* may be launched;
    it does not pin absolute binary paths. If an attacker can place a malicious
    binary named e.g. ``python3`` earlier in ``$PATH``, ``create_subprocess_exec``
    will still resolve to it. Callers running untrusted MCP configs must therefore
    control ``$PATH`` (and the contents of its directories) — this is a runtime
    allowlist, not a sandbox.

    Args:
        command: Command binary name or path
        args: Command arguments

    Raises:
        ValueError: If the command is not in the whitelist or args contain shell metacharacters
    """
    # Extract basename for whitelist check (handles full paths like /usr/bin/python3)
    cmd_basename = os.path.basename(command)

    if cmd_basename not in ALLOWED_STDIO_COMMANDS:
        raise ValueError(
            f"Command '{cmd_basename}' is not in the allowed list: "
            f"{sorted(ALLOWED_STDIO_COMMANDS)}. "
            "Only trusted runtimes are permitted for MCP subprocess execution."
        )

    # Defense in depth: also verify the PATH-resolved binary resolves to an
    # allowed runtime name. Does not defeat a same-named PATH-shadowing binary
    # (see PATH trust model above), but rejects whitelisted aliases that resolve
    # to an unexpected target.
    resolved = shutil.which(command)
    if resolved and os.path.basename(resolved) not in ALLOWED_STDIO_COMMANDS:
        raise ValueError(
            f"Command '{command}' resolves to '{resolved}', which is not an allowed "
            f"runtime: {sorted(ALLOWED_STDIO_COMMANDS)}."
        )

    # Validate args for shell metacharacters
    if args:
        for i, arg in enumerate(args):
            if _SHELL_META_RE.search(arg):
                raise ValueError(
                    f"Argument {i} contains shell metacharacters: '{arg}'. "
                    "Shell metacharacters are not allowed in MCP subprocess arguments."
                )


@dataclass
class MCPToolResult:
    """Result from MCP tool execution."""

    success: bool
    """Whether the tool call succeeded."""

    content: Any
    """The result content (string, dict, etc.)."""

    error: str | None = None
    """Error message if failed."""

    execution_time_ms: float = 0.0
    """Execution time in milliseconds."""


class MCPClient:
    """
    MCP client using SSE transport (HTTP with Server-Sent Events).

    Implements the MCP specification 2024-11-05 SSE transport:
    - Connects to /sse endpoint for server-to-client messages
    - Receives 'endpoint' event with POST URL for client-to-server messages
    - Sends JSON-RPC requests via POST
    - Receives JSON-RPC responses via SSE 'message' events
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize MCP SSE client.

        Args:
            base_url: MCP server base URL (e.g., http://localhost:8000)
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds

        Raises:
            ValueError: If the URL scheme is not http/https or resolves to a private network
        """
        # Pin the base_url's resolved IPs for DNS rebinding protection.
        # Both the SSE client and the request client use a transport that
        # re-checks DNS against this map on every connection.
        self._pinned_ips: dict[str, frozenset[str]] = {}
        self._pinned_lock = threading.Lock()
        ips = _validate_url(base_url)
        base_host = urlparse(base_url).hostname
        if base_host and ips:
            self._pinned_ips[base_host] = ips

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        self._client = None
        self._sse_thread: threading.Thread | None = None
        self._message_endpoint: str | None = None
        self._request_id = 0
        self._pending_requests: dict[int, queue.Queue] = {}
        self._lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._connected = threading.Event()
        self._stop_event = threading.Event()
        self._initialized = False

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @property
    def client(self):
        """Lazy initialization of httpx client with DNS-rebinding-aware transport."""
        if self._client is None:
            try:
                import httpx
            except ImportError as e:
                raise ImportError("httpx package not installed. Install with: pip install httpx") from e

            transport = _build_pinned_transport(self._pinned_ips, self._pinned_lock)
            self._client = httpx.Client(
                headers=self._get_headers(),
                timeout=self.timeout,
                transport=transport,
            )

        return self._client

    def _start_sse_listener(self) -> None:
        """Start SSE listener thread."""
        with self._lock:
            if self._sse_thread is not None and self._sse_thread.is_alive():
                return

            self._stop_event.clear()
            self._connected.clear()
            self._sse_thread = threading.Thread(target=self._sse_listener_loop, daemon=True)
            self._sse_thread.start()

        # Wait for connection and endpoint event (outside lock to avoid deadlock)
        if not self._connected.wait(timeout=self.timeout):
            sse_url = self.base_url if self.base_url.endswith("/sse") else f"{self.base_url}/sse"
            raise TimeoutError(f"Failed to connect to MCP server at {sse_url} within {self.timeout}s")

    def _sse_listener_loop(self) -> None:
        """SSE listener loop running in separate thread."""
        try:
            import httpx
        except ImportError:
            logger.error("httpx not installed")
            return

        # Handle both base URL formats: http://host:port or http://host:port/sse
        if self.base_url.endswith("/sse"):
            sse_url = self.base_url
        else:
            sse_url = f"{self.base_url}/sse"
        logger.info(f"Connecting to MCP SSE endpoint: {sse_url}")

        try:
            # SSE connections need: quick connect, but infinite read timeout
            # httpx.Timeout(default, connect=, read=, write=, pool=)
            sse_timeout = httpx.Timeout(None, connect=10.0)

            # Use a dedicated client with the pinned-host transport so the SSE
            # connection enforces DNS rebinding protection like the request client.
            sse_transport = _build_pinned_transport(self._pinned_ips, self._pinned_lock)
            sse_client = httpx.Client(
                headers=self._get_headers(),
                timeout=sse_timeout,
                transport=sse_transport,
            )

            with sse_client, sse_client.stream("GET", sse_url) as response:
                if response.status_code != 200:
                    logger.error(f"SSE connection failed: HTTP {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    return

                logger.info("SSE connection established, waiting for events...")
                event_type = None
                event_data = []

                for line in response.iter_lines():
                    if self._stop_event.is_set():
                        break

                    line = line.strip()
                    logger.debug(f"SSE line: {line[:100] if line else '(empty)'}")

                    if not line:
                        # Empty line = end of event
                        if event_type and event_data:
                            data = "\n".join(event_data)
                            self._handle_sse_event(event_type, data)
                        event_type = None
                        event_data = []
                        continue

                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        event_data.append(line[5:].strip())

        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to MCP server at {sse_url}: {e}")
        except httpx.TimeoutException as e:
            logger.error(f"Connection timeout to MCP server at {sse_url}: {e}")
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"SSE connection error: {e}")

    def _handle_sse_event(self, event_type: str, data: str) -> None:
        """Handle incoming SSE event."""
        logger.debug(f"SSE event: {event_type}, data: {data[:100]}...")

        if event_type == "endpoint":
            # Server sends the POST endpoint URL. It is either an absolute
            # http(s)://… URL, or a path-only string starting with "/".
            # Anything else (e.g. "file:///etc/passwd" or "ftp://…") is
            # rejected outright — _validate_url will catch non-http schemes,
            # but only if we don't accidentally prepend an origin to them.
            if data.startswith("/"):
                # Relative path — combine with base_url origin (not full
                # base_url, which may contain a path like /sse).
                parsed = urlparse(self.base_url)
                origin = f"{parsed.scheme}://{parsed.netloc}"
                candidate = f"{origin}{data}"
            elif data.startswith(("http://", "https://")):
                candidate = data
            else:
                logger.error(f"Rejecting malformed MCP endpoint: {data[:100]!r}")
                return

            # SSRF protection: validate the server-supplied endpoint URL.
            # A hostile MCP server could otherwise redirect POST traffic to
            # an internal address (which the initial base_url check would block).
            try:
                endpoint_ips = _validate_url(candidate)
            except ValueError as e:
                logger.error(f"Rejecting MCP endpoint URL: {e}")
                return

            # Pin the endpoint's resolved IPs so that the request transport
            # rejects later DNS-rebinding attempts on this hostname.
            endpoint_host = urlparse(candidate).hostname
            if endpoint_host and endpoint_ips:
                with self._pinned_lock:
                    existing = self._pinned_ips.get(endpoint_host)
                    self._pinned_ips[endpoint_host] = existing | endpoint_ips if existing else endpoint_ips

            self._message_endpoint = candidate
            logger.info(f"MCP message endpoint: {self._message_endpoint}")
            self._connected.set()

        elif event_type == "message":
            # JSON-RPC response
            try:
                response = json.loads(data)
                request_id = response.get("id")

                with self._pending_lock:
                    if request_id is not None and request_id in self._pending_requests:
                        self._pending_requests[request_id].put(response)
                    else:
                        logger.warning(f"Received response for unknown request: {request_id}")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse SSE message: {e}")

    def _send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send JSON-RPC request to MCP server via POST.

        Args:
            method: JSON-RPC method name
            params: Method parameters

        Returns:
            Response result dict

        Raises:
            RuntimeError: If not connected or request fails
            TimeoutError: If response not received in time
        """
        if not self._message_endpoint:
            raise RuntimeError("Not connected to MCP server - no message endpoint")

        with self._lock:
            self._request_id += 1
            request_id = self._request_id

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params:
            request["params"] = params

        # Create response queue for this request
        response_queue: queue.Queue = queue.Queue()
        with self._pending_lock:
            self._pending_requests[request_id] = response_queue

        try:
            # Send request via POST
            logger.debug(f"Sending MCP request: {method}")
            response = self.client.post(
                self._message_endpoint,
                json=request,
            )

            if response.status_code != 200 and response.status_code != 202:
                raise RuntimeError(f"MCP request failed: HTTP {response.status_code} - {response.text}")

            # Wait for response via SSE
            try:
                result = response_queue.get(timeout=self.timeout)
            except queue.Empty as err:
                raise TimeoutError(f"MCP request '{method}' timed out after {self.timeout}s") from err

            if "error" in result:
                error = result["error"]
                raise RuntimeError(f"MCP error: {error.get('message', str(error))}")

            return result.get("result", {})

        finally:
            # Cleanup
            with self._pending_lock:
                self._pending_requests.pop(request_id, None)

    def connect(self) -> None:
        """
        Connect to MCP server and initialize session.

        Establishes SSE connection and sends initialize request.
        """
        if self._initialized:
            return

        # Start SSE listener
        self._start_sse_listener()

        # Send initialize request
        self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "eq-chatbot-core",
                    "version": __version__,
                },
            },
        )

        # Send initialized notification (no response expected for notifications)
        # Notifications have no 'id' field
        if self._message_endpoint:
            notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
            self.client.post(self._message_endpoint, json=notification)

        self._initialized = True
        logger.info("MCP session initialized")

    def disconnect(self) -> None:
        """Disconnect from MCP server."""
        self._stop_event.set()

        if self._sse_thread is not None:
            self._sse_thread.join(timeout=2.0)
            self._sse_thread = None

        if self._client is not None:
            self._client.close()
            self._client = None

        self._message_endpoint = None
        self._initialized = False
        self._connected.clear()
        logger.info("MCP client disconnected")

    def list_tools(self) -> list[dict[str, Any]]:
        """
        Get list of available tools from server.

        Returns:
            List of tool definitions with name, description, inputSchema
        """
        try:
            if not self._initialized:
                self.connect()

            result = self._send_request("tools/list", {})
            return result.get("tools", [])

        except Exception as e:
            logger.error(f"Failed to list MCP tools: {e}")
            return []

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        """
        Execute an MCP tool.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            MCPToolResult with execution results
        """
        start_time = time.monotonic()

        try:
            if not self._initialized:
                self.connect()

            result = self._send_request(
                "tools/call",
                {
                    "name": tool_name,
                    "arguments": arguments,
                },
            )

            execution_time = (time.monotonic() - start_time) * 1000

            # Extract content from MCP response
            content = result.get("content", [])
            if content and isinstance(content, list):
                # Combine text content
                text_content = []
                for item in content:
                    if item.get("type") == "text":
                        text_content.append(item.get("text", ""))
                content = "\n".join(text_content) if text_content else content

            return MCPToolResult(
                success=True,
                content=content,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.monotonic() - start_time) * 1000
            logger.error(f"MCP tool call failed: {e}")
            return MCPToolResult(
                success=False,
                content=None,
                error=str(e),
                execution_time_ms=execution_time,
            )

    def get_tool_schema(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get schema for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool schema dict or None if not found
        """
        tools = self.list_tools()

        for tool in tools:
            if tool.get("name") == tool_name:
                return tool

        return None

    def close(self) -> None:
        """Close the MCP client."""
        self.disconnect()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()


class StdioMCPClient:
    """
    MCP client using stdio transport (subprocess).

    Communicates with MCP servers via stdin/stdout using JSON-RPC protocol.
    Suitable for local MCP servers like mcp-odoo in stdio mode.
    """

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize stdio MCP client.

        Args:
            command: Command to execute (e.g., "python", "node")
            args: Command arguments (e.g., ["-m", "mcp_odoo"])
            env: Additional environment variables
            timeout: Request timeout in seconds

        Raises:
            ValueError: If the command is not in the whitelist or args contain shell metacharacters
        """
        _validate_stdio_command(command, args)
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.timeout = timeout
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the MCP server subprocess."""
        if self._process is not None:
            return

        # Build a minimal environment so the subprocess does not inherit the
        # caller's secrets (LLM API keys, DB passwords, etc.). Only forward a
        # whitelist of variables required for normal runtime resolution, then
        # overlay the caller-supplied self.env which is the explicit contract.
        # PYTHONPATH is intentionally excluded — it allows arbitrary module
        # injection that can override stdlib imports inside the subprocess.
        # Callers needing custom Python paths must pass them via self.env.
        _ENV_WHITELIST = (
            "PATH",
            "HOME",
            "LANG",
            "LC_ALL",
            "TZ",
            "TMPDIR",
            "USER",
            "LOGNAME",
            "SHELL",
            "SystemRoot",  # Windows
            "SYSTEMROOT",  # Windows (case-variant)
        )
        full_env = {k: v for k, v in os.environ.items() if k in _ENV_WHITELIST}
        full_env.update(self.env)

        logger.info(f"Starting MCP subprocess: {self.command} {' '.join(self.args)}")

        self._process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )

        # Send initialize request
        await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "eq-chatbot-core",
                    "version": __version__,
                },
            },
        )

        logger.info("MCP subprocess started and initialized")

    async def stop(self) -> None:
        """Stop the MCP server subprocess."""
        if self._process is None:
            return

        try:
            self._process.terminate()
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            self._process.kill()
            await self._process.wait()
        finally:
            self._process = None
            logger.info("MCP subprocess stopped")

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send JSON-RPC request to MCP server.

        Args:
            method: RPC method name
            params: Method parameters

        Returns:
            Response result dict
        """
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("MCP subprocess not started")

        async with self._lock:
            self._request_id += 1
            request_id = self._request_id

            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
            }
            if params:
                request["params"] = params

            # Send request
            request_line = json.dumps(request) + "\n"
            self._process.stdin.write(request_line.encode("utf-8"))
            await self._process.stdin.drain()

            # Read response
            if self._process.stdout is None:
                raise RuntimeError("MCP subprocess stdout not available")

            try:
                response_line = await asyncio.wait_for(
                    self._process.stdout.readline(),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError as err:
                raise TimeoutError(f"MCP request timed out after {self.timeout}s") from err

            if not response_line:
                raise RuntimeError("MCP subprocess closed unexpectedly")

            response = json.loads(response_line.decode("utf-8"))

            if "error" in response:
                error = response["error"]
                raise RuntimeError(f"MCP error: {error.get('message', str(error))}")

            return response.get("result", {})

    async def call_tool_async(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        """
        Execute an MCP tool asynchronously.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            MCPToolResult with execution results
        """
        start_time = time.monotonic()

        try:
            if self._process is None:
                await self.start()

            result = await self._send_request(
                "tools/call",
                {
                    "name": tool_name,
                    "arguments": arguments,
                },
            )

            execution_time = (time.monotonic() - start_time) * 1000

            # Extract content from MCP response
            content = result.get("content", [])
            if content and isinstance(content, list):
                # Combine text content
                text_content = []
                for item in content:
                    if item.get("type") == "text":
                        text_content.append(item.get("text", ""))
                content = "\n".join(text_content) if text_content else content

            return MCPToolResult(
                success=True,
                content=content,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.monotonic() - start_time) * 1000
            logger.error(f"MCP tool call failed: {e}")
            return MCPToolResult(
                success=False,
                content=None,
                error=str(e),
                execution_time_ms=execution_time,
            )

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        """
        Execute an MCP tool synchronously.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            MCPToolResult with execution results
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in an async context - create a new thread to avoid blocking
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.call_tool_async(tool_name, arguments))
                return future.result()
        else:
            return asyncio.run(self.call_tool_async(tool_name, arguments))

    async def list_tools_async(self) -> list[dict[str, Any]]:
        """
        Get list of available tools from server asynchronously.

        Returns:
            List of tool definitions
        """
        try:
            if self._process is None:
                await self.start()

            result = await self._send_request("tools/list", {})
            return result.get("tools", [])

        except Exception as e:
            logger.error(f"Failed to list MCP tools: {e}")
            return []

    def list_tools(self) -> list[dict[str, Any]]:
        """
        Get list of available tools from server synchronously.

        Returns:
            List of tool definitions
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.list_tools_async())
                return future.result()
        else:
            return asyncio.run(self.list_tools_async())

    def get_tool_schema(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get schema for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool schema dict or None if not found
        """
        tools = self.list_tools()

        for tool in tools:
            if tool.get("name") == tool_name:
                return tool

        return None

    def close(self) -> None:
        """Close the subprocess (synchronous wrapper)."""
        if self._process is not None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run, self.stop()).result()
            else:
                asyncio.run(self.stop())

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    def __enter__(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, self.start()).result()
        else:
            asyncio.run(self.start())
        return self

    def __exit__(self, *args):
        self.close()
