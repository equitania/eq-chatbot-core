"""
MCP client implementations for tool execution.

Supports both SSE (HTTP) and stdio (subprocess) transport modes.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

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
    HTTP client for MCP (Model Context Protocol) servers.

    Handles tool discovery and execution.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize MCP client.

        Args:
            base_url: MCP server base URL
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = None

    @property
    def client(self):
        """Lazy initialization of httpx client."""
        if self._client is None:
            try:
                import httpx
            except ImportError as e:
                raise ImportError(
                    "httpx package not installed. "
                    "Install with: pip install httpx"
                ) from e

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )

        return self._client

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
        import time

        start_time = time.monotonic()

        try:
            response = self.client.post(
                "/tools/execute",
                json={
                    "name": tool_name,
                    "arguments": arguments,
                },
            )

            execution_time = (time.monotonic() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                return MCPToolResult(
                    success=True,
                    content=data.get("result"),
                    execution_time_ms=execution_time,
                )
            else:
                return MCPToolResult(
                    success=False,
                    content=None,
                    error=f"HTTP {response.status_code}: {response.text}",
                    execution_time_ms=execution_time,
                )

        except Exception as e:
            execution_time = (time.monotonic() - start_time) * 1000
            return MCPToolResult(
                success=False,
                content=None,
                error=str(e),
                execution_time_ms=execution_time,
            )

    def list_tools(self) -> list[dict[str, Any]]:
        """
        Get list of available tools from server.

        Returns:
            List of tool definitions
        """
        try:
            response = self.client.get("/tools")

            if response.status_code == 200:
                return response.json().get("tools", [])
            else:
                return []

        except Exception:
            return []

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
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
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
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "chatbot-core",
                "version": "0.3.0",
            },
        })

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
            except asyncio.TimeoutError:
                raise TimeoutError(f"MCP request timed out after {self.timeout}s")

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

            result = await self._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments,
            })

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
        return asyncio.get_event_loop().run_until_complete(
            self.call_tool_async(tool_name, arguments)
        )

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
        return asyncio.get_event_loop().run_until_complete(
            self.list_tools_async()
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
