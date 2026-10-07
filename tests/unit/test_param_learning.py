"""Recognition of unsupported-parameter rejections and the process-wide memory."""

import pytest

from eq_chatbot_core.providers import param_learning
from tests.wire_server import (
    ANTHROPIC_TEMPERATURE_DEPRECATED,
    ANTHROPIC_TEMPERATURE_RANGE,
    GATEWAY_TEMPERATURE_REJECTION_NO_PARAM,
    OPENAI_MAX_TOKENS_REJECTION,
    OPENAI_REASONING_EFFORT_REJECTION,
    OPENAI_TEMPERATURE_REJECTION,
    Reply,
)

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]


def _error_for(wire_server, status, body):
    from openai import OpenAI

    wire_server.expect("POST", "/v1/chat/completions", Reply(status, body))
    client = OpenAI(api_key="k", base_url=wire_server.base_url, max_retries=0)
    with pytest.raises(Exception) as caught:
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
    return caught.value


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (OPENAI_TEMPERATURE_REJECTION, "temperature"),
        (OPENAI_MAX_TOKENS_REJECTION, "max_tokens"),
        (GATEWAY_TEMPERATURE_REJECTION_NO_PARAM, "temperature"),
    ],
)
def test_recognises_rejections(wire_server, body, expected):
    assert param_learning.rejected_parameter(_error_for(wire_server, 400, body)) == expected


def test_range_error_is_not_a_rejection(wire_server):
    body = {"error": {"message": "'temperature' must be at most 1.0", "param": "temperature", "code": "invalid_value"}}
    # param names temperature, but the code says the value is out of range, not unsupported
    assert param_learning.rejected_parameter(_error_for(wire_server, 400, body)) is None


def test_other_param_is_not_a_rejection(wire_server):
    body = {
        "error": {"message": "Unsupported parameter: 'logprobs'", "param": "logprobs", "code": "unsupported_parameter"}
    }
    assert param_learning.rejected_parameter(_error_for(wire_server, 400, body)) is None


def test_non_400_is_not_a_rejection(wire_server):
    assert param_learning.rejected_parameter(_error_for(wire_server, 500, OPENAI_TEMPERATURE_REJECTION)) is None


def test_adjust_drops_temperature_and_renames_max_tokens():
    params = {"model": "m", "temperature": 0.7, "max_tokens": 10}
    assert param_learning.adjust(params, "temperature")
    assert param_learning.adjust(params, "max_tokens")
    assert params == {"model": "m", "max_completion_tokens": 10}
    assert not param_learning.adjust(params, "temperature")  # nothing left to adjust


def test_memory_is_per_endpoint_and_model():
    param_learning.mark_unsupported("http://a/v1", "m", "temperature")
    param_learning.mark_unsupported("http://a/v1/", "m", "max_tokens")  # trailing slash: same endpoint

    same = {"temperature": 0.7, "max_tokens": 10}
    param_learning.apply("http://a/v1", "m", same)
    assert same == {"max_completion_tokens": 10}

    other_model = {"temperature": 0.7, "max_tokens": 10}
    param_learning.apply("http://a/v1", "other", other_model)
    assert other_model == {"temperature": 0.7, "max_tokens": 10}

    other_endpoint = {"temperature": 0.7}
    param_learning.apply("http://b/v1", "m", other_endpoint)
    assert other_endpoint == {"temperature": 0.7}


def test_seed_temperature_support():
    param_learning.seed_temperature_support("http://a/v1", "m", supported=False)
    params = {"temperature": 0.7}
    param_learning.apply("http://a/v1", "m", params)
    assert params == {}

    param_learning.seed_temperature_support("http://a/v1", "m", supported=True)
    params = {"temperature": 0.7}
    param_learning.apply("http://a/v1", "m", params)
    assert params == {"temperature": 0.7}


def _anthropic_error_for(wire_server, body):
    from anthropic import Anthropic

    wire_server.expect("POST", "/v1/messages", Reply(400, body))
    client = Anthropic(api_key="k", base_url=wire_server.root_url, max_retries=0)
    with pytest.raises(Exception) as caught:
        client.messages.create(model="m", max_tokens=5, messages=[{"role": "user", "content": "x"}])
    return caught.value


