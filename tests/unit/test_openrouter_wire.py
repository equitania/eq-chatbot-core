"""OpenRouterProvider against the local OpenAI-wire server."""

import base64

import pytest

from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider
from tests.wire_server import OPENAI_TEMPERATURE_REJECTION, Reply, chat_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]


def _provider(wire_server, **kw):
    return OpenRouterProvider(api_key="sk-or-test", base_url=wire_server.base_url, max_retries=0, **kw)


def test_attribution_headers(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    _provider(wire_server, site_url="https://example.com", site_name="eq-test").chat_completion(MSG, model="a/b")
    headers = {k.lower(): v for k, v in wire_server.requests[0].headers.items()}
    assert headers.get("http-referer") == "https://example.com" and headers.get("x-title") == "eq-test"


def test_model_list_seeds_temperature_support(wire_server):
    wire_server.expect(
        "GET",
        "/v1/models",
        Reply(body={"data": [{"id": "x/no-temp", "supported_parameters": ["max_tokens", "tools"]}]}),
    )
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    provider = _provider(wire_server)
    (model,) = provider.list_models()
    assert model["supports_temperature"] is False and model["supports_tools"] is True

    provider.chat_completion(MSG, model="x/no-temp", temperature=0.7)
    assert "temperature" not in wire_server.requests[-1].json  # right on the first request


def test_mid_stream_error_keeps_its_cause(wire_server):
    events = stream_events(["par"])[:1] + [{"error": {"message": "Provider returned error: overloaded", "code": 502}}]
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=events))
    with pytest.raises(ProviderError, match="overloaded"):
        list(_provider(wire_server).stream_completion(MSG, model="a/b"))


def test_generate_image(wire_server):
    png = b"\x89PNG\r\n"
    url = "data:image/png;base64," + base64.b64encode(png).decode()
    body = chat_body("")
    body["choices"][0]["message"]["images"] = [{"type": "image_url", "image_url": {"url": url}}]
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=body))
    result = _provider(wire_server).generate_image("a cat")
    assert result.data == png and result.mime == "image/png"
    assert wire_server.requests[0].json["modalities"] == ["image", "text"]


def test_generate_image_without_image_raises(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("sorry")))
    with pytest.raises(ProviderError, match="No image returned"):
        _provider(wire_server).generate_image("a cat")


def test_runtime_rejection_survives_optimistic_model_list(wire_server):
    wire_server.expect(
        "POST", "/v1/chat/completions", Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body())
    )
    provider = _provider(wire_server)
    provider.chat_completion(MSG, model="x/picky", temperature=0.5)
    assert "temperature" not in wire_server.requests[1].json  # learned at runtime

    wire_server.expect(
        "GET",
        "/v1/models",
        Reply(body={"data": [{"id": "x/picky", "supported_parameters": ["temperature", "max_tokens"]}]}),
    )
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    (model,) = provider.list_models()
    assert model["supports_temperature"] is True

    provider.chat_completion(MSG, model="x/picky", temperature=0.5)
    assert "temperature" not in wire_server.requests[-1].json  # list did not undo it


# --- Ported from the mocked unit files (behaviour that still exists) ---------


def test_defaults_and_site_info():
    provider = OpenRouterProvider(api_key="sk-or-test", site_url="https://e.example", site_name="n")
    assert provider.provider_name == "openrouter"
    assert provider.default_model == OpenRouterProvider.DEFAULT_MODEL
    assert provider.base_url == OpenRouterProvider.DEFAULT_BASE_URL
    assert (provider.site_url, provider.site_name) == ("https://e.example", "n")
    assert provider.supports_image_generation is True


def test_custom_base_url_is_ssrf_checked():
    with pytest.raises(Exception, match="(?i)private|not allowed|blocked|loopback|resolve|internal"):
        OpenRouterProvider(api_key="sk-or-test", base_url="http://169.254.169.254/v1")


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("openai/o1", True),
        ("openai/o3-mini", True),
        ("openai/o4-mini", True),
        ("openai/gpt-4o", False),
        ("meta/llama", False),
    ],
)
def test_reasoning_model_detection(model, expected):
    assert OpenRouterProvider(api_key="k")._is_reasoning_model(model) is expected


def test_reasoning_model_gets_no_temperature(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="openai/o3", temperature=0.7, max_tokens=50)
    assert "temperature" not in wire_server.requests[0].json


