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
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from eq_chatbot_core.version import __version__

logger = logging.getLogger(__name__)


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
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        self._client = None
        self._sse_thread: threading.Thread | None = None
        self._message_endpoint: str | None = None
        self._request_id = 0
        self._pending_requests: dict[int, queue.Queue] = {}
        self._lock = threading.Lock()
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
        """Lazy initialization of httpx client."""
        if self._client is None:
            try:
                import httpx
            except ImportError as e:
                raise ImportError("httpx package not installed. " "Install with: pip install httpx") from e

            self._client = httpx.Client(
                headers=self._get_headers(),
                timeout=self.timeout,
            )

        return self._client

    def _start_sse_listener(self) -> None:
        """Start SSE listener thread."""
        if self._sse_thread is not None and self._sse_thread.is_alive():
            return

        self._stop_event.clear()
        self._connected.clear()
        self._sse_thread = threading.Thread(target=self._sse_listener_loop, daemon=True)
        self._sse_thread.start()

        # Wait for connection and endpoint event
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

            with httpx.stream(
                "GET",
                sse_url,
                headers=self._get_headers(),
                timeout=sse_timeout,
            ) as response:
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
            # Server sends the POST endpoint URL
            self._message_endpoint = data
            if not self._message_endpoint.startswith("http"):
                # Relative URL - extract origin (scheme + host + port) from base_url
                # Don't use full base_url which may contain path like /sse
                parsed = urlparse(self.base_url)
                origin = f"{parsed.scheme}://{parsed.netloc}"
                self._message_endpoint = f"{origin}{data}"
            logger.info(f"MCP message endpoint: {self._message_endpoint}")
            self._connected.set()

        elif event_type == "message":
            # JSON-RPC response
            try:
                response = json.loads(data)
                request_id = response.get("id")

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
            del self._pending_requests[request_id]

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
        """
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

        # Merge environment variables
        full_env = {**os.environ, **self.env}

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
        return asyncio.get_event_loop().run_until_complete(self.call_tool_async(tool_name, arguments))

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
        return asyncio.get_event_loop().run_until_complete(self.list_tools_async())

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
            asyncio.get_event_loop().run_until_complete(self.stop())

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    def __enter__(self):
        asyncio.get_event_loop().run_until_complete(self.start())
        return self

    def __exit__(self, *args):
        self.close()
