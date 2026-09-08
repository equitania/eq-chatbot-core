"""
Unit tests for the MCP Streamable HTTP client and the LAN mode of both HTTP transports.

Run with: pytest tests/unit/test_mcp_streamable_http.py -v
"""

import json
from unittest.mock import MagicMock

import pytest

from eq_chatbot_core.mcp import StreamableHTTPMCPClient, get_mcp_client
from eq_chatbot_core.mcp.client import MCPClient
from eq_chatbot_core.mcp.streamable_http import PROTOCOL_HEADER, PROTOCOL_VERSION, SESSION_HEADER

ENDPOINT = "http://localhost:5100/mcp"


class FakeResponse:
    """Stand-in for an httpx2 streaming response (also its own context manager)."""

    def __init__(
        self,
        status_code: int = 200,
        *,
        json_body=None,
        sse_events=None,
        headers=None,
        text: str = "",
    ):
        self.status_code = status_code
        self.headers = dict(headers or {})
        if json_body is not None:
            self.headers.setdefault("content-type", "application/json")
            self.text = json.dumps(json_body)
        else:
            self.text = text
        self._sse_events = sse_events
        if sse_events is not None:
            self.headers.setdefault("content-type", "text/event-stream")
        self.read_called = False

    def read(self):
        self.read_called = True

    def iter_lines(self):
        for event in self._sse_events or []:
            yield "event: message"
            for chunk in event.split("\n"):
                yield f"data: {chunk}"
            yield ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _rpc_result(request_id: int, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


@pytest.fixture
def client():
    return StreamableHTTPMCPClient(url=ENDPOINT, api_key="secret", timeout=1.0)


@pytest.fixture
def http(client):
    """Attach a mocked httpx2 client; ``stream`` responses are queued via side_effect."""
    mock = MagicMock()
    client._client = mock
    return mock


def _connected(client, http, session_id: str | None = None):
    """Drive the initialize handshake against queued responses and return the mock."""
    headers = {SESSION_HEADER.lower(): session_id} if session_id else {}
    http.stream.side_effect = [
        FakeResponse(json_body=_rpc_result(1, {"protocolVersion": PROTOCOL_VERSION}), headers=headers),
    ]
    http.post.return_value = FakeResponse(202)
    client.connect()
    return http


@pytest.mark.unit
class TestInitialization:
    def test_defaults(self, client):
        assert client.url == ENDPOINT
        assert client.api_key == "secret"
        assert client.timeout == 1.0
        assert client.allow_private_ranges is False
        assert client._initialized is False
        assert client._session_id is None

    def test_headers_before_handshake(self, client):
        headers = client._get_headers()
        assert headers["Accept"] == "application/json, text/event-stream"
        assert headers["Authorization"] == "Bearer secret"
        assert SESSION_HEADER not in headers
        assert PROTOCOL_HEADER not in headers

    def test_headers_without_api_key(self):
        c = StreamableHTTPMCPClient(url=ENDPOINT)
        assert "Authorization" not in c._get_headers()

    def test_rejects_non_http_scheme(self):
        with pytest.raises(ValueError):
            StreamableHTTPMCPClient(url="ftp://localhost/mcp")

    def test_strict_mode_rejects_private_ip(self):
        with pytest.raises(ValueError, match="private"):
            StreamableHTTPMCPClient(url="http://10.0.0.5:5100/mcp")

    def test_lan_mode_accepts_private_ip(self):
        c = StreamableHTTPMCPClient(url="http://10.0.0.5:5100/mcp", allow_private_ranges=True)
        assert c.allow_private_ranges is True
        assert c._pinned_ips == {"10.0.0.5": frozenset({"10.0.0.5"})}

    def test_lan_mode_accepts_unresolvable_intranet_host(self):
        c = StreamableHTTPMCPClient(url="http://mcp-host.invalid:5100/mcp", allow_private_ranges=True)
        assert c._pinned_ips == {}

    def test_strict_mode_rejects_unresolvable_host(self):
        with pytest.raises(ValueError, match="could not be resolved"):
            StreamableHTTPMCPClient(url="http://mcp-host.invalid:5100/mcp")

    def test_lan_mode_still_blocks_link_local(self):
        with pytest.raises(ValueError):
            StreamableHTTPMCPClient(url="http://169.254.169.254/mcp", allow_private_ranges=True)


@pytest.mark.unit
class TestHandshake:
    def test_connect_sends_initialize_and_initialized(self, client, http):
        _connected(client, http)

        assert client._initialized is True
        assert client._protocol_version == PROTOCOL_VERSION
        method, url = http.stream.call_args[0]
        assert (method, url) == ("POST", ENDPOINT)
        body = http.stream.call_args[1]["json"]
        assert body["method"] == "initialize"
        assert body["params"]["protocolVersion"] == PROTOCOL_VERSION
        assert body["params"]["clientInfo"]["name"] == "eq-chatbot-core"
        # the protocol header is only sent AFTER negotiation
        assert PROTOCOL_HEADER not in http.stream.call_args[1]["headers"]
        notification = http.post.call_args[1]["json"]
        assert notification == {"jsonrpc": "2.0", "method": "notifications/initialized"}
        assert http.post.call_args[1]["headers"][PROTOCOL_HEADER] == PROTOCOL_VERSION

    def test_connect_is_idempotent(self, client, http):
        _connected(client, http)
        client.connect()
        assert http.stream.call_count == 1

    def test_stateless_server_leaves_session_unset(self, client, http):
        _connected(client, http)
        assert client._session_id is None
        assert SESSION_HEADER not in client._get_headers()

    def test_session_id_is_captured_and_replayed(self, client, http):
        _connected(client, http, session_id="abc-123")
        assert client._session_id == "abc-123"
        assert http.post.call_args[1]["headers"][SESSION_HEADER] == "abc-123"

    def test_rejected_initialized_notification_raises(self, client, http):
        http.stream.side_effect = [FakeResponse(json_body=_rpc_result(1, {}))]
        http.post.return_value = FakeResponse(400, text="bad")
        with pytest.raises(RuntimeError, match="notifications/initialized"):
            client.connect()
        assert client._initialized is False

    def test_disconnect_deletes_session_and_resets(self, client, http):
        _connected(client, http, session_id="abc-123")
        client.disconnect()
        http.delete.assert_called_once()
        assert http.delete.call_args[1]["headers"][SESSION_HEADER] == "abc-123"
        http.close.assert_called_once()
        assert client._client is None
        assert client._session_id is None
        assert client._initialized is False

    def test_disconnect_without_session_sends_no_delete(self, client, http):
        _connected(client, http)
        client.disconnect()
        http.delete.assert_not_called()
        http.close.assert_called_once()

    def test_context_manager(self, client, http):
        http.stream.side_effect = [FakeResponse(json_body=_rpc_result(1, {}))]
        http.post.return_value = FakeResponse(202)
        with client as c:
            assert c._initialized is True
        assert client._initialized is False


@pytest.mark.unit
class TestRequests:
    def test_json_response(self, client, http):
        _connected(client, http)
        http.stream.side_effect = [FakeResponse(json_body=_rpc_result(2, {"tools": [{"name": "a"}]}))]
        assert client._send_request("tools/list", {}) == {"tools": [{"name": "a"}]}
        assert http.stream.call_args[1]["json"]["id"] == 2

    def test_sse_response(self, client, http):
        _connected(client, http)
        http.stream.side_effect = [FakeResponse(sse_events=[json.dumps(_rpc_result(2, {"ok": True}))])]
        assert client._send_request("ping") == {"ok": True}

    def test_sse_skips_server_notifications(self, client, http):
        _connected(client, http)
        events = [
            json.dumps({"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info"}}),
            json.dumps({"jsonrpc": "2.0", "id": 99, "method": "sampling/createMessage"}),
            json.dumps(_rpc_result(2, {"answer": 42})),
        ]
        http.stream.side_effect = [FakeResponse(sse_events=events)]
        assert client._send_request("ping") == {"answer": 42}

    def test_sse_multiline_data(self, client, http):
        _connected(client, http)
        pretty = json.dumps(_rpc_result(2, {"a": 1}), indent=2)
        http.stream.side_effect = [FakeResponse(sse_events=[pretty])]
        assert client._send_request("ping") == {"a": 1}

    def test_sse_stream_without_answer_raises(self, client, http):
        _connected(client, http)
        http.stream.side_effect = [FakeResponse(sse_events=[])]
        with pytest.raises(RuntimeError, match="without answering"):
            client._send_request("ping")

    def test_batch_json_response(self, client, http):
        _connected(client, http)
        http.stream.side_effect = [FakeResponse(json_body=[_rpc_result(7, {}), _rpc_result(2, {"x": 1})])]
        assert client._send_request("ping") == {"x": 1}

    def test_jsonrpc_error_raises(self, client, http):
        _connected(client, http)
        body = {"jsonrpc": "2.0", "id": 2, "error": {"code": -32601, "message": "Method not found"}}
        http.stream.side_effect = [FakeResponse(json_body=body)]
        with pytest.raises(RuntimeError, match="Method not found"):
            client._send_request("nope")

    def test_http_error_raises_with_body(self, client, http):
        _connected(client, http)
        http.stream.side_effect = [FakeResponse(500, text="boom")]
        with pytest.raises(RuntimeError, match="HTTP 500 - boom"):
            client._send_request("ping")

    def test_authentication_failure(self, client, http):
        http.stream.side_effect = [FakeResponse(401, text="nope")]
        with pytest.raises(RuntimeError, match="authentication failed: HTTP 401"):
            client.connect()

    def test_invalid_json_raises(self, client, http):
        _connected(client, http)
        http.stream.side_effect = [FakeResponse(headers={"content-type": "application/json"}, text="{not json")]
        with pytest.raises(RuntimeError, match="invalid JSON"):
            client._send_request("ping")

    def test_timeout_maps_to_timeout_error(self, client, http):
        import httpx2

        _connected(client, http)
        http.stream.side_effect = httpx2.ReadTimeout("slow")
        with pytest.raises(TimeoutError, match="timed out after 1.0s"):
            client._send_request("ping")

    def test_request_ids_increment(self, client, http):
        _connected(client, http)
        http.stream.side_effect = [
            FakeResponse(json_body=_rpc_result(2, {})),
            FakeResponse(json_body=_rpc_result(3, {})),
        ]
        client._send_request("a")
        client._send_request("b")
        ids = [call[1]["json"]["id"] for call in http.stream.call_args_list]
        assert ids == [1, 2, 3]

    def test_stale_session_reinitialises_once(self, client, http):
        _connected(client, http, session_id="old")
        http.stream.side_effect = [
            FakeResponse(404, text="session not found"),
            FakeResponse(
                json_body=_rpc_result(3, {"protocolVersion": PROTOCOL_VERSION}), headers={SESSION_HEADER.lower(): "new"}
            ),
            FakeResponse(json_body=_rpc_result(4, {"tools": []})),
        ]
        assert client._send_request("tools/list", {}) == {"tools": []}
        assert client._session_id == "new"
        assert http.stream.call_count == 4
        # the retried request carries the fresh session id
        assert http.stream.call_args[1]["headers"][SESSION_HEADER] == "new"

    def test_stale_session_does_not_loop(self, client, http):
        _connected(client, http, session_id="old")
        http.stream.side_effect = [
            FakeResponse(404),
            FakeResponse(json_body=_rpc_result(3, {}), headers={SESSION_HEADER.lower(): "new"}),
            FakeResponse(404),
        ]
        with pytest.raises(RuntimeError, match="could not be re-established"):
            client._send_request("tools/list", {})

    def test_404_without_session_is_a_plain_error(self, client, http):
        _connected(client, http)
        http.stream.side_effect = [FakeResponse(404, text="no such endpoint")]
        with pytest.raises(RuntimeError, match="HTTP 404"):
            client._send_request("ping")