def test_chat_with_temperature_and_tools(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    tool = {"type": "function", "function": {"name": "f", "description": "d", "parameters": {"type": "object"}}}
    _provider(wire_server).chat_completion(MSG, model="openai/gpt-4o", temperature=0.5, tools=[tool])
    sent = wire_server.requests[0].json
    assert sent["temperature"] == 0.5 and sent["tools"][0]["function"]["name"] == "f"


def test_stream_accumulates_tool_calls(wire_server):
    base = {"id": "c", "object": "chat.completion.chunk", "created": 0, "model": "a/b"}

    def delta(d, finish=None):
        return {**base, "choices": [{"index": 0, "delta": d, "finish_reason": finish}]}

    first = {"index": 0, "id": "call_1", "type": "function", "function": {"name": "f", "arguments": '{"a"'}}
    events = [
        delta({"tool_calls": [first]}),
        delta({"tool_calls": [{"index": 0, "function": {"arguments": ": 1}"}}]}),
        delta({}, "tool_calls"),
    ]
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=events))
    chunks = list(_provider(wire_server).stream_completion(MSG, model="a/b"))
    final = [c for c in chunks if c.is_final][-1]
    assert final.finish_reason == "tool_calls"
    assert final.tool_calls[0]["function"]["name"] == "f"
    assert final.tool_calls[0]["function"]["arguments"] == '{"a": 1}'


def test_list_models_metadata_and_constraints(wire_server):
    wire_server.expect(
        "GET",
        "/v1/models",
        Reply(
            body={
                "data": [
                    {
                        "id": "openai/gpt-4o",
                        "name": "GPT-4o",
                        "description": "d",
                        "context_length": 128000,
                        "created": 5,
                        "supported_parameters": ["temperature", "max_tokens", "tools"],
                    },
                    {"id": "openai/o3", "name": "o3", "context_length": 200000},
                ]
            }
        ),
    )
    models = {m["id"]: m for m in _provider(wire_server).list_models()}
    gpt = models["openai/gpt-4o"]
    assert (gpt["name"], gpt["context_length"], gpt["provider"], gpt["created"]) == ("GPT-4o", 128000, "openrouter", 5)
    assert gpt["supports_temperature"] is True and gpt["supports_tools"] is True
    assert models["openai/o3"]["supports_temperature"] is False


@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (429, {"error": {"message": "rate limited"}}, "RateLimitError"),
        (401, {"error": {"message": "bad key"}}, "AuthenticationError"),
        (
            400,
            {"error": {"message": "maximum context length exceeded", "code": "context_length_exceeded"}},
            "ContextLengthError",
        ),
        (504, {"error": {"message": "upstream timed out"}}, "ProviderError"),
    ],
)
def test_error_mapping_keeps_message_and_status(wire_server, status, body, error):
    wire_server.expect("POST", "/v1/chat/completions", Reply(status, body))
    with pytest.raises(ProviderError) as excinfo:
        _provider(wire_server).chat_completion(MSG, model="a/b")
    assert type(excinfo.value).__name__ == error
    assert body["error"]["message"] in str(excinfo.value)
    if error != "ContextLengthError":
        assert excinfo.value.status_code == status


@pytest.mark.parametrize(("status", "error"), [(401, "AuthenticationError"), (429, "RateLimitError")])
def test_generate_image_http_errors(wire_server, status, error):
    wire_server.expect("POST", "/v1/chat/completions", Reply(status, {"error": {"message": "nope"}}))
    with pytest.raises(ProviderError) as excinfo:
        _provider(wire_server).generate_image("a cat")
    assert type(excinfo.value).__name__ == error


def test_generate_image_defaults_and_custom_model(wire_server):
    url = "data:image/png;base64," + base64.b64encode(b"x").decode()
    body = chat_body("")
    body["choices"][0]["message"]["images"] = [{"type": "image_url", "image_url": {"url": url}}]
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=body), Reply(body=body))
    provider = _provider(wire_server)
    first = provider.generate_image("a cat")
    assert first.model == OpenRouterProvider.DEFAULT_IMAGE_MODEL
    assert wire_server.requests[0].json["messages"] == [{"role": "user", "content": "a cat"}]
    second = provider.generate_image("a cat", model="custom/image-model")
    assert second.model == "custom/image-model" and wire_server.requests[1].json["model"] == "custom/image-model"


def test_generate_image_invalid_url_raises(wire_server):
    body = chat_body("")
    body["choices"][0]["message"]["images"] = [{"type": "image_url", "image_url": {"url": "https://example.com/i.png"}}]
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=body))
    with pytest.raises(ProviderError, match="Unexpected image URL"):
        _provider(wire_server).generate_image("a cat")


