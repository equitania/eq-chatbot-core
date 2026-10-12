"""4.2.1: LangDock's anthropic backend sends a tool call history in the Messages API format.

The chat keeps one OpenAI-shaped history for every provider. LangDock's
anthropic backend passed it through unchanged, so the turn after the first tool
call was refused (assistant ``content`` null, role ``tool`` unknown).
"""

import pytest

from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.langdock_provider import LangDockProvider
from tests.wire_server import Reply, anthropic_message_body, anthropic_stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MESSAGES = ("POST", "/anthropic/eu/v1/messages")
HISTORY = [
    {"role": "system", "content": "Be brief."},
    {"role": "user", "content": "Find partner acme"},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "search", "arguments": '{"name": "acme"}'}}
        ],
    },
    {"role": "tool", "tool_call_id": "call_1", "content": '{"count": 0}'},
]


def _provider(wire_server):
    return LangDockProvider(api_key="ld-test", base_url=wire_server.root_url, backend="anthropic", max_retries=0)


def _sent(wire_server):
    return [r.json for r in wire_server.requests if r.method == "POST"][-1]


def _assert_converted(body):
    assert body["system"] == "Be brief."
    assistant, tool_result = body["messages"][1], body["messages"][2]
    assert assistant == {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": "call_1", "name": "search", "input": {"name": "acme"}}],
    }
    assert tool_result == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "call_1", "content": '{"count": 0}'}],
    }


def test_stream_converts_tool_history(wire_server):
    wire_server.expect(*MESSAGES, Reply(sse=anthropic_stream_events(["none"])))
    chunks = list(_provider(wire_server).stream_completion(HISTORY, model="claude-x"))
    assert "".join(c.content or "" for c in chunks) == "none"
    _assert_converted(_sent(wire_server))


def test_chat_converts_tool_history(wire_server):
    wire_server.expect(*MESSAGES, Reply(body=anthropic_message_body("none")))
    assert _provider(wire_server).chat_completion(HISTORY, model="claude-x").content == "none"
    _assert_converted(_sent(wire_server))


def test_direct_provider_keeps_its_method():
    """``AnthropicProvider._convert_messages`` stays callable under its name."""
    converted = AnthropicProvider(api_key="k")._convert_messages(HISTORY[1:])
    assert converted[1]["content"][0]["type"] == "tool_use"
