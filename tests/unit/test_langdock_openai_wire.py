"""LangDock's openai backend against the local OpenAI-wire server.

LangDock builds backend URLs as `<base_url>/openai/<region>/v1`, so the test
server answers on that path.
"""

import pytest

from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.langdock_provider import LangDockProvider
from tests.wire_server import OPENAI_TEMPERATURE_REJECTION, Reply, chat_body, models_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]
CHAT = ("POST", "/openai/eu/v1/chat/completions")


def _provider(wire_server, **kw):
    return LangDockProvider(api_key="ld-test", base_url=wire_server.root_url, max_retries=0, **kw)


def test_chat_goes_to_backend_path(wire_server):
    wire_server.expect(*CHAT, Reply(body=chat_body("hallo")))
    assert _provider(wire_server).chat_completion(MSG, model="gpt-6-luna").content == "hallo"


@pytest.mark.xfail(
    reason="stage 2: reasoning_effort is sent for every model and learned away; ported to test_no_name_lists_wire.py::test_langdock_constructor_reasoning_effort_sent_for_any_model_and_learned_away",
    strict=False,
)
def test_reasoning_effort_only_for_reasoning_models(wire_server):
    wire_server.expect(*CHAT, Reply(body=chat_body()))
    provider = _provider(wire_server, reasoning_effort="high")
    provider.chat_completion(MSG, model="o3")
    provider.chat_completion(MSG, model="gpt-4.1")
    assert wire_server.requests[0].json["reasoning_effort"] == "high"
    assert "reasoning_effort" not in wire_server.requests[1].json


def test_learning_and_stream(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(sse=stream_events(["o", "k"])))
    chunks = list(_provider(wire_server).stream_completion(MSG, model="gpt-6-luna", temperature=0.7))
    assert "".join(c.content for c in chunks) == "ok"


def test_errors_carry_langdock_as_provider(wire_server):
    wire_server.expect(*CHAT, Reply(500, {"error": {"message": "boom"}}))
    with pytest.raises(ProviderError) as caught:
        _provider(wire_server).chat_completion(MSG, model="gpt-6-luna")
    assert caught.value.provider == "langdock" and caught.value.status_code == 500


def test_openai_client_property_still_exists(wire_server):
    from openai import OpenAI

    assert isinstance(_provider(wire_server).openai_client, OpenAI)


@pytest.mark.xfail(
    reason="stage 2: no prefix filter; ported to test_list_models_wire.py::test_langdock_openai_lists_everything",
    strict=False,
)
def test_list_models_filters_to_supported_prefixes(wire_server):
    """Embeddings and other non-chat models must not appear (ported from the mocked listing test)."""
    body = models_body(["gpt-4o", "o3-mini", "text-embedding-ada-002"])
    wire_server.expect("GET", "/openai/eu/v1/models", Reply(body=body))
    ids = {m["id"] for m in _provider(wire_server).list_models()}
    assert ids == {"gpt-4o", "o3-mini"}


def test_unbuildable_delegate_is_provider_error_not_value_error(wire_server):
    """A DNS/validation failure while building the openai delegate must reach callers as ProviderError."""
    provider = _provider(wire_server)
    provider.base_url = "http://does-not-exist.invalid"
    with pytest.raises(ProviderError) as caught:
        provider.chat_completion(MSG, model="gpt-6-luna")
    assert caught.value.provider == "langdock"
    with pytest.raises(ProviderError):
        list(provider.stream_completion(MSG, model="gpt-6-luna"))
    with pytest.raises(ProviderError):
        provider.list_models()
    assert provider._openai_backend is None
