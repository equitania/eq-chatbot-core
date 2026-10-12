"""4.1.0: output and context limits, read from the provider instead of guessed.

Against the real SDKs and a local HTTP server (``tests/wire_server.py``):

- a rejection that states a limit is remembered at once, and an oversized
  request is resent once, capped to it; later requests are capped before sending;
- a context rejection that names the input tokens is resent with the room left;
- ``probe_output_limit`` asks with an oversized request and reads the number
  from the rejection — or reports ``None`` when the provider names none;
- ``list_models`` fills a limit the endpoint does not report from what was learned.

The rejection bodies are the providers' real wording, captured 12.10.2026.
"""

import pytest

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.base import AuthenticationError, ContextLengthError, ProviderError
from eq_chatbot_core.providers.litellm_provider import LiteLLMProvider
from tests.wire_server import (
    Reply,
    anthropic_message_body,
    anthropic_stream_events,
    chat_body,
    models_body,
    stream_events,
)

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]

MSG = [{"role": "user", "content": "x"}]
CHAT = "/v1/chat/completions"

OPENAI_OUTPUT_LIMIT = {
    "error": {
        "message": "max_tokens is too large: 200000. This model supports at most 16384 completion tokens, "
        "whereas you provided 200000.",
        "type": "invalid_request_error",
        "param": "max_tokens",
        "code": "invalid_value",
    }
}
OPENAI_CONTEXT = {
    "error": {
        "message": "This model's maximum context length is 128000 tokens. However, your messages resulted in "
        "140008 tokens. Please reduce the length of the messages.",
        "type": "invalid_request_error",
        "param": "messages",
        "code": "context_length_exceeded",
    }
}
VLLM_CONTEXT = {
    "object": "error",
    "message": "'max_tokens' or 'max_completion_tokens' is too large: 5000. This model's maximum context length "
    "is 4096 tokens and your request has 20 input tokens (5000 > 4096 - 20).",
    "type": "BadRequestError",
    "param": None,
    "code": 400,
}
ANTHROPIC_OUTPUT_LIMIT = {
    "type": "error",
    "error": {
        "type": "invalid_request_error",
        "message": "max_tokens: 200000 > 128000, which is the maximum allowed number of output tokens for m",
    },
}
GENERIC_400 = {"error": {"message": "Bad request", "type": "invalid_request_error"}}


def _provider(wire_server, api_key="k"):
    return LiteLLMProvider(api_key=api_key, base_url=wire_server.base_url, max_retries=0)


def _anthropic(wire_server):
    return AnthropicProvider(api_key="k", base_url=wire_server.root_url, max_retries=0)


def _sent_limit(request):
    return request.json.get("max_tokens", request.json.get("max_completion_tokens"))


# --- reading the number ----------------------------------------------------------


def _error_for(wire_server, status, body):
    from openai import OpenAI

    wire_server.expect("POST", CHAT, Reply(status, body))
    client = OpenAI(api_key="k", base_url=wire_server.base_url, max_retries=0)
    with pytest.raises(Exception) as caught:
        client.chat.completions.create(model="m", messages=MSG)
    return caught.value


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (OPENAI_OUTPUT_LIMIT, {"max_output_tokens": 16384}),
        (OPENAI_CONTEXT, {"context_length": 128000}),
        (VLLM_CONTEXT, {"context_length": 4096}),
        (GENERIC_400, {}),
    ],
)
def test_stated_limits(wire_server, body, expected):
    assert param_learning.stated_limits(_error_for(wire_server, 400, body)) == expected


def test_server_error_states_no_limit(wire_server):
    assert param_learning.stated_limits(_error_for(wire_server, 500, OPENAI_OUTPUT_LIMIT)) == {}


# --- learning from a real request --------------------------------------------------


def test_oversized_request_is_capped_and_remembered(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, OPENAI_OUTPUT_LIMIT), Reply(body=chat_body()))
    provider = _provider(wire_server)

    provider.chat_completion(MSG, model="m", max_tokens=200000)
    assert [_sent_limit(r) for r in wire_server.requests] == [200000, 16384]
    assert provider.learned_limits("m") == {"max_output_tokens": 16384}

    provider.chat_completion(MSG, model="m", max_tokens=200000)
    assert len(wire_server.requests) == 3, "the learned limit should cap before sending"
    assert _sent_limit(wire_server.requests[-1]) == 16384


def test_setting_below_the_limit_is_untouched(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, OPENAI_OUTPUT_LIMIT), Reply(body=chat_body()))
    provider = _provider(wire_server)
    provider.chat_completion(MSG, model="m", max_tokens=200000)

    provider.chat_completion(MSG, model="m", max_tokens=1000)
    assert _sent_limit(wire_server.requests[-1]) == 1000


def test_capped_retry_is_sent_only_once(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, OPENAI_OUTPUT_LIMIT))
    with pytest.raises(ProviderError):
        _provider(wire_server).chat_completion(MSG, model="m", max_tokens=200000)
    assert len(wire_server.requests) == 2