@pytest.mark.unit
class TestTools:
    def test_list_tools_connects_lazily(self, client, http):
        http.stream.side_effect = [
            FakeResponse(json_body=_rpc_result(1, {})),
            FakeResponse(json_body=_rpc_result(2, {"tools": [{"name": "artikel_suchen"}]})),
        ]
        http.post.return_value = FakeResponse(202)
        assert client.list_tools() == [{"name": "artikel_suchen"}]
        assert client._initialized is True

    def test_list_tools_follows_pagination(self, client, http):
        _connected(client, http)
        http.stream.side_effect = [
            FakeResponse(json_body=_rpc_result(2, {"tools": [{"name": "a"}], "nextCursor": "p2"})),
            FakeResponse(json_body=_rpc_result(3, {"tools": [{"name": "b"}]})),
        ]
        assert [t["name"] for t in client.list_tools()] == ["a", "b"]
        assert http.stream.call_args[1]["json"]["params"] == {"cursor": "p2"}

    def test_list_tools_swallows_errors(self, client, http):
        _connected(client, http)
        http.stream.side_effect = [FakeResponse(500, text="down")]
        assert client.list_tools() == []

    def test_call_tool_success_joins_text(self, client, http):
        _connected(client, http)
        result = {"content": [{"type": "text", "text": "line 1"}, {"type": "text", "text": "line 2"}]}
        http.stream.side_effect = [FakeResponse(json_body=_rpc_result(2, result))]
        out = client.call_tool("artikel_suchen", {"suchbegriff": "Schraube"})
        assert out.success is True
        assert out.content == "line 1\nline 2"
        assert out.execution_time_ms >= 0
        assert http.stream.call_args[1]["json"]["params"] == {
            "name": "artikel_suchen",
            "arguments": {"suchbegriff": "Schraube"},
        }

    def test_call_tool_keeps_non_text_content(self, client, http):
        _connected(client, http)
        content = [{"type": "image", "data": "abc", "mimeType": "image/png"}]
        http.stream.side_effect = [FakeResponse(json_body=_rpc_result(2, {"content": content}))]
        assert client.call_tool("shot", {}).content == content

    def test_call_tool_is_error_flag(self, client, http):
        _connected(client, http)
        result = {"isError": True, "content": [{"type": "text", "text": "Kunde 4711 nicht gefunden"}]}
        http.stream.side_effect = [FakeResponse(json_body=_rpc_result(2, result))]
        out = client.call_tool("kunde_suchen", {"nummer": "4711"})
        assert out.success is False
        assert out.error == "Kunde 4711 nicht gefunden"
        assert out.content is None

    def test_call_tool_transport_failure(self, client, http):
        _connected(client, http)
        http.stream.side_effect = [FakeResponse(503, text="busy")]
        out = client.call_tool("x", {})
        assert out.success is False
        assert "HTTP 503" in out.error

    def test_get_tool_schema(self, client, http):
        _connected(client, http)
        tools = [{"name": "a", "inputSchema": {}}, {"name": "b", "inputSchema": {"type": "object"}}]
        http.stream.side_effect = [
            FakeResponse(json_body=_rpc_result(2, {"tools": tools})),
            FakeResponse(json_body=_rpc_result(3, {"tools": tools})),
        ]
        assert client.get_tool_schema("b") == tools[1]
        assert client.get_tool_schema("zzz") is None