def test_close_and_context_manager(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    with _provider(wire_server) as provider:
        provider.chat_completion(MSG, model="a/b")
    assert provider._client is None


def test_error_message_scrubs_secret(wire_server):
    wire_server.expect(
        "POST", "/v1/chat/completions", Reply(500, {"error": {"message": "500 error for key sk-leakedsecret12345"}})
    )
    with pytest.raises(ProviderError) as excinfo:
        _provider(wire_server).chat_completion(MSG, model="a/b")
    assert "sk-leakedsecret12345" not in str(excinfo.value)


def test_factory_returns_openrouter():
    from eq_chatbot_core.providers import get_provider

    assert isinstance(get_provider("openrouter", api_key="k"), OpenRouterProvider)


# --- Fix round 1: non-JSON errors, SSE comments, streaming errors, constraints ---

HTML_504 = "<html><body>504 Gateway Timeout</body></html>"


def test_html_error_body_non_streaming(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(504, raw=HTML_504))
    with pytest.raises(ProviderError) as excinfo:
        _provider(wire_server).chat_completion(MSG, model="a/b")
    assert excinfo.value.status_code == 504
    assert str(excinfo.value).strip()


def test_html_error_body_streaming(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(504, raw=HTML_504))
    with pytest.raises(ProviderError) as excinfo:
        list(_provider(wire_server).stream_completion(MSG, model="a/b"))
    assert excinfo.value.status_code == 504
    assert str(excinfo.value).strip()


def test_streaming_http_error_maps_to_rate_limit(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(429, {"error": {"message": "slow down"}}))
    with pytest.raises(ProviderError) as excinfo:
        list(_provider(wire_server).stream_completion(MSG, model="a/b"))
    assert type(excinfo.value).__name__ == "RateLimitError"
    assert "slow down" in str(excinfo.value) and excinfo.value.status_code == 429


def test_stream_skips_sse_comment_lines(wire_server):
    events = stream_events(["Hel", "lo"], model="a/b")
    mixed = [": OPENROUTER PROCESSING", events[0], ": OPENROUTER PROCESSING", *events[1:]]
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=mixed))
    chunks = list(_provider(wire_server).stream_completion(MSG, model="a/b"))
    assert "".join(c.content for c in chunks if c.content) == "Hello"
    assert any(c.is_final for c in chunks)


@pytest.mark.parametrize("finish", ["stop", "length"])
def test_stream_final_chunk_carries_finish_reason(wire_server, finish):
    events = stream_events(["x"], model="a/b")
    events[-2]["choices"][0]["finish_reason"] = finish
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=events))
    chunks = list(_provider(wire_server).stream_completion(MSG, model="a/b"))
    assert chunks[-1].is_final and chunks[-1].finish_reason == finish


def test_generate_image_jpeg_data_url(wire_server):
    jpeg = b"\xff\xd8\xff\xe0jpegdata"
    url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
    body = chat_body("")
    body["choices"][0]["message"]["images"] = [{"type": "image_url", "image_url": {"url": url}}]
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=body))
    result = _provider(wire_server).generate_image("a cat")
    assert result.mime == "image/jpeg" and result.data == jpeg


def test_model_constraints_regular_reasoning_and_null_parameters(wire_server):
    wire_server.expect(
        "GET",
        "/v1/models",
        Reply(
            body={
                "data": [
                    {
                        "id": "openai/gpt-4o",
                        "supported_parameters": ["temperature", "max_tokens"],
                        "input_modalities": ["text", "image"],
                    },
                    {"id": "openai/o3", "supported_parameters": ["max_tokens"], "input_modalities": ["text"]},
                    {"id": "x/null-params", "supported_parameters": None},
                ]
            }
        ),
    )
    models = {m["id"]: m for m in _provider(wire_server).list_models()}
    regular, reasoning = models["openai/gpt-4o"], models["openai/o3"]
    assert regular["supports_temperature"] is True and regular["supports_vision"] is True
    assert (regular["min_temperature"], regular["max_temperature"]) == (0.0, 2.0)
    assert regular["supports_reasoning"] is False
    assert reasoning["supports_temperature"] is False and reasoning["supports_reasoning"] is True
    assert (reasoning["min_temperature"], reasoning["max_temperature"]) == (1.0, 1.0)
    assert reasoning["default_temperature"] == 1.0
    assert regular["default_temperature"] is not None
    null = models["x/null-params"]
    assert "supports_temperature" in null and "supports_tools" in null


def test_chat_response_fields_and_max_tokens(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("Test response", model="openai/gpt-4o")))
    response = _provider(wire_server).chat_completion(MSG, model="openai/gpt-4o", max_tokens=100)
    assert response.content == "Test response" and response.model == "openai/gpt-4o"
    assert (response.input_tokens, response.output_tokens) == (5, 2)
    assert wire_server.requests[0].json["max_tokens"] == 100


def test_init_stores_key_and_timeout():
    provider = OpenRouterProvider(api_key="sk-or-test", timeout=120.0)
    assert provider.api_key == "sk-or-test" and provider.timeout == 120.0
