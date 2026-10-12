"""4.2.0: a model that refuses function tools while it reasons gets reasoning_effort "none".

OpenAI's gpt-6-luna reasons by default and answers every /chat/completions
request that carries tools with HTTP 400 — even when no reasoning_effort was
sent. Odoo's chat always sends tools, so every turn failed while "Test
Connection" (no tools) succeeded. The rejection body is the real wording,
captured 12.10.2026.
"""

import pytest

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.litellm_provider import LiteLLMProvider
from tests.wire_server import Reply, chat_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]

MSG = [{"role": "user", "content": "x"}]
CHAT = "/v1/chat/completions"
TOOLS = [{"type": "function", "function": {"name": "t", "description": "d", "parameters": {"type": "object"}}}]
TOOLS_WITH_REASONING = {
    "error": {
        "message": "Function tools with reasoning_effort are not supported for gpt-6-luna in /v1/chat/completions. "
        "To use function tools, use /v1/responses or set reasoning_effort to 'none'.",
        "type": "invalid_request_error",
        "param": "reasoning_effort",
        "code": None,
    }
}


def _provider(wire_server):
    return LiteLLMProvider(api_key="k", base_url=wire_server.base_url, max_retries=0)


def test_rejection_is_recognised():
    class Rejection(Exception):
        status_code = 400
        body = TOOLS_WITH_REASONING["error"]

    assert param_learning.rejected_parameter(Rejection()) == "reasoning_with_tools"


def test_tool_request_is_resent_with_reasoning_none_and_remembered(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, TOOLS_WITH_REASONING), Reply(body=chat_body()))
    provider = _provider(wire_server)

    provider.chat_completion(MSG, model="m", tools=TOOLS)
    assert "reasoning_effort" not in wire_server.requests[0].json
    assert wire_server.requests[1].json["reasoning_effort"] == "none"

    provider.chat_completion(MSG, model="m", tools=TOOLS)
    assert len(wire_server.requests) == 3, "the model should be right the first time now"
    assert wire_server.requests[-1].json["reasoning_effort"] == "none"


def test_streamed_tool_request_is_resent_too(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, TOOLS_WITH_REASONING), Reply(sse=stream_events(["ok"])))
    chunks = list(_provider(wire_server).stream_completion(MSG, model="m", tools=TOOLS))
    assert "".join(c.content for c in chunks) == "ok"
    assert wire_server.requests[-1].json["reasoning_effort"] == "none"


def test_a_request_without_tools_keeps_reasoning(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, TOOLS_WITH_REASONING), Reply(body=chat_body()))
    provider = _provider(wire_server)
    provider.chat_completion(MSG, model="m", tools=TOOLS)

    provider.chat_completion(MSG, model="m")
    assert "reasoning_effort" not in wire_server.requests[-1].json


def test_a_set_effort_is_replaced_once(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, TOOLS_WITH_REASONING))
    with pytest.raises(Exception):
        _provider(wire_server).chat_completion(MSG, model="m", tools=TOOLS, reasoning_effort="low")
    assert [r.json.get("reasoning_effort") for r in wire_server.requests] == ["low", "none"]
