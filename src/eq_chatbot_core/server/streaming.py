"""Translate :class:`StreamChunk` iterators into Server-Sent Events.

The provider abstraction yields :class:`~eq_chatbot_core.providers.base.StreamChunk`
objects with content deltas, tool-call deltas, and a final chunk carrying usage
data. The HTTP layer needs to surface that on the wire as SSE so a JavaScript
or .NET ``HttpClient`` consumer can show tokens in real-time.

We use a typed event stream (``event: <name>``) instead of a single
``data: ...`` channel so consumers can dispatch on event type without parsing
each payload to figure out which kind of update it is.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from eq_chatbot_core.providers.base import StreamChunk


def stream_chunk_to_sse_events(chunks: Iterator[StreamChunk]) -> Iterator[dict[str, Any]]:
    """Yield SSE-Starlette compatible event dicts from a StreamChunk iterator.

    Each yielded dict has the shape ``{"event": str, "data": str}``. The
    ``data`` payload is always a compact JSON string. ``sse-starlette``'s
    ``EventSourceResponse`` serializes these to the wire format::

        event: chunk
        data: {"content": "Hello"}

        event: done
        data: {"finish_reason": "stop"}

    Events emitted (in order during a typical stream):

    * ``chunk`` — ``{"content": str}`` per content delta
    * ``tool_call_delta`` — partial tool-call data (per provider stream)
    * ``usage`` — ``{"input_tokens": int, "output_tokens": int}`` on final
    * ``tool_calls`` — ``{"tool_calls": [...]}`` on final, only if tool calls were made
    * ``done`` — ``{"finish_reason": str | null}`` always last
    """
    for chunk in chunks:
        if chunk.content:
            yield {"event": "chunk", "data": json.dumps({"content": chunk.content})}

        if chunk.tool_call_delta:
            yield {"event": "tool_call_delta", "data": json.dumps(chunk.tool_call_delta)}

        if chunk.is_final:
            if chunk.input_tokens or chunk.output_tokens:
                yield {
                    "event": "usage",
                    "data": json.dumps(
                        {
                            "input_tokens": chunk.input_tokens,
                            "output_tokens": chunk.output_tokens,
                        }
                    ),
                }

            if chunk.tool_calls:
                yield {
                    "event": "tool_calls",
                    "data": json.dumps({"tool_calls": chunk.tool_calls}),
                }

            yield {
                "event": "done",
                "data": json.dumps({"finish_reason": chunk.finish_reason}),
            }