def test_recognises_reasoning_effort_rejection(wire_server):
    error = _error_for(wire_server, 400, OPENAI_REASONING_EFFORT_REJECTION)
    assert param_learning.rejected_parameter(error) == "reasoning_effort"


def test_recognises_anthropic_deprecation_inside_its_envelope(wire_server):
    error = _anthropic_error_for(wire_server, ANTHROPIC_TEMPERATURE_DEPRECATED)
    assert param_learning.rejected_parameter(error) == "temperature"


def test_anthropic_range_error_is_not_a_rejection(wire_server):
    assert param_learning.rejected_parameter(_anthropic_error_for(wire_server, ANTHROPIC_TEMPERATURE_RANGE)) is None


def test_adjust_temperature_in_extra_body_without_touching_the_callers_dict():
    caller_extra = {"temperature": 0.7, "metadata": {"a": 1}}
    params = {"model": "m", "extra_body": caller_extra}
    assert param_learning.adjust(params, "temperature")
    assert params["extra_body"] == {"metadata": {"a": 1}}
    assert caller_extra == {"temperature": 0.7, "metadata": {"a": 1}}

    only_temperature = {"model": "m", "extra_body": {"temperature": 0.7}}
    assert param_learning.adjust(only_temperature, "temperature")
    assert only_temperature == {"model": "m"}


def test_reasoning_effort_dropped_and_remembered():
    params = {"model": "m", "reasoning_effort": "high"}
    assert param_learning.adjust(params, "reasoning_effort") and params == {"model": "m"}
    param_learning.mark_unsupported("http://a/v1", "m", "reasoning_effort")
    later = {"reasoning_effort": "low", "temperature": 0.5}
    param_learning.apply("http://a/v1", "m", later)
    assert later == {"temperature": 0.5}


def test_apply_only_touches_the_named_parameters():
    param_learning.mark_unsupported("http://a/v1", "m", "max_tokens")
    params = {"max_tokens": 10}
    param_learning.apply("http://a/v1", "m", params, only=("temperature",))
    assert params == {"max_tokens": 10}


def test_learn_from_rejection_retries_each_parameter_once(wire_server, caplog):
    import logging

    logger = logging.getLogger("tests.learning")
    error = _error_for(wire_server, 400, OPENAI_TEMPERATURE_REJECTION)
    params = {"model": "m", "temperature": 0.7}
    adjusted: set[str] = set()
    with caplog.at_level("INFO", logger="tests.learning"):
        assert param_learning.learn_from_rejection(
            error, "http://a/v1", "m", params, adjusted, provider="p", logger=logger
        )
    assert params == {"model": "m"} and adjusted == {"temperature"}
    assert "p: model m rejected 'temperature'" in caplog.text
    assert param_learning.temperature_support("http://a/v1", "m") is False
    # Same rejection again in this call: no second retry.
    assert not param_learning.learn_from_rejection(
        error, "http://a/v1", "m", params, adjusted, provider="p", logger=logger
    )


def test_learn_from_rejection_respects_only(wire_server):
    import logging

    error = _error_for(wire_server, 400, OPENAI_MAX_TOKENS_REJECTION)
    params = {"model": "m", "max_tokens": 10}
    learned = param_learning.learn_from_rejection(
        error, "http://a/v1", "m", params, set(), provider="p", logger=logging.getLogger("t"), only=("temperature",)
    )
    assert not learned and params == {"model": "m", "max_tokens": 10}


def test_temperature_support_and_model_metadata():
    assert param_learning.temperature_support("http://a/v1", "m") is None
    meta = param_learning.model_metadata("http://a/v1", "m", context_length=1000)
    assert meta == {**dict.fromkeys(param_learning.METADATA_KEYS), "context_length": 1000}
    param_learning.mark_unsupported("http://a/v1/", "m", "temperature")
    assert param_learning.temperature_support("http://a/v1", "m") is False
    reported_true = param_learning.model_metadata("http://a/v1", "m", supports_temperature=True)
    assert reported_true["supports_temperature"] is False  # learned beats reported
