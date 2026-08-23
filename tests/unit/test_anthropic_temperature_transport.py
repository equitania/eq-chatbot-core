"""Where `temperature` has to travel since anthropic 1.0.0.

The SDK removed `temperature`, `top_p` and `top_k` from `messages.create()`,
`messages.stream()` and their beta counterparts — passing one is a TypeError, not
a warning. Current models ignore the parameter anyway; older ones still honour it
via `extra_body`. Verified live on 23.08.2026: without this, every temperature-
setting call to Claude 3.x raised
"Messages.create() got an unexpected keyword argument 'temperature'".
"""

import pytest

from eq_chatbot_core.providers.temperature_constraints import apply_anthropic_temperature


@pytest.mark.unit
class TestApplyAnthropicTemperature:
    def test_older_model_travels_in_extra_body(self):
        params: dict = {"model": "claude-3-haiku-20240307"}

        apply_anthropic_temperature(params, "claude-3-haiku-20240307", 0.7)

        assert "temperature" not in params, "a top-level temperature is a TypeError on SDK 1.x"
        assert params["extra_body"]["temperature"] == 0.7

    def test_reasoning_model_gets_no_temperature_at_all(self):
        params: dict = {"model": "claude-opus-5"}

        apply_anthropic_temperature(params, "claude-opus-5", 0.7)

        assert "temperature" not in params
        assert "extra_body" not in params

    def test_value_is_clamped_before_it_travels(self):
        params: dict = {}

        apply_anthropic_temperature(params, "claude-3-5-sonnet-20241022", 1.8)

        assert params["extra_body"]["temperature"] == 1.0

    def test_existing_extra_body_is_preserved(self):
        params: dict = {"extra_body": {"foo": "bar"}}

        apply_anthropic_temperature(params, "claude-3-haiku-20240307", 0.3)

        assert params["extra_body"] == {"foo": "bar", "temperature": 0.3}

    def test_returns_whether_it_applied_anything(self):
        assert apply_anthropic_temperature({}, "claude-3-haiku-20240307", 0.5) is True
        assert apply_anthropic_temperature({}, "claude-opus-5", 0.5) is False
