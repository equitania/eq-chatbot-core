"""Recognition of unsupported-parameter rejections and the process-wide memory."""

import pytest

from eq_chatbot_core.providers import param_learning
from tests.wire_server import (
    GATEWAY_TEMPERATURE_REJECTION_NO_PARAM,
    OPENAI_MAX_TOKENS_REJECTION,
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
