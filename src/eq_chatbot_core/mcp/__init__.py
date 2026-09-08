"""
MCP (Model Context Protocol) client integration.

Three transports:

- ``"http"`` — Streamable HTTP (MCP 2025-03-26 and later): one POST endpoint,
  the transport every current MCP server SDK offers for remote operation.
- ``"sse"`` — the legacy HTTP+SSE transport of MCP 2024-11-05 (``/sse`` endpoint
  plus a server-announced POST URL). Kept for servers that still speak it.
- ``"stdio"`` — a local subprocess.
"""

from eq_chatbot_core.mcp.client import (
    ALLOWED_STDIO_COMMANDS,
    MCPClient,
    MCPToolResult,
    StdioMCPClient,
)
from eq_chatbot_core.mcp.streamable_http import StreamableHTTPMCPClient

_HTTP_TRANSPORTS = frozenset({"http", "streamable_http", "streamable-http"})


def get_mcp_client(
    transport: str,
    # HTTP / SSE parameters
    url: str | None = None,
    api_key: str | None = None,
    # stdio parameters
    command: str | None = None,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    # Common parameters
    timeout: float = 30.0,
    allow_private_ranges: bool = False,
) -> MCPClient | StreamableHTTPMCPClient | StdioMCPClient:
    """
    Factory function for creating MCP clients.

    Args:
        transport: ``"http"`` for Streamable HTTP, ``"sse"`` for the legacy
            HTTP+SSE transport, ``"stdio"`` for a subprocess.
        url: Server URL (http/sse modes). For ``"http"`` this is the MCP
            endpoint itself, e.g. ``http://mcp-host:5100/mcp``; for ``"sse"``
            the base URL or the ``/sse`` endpoint.
        api_key: Bearer token for authentication (http/sse modes).
        command: Command to execute (stdio mode only)
        args: Command arguments (stdio mode only)
        env: Environment variables (stdio mode only)
        timeout: Request timeout in seconds
        allow_private_ranges: LAN mode for http/sse — accept private and
            loopback addresses and hostnames only the on-prem resolver knows.
            Link-local / cloud-metadata targets stay blocked. Ignored for stdio.

    Returns:
        StreamableHTTPMCPClient, MCPClient or StdioMCPClient

    Raises:
        ValueError: If transport is unknown or required parameters are missing

    Example:
        # Streamable HTTP (current remote transport), server on the intranet
        client = get_mcp_client(
            transport="http",
            url="http://mcp-host:5100/mcp",
            api_key="secret",
            allow_private_ranges=True,
        )

        # Legacy SSE transport
        client = get_mcp_client(
            transport="sse",
            url="http://localhost:8000",
            api_key="secret",
        )

        # stdio transport (local subprocess)
        client = get_mcp_client(
            transport="stdio",
            command="python",
            args=["-m", "mcp_odoo"],
            env={"ODOO_URL": "http://localhost:8069"},
        )
    """
    if transport in _HTTP_TRANSPORTS:
        if not url:
            raise ValueError("url is required for Streamable HTTP transport")
        return StreamableHTTPMCPClient(
            url=url,
            api_key=api_key,
            timeout=timeout,
            allow_private_ranges=allow_private_ranges,
        )
    elif transport == "sse":
        if not url:
            raise ValueError("url is required for SSE transport")
        return MCPClient(
            base_url=url,
            api_key=api_key,
            timeout=timeout,
            allow_private_ranges=allow_private_ranges,
        )
    elif transport == "stdio":
        if not command:
            raise ValueError("command is required for stdio transport")
        return StdioMCPClient(
            command=command,
            args=args,
            env=env,
            timeout=timeout,
        )
    else:
        raise ValueError(f"Unknown transport: {transport}. Use 'http', 'sse' or 'stdio'.")


__all__ = [
    "ALLOWED_STDIO_COMMANDS",
    "MCPClient",
    "StreamableHTTPMCPClient",
    "StdioMCPClient",
    "MCPToolResult",
    "get_mcp_client",
]
