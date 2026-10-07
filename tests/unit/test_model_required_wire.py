"""Stage 2: the model always comes from the caller — per call or per provider instance.

Runs against the wire server; a missing model must fail before any request is sent.
"""

import inspect

import pytest

from eq_chatbot_core.providers import ModelNotSpecifiedError, ProviderError, get_provider
from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.ionos_provider import IonosProvider
from eq_chatbot_core.providers.langdock_provider import LangDockAgentManager, LangDockProvider
from eq_chatbot_core.providers.litellm_provider import LiteLLMProvider
from eq_chatbot_core.providers.local_provider import LocalLLMProvider
from eq_chatbot_core.providers.mammouth_provider import MammouthProvider
from eq_chatbot_core.providers.melious_provider import MeliousProvider
from eq_chatbot_core.providers.openai_provider import OpenAIProvider
from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider
from eq_chatbot_core.providers.privatemode_provider import PrivatemodeProvider
from tests.wire_server import Reply, chat_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]
CHAT = ("POST", "/v1/chat/completions")
WIRE_NAMES = ["openai", "mammouth", "openrouter", "local", "ionos", "melious", "litellm", "privatemode"]


def _wire_provider(wire_server, name, **kw):
    url = wire_server.base_url
    makers = {
        "openai": lambda: OpenAIProvider(api_key="k", base_url=url, max_retries=0, **kw),
        "mammouth": lambda: MammouthProvider(api_key="k", base_url=url, max_retries=0, **kw),
        "openrouter": lambda: OpenRouterProvider(api_key="k", base_url=url, max_retries=0, **kw),
        "local": lambda: LocalLLMProvider(base_url=url, max_retries=0, **kw),
        "ionos": lambda: IonosProvider(api_key="k", base_url=url, max_retries=0, **kw),
        "melious": lambda: MeliousProvider(api_key="k", base_url=url, max_retries=0, **kw),
        "litellm": lambda: LiteLLMProvider(api_key="k", base_url=url, max_retries=0, **kw),
        "privatemode": lambda: PrivatemodeProvider(base_url=url, max_retries=0, allow_insecure_transport=True, **kw),
    }
    return makers[name]()


@pytest.mark.parametrize("name", WIRE_NAMES)
def test_chat_without_any_model_raises_before_sending(wire_server, name):
    with pytest.raises(ModelNotSpecifiedError) as caught:
        _wire_provider(wire_server, name).chat_completion(MSG)
    assert caught.value.provider == name
    assert wire_server.requests == []


@pytest.mark.parametrize("name", WIRE_NAMES)
def test_stream_without_any_model_raises_before_sending(wire_server, name):
    with pytest.raises(ModelNotSpecifiedError):
        next(iter(_wire_provider(wire_server, name).stream_completion(MSG)))
    assert wire_server.requests == []


@pytest.mark.parametrize("name", WIRE_NAMES)
def test_constructor_model_is_used(wire_server, name):
    wire_server.expect(*CHAT, Reply(body=chat_body()))
    _wire_provider(wire_server, name, model="ctor-model").chat_completion(MSG)
    assert wire_server.requests[0].json["model"] == "ctor-model"


@pytest.mark.parametrize("name", WIRE_NAMES)
def test_call_model_beats_constructor_model(wire_server, name):
    wire_server.expect(*CHAT, Reply(sse=stream_events(["a"])))
    chunks = list(_wire_provider(wire_server, name, model="ctor-model").stream_completion(MSG, model="call-model"))
    assert chunks[-1].is_final
    assert wire_server.requests[0].json["model"] == "call-model"


@pytest.mark.parametrize("empty", ["", None, False])
def test_empty_model_from_a_form_field_falls_back_to_constructor(wire_server, empty):
    """Review focus 1: Odoo passes an unset char field as False and a cleared one as ""."""
    wire_server.expect(*CHAT, Reply(body=chat_body()))
    _wire_provider(wire_server, "openai", model="ctor-model").chat_completion(MSG, model=empty)
    assert wire_server.requests[0].json["model"] == "ctor-model"


@pytest.mark.parametrize("empty", ["", None, False])
def test_empty_model_without_constructor_model_never_sends_an_empty_id(wire_server, empty):
    with pytest.raises(ModelNotSpecifiedError):
        _wire_provider(wire_server, "mammouth").chat_completion(MSG, model=empty)
    assert wire_server.requests == []


def test_error_names_both_places_and_is_a_provider_error():
    error = ModelNotSpecifiedError("openai")
    assert isinstance(error, ProviderError)
    assert error.provider == "openai" and error.status_code is None and error.what == "model"
    assert 'model="..."' in str(error) and 'get_provider("openai"' in str(error)


@pytest.mark.parametrize("backend", ["openai", "anthropic", "google", "codestral"])
def test_langdock_backends_need_a_model(backend):
    provider = LangDockProvider(api_key="k", backend=backend)
    with pytest.raises(ModelNotSpecifiedError):
        provider.chat_completion(MSG)
    with pytest.raises(ModelNotSpecifiedError):
        next(iter(provider.stream_completion(MSG)))


