"""list_models(): every model the provider lists; provider data or learned facts, else None."""

import pytest

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.langdock_provider import LangDockProvider
from eq_chatbot_core.providers.local_provider import LocalLLMProvider
from eq_chatbot_core.providers.mammouth_provider import MammouthProvider
from eq_chatbot_core.providers.openai_provider import OpenAIProvider
from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider
from tests.wire_server import (
    OPENAI_TEMPERATURE_REJECTION,
    Reply,
    anthropic_models_body,
    chat_body,
    models_body,
)

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]
UNKNOWN = dict.fromkeys(param_learning.METADATA_KEYS)


def _unknown_part(entry):
    return {k: entry[k] for k in UNKNOWN}


def test_openai_lists_everything_unfiltered_with_unknown_metadata(wire_server):
    wire_server.expect("GET", "/v1/models", Reply(body=models_body(["chat-a", "embed-b", "brand-new-family-1"])))
    models = OpenAIProvider(api_key="k", base_url=wire_server.base_url, max_retries=0).list_models()
    assert [m["id"] for m in models] == ["brand-new-family-1", "chat-a", "embed-b"]
    for m in models:
        assert _unknown_part(m) == UNKNOWN
        assert (m["name"], m["provider"], m["owned_by"], m["created"]) == (m["id"], "openai", "test", 0)


def test_openai_learned_rejection_shows_in_the_list(wire_server):
    provider = OpenAIProvider(api_key="k", base_url=wire_server.base_url, max_retries=0)
    wire_server.expect(
        "POST", "/v1/chat/completions", Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body())
    )
    provider.chat_completion(MSG, model="picky", temperature=0.7)
    wire_server.expect("GET", "/v1/models", Reply(body=models_body(["picky", "other"])))
    by_id = {m["id"]: m for m in provider.list_models()}
    assert by_id["picky"]["supports_temperature"] is False
    assert by_id["other"]["supports_temperature"] is None


def test_langdock_openai_lists_everything(wire_server):
    wire_server.expect("GET", "/openai/eu/v1/models", Reply(body=models_body(["chat-like", "embedding-like"])))
    models = LangDockProvider(api_key="k", base_url=wire_server.root_url, max_retries=0).list_models()
    assert [m["id"] for m in models] == ["chat-like", "embedding-like"]
    for m in models:
        assert (m["backend"], m["region"], m["provider"]) == ("openai", "eu", "langdock")
        assert _unknown_part(m) == UNKNOWN


@pytest.mark.parametrize(
    ("make", "path"),
    [
        (lambda ws: AnthropicProvider(api_key="k", base_url=ws.root_url, max_retries=0), "/v1/models"),
        (
            lambda ws: LangDockProvider(api_key="k", base_url=ws.root_url, max_retries=0, backend="anthropic"),
            "/anthropic/eu/v1/models",
        ),
    ],
    ids=["anthropic", "langdock-anthropic"],
)
def test_anthropic_metadata_comes_from_the_models_api(wire_server, make, path):
    body = anthropic_models_body(
        [
            {
                "id": "reported",
                "display_name": "Reported",
                "max_input_tokens": 1000,
                "max_tokens": 200,
                "capabilities": {"image_input": {"supported": True}, "thinking": {"supported": False, "types": {}}},
            },
            {"id": "silent"},
        ]
    )
    wire_server.expect("GET", path, Reply(body=body))
    by_id = {m["id"]: m for m in make(wire_server).list_models()}
    reported = by_id["reported"]
    assert reported["name"] == "Reported"
    assert (reported["context_length"], reported["max_output_tokens"]) == (1000, 200)
    assert reported["supports_vision"] is True and reported["supports_reasoning"] is False
    assert reported["min_temperature"] is None and reported["supports_temperature"] is None
    assert _unknown_part(by_id["silent"]) == UNKNOWN


def test_langdock_google_reports_what_gemini_reports(wire_server):
    body = {
        "models": [
            {
                "name": "models/g-1",
                "inputTokenLimit": 1000,
                "outputTokenLimit": 100,
                "temperature": 1.0,
                "maxTemperature": 2.0,
                "thinking": True,
            },
            {"name": "models/g-2"},
        ]
    }
    wire_server.expect("GET", "/google/eu/v1beta/models", Reply(body=body))
    provider = LangDockProvider(api_key="k", base_url=wire_server.root_url, max_retries=0, backend="google")
    by_id = {m["id"]: m for m in provider.list_models()}
    g1 = by_id["g-1"]
    assert (g1["context_length"], g1["max_output_tokens"]) == (1000, 100)
    assert (g1["default_temperature"], g1["max_temperature"], g1["supports_reasoning"]) == (1.0, 2.0, True)
    assert g1["min_temperature"] is None and g1["supports_vision"] is None
    assert _unknown_part(by_id["g-2"]) == UNKNOWN


def _mammouth(wire_server):
    provider = MammouthProvider(api_key="k", base_url=wire_server.base_url, max_retries=0)
    provider.MODELS_URL = f"{wire_server.root_url}/public/models"
    return provider


def test_mammouth_reports_its_limits_and_nothing_else(wire_server):
    data = [{"id": "b-model", "max_input_tokens": 1000, "max_output_tokens": 100}, {"id": "a-model"}]
    wire_server.expect("GET", "/public/models", Reply(body={"data": data}))
    models = _mammouth(wire_server).list_models()
    assert [m["id"] for m in models] == ["a-model", "b-model"]
    assert models[1] == {
        "id": "b-model",
        "name": "b-model",
        "provider": "mammouth",
        "context_length": 1000,
        "max_output_tokens": 100,
        "supports_temperature": None,
        "min_temperature": None,
        "max_temperature": None,
        "supports_reasoning": None,
        "supports_streaming": True,
    }


