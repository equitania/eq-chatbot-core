"""
MCP (Model Context Protocol) client integration.

Supports both SSE (HTTP) and stdio (subprocess) transport modes.
"""

from eq_chatbot_core.mcp.client import MCPClient, MCPToolResult, StdioMCPClient


def get_mcp_client(
    transport: str,
    # SSE parameters
    url: str | None = None,
    api_key: str | None = None,
    # stdio parameters
    command: str | None = None,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    # Common parameters
    timeout: float = 30.0,
) -> MCPClient | StdioMCPClient:
    """
    Factory function for creating MCP clients.

    Args:
        transport: Transport mode - "sse" for HTTP or "stdio" for subprocess
        url: Server URL (SSE mode only)
        api_key: API key for authentication (SSE mode only)
        command: Command to execute (stdio mode only)
        args: Command arguments (stdio mode only)
        env: Environment variables (stdio mode only)
        timeout: Request timeout in seconds

    Returns:
        MCPClient for SSE transport or StdioMCPClient for stdio transport

    Raises:
        ValueError: If transport is unknown or required parameters are missing

    Example:
        # SSE transport (remote server)
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
    if transport == "sse":
        if not url:
            raise ValueError("url is required for SSE transport")
        return MCPClient(
            base_url=url,
            api_key=api_key,
            timeout=timeout,
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
        raise ValueError(f"Unknown transport: {transport}. Use 'sse' or 'stdio'.")


__all__ = [
    "MCPClient",
    "StdioMCPClient",
    "MCPToolResult",
    "get_mcp_client",
]
