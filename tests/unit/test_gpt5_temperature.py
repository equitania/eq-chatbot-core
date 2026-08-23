"""Which GPT-5 generations still accept `temperature`.

Measured live against the OpenAI API on 23.08.2026 — the pattern is NOT a clean
cut-off and cannot be guessed:

    gpt-4.1        accepts
    gpt-5          REJECTS   "Unsupported value: 'temperature' does not support
    gpt-5-mini     REJECTS    0.7 with this model. Only the default (1) ..."
    gpt-5.1        accepts
    gpt-5.2        accepts
    gpt-5.4        accepts
    gpt-5.4-mini   accepts
    gpt-5.5        REJECTS
    gpt-5.6-*      REJECTS

Before this, the table carried a single `gpt-5` prefix entry declaring the whole
family temperature-capable, so every call to gpt-5, gpt-5.5 and the current
gpt-5.6 tier failed with HTTP 400. Same failure mode as the Claude Opus 4.7
regression fixed in v2.0.2.

The default for an UNKNOWN gpt-5.x is "no temperature": omitting the parameter
never breaks a model that would have accepted it, while sending it to one that
refuses breaks every single call.
"""

import pytest

from eq_chatbot_core.providers.temperature_constraints import clamp_temperature

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "model",
    [
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-5-2025-08-07",
        "gpt-5.5",
        "gpt-5.6-luna",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
    ],
)
def test_temperature_is_omitted_where_openai_refuses_it(model):
    assert clamp_temperature(model, 0.7) is None


@pytest.mark.parametrize("model", ["gpt-5.1", "gpt-5.2", "gpt-5.4", "gpt-5.4-mini", "gpt-4.1", "gpt-4o"])
def test_temperature_still_passes_where_it_is_accepted(model):
    assert clamp_temperature(model, 0.7) == 0.7


def test_unknown_future_gpt5_generation_defaults_to_omitting():
    """A generation nobody has tested yet must fail safe, not fail loud."""
    assert clamp_temperature("gpt-5.9-whatever", 0.7) is None


def test_provider_prefixed_ids_resolve_the_same_way():
    assert clamp_temperature("openai/gpt-5.6-luna", 0.7) is None
    assert clamp_temperature("openai/gpt-5.2", 0.7) == 0.7