def test_langdock_agent_backend_needs_no_model():
    """Review focus 2: the agent's model is configured in LangDock, not per request."""
    provider = LangDockProvider(api_key="k", backend="agent", agent_id="agent-1")
    assert provider.default_model is None
    assert provider.resolve_model(None) == ""


def test_langdock_constructor_model():
    assert LangDockProvider(api_key="k", backend="google", model="ctor-model").resolve_model() == "ctor-model"


def test_anthropic_needs_a_model_and_takes_one_in_the_constructor():
    with pytest.raises(ModelNotSpecifiedError):
        AnthropicProvider(api_key="k").chat_completion(MSG)
    with pytest.raises(ModelNotSpecifiedError):
        next(iter(AnthropicProvider(api_key="k").stream_completion(MSG)))
    assert AnthropicProvider(api_key="k", model="ctor-model").default_model == "ctor-model"


def test_get_provider_forwards_model():
    assert get_provider("mammouth", api_key="k", model="ctor-model").default_model == "ctor-model"
    assert get_provider("ollama", model="ctor-model").default_model == "ctor-model"


def _image_reply_body():
    body = chat_body("")
    body["choices"][0]["message"]["images"] = [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw=="}}
    ]
    return body


def test_openai_image_needs_a_model(wire_server):
    with pytest.raises(ModelNotSpecifiedError, match="image_model"):
        _wire_provider(wire_server, "openai").generate_image("a cat")
    assert wire_server.requests == []


def test_openai_image_model_from_constructor(wire_server):
    wire_server.expect("POST", "/v1/images/generations", Reply(body={"created": 0, "data": [{"b64_json": "iVBORw=="}]}))
    provider = _wire_provider(wire_server, "openai", image_model="img-model")
    assert provider.generate_image("a cat").model == "img-model"
    assert wire_server.requests[0].json["model"] == "img-model"


def test_openrouter_image_needs_a_model(wire_server):
    with pytest.raises(ModelNotSpecifiedError, match="image_model"):
        _wire_provider(wire_server, "openrouter").generate_image("a cat")
    assert wire_server.requests == []


def test_openrouter_image_model_from_constructor(wire_server):
    wire_server.expect(*CHAT, Reply(body=_image_reply_body()))
    provider = _wire_provider(wire_server, "openrouter", image_model="img-model")
    assert provider.generate_image("a cat").model == "img-model"
    assert wire_server.requests[0].json["model"] == "img-model"


def test_tts_needs_model_and_voice(wire_server):
    with pytest.raises(ModelNotSpecifiedError, match="tts_model"):
        _wire_provider(wire_server, "litellm").text_to_speech("Hallo", voice="voice-1")
    with pytest.raises(ModelNotSpecifiedError, match="tts_voice"):
        _wire_provider(wire_server, "litellm").text_to_speech("Hallo", model="tts-model")
    assert wire_server.requests == []


def test_stt_needs_a_model(wire_server):
    with pytest.raises(ModelNotSpecifiedError, match="stt_model"):
        _wire_provider(wire_server, "litellm").transcribe(("a.wav", b"RIFF0000", "audio/wav"))
    assert wire_server.requests == []


def test_tts_and_stt_use_constructor_settings(wire_server):
    wire_server.expect("POST", "/v1/audio/speech", Reply(raw=b"RIFF", headers={"Content-Type": "audio/wav"}))
    wire_server.expect("POST", "/v1/audio/transcriptions", Reply(body={"text": "hallo"}))
    provider = _wire_provider(wire_server, "litellm", tts_model="tts-model", tts_voice="voice-1", stt_model="stt-model")
    assert provider.text_to_speech("Hallo") == b"RIFF"
    assert (wire_server.requests[0].json["model"], wire_server.requests[0].json["voice"]) == ("tts-model", "voice-1")
    assert provider.transcribe(("a.wav", b"RIFF0000", "audio/wav")) == "hallo"


def test_agent_manager_create_agent_requires_a_model():
    parameter = inspect.signature(LangDockAgentManager.create_agent).parameters["model"]
    assert parameter.default is inspect.Parameter.empty


def test_langdock_agent_chat_works_without_any_model(wire_server):
    """The agent backend sends no model: a chat call succeeds with neither call nor constructor model."""
    wire_server.expect(
        "POST",
        "/agent/v1/chat/completions",
        Reply(
            sse=[
                {"type": "start", "messageMetadata": {"modelName": "agent-side-model"}},
                {"type": "text-delta", "id": "t1", "delta": "hallo"},
            ]
        ),
    )
    provider = LangDockProvider(api_key="k", base_url=wire_server.root_url, backend="agent", agent_id="agent-1")
    response = provider.chat_completion(MSG)
    assert response.content == "hallo"
    assert "model" not in wire_server.requests[0].json
