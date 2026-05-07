"""Unit tests for StreamChunk → SSE event translation."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")  # skip whole module if [server] extras missing

from eq_chatbot_core.providers.base import StreamChunk  # noqa: E402
from eq_chatbot_core.server.streaming import stream_chunk_to_sse_events  # noqa: E402


@pytest.mark.unit
class TestStreamChunkToSseEvents:
    def test_content_only_chunk_emits_chunk_event(self) -> None:
        chunks = [StreamChunk(content="Hello")]
        events = list(stream_chunk_to_sse_events(iter(chunks)))

        assert events == [{"event": "chunk", "data": json.dumps({"content": "Hello"})}]

    def test_empty_content_is_skipped(self) -> None:
        # Some providers emit empty deltas (e.g. role-only first chunk in OpenAI).
        chunks = [StreamChunk(content="")]
        events = list(stream_chunk_to_sse_events(iter(chunks)))

        assert events == []

    def test_final_chunk_emits_done_with_finish_reason(self) -> None:
        chunks = [
            StreamChunk(content="Hi", is_final=False),
            StreamChunk(content="", is_final=True, finish_reason="stop"),
        ]
        events = list(stream_chunk_to_sse_events(iter(chunks)))

        assert events[0] == {"event": "chunk", "data": json.dumps({"content": "Hi"})}
        assert events[-1] == {"event": "done", "data": json.dumps({"finish_reason": "stop"})}

    def test_final_chunk_with_usage_emits_usage_event(self) -> None:
        chunks = [
            StreamChunk(
                content="",
                is_final=True,
                finish_reason="stop",
                input_tokens=5,
                output_tokens=10,
            )
        ]
        events = list(stream_chunk_to_sse_events(iter(chunks)))

        # Order: usage before done
        assert events[0]["event"] == "usage"
        assert json.loads(events[0]["data"]) == {"input_tokens": 5, "output_tokens": 10}
        assert events[-1]["event"] == "done"

    def test_zero_token_usage_does_not_emit_usage_event(self) -> None:
        # Some providers don't return usage in stream mode.
        chunks = [StreamChunk(content="", is_final=True, finish_reason="stop")]
        events = list(stream_chunk_to_sse_events(iter(chunks)))

        assert all(e["event"] != "usage" for e in events)

    def test_tool_call_delta_passes_through(self) -> None:
        delta = {"index": 0, "id": "call_1", "function": {"name": "get_weather"}}
        chunks = [StreamChunk(content="", tool_call_delta=delta)]
        events = list(stream_chunk_to_sse_events(iter(chunks)))

        assert events == [{"event": "tool_call_delta", "data": json.dumps(delta)}]

    def test_final_chunk_with_tool_calls_emits_tool_calls_event(self) -> None:
        tool_calls = [{"id": "call_1", "type": "function", "function": {"name": "f", "arguments": "{}"}}]
        chunks = [
            StreamChunk(
                content="",
                is_final=True,
                finish_reason="tool_calls",
                tool_calls=tool_calls,
            )
        ]
        events = list(stream_chunk_to_sse_events(iter(chunks)))

        types = [e["event"] for e in events]
        assert "tool_calls" in types
        # done is always last
        assert types[-1] == "done"
        tc_event = next(e for e in events if e["event"] == "tool_calls")
        assert json.loads(tc_event["data"]) == {"tool_calls": tool_calls}

    def test_full_stream_event_order(self) -> None:
        """Mixed stream: content + tool delta, then final with usage + tool_calls."""
        tool_calls = [{"id": "call_1", "type": "function", "function": {"name": "f"}}]
        chunks = [
            StreamChunk(content="Going to call "),
            StreamChunk(content="a tool"),
            StreamChunk(content="", tool_call_delta={"index": 0, "id": "call_1"}),
            StreamChunk(
                content="",
                is_final=True,
                finish_reason="tool_calls",
                input_tokens=20,
                output_tokens=5,
                tool_calls=tool_calls,
            ),
        ]
        events = list(stream_chunk_to_sse_events(iter(chunks)))
        types = [e["event"] for e in events]

        # Content events come before final marker
        assert types[:2] == ["chunk", "chunk"]
        assert "tool_call_delta" in types
        # Final group order: usage, tool_calls, done
        final = types[-3:]
        assert final == ["usage", "tool_calls", "done"]