@pytest.mark.unit
class TestFactory:
    @pytest.mark.parametrize("transport", ["http", "streamable_http", "streamable-http"])
    def test_http_aliases(self, transport):
        c = get_mcp_client(transport=transport, url=ENDPOINT, api_key="k", timeout=5.0)
        assert isinstance(c, StreamableHTTPMCPClient)
        assert c.timeout == 5.0
        assert c.api_key == "k"

    def test_http_requires_url(self):
        with pytest.raises(ValueError, match="url is required"):
            get_mcp_client(transport="http")

    def test_http_lan_mode(self):
        c = get_mcp_client(transport="http", url="http://192.168.1.20:5100/mcp", allow_private_ranges=True)
        assert isinstance(c, StreamableHTTPMCPClient)
        assert c.allow_private_ranges is True

    def test_http_strict_by_default(self):
        with pytest.raises(ValueError):
            get_mcp_client(transport="http", url="http://192.168.1.20:5100/mcp")

    def test_sse_lan_mode(self):
        c = get_mcp_client(transport="sse", url="http://192.168.1.20:8000", allow_private_ranges=True)
        assert isinstance(c, MCPClient)
        assert c.allow_private_ranges is True

    def test_sse_strict_by_default(self):
        with pytest.raises(ValueError):
            get_mcp_client(transport="sse", url="http://192.168.1.20:8000")

    def test_unknown_transport_lists_options(self):
        with pytest.raises(ValueError, match="'http', 'sse' or 'stdio'"):
            get_mcp_client(transport="carrier-pigeon")


@pytest.mark.unit
class TestSSEClientLanMode:
    def test_endpoint_event_accepts_private_ip_in_lan_mode(self):
        client = MCPClient(base_url="http://10.0.0.5:8000", allow_private_ranges=True)
        client._handle_sse_event("endpoint", "http://10.0.0.5:8000/messages")
        assert client._message_endpoint == "http://10.0.0.5:8000/messages"
        assert client._connected.is_set()

    def test_endpoint_event_still_rejects_metadata_target_in_lan_mode(self):
        client = MCPClient(base_url="http://10.0.0.5:8000", allow_private_ranges=True)
        client._handle_sse_event("endpoint", "http://169.254.169.254/latest/meta-data")
        assert client._message_endpoint is None
        assert not client._connected.is_set()

    def test_endpoint_event_rejects_private_ip_in_strict_mode(self):
        client = MCPClient(base_url="http://localhost:8000")
        client._handle_sse_event("endpoint", "http://10.0.0.5:8000/messages")
        assert client._message_endpoint is None
