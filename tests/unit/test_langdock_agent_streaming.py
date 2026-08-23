"""LangDock Agent streaming over the AI SDK 5 data-stream protocol.

Until 23.08.2026 `_agent_stream_completion` sent `"stream": False` and yielded the
whole answer as one final chunk — it never streamed at all, and LangDock aborts a
non-streaming request with HTTP 524 after 100 seconds, which an agent with tools
or knowledge search reaches easily.

The event shapes below are a verbatim capture from
POST https://api.langdock.com/agent/v1/chat/completions with stream:true.
Note the last two events: LangDock does not always put a blank line between
`data:` blocks, so a parser that splits on blank lines loses text.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.langdock_provider import _iter_sse_data

pytestmark = pytest.mark.unit

MSG = "msg_07f60f20a7cd721a016a8b1bbb181c81a4bab45e4e0ed9ef02"

CAPTURED_LINES = [
    'data: {"type":"data-conversation-id","data":null}',
    "",
    'data: {"type":"start","messageId":"5f56521c","messageMetadata":{"modelName":"GPT-5.6 Luna"}}',
    "",
    'data: {"type":"start-step"}',
    "",
    'data: {"type":"reasoning-start","id":"rs_07f6:0"}',
    "",
    'data: {"type":"reasoning-end","id":"rs_07f6:0"}',
    "",
    f'data: {{"type":"text-start","id":"{MSG}"}}',
    "",
    f'data: {{"type":"text-delta","id":"{MSG}","delta":"1"}}',
    "",
    f'data: {{"type":"text-delta","id":"{MSG}","delta":" \\u2026"}}',
    "",
    # Two events in one line, no blank separator — as captured.
    f'data: {{"type":"text-delta","id":"{MSG}","delta":"  \\n"}}data: {{"type":"text-delta","id":"{MSG}","delta":"2"}}',
    "",
    f'data: {{"type":"text-end","id":"{MSG}"}}',
    "",
    'data: {"type":"finish-step"}',
    "",
    'data: {"type":"finish"}',
    "",
    "data: [DONE]",
]


def _provider():
    with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
        from eq_chatbot_core.providers.langdock_provider import LangDockProvider

        return LangDockProvider(api_key="test-key", backend="agent", agent_id="ag-1")


def _with_stream(provider, lines, status=200, error_body=""):
    """Attach an http_client whose .stream() replays `lines`."""
    response = MagicMock()
    response.status_code = status
    response.iter_lines.return_value = iter(lines)
    response.text = error_body
    response.read.return_value = error_body.encode()

    ctx = MagicMock()
    ctx.__enter__.return_value = response
    ctx.__exit__.return_value = False

    client = MagicMock()
    client.stream.return_value = ctx
    provider._http_client = client
    return client, response


class TestSSEParsing:
    def test_yields_one_object_per_event(self):
        events = list(_iter_sse_data(CAPTURED_LINES))

        assert [e["type"] for e in events][:3] == ["data-conversation-id", "start", "start-step"]

    def test_glued_events_are_both_recovered(self):
        deltas = [e["delta"] for e in _iter_sse_data(CAPTURED_LINES) if e["type"] == "text-delta"]

        assert deltas == ["1", " …", "  \n", "2"]

    def test_done_sentinel_is_not_emitted(self):
        assert all(isinstance(e, dict) for e in _iter_sse_data(CAPTURED_LINES))

    def test_malformed_json_is_skipped_not_raised(self):
        events = list(_iter_sse_data(['data: {"type":"start"}', "data: {broken", 'data: {"type":"finish"}']))

        assert [e["type"] for e in events] == ["start", "finish"]


class TestAgentStreamCompletion:
    def test_request_actually_asks_for_a_stream(self):
        provider = _provider()
        client, _ = _with_stream(provider, CAPTURED_LINES)

        list(provider.stream_completion([{"role": "user", "content": "hi"}]))

        payload = client.stream.call_args.kwargs["json"]
        assert payload["stream"] is True, "the whole point: without this LangDock buffers and 524s"
        assert payload["agentId"] == "ag-1"

    def test_text_arrives_incrementally(self):
        provider = _provider()
        _with_stream(provider, CAPTURED_LINES)

        chunks = list(provider.stream_completion([{"role": "user", "content": "hi"}]))
        contentful = [c for c in chunks if c.content]

        assert len(contentful) > 1, "a single chunk means it is still not streaming"
        assert "".join(c.content for c in contentful) == "1 …  \n2"

    def test_last_chunk_is_final(self):
        provider = _provider()
        _with_stream(provider, CAPTURED_LINES)

        chunks = list(provider.stream_completion([{"role": "user", "content": "hi"}]))

        assert chunks[-1].is_final is True
        assert chunks[-1].finish_reason == "stop"
        assert sum(1 for c in chunks if c.is_final) == 1

    def test_reasoning_events_do_not_leak_into_content(self):
        provider = _provider()
        _with_stream(provider, CAPTURED_LINES)

        text = "".join(c.content or "" for c in provider.stream_completion([{"role": "user", "content": "hi"}]))

        assert "rs_07f6" not in text

    def test_error_event_raises_with_its_text(self):
        provider = _provider()
        _with_stream(
            provider,
            ['data: {"type":"start"}', 'data: {"type":"error","errorText":"agent exploded"}'],
        )

        with pytest.raises(ProviderError, match="agent exploded"):
            list(provider.stream_completion([{"role": "user", "content": "hi"}]))

    def test_http_error_is_translated_not_swallowed(self):
        provider = _provider()
        _with_stream(
            provider,
            [],
            status=400,
            error_body=json.dumps(
                {
                    "message": "INVALID REQUEST: No valid model in the request, and no default model set for this workspace."
                }
            ),
        )

        with pytest.raises(ProviderError) as exc:
            list(provider.stream_completion([{"role": "user", "content": "hi"}]))

        assert exc.value.status_code == 400
        assert "festes Modell" in str(exc.value)

    def test_error_body_is_read_before_access(self):
        """A streamed response must be read() first or httpx2 raises ResponseNotRead."""
        provider = _provider()
        _, response = _with_stream(provider, [], status=400, error_body='{"message":"nope"}')

        with pytest.raises(ProviderError):
            list(provider.stream_completion([{"role": "user", "content": "hi"}]))

        response.read.assert_called_once()


class TestAgentChatCompletionStreamsInternally:
    """The synchronous path streams too, and assembles the answer itself.

    LangDock aborts a non-streaming request with HTTP 524 after 100 seconds. An
    agent that runs tools or searches a knowledge base reaches that easily, so
    `stream: false` was a timeout waiting to happen even for callers that only
    want the finished text.
    """

    def test_request_asks_for_a_stream(self):
        provider = _provider()
        client, _ = _with_stream(provider, CAPTURED_LINES)

        provider.chat_completion([{"role": "user", "content": "hi"}])

        assert client.stream.call_args.kwargs["json"]["stream"] is True
        assert not client.post.called, "the synchronous path must not fall back to a buffered POST"

    def test_deltas_are_assembled_into_one_answer(self):
        provider = _provider()
        _with_stream(provider, CAPTURED_LINES)

        response = provider.chat_completion([{"role": "user", "content": "hi"}])

        assert response.content == "1 …  \n2"
        assert response.finish_reason == "stop"

    def test_model_name_comes_from_the_start_event(self):
        provider = _provider()
        _with_stream(provider, CAPTURED_LINES)

        response = provider.chat_completion([{"role": "user", "content": "hi"}])

        assert response.model == "GPT-5.6 Luna"

    def test_model_falls_back_to_the_agent_id(self):
        provider = _provider()
        _with_stream(provider, ['data: {"type":"text-delta","id":"m","delta":"x"}'])

        assert provider.chat_completion([{"role": "user", "content": "hi"}]).model == "agent:ag-1"

    def test_http_error_is_translated(self):
        provider = _provider()
        _with_stream(
            provider,
            [],
            status=400,
            error_body='{"message":"INVALID REQUEST: No valid model in the request, and no default model set for this workspace."}',
        )

        with pytest.raises(ProviderError) as exc:
            provider.chat_completion([{"role": "user", "content": "hi"}])

        assert exc.value.status_code == 400
        assert "festes Modell" in str(exc.value)

    def test_error_event_raises(self):
        provider = _provider()
        _with_stream(provider, ['data: {"type":"error","errorText":"tool blew up"}'])

        with pytest.raises(ProviderError, match="tool blew up"):
            provider.chat_completion([{"role": "user", "content": "hi"}])

    def test_empty_message_list_never_reaches_the_network(self):
        provider = _provider()
        client, _ = _with_stream(provider, CAPTURED_LINES)

        response = provider.chat_completion([{"role": "system", "content": "only instructions"}])

        assert response.finish_reason == "error"
        assert not client.stream.called