def test_openrouter_metadata_from_the_api(wire_server):
    body = {
        "data": [
            {
                "id": "v/full",
                "name": "Full",
                "description": "d",
                "context_length": 1000,
                "created": 5,
                "supported_parameters": ["temperature", "tools", "reasoning"],
                "default_parameters": {"temperature": 0.6},
                "input_modalities": ["text", "image"],
                "output_modalities": ["text"],
                "top_provider": {"max_completion_tokens": 300},
            },
            {"id": "v/bare", "supported_parameters": None, "input_modalities": None},
        ]
    }
    wire_server.expect("GET", "/v1/models", Reply(body=body))
    provider = OpenRouterProvider(api_key="k", base_url=wire_server.base_url, max_retries=0)
    by_id = {m["id"]: m for m in provider.list_models()}
    full, bare = by_id["v/full"], by_id["v/bare"]
    assert (full["name"], full["description"], full["provider"], full["created"]) == ("Full", "d", "openrouter", 5)
    flags = (full["supports_temperature"], full["supports_tools"], full["supports_reasoning"], full["supports_vision"])
    assert flags == (True, True, True, True)
    assert (full["default_temperature"], full["min_temperature"], full["max_temperature"]) == (0.6, None, None)
    assert (full["max_output_tokens"], full["default_max_tokens"], full["context_length"]) == (300, None, 1000)
    for key in (
        "supports_temperature",
        "supports_tools",
        "supports_reasoning",
        "supports_vision",
        "max_output_tokens",
        "input_modalities",
        "default_temperature",
    ):
        assert bare[key] is None, key


def test_openrouter_learned_rejection_beats_the_list(wire_server):
    provider = OpenRouterProvider(api_key="k", base_url=wire_server.base_url, max_retries=0)
    wire_server.expect(
        "POST", "/v1/chat/completions", Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body())
    )
    provider.chat_completion(MSG, model="v/picky", temperature=0.5)
    wire_server.expect(
        "GET", "/v1/models", Reply(body={"data": [{"id": "v/picky", "supported_parameters": ["temperature"]}]})
    )
    (model,) = provider.list_models()
    assert model["supports_temperature"] is False
    provider.chat_completion(MSG, model="v/picky", temperature=0.5)
    assert "temperature" not in wire_server.requests[-1].json  # the list did not undo it


def test_local_does_not_guess_tools_or_vision(wire_server):
    wire_server.expect("GET", "/v1/models", Reply(body=models_body(["m"])))
    (model,) = LocalLLMProvider(base_url=wire_server.base_url, max_retries=0).list_models()
    assert model == {
        "id": "m",
        "name": "m",
        "provider": "local",
        "context_length": None,
        "supports_streaming": True,
        "supports_tools": None,
        "supports_vision": None,
        "owned_by": "test",
        "created": 0,
    }


def test_google_name_is_display_name_or_the_id(wire_server):
    body = {"models": [{"name": "models/g-1", "displayName": "Gee One"}, {"name": "models/g-2"}]}
    wire_server.expect("GET", "/google/eu/v1beta/models", Reply(body=body))
    provider = LangDockProvider(api_key="k", base_url=wire_server.root_url, max_retries=0, backend="google")
    assert {m["id"]: m["name"] for m in provider.list_models()} == {"g-1": "Gee One", "g-2": "g-2"}


# --- an unreachable or malformed listing raises a typed error, never [] ---


def _langdock(wire_server, backend, **kw):
    return LangDockProvider(api_key="k", base_url=wire_server.root_url, max_retries=0, backend=backend, **kw)


def _openai(ws):
    return OpenAIProvider(api_key="k", base_url=ws.base_url, max_retries=0)


@pytest.mark.parametrize(
    ("make", "path", "reply"),
    [
        (_openai, "/v1/models", Reply(500, {"error": {"message": "boom"}})),
        (_openai, "/v1/models", Reply(body=["not", "a", "dict"])),
        (lambda ws: _langdock(ws, "anthropic"), "/anthropic/eu/v1/models", Reply(500, {"error": "boom"})),
        (lambda ws: _langdock(ws, "anthropic"), "/anthropic/eu/v1/models", Reply(body=["x"])),
        (lambda ws: _langdock(ws, "google"), "/google/eu/v1beta/models", Reply(500, {"error": "boom"})),
        (lambda ws: _langdock(ws, "agent", agent_id="ag-1"), "/agent/v1/models", Reply(500, {"error": "boom"})),
        (lambda ws: _langdock(ws, "agent", agent_id="ag-1"), "/agent/v1/models", Reply(body=["x"])),
        (_mammouth, "/public/models", Reply(raw='"oops"', headers={"Content-Type": "application/json"})),
        (lambda ws: LocalLLMProvider(base_url=ws.base_url, max_retries=0), "/v1/models", Reply(body=["x"])),
        (
            lambda ws: OpenRouterProvider(api_key="k", base_url=ws.base_url, max_retries=0),
            "/v1/models",
            Reply(body=["x"]),
        ),
    ],
    ids=[
        "openai-500",
        "openai-non-dict",
        "langdock-anthropic-500",
        "langdock-anthropic-non-dict",
        "langdock-google-500",
        "langdock-agent-500",
        "langdock-agent-non-dict",
        "mammouth-bad-body",
        "local-non-dict",
        "openrouter-non-dict",
    ],
)
def test_unusable_listing_raises_provider_error(wire_server, make, path, reply):
    wire_server.expect("GET", path, reply)
    with pytest.raises(ProviderError):
        make(wire_server).list_models()


def test_langdock_unknown_backend_raises(wire_server):
    provider = _langdock(wire_server, "openai")
    provider.backend = "nonsense"
    with pytest.raises(ProviderError, match="unknown LangDock backend"):
        provider.list_models()
