"""AnthropicProvider and LangDock's anthropic backend against the wire server.

The real anthropic SDK talks the Messages API shape (POST /v1/messages, error body
{"type": "error", "error": {...}}) to the local server; only the remote is simulated.
"""

import pytest

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.langdock_provider import LangDockProvider
from tests.wire_server import (
    ANTHROPIC_TEMPERATURE_DEPRECATED,
    ANTHROPIC_TEMPERATURE_RANGE,
    Reply,
    anthropic_message_body,
    anthropic_stream_events,
)

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]


def _anthropic(wire_server):
    provider = AnthropicProvider(api_key="sk-ant-test", base_url=wire_server.root_url, max_retries=0)
    return provider, "/v1/messages", wire_server.root_url


def _langdock(wire_server):
    provider = LangDockProvider(api_key="ld-test", base_url=wire_server.root_url, max_retries=0, backend="anthropic")
    return provider, "/anthropic/eu/v1/messages", provider._get_backend_url()


BOTH = [_anthropic, _langdock]
IDS = ["anthropic", "langdock-anthropic"]


def _sent(wire_server, path):
    return [r.json for r in wire_server.requests if r.path == path]


@pytest.mark.parametrize("make", BOTH, ids=IDS)
def test_deprecated_temperature_is_dropped_and_learned(wire_server, make):
    provider, path, _ = make(wire_server)
    wire_server.expect(
        "POST", path, Reply(400, ANTHROPIC_TEMPERATURE_DEPRECATED), Reply(body=anthropic_message_body("hallo"))
    )
    assert provider.chat_completion(MSG, model="m", temperature=0.7).content == "hallo"
    assert provider.chat_completion(MSG, model="m", temperature=0.7).content == "hallo"
    first, second, third = _sent(wire_server, path)
    assert first["temperature"] == 0.7
    assert "temperature" not in second
    assert "temperature" not in third  # learned: the second call sends no retry


@pytest.mark.parametrize("make", BOTH, ids=IDS)
def test_stream_learns_before_the_first_chunk(wire_server, make):
    provider, path, _ = make(wire_server)
    wire_server.expect(
        "POST",
        path,
        Reply(400, ANTHROPIC_TEMPERATURE_DEPRECATED),
        Reply(sse=anthropic_stream_events(["hal", "lo"])),
    )
    chunks = list(provider.stream_completion(MSG, model="m", temperature=0.7))
    assert "".join(c.content for c in chunks) == "hallo"  # nothing duplicated
    assert chunks[-1].is_final and (chunks[-1].input_tokens, chunks[-1].output_tokens) == (5, 2)
    assert "temperature" not in _sent(wire_server, path)[1]


@pytest.mark.parametrize("make", BOTH, ids=IDS)
def test_range_error_is_not_learned(wire_server, make):
    """Review focus 3: '0..1' means the value is wrong, not that the model takes none."""
    provider, path, key = make(wire_server)
    wire_server.expect("POST", path, Reply(400, ANTHROPIC_TEMPERATURE_RANGE))
    with pytest.raises(ProviderError):
        provider.chat_completion(MSG, model="m", temperature=0.9)
    assert len(_sent(wire_server, path)) == 1
    assert param_learning.temperature_support(key, "m") is None


@pytest.mark.parametrize("make", BOTH, ids=IDS)
def test_learning_shared_across_instances(wire_server, make):
    provider, path, _ = make(wire_server)
    wire_server.expect("POST", path, Reply(400, ANTHROPIC_TEMPERATURE_DEPRECATED), Reply(body=anthropic_message_body()))
    provider.chat_completion(MSG, model="m", temperature=0.7)
    again, _, _ = make(wire_server)
    again.chat_completion(MSG, model="m", temperature=0.7)
    sent = _sent(wire_server, path)
    assert len(sent) == 3 and "temperature" not in sent[-1]


@pytest.mark.parametrize("make", BOTH, ids=IDS)
def test_temperature_travels_in_the_body_and_max_tokens_is_kept(wire_server, make):
    provider, path, _ = make(wire_server)
    wire_server.expect("POST", path, Reply(body=anthropic_message_body()))
    provider.chat_completion(MSG, model="m", temperature=0.4, max_tokens=50)
    sent = _sent(wire_server, path)[0]
    assert sent["temperature"] == 0.4 and sent["max_tokens"] == 50
