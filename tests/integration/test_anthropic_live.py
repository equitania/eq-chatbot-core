"""Anthropic live: temperature learning without a name list (stage 2)."""

import logging

import pytest

from eq_chatbot_core.providers import get_provider

# Probed 07.10.2026: answers "`temperature` is deprecated for this model." Test data.
TEMPERATURE_DEPRECATED_MODEL = "claude-sonnet-5"
_LOGGER = "eq_chatbot_core.providers.anthropic_provider"


@pytest.mark.integration
def test_deprecated_temperature_is_learned_once(anthropic_api_key, clean_param_memory, caplog):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    provider = get_provider("anthropic", api_key=anthropic_api_key)
    messages = [{"role": "user", "content": "Say OK"}]

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        first = provider.chat_completion(messages, model=TEMPERATURE_DEPRECATED_MODEL, temperature=0.7, max_tokens=64)
    assert first.content.strip()
    assert "rejected 'temperature'" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        second = provider.chat_completion(messages, model=TEMPERATURE_DEPRECATED_MODEL, temperature=0.7, max_tokens=64)
    assert second.content.strip()
    assert "rejected" not in caplog.text  # the second call sends no retry


@pytest.mark.integration
def test_chat_and_stream_with_the_registry_model(anthropic_api_key, anthropic_resolved_model):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    from tests.integration.live_checks import check_chat, check_stream

    provider = get_provider("anthropic", api_key=anthropic_api_key)
    check_chat(provider, anthropic_resolved_model)
    check_stream(provider, anthropic_resolved_model)
