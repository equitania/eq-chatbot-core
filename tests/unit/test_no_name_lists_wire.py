"""Stage 2: what name lists used to decide is now decided by the API or learned.

Real-looking model names below are test data: they show that a name no longer
changes what is sent.
"""

import pytest

from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.langdock_provider import LangDockProvider
from eq_chatbot_core.providers.mammouth_provider import MammouthProvider
from eq_chatbot_core.providers.openai_provider import OpenAIProvider
from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider
from eq_chatbot_core.providers.temperature_constraints import apply_anthropic_temperature, clamp_temperature
from tests.wire_server import OPENAI_REASONING_EFFORT_REJECTION, Reply, anthropic_message_body, chat_body

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]
CHAT = ("POST", "/v1/chat/completions")
LANGDOCK_CHAT = ("POST", "/openai/eu/v1/chat/completions")


def test_clamp_is_provider_level_only():
    assert clamp_temperature(0.7) == 0.7
    assert clamp_temperature(3.0) == 2.0
    assert clamp_temperature(-1.0) == 0.0
    assert clamp_temperature(1.5, maximum=1.0) == 1.0


def test_anthropic_temperature_clamped_into_extra_body():
    params = {"model": "m"}
    apply_anthropic_temperature(params, 1.5)
    assert params == {"model": "m", "extra_body": {"temperature": 1.0}}


def test_anthropic_temperature_merges_into_existing_extra_body():
    params = {"extra_body": {"foo": "bar"}}
    apply_anthropic_temperature(params, 0.3)
    assert params["extra_body"] == {"foo": "bar", "temperature": 0.3}


@pytest.mark.parametrize("provider_cls", [MammouthProvider, OpenAIProvider, OpenRouterProvider])
@pytest.mark.parametrize("model", ["o3", "gpt-5", "deepseek-reasoner", "anything-new"])
def test_temperature_is_sent_whatever_the_model_name(wire_server, provider_cls, model):
    wire_server.expect(*CHAT, Reply(body=chat_body()))
    provider_cls(api_key="k", base_url=wire_server.base_url, max_retries=0).chat_completion(
        MSG, model=model, temperature=0.3
    )
    assert wire_server.requests[0].json["temperature"] == 0.3


def test_anthropic_sends_temperature_for_any_model_name(wire_server):
    wire_server.expect("POST", "/v1/messages", Reply(body=anthropic_message_body()))
    AnthropicProvider(api_key="k", base_url=wire_server.root_url, max_retries=0).chat_completion(
        MSG, model="claude-sonnet-5", temperature=1.4
    )
    assert wire_server.requests[0].json["temperature"] == 1.0  # Anthropic's provider-level 0..1


def test_openai_always_sends_max_completion_tokens(wire_server):
    wire_server.expect(*CHAT, Reply(body=chat_body()))
    OpenAIProvider(api_key="k", base_url=wire_server.base_url, max_retries=0).chat_completion(
        MSG, model="any-model", max_tokens=20
    )
    sent = wire_server.requests[0].json
    assert sent["max_completion_tokens"] == 20 and "max_tokens" not in sent


def test_langdock_openai_sends_max_tokens_whatever_the_model(wire_server):
    wire_server.expect(*LANGDOCK_CHAT, Reply(body=chat_body()))
    LangDockProvider(api_key="k", base_url=wire_server.root_url, max_retries=0).chat_completion(
        MSG, model="gpt-5", max_tokens=20
    )
    sent = wire_server.requests[0].json
    assert sent["max_tokens"] == 20 and "max_completion_tokens" not in sent


def test_langdock_constructor_reasoning_effort_sent_for_any_model_and_learned_away(wire_server):
    """Set once in the constructor, never per call: still dropped once a model rejects it."""
    wire_server.expect(*LANGDOCK_CHAT, Reply(400, OPENAI_REASONING_EFFORT_REJECTION), Reply(body=chat_body()))
    provider = LangDockProvider(api_key="k", base_url=wire_server.root_url, max_retries=0, reasoning_effort="high")
    provider.chat_completion(MSG, model="plain-model")
    provider.chat_completion(MSG, model="plain-model")
    first, second, third = [r.json for r in wire_server.requests]
    assert first["reasoning_effort"] == "high"
    assert "reasoning_effort" not in second and "reasoning_effort" not in third


def test_openrouter_reasoning_effort_passes_through(wire_server):
    wire_server.expect(*CHAT, Reply(body=chat_body()))
    OpenRouterProvider(api_key="k", base_url=wire_server.base_url, max_retries=0).chat_completion(
        MSG, model="vendor/plain", reasoning_effort="low"
    )
    assert wire_server.requests[0].json["reasoning_effort"] == "low"


def test_openai_image_without_b64_is_a_clear_error(wire_server):
    wire_server.expect(
        "POST", "/v1/images/generations", Reply(body={"created": 0, "data": [{"url": "https://example.invalid/i.png"}]})
    )
    provider = OpenAIProvider(api_key="k", base_url=wire_server.base_url, max_retries=0, image_model="dall-e-3")
    with pytest.raises(ProviderError, match="response_format"):
        provider.generate_image("a cat")
    assert "response_format" not in wire_server.requests[0].json  # no name-based guess any more
