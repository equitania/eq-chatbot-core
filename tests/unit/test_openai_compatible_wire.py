"""OpenAICompatibleProvider against a real local OpenAI-wire server.

The SDK, transport and error mapping are the production code paths; only the
remote provider is simulated (tests/wire_server.py).
"""

import pytest

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    ContextLengthError,
    OverloadedError,
    ProviderError,
    RateLimitError,
)
from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider
from tests.wire_server import (
    GATEWAY_TEMPERATURE_REJECTION_NO_PARAM,
    OPENAI_MAX_TOKENS_REJECTION,
    OPENAI_REASONING_EFFORT_REJECTION,
    OPENAI_TEMPERATURE_REJECTION,
    Reply,
    chat_body,
    stream_events,
)

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]

MSG = [{"role": "user", "content": "x"}]
CHAT = ("POST", "/v1/chat/completions")


class _Gateway(OpenAICompatibleProvider):
    PROVIDER_NAME = "testgateway"


def _provider(wire_server, **kw):
    return _Gateway(api_key="k", base_url=wire_server.base_url, max_retries=0, **kw)


def _sent(wire_server):
    return [r.json for r in wire_server.requests if r.path == CHAT[1]]


# --- learning ---------------------------------------------------------------


def test_temperature_rejection_retried_without_it(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body("ok")))
    response = _provider(wire_server).chat_completion(MSG, model="m", temperature=0.7)

    assert response.content == "ok"
    first, second = _sent(wire_server)
    assert first["temperature"] == 0.7
    assert "temperature" not in second


def test_max_tokens_rejection_retried_as_max_completion_tokens(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_MAX_TOKENS_REJECTION), Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="m", max_tokens=50)

    first, second = _sent(wire_server)
    assert first["max_tokens"] == 50
    assert second["max_completion_tokens"] == 50 and "max_tokens" not in second


def test_both_parameters_rejected_learned_in_one_call(wire_server):
    wire_server.expect(
        *CHAT,
        Reply(400, OPENAI_TEMPERATURE_REJECTION),
        Reply(400, OPENAI_MAX_TOKENS_REJECTION),
        Reply(body=chat_body()),
    )
    provider = _provider(wire_server)
    provider.chat_completion(MSG, model="m", temperature=0.7, max_tokens=50)
    assert len(_sent(wire_server)) == 3

    provider.chat_completion(MSG, model="m", temperature=0.7, max_tokens=50)
    fourth = _sent(wire_server)[3]
    assert "temperature" not in fourth and fourth["max_completion_tokens"] == 50
    assert len(_sent(wire_server)) == 4  # learned: no retry on the second call


def test_learning_shared_across_instances(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="m", temperature=0.7)
    _provider(wire_server).chat_completion(MSG, model="m", temperature=0.7)

    assert len(_sent(wire_server)) == 3
    assert "temperature" not in _sent(wire_server)[2]


def test_same_rejection_twice_propagates(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION))  # repeats forever
    with pytest.raises(ProviderError) as caught:
        _provider(wire_server).chat_completion(MSG, model="m", temperature=0.7)
    assert caught.value.status_code == 400
    assert len(_sent(wire_server)) == 2  # one retry, then give up


def test_gateway_rejection_without_param_field(wire_server):
    wire_server.expect(*CHAT, Reply(400, GATEWAY_TEMPERATURE_REJECTION_NO_PARAM), Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="m", temperature=0.7)
    assert "temperature" not in _sent(wire_server)[1]


def test_stream_retries_before_first_chunk(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(sse=stream_events(["Hal", "lo"])))
    chunks = list(_provider(wire_server).stream_completion(MSG, model="m", temperature=0.7))

    assert "".join(c.content for c in chunks) == "Hallo"
    assert chunks[-1].is_final and chunks[-1].input_tokens == 5
    assert len(_sent(wire_server)) == 2


# --- error mapping ----------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "exc_type"),
    [
        (429, RateLimitError),
        (401, AuthenticationError),
        (403, AuthenticationError),
        (503, OverloadedError),
        (529, OverloadedError),
    ],
)
def test_status_mapping(wire_server, status, exc_type):
    wire_server.expect(*CHAT, Reply(status, {"error": {"message": "nope"}}))
    with pytest.raises(exc_type) as caught:
        _provider(wire_server).chat_completion(MSG, model="m")
    assert caught.value.status_code == status


def test_rate_limit_carries_retry_after(wire_server):
    wire_server.expect(*CHAT, Reply(429, {"error": {"message": "slow down"}}, headers={"Retry-After": "7"}))
    with pytest.raises(RateLimitError) as caught:
        _provider(wire_server).chat_completion(MSG, model="m")
    assert caught.value.retry_after == 7


def test_context_length_by_code(wire_server):
    body = {
        "error": {
            "message": "This model's maximum context length is 8192 tokens.",
            "code": "context_length_exceeded",
        }
    }
    wire_server.expect(*CHAT, Reply(400, body))
    with pytest.raises(ContextLengthError):
        _provider(wire_server).chat_completion(MSG, model="m")


def test_word_token_alone_is_not_context_length(wire_server):
    body = {"error": {"message": "Invalid token in request", "code": "invalid_request"}}
    wire_server.expect(*CHAT, Reply(400, body))
    with pytest.raises(ProviderError) as caught:
        _provider(wire_server).chat_completion(MSG, model="m")
    assert type(caught.value) is ProviderError


def test_error_in_200_body_raises_typed_error(wire_server):
    wire_server.expect(*CHAT, Reply(200, {"error": {"message": "model crashed"}}))
    with pytest.raises(ProviderError, match="model crashed"):
        _provider(wire_server).chat_completion(MSG, model="m")