def test_stream_is_capped_too(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, OPENAI_OUTPUT_LIMIT), Reply(sse=stream_events(["hi"])))
    chunks = list(_provider(wire_server).stream_completion(MSG, model="m", max_tokens=200000))
    assert "".join(c.content for c in chunks) == "hi"
    assert _sent_limit(wire_server.requests[-1]) == 16384


def test_context_rejection_naming_input_is_resent_with_the_room_left(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, VLLM_CONTEXT), Reply(body=chat_body()))
    provider = _provider(wire_server)

    provider.chat_completion(MSG, model="m", max_tokens=5000)
    assert _sent_limit(wire_server.requests[-1]) == 4076
    # The room depends on this request's input: it is not the model's output limit.
    assert provider.learned_limits("m") == {"context_length": 4096}


def test_context_rejection_about_the_input_is_raised_and_learned(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, OPENAI_CONTEXT))
    provider = _provider(wire_server)
    with pytest.raises(ContextLengthError):
        provider.chat_completion(MSG, model="m", max_tokens=1000)
    assert len(wire_server.requests) == 1
    assert provider.learned_limits("m") == {"context_length": 128000}


def test_limits_are_separate_per_api_key(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, OPENAI_OUTPUT_LIMIT), Reply(body=chat_body()))
    _provider(wire_server, api_key="key-a").chat_completion(MSG, model="m", max_tokens=200000)
    assert _provider(wire_server, api_key="key-b").learned_limits("m") == {}


def test_list_models_fills_unreported_limits(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, OPENAI_OUTPUT_LIMIT), Reply(body=chat_body()))
    wire_server.expect("GET", "/v1/models", Reply(body=models_body(["m", "other"])))
    provider = _provider(wire_server)
    provider.chat_completion(MSG, model="m", max_tokens=200000)

    models = {m["id"]: m for m in provider.list_models()}
    assert models["m"]["max_output_tokens"] == 16384
    assert models["other"]["max_output_tokens"] is None


# --- probing ---------------------------------------------------------------------


def test_probe_reads_the_limit_from_the_rejection(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, OPENAI_OUTPUT_LIMIT))
    provider = _provider(wire_server)

    assert provider.probe_output_limit("m") == 16384
    assert len(wire_server.requests) == 1, "the probe must not retry with the stated limit"
    request = wire_server.requests[0].json
    assert _sent_limit(wire_server.requests[0]) == provider.PROBE_MAX_TOKENS
    assert request["stream"] is True

    assert provider.probe_output_limit("m") == 16384
    assert len(wire_server.requests) == 1, "a known limit needs no second probe"


def test_probe_accepted_stays_unknown(wire_server):
    wire_server.expect("POST", CHAT, Reply(sse=stream_events(["a", "b", "c"])))
    provider = _provider(wire_server)
    assert provider.probe_output_limit("m") is None
    assert provider.learned_limits("m") == {}


def test_probe_rejected_without_a_number_stays_unknown(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, GENERIC_400))
    assert _provider(wire_server).probe_output_limit("m") is None


def test_probe_rejected_inside_the_stream_stays_unknown(wire_server):
    # Melious answers HTTP 200 and sends the rejection as the stream's first event.
    wire_server.expect("POST", CHAT, Reply(sse=[{"error": {"message": "The request was rejected as malformed."}}]))
    assert _provider(wire_server).probe_output_limit("m") is None


def test_probe_raises_on_authentication_error(wire_server):
    wire_server.expect("POST", CHAT, Reply(401, {"error": {"message": "bad key"}}))
    with pytest.raises(AuthenticationError):
        _provider(wire_server).probe_output_limit("m")


def test_probe_then_chat_is_capped(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, OPENAI_OUTPUT_LIMIT), Reply(body=chat_body()))
    provider = _provider(wire_server)
    provider.probe_output_limit("m")
    provider.chat_completion(MSG, model="m", max_tokens=200000)
    assert len(wire_server.requests) == 2
    assert _sent_limit(wire_server.requests[-1]) == 16384


# --- Anthropic -------------------------------------------------------------------


def test_anthropic_probe(wire_server):
    wire_server.expect("POST", "/v1/messages", Reply(400, ANTHROPIC_OUTPUT_LIMIT))
    provider = _anthropic(wire_server)
    assert provider.probe_output_limit("m") == 128000
    assert wire_server.requests[0].json["max_tokens"] == provider.PROBE_MAX_TOKENS


def test_anthropic_probe_accepted_stays_unknown(wire_server):
    wire_server.expect("POST", "/v1/messages", Reply(sse=anthropic_stream_events(["ok"])))
    assert _anthropic(wire_server).probe_output_limit("m") is None


def test_anthropic_chat_is_capped_and_remembered(wire_server):
    wire_server.expect("POST", "/v1/messages", Reply(400, ANTHROPIC_OUTPUT_LIMIT), Reply(body=anthropic_message_body()))
    provider = _anthropic(wire_server)
    provider.chat_completion(MSG, model="m", max_tokens=200000)
    assert [r.json["max_tokens"] for r in wire_server.requests] == [200000, 128000]
    assert provider.learned_limits("m") == {"max_output_tokens": 128000}
