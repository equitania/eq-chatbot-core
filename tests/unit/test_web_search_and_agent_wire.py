"""4.3.0: built-in web search, and what a LangDock agent shows and can do.

Against the real SDKs and a local HTTP server (``tests/wire_server.py``).
"""

import pytest

from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.anthropic_shared import WEB_SEARCH_TOOL
from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.langdock_provider import LangDockProvider, _AgentText
from eq_chatbot_core.providers.litellm_provider import LiteLLMProvider
from tests.wire_server import Reply, anthropic_message_body, anthropic_stream_events, chat_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
USER = [{"role": "user", "content": "x"}]
TOOL = {"type": "function", "function": {"name": "get_time", "description": "t", "parameters": {"type": "object"}}}
AGENT = "ag-1"


def _posts(wire_server):
    return [r.json for r in wire_server.requests if r.method == "POST"]


# --- web search --------------------------------------------------------------------


def test_anthropic_sends_the_server_tool_after_function_tools(wire_server):
    wire_server.expect("POST", "/v1/messages", Reply(sse=anthropic_stream_events(["ok"])))
    provider = AnthropicProvider(api_key="k", base_url=wire_server.root_url, max_retries=0)
    list(provider.stream_completion(USER, model="m", tools=[TOOL], web_search=True))
    tools = _posts(wire_server)[0]["tools"]
    assert [t.get("name") for t in tools] == ["get_time", "web_search"]
    assert tools[1] == WEB_SEARCH_TOOL


def test_anthropic_without_web_search_sends_no_server_tool(wire_server):
    wire_server.expect("POST", "/v1/messages", Reply(body=anthropic_message_body("ok")))
    AnthropicProvider(api_key="k", base_url=wire_server.root_url, max_retries=0).chat_completion(USER, model="m")
    assert "tools" not in _posts(wire_server)[0]


@pytest.mark.parametrize("stream", [True, False])
def test_langdock_anthropic_backend_passes_web_search(wire_server, stream):
    reply = Reply(sse=anthropic_stream_events(["ok"])) if stream else Reply(body=anthropic_message_body("ok"))
    wire_server.expect("POST", "/anthropic/eu/v1/messages", reply)
    provider = LangDockProvider(api_key="k", base_url=wire_server.root_url, backend="anthropic", max_retries=0)
    call = provider.stream_completion if stream else provider.chat_completion
    result = call(USER, model="m", web_search=True)
    if stream:
        list(result)
    assert _posts(wire_server)[0]["tools"] == [WEB_SEARCH_TOOL]
    assert provider.supports_native_web_search()


def test_providers_without_web_search_ignore_it(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    provider = LiteLLMProvider(api_key="k", base_url=wire_server.base_url, max_retries=0)
    provider.chat_completion(USER, model="m", web_search=True)
    body = _posts(wire_server)[0]
    assert "web_search" not in body and "tools" not in body
    assert not provider.supports_native_web_search()
    assert not LangDockProvider(api_key="k", backend="openai").supports_native_web_search()


def test_check_model_tries_web_search_where_it_exists(wire_server):
    wire_server.expect("POST", "/v1/messages", Reply(sse=anthropic_stream_events(["OK"])))
    provider = AnthropicProvider(api_key="k", base_url=wire_server.root_url, max_retries=0)
    check = provider.check_model("m", probe_limit=False)
    assert check.web_search == "ok"
    last = _posts(wire_server)[-1]
    assert last["tools"] == [WEB_SEARCH_TOOL], "the web search step sends only the server tool"


def test_check_model_reports_a_refused_web_search(wire_server):
    refused = {"type": "error", "error": {"type": "invalid_request_error", "message": "web search is not enabled"}}
    ok = Reply(sse=anthropic_stream_events(["OK"]))
    wire_server.expect("POST", "/v1/messages", ok, ok, ok, Reply(400, refused), Reply(400, refused))
    check = AnthropicProvider(api_key="k", base_url=wire_server.root_url, max_retries=0).check_model(
        "m", probe_limit=False
    )
    assert (check.text, check.tools, check.vision, check.web_search) == ("ok", "ok", "ok", "refused")
    assert "not enabled" in check.messages["web_search"]


def test_check_model_skips_web_search_without_it(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=stream_events(["OK"])))
    check = LiteLLMProvider(api_key="k", base_url=wire_server.base_url, max_retries=0).check_model(
        "m", probe_limit=False
    )
    assert check.web_search == "skipped"
    assert len(_posts(wire_server)) == 3


# --- LangDock agent ----------------------------------------------------------------


def _agent(wire_server):
    return LangDockProvider(api_key="k", base_url=wire_server.root_url, backend="agent", agent_id=AGENT, max_retries=0)


def test_agent_info_reads_the_agent_without_its_instructions(wire_server):
    agent = {
        "id": AGENT,
        "name": "Research",
        "instruction": "secret instructions",
        "owner": {"id": "u", "name": "Someone", "email": "someone@example.com"},
        "model": "claude-x",
        "webSearchEnabled": True,
        "imageGenerationEnabled": False,
        "extendedThinking": True,
        "canvasEnabled": False,
        "knowledgeFolderIds": ["f1"],
        "actions": [{"actionId": "a1", "requiresConfirmation": True}],
    }
    wire_server.expect("GET", "/agent/v1/get", Reply(body={"status": "success", "agent": agent}))
    info = _agent(wire_server).agent_info()
    assert info == {
        "name": "Research",
        "model": "claude-x",
        "web_search": True,
        "image_generation": False,
        "extended_thinking": True,
        "canvas": False,
        "knowledge": True,
        "actions": 1,
    }
    request = [r for r in wire_server.requests if r.method == "GET"][0]
    assert request.path == "/agent/v1/get" and request.query == f"agentId={AGENT}"


def test_agent_info_without_access_is_a_provider_error(wire_server):
    wire_server.expect("GET", "/agent/v1/get", Reply(403, {"message": "no access"}))
    with pytest.raises(ProviderError) as caught:
        _agent(wire_server).agent_info()
    assert caught.value.status_code == 403


def _delta(text):
    return {"type": "text-delta", "id": "1", "delta": text}


def test_agent_stream_drops_markers_and_separates_steps(wire_server):
    events = [
        {"type": "start", "messageMetadata": {"modelName": "Haiku"}},
        {"type": "start-step"},
        _delta("I check the site."),
        {"type": "finish-step"},
        {"type": "start-step"},
        {"type": "tool-input-start", "toolCallId": "toolu_1", "toolName": "web_search"},
        {"type": "finish-step"},
        {"type": "start-step"},
        _delta("The code is 12345 【tool"),
        _delta("u_vrtx_01AB-0】."),
        _delta(" Done【4:0†source】"),
        {"type": "finish-step"},
        {"type": "finish"},
    ]
    wire_server.expect("POST", "/agent/v1/chat/completions", Reply(sse=events), Reply(sse=events))
    streamed = "".join(c.content for c in _agent(wire_server).stream_completion(USER))
    assert streamed == "I check the site.\n\nThe code is 12345. Done"
    assert _agent(wire_server).chat_completion(USER).content == streamed


def test_agent_text_keeps_brackets_that_are_no_marker():
    text = _AgentText()
    out = text.feed(_delta("Termin 【wichtig】 und 【offen")) + text.flush()
    assert out == "Termin 【wichtig】 und 【offen"
