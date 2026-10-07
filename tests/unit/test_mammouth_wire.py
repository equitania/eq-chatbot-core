"""MammouthProvider against the local OpenAI-wire server."""

import pytest

from eq_chatbot_core.providers.mammouth_provider import MammouthProvider
from tests.wire_server import OPENAI_TEMPERATURE_REJECTION, Reply, chat_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]


def _provider(wire_server):
    provider = MammouthProvider(api_key="mm-test", base_url=wire_server.base_url, max_retries=0)
    # MODELS_URL is a separate public endpoint; point this instance at the test server.
    provider.MODELS_URL = f"{wire_server.root_url}/public/models"
    return provider


def test_chat_and_auth_header(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("hallo", model="gpt-x")))
    response = _provider(wire_server).chat_completion(MSG, model="gpt-x")
    assert response.content == "hallo" and response.model == "gpt-x"
    assert {k.lower(): v for k, v in wire_server.requests[0].headers.items()}["authorization"] == "Bearer mm-test"


def test_stream(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=stream_events(["a", "b"])))
    chunks = list(_provider(wire_server).stream_completion(MSG, model="gpt-x"))
    assert "".join(c.content for c in chunks) == "ab" and chunks[-1].is_final


def test_temperature_learning(wire_server):
    wire_server.expect(
        "POST", "/v1/chat/completions", Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body())
    )
    _provider(wire_server).chat_completion(MSG, model="gpt-x", temperature=0.5)
    assert "temperature" not in wire_server.requests[1].json


def test_list_models_from_public_endpoint(wire_server):
    wire_server.expect(
        "GET",
        "/public/models",
        Reply(body=[{"id": "gpt-x", "name": "GPT X", "max_input_tokens": 1000, "max_output_tokens": 100}]),
    )
    models = _provider(wire_server).list_models()
    assert models == [
        {
            "id": "gpt-x",
            "name": "GPT X",
            "provider": "mammouth",
            "context_length": 1000,
            "max_output_tokens": 100,
            "supports_temperature": True,
            "min_temperature": 0.0,
            "max_temperature": 2.0,
            "supports_reasoning": False,
            "supports_streaming": True,
        }
    ]
    assert {k.lower(): v for k, v in wire_server.requests[0].headers.items()}["authorization"] == "Bearer mm-test"


def test_construction_needs_no_network():
    MammouthProvider(api_key="mm-test")  # default URL is validated lazily, on first request


# --- Ported from the old mocked tests (behaviour that still exists) ----------------


def _models_payload():
    return [
        {"id": "o3", "name": "O3", "max_input_tokens": 200000, "max_output_tokens": 100000},
        {"id": "gpt-4o", "name": "GPT-4o", "max_input_tokens": 128000, "max_output_tokens": 16384},
        {"id": "gpt-4.1", "name": "GPT-4.1", "max_input_tokens": 1048576, "max_output_tokens": 32768},
    ]


def test_list_models_constraints_and_sorting(wire_server):
    wire_server.expect("GET", "/public/models", Reply(body={"data": _models_payload()}))
    models = _provider(wire_server).list_models()
    assert [m["id"] for m in models] == ["gpt-4.1", "gpt-4o", "o3"]
    by_id = {m["id"]: m for m in models}
    assert by_id["gpt-4o"]["supports_temperature"] is True
    assert (by_id["gpt-4o"]["min_temperature"], by_id["gpt-4o"]["max_temperature"]) == (0.0, 2.0)
    assert by_id["o3"]["supports_temperature"] is False and by_id["o3"]["supports_reasoning"] is True
    assert by_id["gpt-4.1"]["context_length"] == 1048576


def test_reasoning_model_gets_no_temperature(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="o1", temperature=0.7)
    assert "temperature" not in wire_server.requests[0].json


def test_temperature_passes_through_for_gpt41(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="gpt-4.1", temperature=0.3)
    assert wire_server.requests[0].json["temperature"] == 0.3


def test_max_tokens_and_tools_reach_the_wire(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    tool = {"type": "function", "function": {"name": "f", "parameters": {"type": "object", "properties": {}}}}
    _provider(wire_server).chat_completion(MSG, model="gpt-x", max_tokens=50, tools=[tool])
    sent = wire_server.requests[0].json
    assert sent["tools"] == [tool]
    assert 50 in (sent.get("max_tokens"), sent.get("max_completion_tokens"))


@pytest.mark.parametrize(
    ("status", "body", "exc_name"),
    [
        (429, {"error": {"message": "slow down"}}, "RateLimitError"),
        (401, {"error": {"message": "bad key"}}, "AuthenticationError"),
        (503, {"error": {"message": "busy"}}, "OverloadedError"),
        (500, {"error": {"message": "boom"}}, "ProviderError"),
    ],
)
def test_errors_by_status(wire_server, status, body, exc_name):
    from eq_chatbot_core.providers import base

    wire_server.expect("POST", "/v1/chat/completions", Reply(status, body))
    with pytest.raises(base.ProviderError) as info:
        _provider(wire_server).chat_completion(MSG, model="gpt-x")
    assert type(info.value) is getattr(base, exc_name)
    assert info.value.provider == "mammouth"


def test_string_error_body_is_surfaced(wire_server):
    from eq_chatbot_core.providers.base import ProviderError

    wire_server.expect("POST", "/v1/chat/completions", Reply(500, {"error": "plain string failure"}))
    with pytest.raises(ProviderError, match="plain string failure"):
        _provider(wire_server).chat_completion(MSG, model="gpt-x")


def test_list_models_error_is_provider_error(wire_server):
    from eq_chatbot_core.providers.base import AuthenticationError

    wire_server.expect("GET", "/public/models", Reply(401, {"error": {"message": "bad key"}}))
    with pytest.raises(AuthenticationError):
        _provider(wire_server).list_models()


def test_close_and_context_manager(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    with _provider(wire_server) as provider:
        provider.chat_completion(MSG, model="gpt-x")
        assert provider._client is not None
    assert provider._client is None


def test_error_message_scrubs_secret(wire_server):
    from eq_chatbot_core.providers.base import ProviderError

    body = {"error": {"message": "failed for key sk-leakedsecret12345"}}
    wire_server.expect("POST", "/v1/chat/completions", Reply(500, body))
    with pytest.raises(ProviderError) as info:
        _provider(wire_server).chat_completion(MSG, model="gpt-x")
    assert "sk-leakedsecret12345" not in str(info.value)
