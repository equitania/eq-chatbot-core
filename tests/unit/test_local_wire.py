"""LocalLLMProvider against the local OpenAI-wire server (it *is* a local server)."""

import pytest

from eq_chatbot_core.providers.base import ContextLengthError, ProviderError
from eq_chatbot_core.providers.local_provider import LocalLLMProvider
from tests.wire_server import Reply, chat_body, models_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]


def _provider(wire_server):
    return LocalLLMProvider(base_url=wire_server.base_url, max_retries=0)


def test_defaults():
    p = LocalLLMProvider()
    assert p.base_url == "http://localhost:1234/v1" and p.timeout == 120.0 and p.api_key == "not-used"
    assert LocalLLMProvider(base_url="http://localhost:11434/v1")._get_server_type() == "ollama"


def test_chat(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("lokal")))
    assert _provider(wire_server).chat_completion(MSG, model="qwen").content == "lokal"


def test_stream_sends_no_stream_options(wire_server):
    """Unchanged wire behaviour: older LM Studio/Ollama builds reject stream_options."""
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=stream_events(["a"])))
    list(_provider(wire_server).stream_completion(MSG, model="qwen"))
    assert "stream_options" not in wire_server.requests[0].json


def test_context_overflow_in_200_body(wire_server):
    wire_server.expect(
        "POST",
        "/v1/chat/completions",
        Reply(200, {"error": "Trying to keep the first 9000 tokens when context overflows"}),
    )
    with pytest.raises(ContextLengthError):
        _provider(wire_server).chat_completion(MSG, model="qwen")


def test_context_overflow_as_stream_event(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=[{"error": {"message": "context length exceeded"}}]))
    with pytest.raises(ContextLengthError):
        list(_provider(wire_server).stream_completion(MSG, model="qwen"))


def test_list_models_format(wire_server):
    wire_server.expect("GET", "/v1/models", Reply(body=models_body(["qwen"])))
    (model,) = _provider(wire_server).list_models()
    assert model == {
        "id": "qwen",
        "name": "qwen",
        "provider": "local",
        "context_length": None,
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": False,
        "owned_by": "test",
        "created": 0,
    }


def test_server_availability(wire_server):
    wire_server.expect("GET", "/v1/models", Reply(body=models_body([])))
    assert _provider(wire_server).is_server_available()
    assert not LocalLLMProvider(base_url="http://127.0.0.1:9/v1", max_retries=0).is_server_available()


def test_connection_refused_message(real_openai):
    with pytest.raises(ProviderError, match="Cannot connect to local LLM server"):
        LocalLLMProvider(base_url="http://127.0.0.1:9/v1", max_retries=0).chat_completion(MSG, model="qwen")


def test_auth_header_and_default_key(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="qwen")
    headers = {k.lower(): v for k, v in wire_server.requests[0].headers.items()}
    assert headers["authorization"] == "Bearer not-used"


def test_model_temperature_max_tokens_and_tools_sent(wire_server):
    tool = {"type": "function", "function": {"name": "f", "parameters": {"type": "object", "properties": {}}}}
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="qwen", temperature=0.3, max_tokens=50, tools=[tool])
    sent = wire_server.requests[0].json
    assert sent["model"] == "qwen" and sent["temperature"] == 0.3 and sent["tools"] == [tool]
    assert 50 in (sent.get("max_tokens"), sent.get("max_completion_tokens"))


def test_tool_calls_parsed(wire_server):
    calls = [{"id": "c1", "type": "function", "function": {"name": "f", "arguments": '{"a": 1}'}}]
    wire_server.expect(
        "POST", "/v1/chat/completions", Reply(body=chat_body("", tool_calls=calls, finish_reason="tool_calls"))
    )
    response = _provider(wire_server).chat_completion(MSG, model="qwen")
    assert response.tool_calls and response.tool_calls[0]["function"]["name"] == "f"


def test_stream_content_and_final_chunk(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=stream_events(["a", "b"])))
    chunks = list(_provider(wire_server).stream_completion(MSG, model="qwen"))
    assert "".join(c.content or "" for c in chunks) == "ab"
    assert chunks[-1].is_final


@pytest.mark.parametrize(
    ("status", "exc_name"),
    [(429, "RateLimitError"), (401, "AuthenticationError"), (500, "ProviderError")],
)
def test_errors_by_status(wire_server, status, exc_name):
    from eq_chatbot_core.providers import base

    wire_server.expect("POST", "/v1/chat/completions", Reply(status, {"error": {"message": "nope"}}))
    with pytest.raises(base.ProviderError) as info:
        _provider(wire_server).chat_completion(MSG, model="qwen")
    assert type(info.value) is getattr(base, exc_name)
    assert info.value.provider == "local"
    if status == 401:
        assert "Authentication failed (local server may require API key)" in str(info.value)


def test_connection_error_scrubs_token_in_base_url(real_openai):
    p = LocalLLMProvider(base_url="http://127.0.0.1:9/v1?api_key=sk-leak-abcdef123456", max_retries=0)
    with pytest.raises(ProviderError) as info:
        p.chat_completion(MSG, model="qwen")
    assert "sk-leak-abcdef123456" not in str(info.value)


def test_list_models_empty(wire_server):
    wire_server.expect("GET", "/v1/models", Reply(body=models_body([])))
    assert _provider(wire_server).list_models() == []


def test_list_models_connection_error(real_openai):
    with pytest.raises(ProviderError, match="Cannot connect to local LLM server"):
        LocalLLMProvider(base_url="http://127.0.0.1:9/v1", max_retries=0).list_models()


def test_timeout_message(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body(), delay=1.5))
    provider = LocalLLMProvider(base_url=wire_server.base_url, timeout=0.2, max_retries=0)
    with pytest.raises(ProviderError, match="Request timed out after"):
        provider.chat_completion(MSG, model="qwen")


def test_server_unavailable_on_http_500(wire_server):
    wire_server.expect("GET", "/v1/models", Reply(500, {"error": {"message": "boom"}}))
    assert not _provider(wire_server).is_server_available()


def test_list_models_passes_context_length(wire_server):
    body = {"data": [{"id": "qwen", "context_length": 32768, "owned_by": "test", "created": 0}]}
    wire_server.expect("GET", "/v1/models", Reply(body=body))
    (model,) = _provider(wire_server).list_models()
    assert model["context_length"] == 32768


def test_timeout_is_not_retried_by_the_sdk(wire_server):
    """The pre-3.4 provider never retried; a timed-out generation must not be re-sent."""
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body(), delay=1.5))
    provider = LocalLLMProvider(base_url=wire_server.base_url, timeout=0.3, max_retries=2)
    with pytest.raises(ProviderError, match="Request timed out after"):
        provider.chat_completion(MSG, model="qwen")
    assert provider.max_retries == 2
    assert len([r for r in wire_server.requests if r.path == "/v1/chat/completions"]) == 1
