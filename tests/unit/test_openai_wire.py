"""OpenAIProvider against the local OpenAI-wire server."""

import base64

import pytest

from eq_chatbot_core.providers.openai_provider import OpenAIProvider
from tests.wire_server import Reply, chat_body

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]


def _provider(wire_server, **kw):
    return OpenAIProvider(api_key="sk-test", base_url=wire_server.base_url, max_retries=0, **kw)


def test_new_token_api_is_initial_guess(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="gpt-5.6-luna", max_tokens=20)
    assert wire_server.requests[0].json["max_completion_tokens"] == 20


def test_organization_header(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    _provider(wire_server, organization="org-test").chat_completion(MSG, model="gpt-4.1")
    headers = {k.lower(): v for k, v in wire_server.requests[0].headers.items()}
    assert headers.get("openai-organization") == "org-test"


def test_generate_image(wire_server):
    png = b"\x89PNG\r\n"
    wire_server.expect(
        "POST",
        "/v1/images/generations",
        Reply(body={"created": 0, "data": [{"b64_json": base64.b64encode(png).decode()}]}),
    )
    result = _provider(wire_server).generate_image("a cat", model="img-model")
    assert result.data == png and result.provider == "openai"
    assert wire_server.requests[0].json["model"] == "img-model"


def test_default_base_url_and_offline_construction():
    assert OpenAIProvider(api_key="sk-test").base_url == "https://api.openai.com/v1"


@pytest.mark.parametrize(
    ("status", "body", "exc_name"),
    [
        (429, {"error": {"message": "Rate limit exceeded"}}, "RateLimitError"),
        (401, {"error": {"message": "Authentication failed"}}, "AuthenticationError"),
        (
            400,
            {
                "error": {
                    "message": "This model's maximum context length is 8192 tokens",
                    "code": "context_length_exceeded",
                }
            },
            "ContextLengthError",
        ),
        (503, {"error": {"message": "busy"}}, "OverloadedError"),
        (500, {"error": {"message": "Unknown server error"}}, "ProviderError"),
    ],
)
def test_errors_by_status(wire_server, status, body, exc_name):
    from eq_chatbot_core.providers import base

    wire_server.expect("POST", "/v1/chat/completions", Reply(status, body))
    with pytest.raises(base.ProviderError) as info:
        _provider(wire_server).chat_completion(MSG, model="gpt-4.1")
    assert type(info.value) is getattr(base, exc_name)
    assert info.value.provider == "openai"


def test_error_message_scrubs_secret(wire_server):
    from eq_chatbot_core.providers.base import ProviderError

    body = {"error": {"message": "failed for key sk-leakedsecret12345"}}
    wire_server.expect("POST", "/v1/chat/completions", Reply(500, body))
    with pytest.raises(ProviderError) as info:
        _provider(wire_server).chat_completion(MSG, model="gpt-4.1")
    assert "sk-leakedsecret12345" not in str(info.value)


def test_stream_error_is_provider_error(wire_server):
    from eq_chatbot_core.providers.base import ProviderError

    wire_server.expect("POST", "/v1/chat/completions", Reply(500, {"error": {"message": "Stream error"}}))
    with pytest.raises(ProviderError):
        list(_provider(wire_server).stream_completion(MSG, model="gpt-4.1"))


def test_list_models_error_is_authentication_error(wire_server):
    from eq_chatbot_core.providers.base import AuthenticationError

    wire_server.expect("GET", "/v1/models", Reply(401, {"error": {"message": "bad key"}}))
    with pytest.raises(AuthenticationError):
        _provider(wire_server).list_models()


@pytest.mark.parametrize(
    ("status", "exc_name"),
    [(401, "AuthenticationError"), (429, "RateLimitError")],
)
def test_generate_image_errors_by_status(wire_server, status, exc_name):
    from eq_chatbot_core.providers import base

    wire_server.expect("POST", "/v1/images/generations", Reply(status, {"error": {"message": "nope"}}))
    with pytest.raises(base.ProviderError) as info:
        _provider(wire_server).generate_image("a cat", model="img-model")
    assert type(info.value) is getattr(base, exc_name)


def test_stream_tool_call_delta_and_accumulated_result(wire_server):
    base = {"id": "c", "object": "chat.completion.chunk", "created": 0, "model": "gpt-4.1"}
    call = {
        "index": 0,
        "id": "call_123",
        "type": "function",
        "function": {"name": "test_func", "arguments": '{"a": 1}'},
    }
    events = [
        {**base, "choices": [{"index": 0, "delta": {"tool_calls": [call]}, "finish_reason": None}]},
        {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
    ]
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=events))
    tools = [{"type": "function", "function": {"name": "test_func"}}]
    chunks = list(_provider(wire_server).stream_completion(MSG, model="gpt-4.1", tools=tools))
    delta = next(c.tool_call_delta for c in chunks if c.tool_call_delta)
    assert delta["function"]["name"] == "test_func" and delta["id"] == "call_123"
    final = chunks[-1]
    assert final.is_final and final.tool_calls[0]["function"]["name"] == "test_func"
    assert final.tool_calls[0]["function"]["arguments"] == '{"a": 1}'


def test_client_carries_organization_key_and_url(wire_server):
    provider = _provider(wire_server, organization="org-test")
    assert provider.client.organization == "org-test"
    assert provider.client.api_key == "sk-test"
    assert str(provider.client.base_url).rstrip("/") == wire_server.base_url.rstrip("/")
