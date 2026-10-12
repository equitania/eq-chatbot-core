"""4.2.0: check_model — find out what a model accepts before a chat needs it.

Against the real SDKs and a local HTTP server (``tests/wire_server.py``). The
rejection wordings below are invented on purpose: the point of exploring is
that a wording the library has never seen still leads to the right adjustment.
"""

import pytest

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.base import CHECK_MAX_TOKENS, ProviderError
from eq_chatbot_core.providers.litellm_provider import LiteLLMProvider
from tests.wire_server import Reply, anthropic_stream_events, chat_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]

CHAT = "/v1/chat/completions"
OK = Reply(sse=stream_events(["OK"]))
# Unknown wordings: no rule in param_learning recognises them.
TOOLS_NEED_NO_THINKING = {
    "error": {"message": "Tools cannot be combined with thinking on this model; turn reasoning off.", "code": None}
}
MALFORMED = {"error": {"message": "The request was rejected as malformed.", "type": "invalid_request_error"}}
NO_IMAGES = {"error": {"message": "This model only reads text.", "type": "invalid_request_error"}}
OUTPUT_LIMIT = {
    "error": {
        "message": "max_tokens is too large: 10000000. This model supports at most 16384 completion tokens, "
        "whereas you provided 10000000.",
        "param": "max_tokens",
        "code": "invalid_value",
    }
}


def _provider(wire_server):
    return LiteLLMProvider(api_key="k", base_url=wire_server.base_url, max_retries=0)


def _posts(wire_server):
    return [r.json for r in wire_server.requests if r.method == "POST"]


def test_everything_accepted(wire_server):
    wire_server.expect("POST", CHAT, OK)
    check = _provider(wire_server).check_model("m", probe_limit=False)

    assert (check.text, check.tools, check.vision, check.ok) == ("ok", "ok", "ok", True)
    assert check.adjustments == [] and check.messages == {}
    posts = _posts(wire_server)
    assert len(posts) == 3, "one request per step"
    assert all(p["stream"] is True and p["max_tokens"] == CHECK_MAX_TOKENS for p in posts)
    assert posts[0]["messages"][0]["role"] == "system"
    assert "tools" not in posts[0] and posts[1]["tools"][0]["function"]["name"] == "get_time"
    assert posts[2]["messages"][1]["content"][1]["type"] == "image_url"


def test_small_configured_output_limit_is_kept(wire_server):
    wire_server.expect("POST", CHAT, OK)
    _provider(wire_server).check_model("m", max_tokens=50, tools=False, vision=False, probe_limit=False)
    assert _posts(wire_server)[0]["max_tokens"] == 50


def test_unknown_wording_is_explored_and_remembered(wire_server):
    wire_server.expect("POST", CHAT, OK, Reply(400, TOOLS_NEED_NO_THINKING), Reply(400, TOOLS_NEED_NO_THINKING), OK)
    provider = _provider(wire_server)

    check = provider.check_model("m", vision=False, probe_limit=False)

    assert (check.text, check.tools) == ("ok", "ok")
    assert check.adjustments == ["reasoning_with_tools"]
    posts = _posts(wire_server)
    assert len(posts) == 4, "text, refused, unchanged once more, adjusted"
    assert "reasoning_effort" not in posts[2], "the replay is unchanged"
    assert posts[3]["reasoning_effort"] == "none"

    # A chat afterwards is right the first time (the server keeps answering OK).
    list(provider.stream_completion([{"role": "user", "content": "x"}], model="m", tools=[posts[1]["tools"][0]]))
    assert len(_posts(wire_server)) == 5
    assert _posts(wire_server)[-1]["reasoning_effort"] == "none"


def test_a_rejection_that_does_not_repeat_teaches_nothing(wire_server):
    wire_server.expect("POST", CHAT, OK, Reply(400, MALFORMED), OK)
    check = _provider(wire_server).check_model("m", vision=False, probe_limit=False)
    assert check.tools == "ok"
    assert check.adjustments == []
    assert "temperature" in _posts(wire_server)[-1]


def test_without_a_name_only_harmless_adjustments_are_tried(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, MALFORMED))
    check = _provider(wire_server).check_model("m", probe_limit=False)

    assert check.text == "refused" and not check.ok
    assert (check.tools, check.vision) == ("skipped", "skipped"), "nothing else is tried when text fails"
    assert "malformed" in check.messages["text"]
    posts = _posts(wire_server)
    # refused, unchanged once more, without temperature, without stream usage
    assert len(posts) == 4
    assert not any("max_completion_tokens" in p for p in posts), "renaming the limit needs the name"
    assert "temperature" not in posts[2] and "stream_options" not in posts[3]
    assert check.adjustments == []