def test_context_overflow_in_200_body(wire_server):
    body = {"error": {"message": "maximum context length exceeded", "code": "context_length_exceeded"}}
    wire_server.expect(*CHAT, Reply(200, body))
    with pytest.raises(ContextLengthError):
        _provider(wire_server).chat_completion(MSG, model="m")


def test_stream_error_event_mid_stream(wire_server):
    events = stream_events(["Hal"])[:1] + [{"error": {"message": "upstream died"}}]
    wire_server.expect(*CHAT, Reply(sse=events))
    received = []
    with pytest.raises(ProviderError, match="upstream died"):
        for chunk in _provider(wire_server).stream_completion(MSG, model="m"):
            received.append(chunk.content)
    assert received == ["Hal"]
    assert len(_sent(wire_server)) == 1  # no retry once output has started


def test_secrets_scrubbed_from_errors(wire_server):
    wire_server.expect(*CHAT, Reply(500, {"error": {"message": "bad key sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX"}}))
    with pytest.raises(ProviderError) as caught:
        _provider(wire_server).chat_completion(MSG, model="m")
    assert "ABCDEFGHIJKLMNOPQRSTUVWX" not in str(caught.value)


# --- hooks ------------------------------------------------------------------


def test_default_headers_hook(wire_server):
    class _WithHeaders(_Gateway):
        def _default_headers(self):
            return {"X-Title": "eq-test"}

    wire_server.expect(*CHAT, Reply(body=chat_body()))
    _WithHeaders(api_key="k", base_url=wire_server.base_url, max_retries=0).chat_completion(MSG, model="m")
    # HTTP/1.1 header names arrive lower-cased from the SDK transport.
    sent = {name.lower(): value for name, value in wire_server.requests[0].headers.items()}
    assert sent.get("x-title") == "eq-test"


def test_token_param_hook_is_initial_guess(wire_server):
    class _NewTokenApi(_Gateway):
        def _token_param(self, model):
            return "max_completion_tokens"

    wire_server.expect(*CHAT, Reply(body=chat_body()))
    _NewTokenApi(api_key="k", base_url=wire_server.base_url, max_retries=0).chat_completion(
        MSG, model="m", max_tokens=9
    )
    assert _sent(wire_server)[0]["max_completion_tokens"] == 9


# --- ported from the mocked per-provider tests -------------------------------


def _migrated_providers():
    from eq_chatbot_core.providers.ionos_provider import IonosProvider
    from eq_chatbot_core.providers.litellm_provider import LiteLLMProvider
    from eq_chatbot_core.providers.melious_provider import MeliousProvider
    from eq_chatbot_core.providers.privatemode_provider import PrivatemodeProvider

    return [IonosProvider, MeliousProvider, LiteLLMProvider, PrivatemodeProvider]


@pytest.mark.parametrize("index", range(4), ids=["ionos", "melious", "litellm", "privatemode"])
@pytest.mark.parametrize(
    ("status", "exc_type"),
    [(401, AuthenticationError), (429, RateLimitError), (500, ProviderError)],
)
def test_migrated_providers_map_errors_by_status(wire_server, index, status, exc_type):
    cls = _migrated_providers()[index]
    kwargs = {"allow_insecure_transport": True} if cls.__name__ == "PrivatemodeProvider" else {}
    provider = cls(api_key="k", base_url=wire_server.base_url, max_retries=0, **kwargs)
    wire_server.expect(*CHAT, Reply(status, {"error": {"message": "nope sk-leakedsecret12345"}}))
    with pytest.raises(exc_type) as caught:
        provider.chat_completion(MSG, model="m")
    assert caught.value.status_code == status
    assert "sk-leakedsecret12345" not in str(caught.value)


def _litellm(wire_server):
    from eq_chatbot_core.providers.litellm_provider import LiteLLMProvider

    return LiteLLMProvider(api_key="k", base_url=wire_server.base_url, max_retries=0)


def test_litellm_tts_failure_is_scrubbed_provider_error(wire_server):
    body = {"error": {"message": "bad key sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX"}}
    wire_server.expect("POST", "/v1/audio/speech", Reply(500, body))
    with pytest.raises(ProviderError) as caught:
        _litellm(wire_server).text_to_speech("Hallo", model="tts-model", voice="voice-1")
    assert caught.value.status_code == 500
    assert "ABCDEFGHIJKLMNOPQRSTUVWX" not in str(caught.value)


def test_litellm_transcribe_failure_is_provider_error(wire_server):
    wire_server.expect("POST", "/v1/audio/transcriptions", Reply(500, {"error": {"message": "stt backend down"}}))
    with pytest.raises(ProviderError) as caught:
        _litellm(wire_server).transcribe(("a.wav", b"RIFF0000", "audio/wav"), model="stt-model")
    assert caught.value.status_code == 500


def test_reasoning_effort_rejection_learned(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_REASONING_EFFORT_REJECTION), Reply(body=chat_body()))
    provider = _provider(wire_server)
    provider.chat_completion(MSG, model="m", reasoning_effort="high")
    provider.chat_completion(MSG, model="m", reasoning_effort="high")
    first, second, third = _sent(wire_server)
    assert first["reasoning_effort"] == "high"
    assert "reasoning_effort" not in second and "reasoning_effort" not in third


def test_learning_is_logged_on_the_provider_module_logger(wire_server, caplog):
    """The live learning test listens on this logger name."""
    wire_server.expect(*CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body()))
    with caplog.at_level("INFO", logger="eq_chatbot_core.providers.openai_compatible"):
        _provider(wire_server).chat_completion(MSG, model="m", temperature=0.7)
    assert "rejected 'temperature'" in caplog.text
