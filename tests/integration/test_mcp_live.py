"""
Integration tests for MCP (Model Context Protocol) client.

These tests require a running MCP server.
Set MCP_TEST_URL in .env.test to enable, e.g.:
    MCP_TEST_URL=http://localhost:8000/sse

Run with: pytest -m integration tests/integration/test_mcp_live.py
"""

import os

import pytest


def get_mcp_test_url():
    """Get MCP test URL from environment."""
    return os.environ.get("MCP_TEST_URL")


def mcp_server_available():
    """Check if MCP server is available for testing."""
    url = get_mcp_test_url()
    if not url:
        return False

    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8000

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


skip_if_no_mcp_server = pytest.mark.skipif(
    not mcp_server_available(),
    reason="MCP server not available (set MCP_TEST_URL in .env.test)",
)


# =============================================================================
# MCP SSE Transport Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.local
class TestMCPLive:
    """Live integration tests for MCP SSE client."""

    @pytest.fixture
    def mcp_url(self):
        """Get MCP server URL."""
        url = get_mcp_test_url()
        if not url:
            pytest.skip("MCP_TEST_URL not set")
        return url

    @skip_if_no_mcp_server
    def test_connect_to_server(self, mcp_url):
        """Test connecting to real MCP server."""
        from eq_chatbot_core.mcp import get_mcp_client

        client = get_mcp_client(
            transport="sse",
            url=mcp_url,
            timeout=10.0,
        )

        try:
            with client:
                assert client._initialized
                assert client._message_endpoint is not None
                print(f"\n  Connected to: {mcp_url}")
                print(f"  Message endpoint: {client._message_endpoint}")
        except Exception as e:
            pytest.fail(f"Failed to connect: {e}")

    @skip_if_no_mcp_server
    def test_list_tools_live(self, mcp_url):
        """Test listing tools from real MCP server."""
        from eq_chatbot_core.mcp import get_mcp_client

        client = get_mcp_client(
            transport="sse",
            url=mcp_url,
            timeout=10.0,
        )

        with client:
            tools = client.list_tools()

            assert isinstance(tools, list)
            print(f"\n  Found {len(tools)} tools")
            for tool in tools[:5]:  # Show first 5
                print(f"  - {tool.get('name', 'unnamed')}")

    @skip_if_no_mcp_server
    def test_call_tool_live(self, mcp_url):
        """Test calling a tool on real MCP server."""
        from eq_chatbot_core.mcp import get_mcp_client

        client = get_mcp_client(
            transport="sse",
            url=mcp_url,
            timeout=10.0,
        )

        with client:
            tools = client.list_tools()

            if not tools:
                pytest.skip("No tools available on server")

            # Call the first available tool with empty arguments
            tool_name = tools[0].get("name")
            if not tool_name:
                pytest.skip("Tool has no name")

            result = client.call_tool(tool_name, {})

            print(f"\n  Tool: {tool_name}")
            print(f"  Success: {result.success}")
            print(f"  Time: {result.execution_time_ms:.2f}ms")
            if result.error:
                print(f"  Error: {result.error}")

    @skip_if_no_mcp_server
    def test_connection_error_handling(self):
        """Test graceful handling of connection errors."""
        from eq_chatbot_core.mcp import get_mcp_client

        # Try to connect to non-existent server
        client = get_mcp_client(
            transport="sse",
            url="http://localhost:9999/sse",
            timeout=2.0,
        )

        with pytest.raises((TimeoutError, RuntimeError)):
            with client:
                pass


# =============================================================================
# MCP stdio Transport Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.local
class TestMCPStdioLive:
    """Live integration tests for MCP stdio client."""

    @pytest.fixture
    def has_mcp_odoo(self):
        """Check if mcp-odoo is installed."""
        import subprocess

        try:
            result = subprocess.run(
                ["python", "-c", "import mcp_odoo"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def test_stdio_client_not_installed(self):
        """Test stdio client with unavailable command."""
        from eq_chatbot_core.mcp import get_mcp_client

        client = get_mcp_client(
            transport="stdio",
            command="nonexistent_command_12345",
            timeout=2.0,
        )

        with pytest.raises((RuntimeError, FileNotFoundError, OSError)):
            with client:
                pass