def test_a_named_parameter_is_tried_first(wire_server):
    named = {"error": {"message": "Use max_completion_tokens with this model.", "code": None}}
    wire_server.expect("POST", CHAT, Reply(400, named), Reply(400, named), OK)
    check = _provider(wire_server).check_model("m", tools=False, vision=False, probe_limit=False)
    assert check.ok and check.adjustments == ["max_tokens"]
    assert _posts(wire_server)[-1]["max_completion_tokens"] == CHECK_MAX_TOKENS


def test_refused_images_are_reported(wire_server):
    wire_server.expect("POST", CHAT, OK, OK, Reply(400, NO_IMAGES))
    check = _provider(wire_server).check_model("m", probe_limit=False)
    assert (check.text, check.tools, check.vision) == ("ok", "ok", "refused")
    assert "only reads text" in check.messages["vision"]
    assert check.adjustments == []


def test_authentication_error_is_no_verdict_and_stops(wire_server):
    wire_server.expect("POST", CHAT, Reply(401, {"error": {"message": "bad key"}}))
    check = _provider(wire_server).check_model("m")
    assert (check.text, check.tools, check.vision) == ("error", "skipped", "skipped")
    assert len(_posts(wire_server)) == 1


def test_overload_inside_the_stream_is_no_rejection(wire_server):
    overloaded = {"error": {"message": "Upstream overloaded", "code": 502}}
    wire_server.expect("POST", CHAT, Reply(sse=[overloaded]))
    check = _provider(wire_server).check_model("m", probe_limit=False)
    assert check.text == "error"
    assert len(_posts(wire_server)) == 1, "nothing is explored"


def test_refusal_after_an_empty_opening_chunk_is_explored(wire_server):
    empty = {"id": "c", "object": "chat.completion.chunk", "created": 0, "model": "m", "choices": []}
    refusal = Reply(sse=[empty, TOOLS_NEED_NO_THINKING])
    wire_server.expect("POST", CHAT, OK, refusal, refusal, OK)
    check = _provider(wire_server).check_model("m", vision=False, probe_limit=False)
    assert check.tools == "ok" and check.adjustments == ["reasoning_with_tools"]


def test_a_recheck_starts_from_the_plain_request(wire_server):
    wire_server.expect("POST", CHAT, OK)
    provider = _provider(wire_server)
    provider.seed_adjustments("m", ["temperature"])
    assert provider.learned_adjustments("m") == ["temperature"]

    check = provider.check_model("m", tools=False, vision=False, probe_limit=False)

    assert "temperature" in _posts(wire_server)[0], "the old adjustment is forgotten"
    assert check.adjustments == [] and provider.learned_adjustments("m") == []


def test_seeded_adjustments_apply_to_a_chat(wire_server):
    wire_server.expect("POST", CHAT, Reply(body=chat_body()))
    provider = _provider(wire_server)
    provider.seed_adjustments("m", ["temperature", "no-such-adjustment"])
    provider.chat_completion([{"role": "user", "content": "x"}], model="m")
    assert "temperature" not in _posts(wire_server)[0]


def test_a_chat_does_not_explore(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, MALFORMED))
    with pytest.raises(ProviderError):
        _provider(wire_server).chat_completion([{"role": "user", "content": "x"}], model="m")
    assert len(_posts(wire_server)) == 1


def test_the_limit_probe_is_not_explored(wire_server):
    wire_server.expect("POST", CHAT, OK, OK, OK, Reply(400, OUTPUT_LIMIT))
    check = _provider(wire_server).check_model("m")
    assert check.limits == {"max_output_tokens": 16384}
    assert len(_posts(wire_server)) == 4, "three steps and one probe"


def test_is_rejection_follows_the_cause_of_a_provider_error(wire_server):
    wire_server.expect("POST", CHAT, Reply(400, MALFORMED))
    with pytest.raises(ProviderError) as caught:
        _provider(wire_server).chat_completion([{"role": "user", "content": "x"}], model="m")
    assert param_learning.is_rejection(caught.value)
    assert not param_learning.is_rejection(ProviderError("network down", "x"))


# --- Anthropic -----------------------------------------------------------------------


def test_anthropic_check_sends_its_own_image_block(wire_server):
    wire_server.expect("POST", "/v1/messages", Reply(sse=anthropic_stream_events(["OK"])))
    provider = AnthropicProvider(api_key="k", base_url=wire_server.root_url, max_retries=0)
    check = provider.check_model("m", probe_limit=False)
    assert (check.text, check.tools, check.vision) == ("ok", "ok", "ok")
    image = _posts(wire_server)[2]["messages"][0]["content"][1]
    assert image["type"] == "image" and image["source"]["media_type"] == "image/png"
    assert _posts(wire_server)[1]["tools"][0]["name"] == "get_time"


@pytest.mark.parametrize(("backend", "kind"), [("anthropic", "image"), ("openai", "image_url")])
def test_langdock_image_part_follows_the_backend(backend, kind):
    from eq_chatbot_core.providers.langdock_provider import LangDockProvider

    assert LangDockProvider(api_key="k", backend=backend)._check_image_part("AAAA")["type"] == kind
