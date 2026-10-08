"""4.0.2: parameter learning remembers only what was proven, and hears more rejections.

Against the real SDKs and a local HTTP server (``tests/wire_server.py``):

- a rejection is remembered only once the adjusted request succeeded;
- a rejection sent as an error event inside a stream (HTTP 200 already sent)
  is retried and learned like a 400;
- HTTP 422, OpenRouter's wrapped upstream body and Azure's "Unrecognized
  request argument supplied" are recognised;
- the memory is separate per API key on the same endpoint;
- ``stream_completion`` without a model raises at the call;
- the Anthropic model list follows pagination.
"""

import json

import pytest

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.base import ModelNotSpecifiedError, ProviderError
from eq_chatbot_core.providers.mammouth_provider import MammouthProvider
from tests.wire_server import (
    OPENAI_TEMPERATURE_REJECTION,
    Reply,
    anthropic_models_body,
    chat_body,
    stream_events,
)

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]

MSG = [{"role": "user", "content": "x"}]
CHAT = "/v1/chat/completions"


def _provider(wire_server, api_key="k"):
    return MammouthProvider(api_key=api_key, base_url=wire_server.base_url, max_retries=0)


def _error_for(wire_server, status, body):
    from openai import OpenAI

    wire_server.expect("POST", CHAT, Reply(status, body))
    client = OpenAI(api_key="k", base_url=wire_server.base_url, max_retries=0)
    with pytest.raises(Exception) as caught:
        client.chat.completions.create(model="m", messages=MSG)
    return caught.value


# --- remembered only after the adjusted request succeeded ---------------------


def test_retry_that_fails_otherwise_teaches_nothing(wire_server):
    wire_server.expect(
        "POST",
        CHAT,
        Reply(400, OPENAI_TEMPERATURE_REJECTION),
        Reply(500, {"error": {"message": "upstream down"}}),
        Reply(body=chat_body()),
    )
    provider = _provider(wire_server)
    with pytest.raises(ProviderError):
        provider.chat_completion(MSG, model="m", temperature=0.7)

    provider.chat_completion(MSG, model="m", temperature=0.7)
    assert "temperature" in wire_server.requests[-1].json, "an unproven rejection was remembered"


def test_successful_retry_is_remembered(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body()))
    provider = _provider(wire_server)
    provider.chat_completion(MSG, model="m", temperature=0.7)
    provider.chat_completion(MSG, model="m", temperature=0.7)
    assert len(wire_server.requests) == 3
    assert "temperature" not in wire_server.requests[-1].json


# --- rejection as an error event inside a stream ------------------------------


def test_stream_error_event_is_retried_and_learned(wire_server):
    error_event = {"error": {"message": "'temperature' is not supported for this model", "code": 400}}
    wire_server.expect("POST", CHAT, Reply(sse=[error_event]), Reply(sse=stream_events(["Hel", "lo"])))
    provider = _provider(wire_server)

    chunks = list(provider.stream_completion(MSG, model="m", temperature=0.7))

    assert "".join(c.content for c in chunks) == "Hello"
    assert len(wire_server.requests) == 2
    assert "temperature" not in wire_server.requests[1].json
    scope = provider._learning_scope(wire_server.base_url)
    assert param_learning.temperature_support(scope, "m") is False


def test_unrelated_stream_error_event_propagates(wire_server):
    wire_server.expect("POST", CHAT, Reply(sse=[{"error": {"message": "quota exhausted"}}]))
    with pytest.raises(ProviderError):
        list(_provider(wire_server).stream_completion(MSG, model="m", temperature=0.7))
    assert len(wire_server.requests) == 1


# --- more rejection shapes -----------------------------------------------------


def test_422_is_a_rejection(wire_server):
    assert (
        param_learning.rejected_parameter(_error_for(wire_server, 422, OPENAI_TEMPERATURE_REJECTION)) == "temperature"
    )


def test_openrouter_wrapped_upstream_rejection(wire_server):
    raw = json.dumps(
        {"error": {"message": "Unsupported parameter: 'reasoning_effort' is not supported with this model."}}
    )
    body = {
        "error": {"message": "Provider returned error", "code": 400, "metadata": {"raw": raw, "provider_name": "x"}}
    }
    assert param_learning.rejected_parameter(_error_for(wire_server, 400, body)) == "reasoning_effort"


def test_azure_unrecognized_argument(wire_server):
    body = {
        "error": {
            "message": "Unrecognized request argument supplied: reasoning_effort",
            "type": "invalid_request_error",
            "param": None,
            "code": None,
        }
    }
    assert param_learning.rejected_parameter(_error_for(wire_server, 400, body)) == "reasoning_effort"


def test_server_error_is_still_not_a_rejection(wire_server):
    assert param_learning.rejected_parameter(_error_for(wire_server, 500, OPENAI_TEMPERATURE_REJECTION)) is None


# --- memory per API key -----------------------------------------------------------


def test_memory_is_separate_per_api_key(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body()))
    _provider(wire_server, api_key="key-a").chat_completion(MSG, model="m", temperature=0.7)

    _provider(wire_server, api_key="key-b").chat_completion(MSG, model="m", temperature=0.7)
    assert "temperature" in wire_server.requests[-1].json, "key B inherited what key A learned"

    _provider(wire_server, api_key="key-a").chat_completion(MSG, model="m", temperature=0.7)
    assert "temperature" not in wire_server.requests[-1].json


def test_scope_never_contains_the_key():
    assert "secret" not in param_learning.scope("http://a/v1/", "secret")
    assert param_learning.scope("http://a/v1/") == "http://a/v1"


# --- eager model check ---------------------------------------------------------------


def test_stream_without_model_raises_at_the_call(wire_server):
    provider = _provider(wire_server)
    with pytest.raises(ModelNotSpecifiedError):
        provider.stream_completion(MSG)  # not iterated
    assert wire_server.requests == []


# --- Anthropic pagination -----------------------------------------------------------


def test_anthropic_list_follows_pagination(wire_server):
    first = anthropic_models_body([{"id": "page-1-a"}, {"id": "page-1-b"}])
    first["has_more"] = True
    second = anthropic_models_body([{"id": "page-2-a"}])
    wire_server.expect("GET", "/v1/models", Reply(body=first), Reply(body=second))

    models = AnthropicProvider(api_key="k", base_url=wire_server.root_url, max_retries=0).list_models()

    assert {m["id"] for m in models} == {"page-1-a", "page-1-b", "page-2-a"}
    assert len(wire_server.requests) == 2
