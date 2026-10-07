"""A real HTTP server speaking the OpenAI Chat Completions wire protocol.

Tests point a provider's ``base_url`` at it so that the real ``openai`` SDK,
the pinned transport and the real error mapping run end to end. Only the
remote provider is simulated; no library code is patched.

Replies are queued per (method, path). The last queued reply repeats, so a
test that only cares about one answer queues it once.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# Recorded verbatim from api.openai.com on 07.10.2026 (gpt-5.6-luna).
OPENAI_TEMPERATURE_REJECTION: dict[str, Any] = {
    "error": {
        "message": "Unsupported value: 'temperature' does not support 0.7 with this model. "
        "Only the default (1) value is supported.",
        "type": "invalid_request_error",
        "param": "temperature",
        "code": "unsupported_value",
    }
}
OPENAI_MAX_TOKENS_REJECTION: dict[str, Any] = {
    "error": {
        "message": "Unsupported parameter: 'max_tokens' is not supported with this model. "
        "Use 'max_completion_tokens' instead.",
        "type": "invalid_request_error",
        "param": "max_tokens",
        "code": "unsupported_parameter",
    }
}
# Shape of gateways that relay the message but drop the structured field.
GATEWAY_TEMPERATURE_REJECTION_NO_PARAM: dict[str, Any] = {
    "error": {"message": "Upstream error: 'temperature' is not supported for this model", "code": 400}
}

# Same envelope as OPENAI_MAX_TOKENS_REJECTION; modelled on it, not recorded.
OPENAI_REASONING_EFFORT_REJECTION: dict[str, Any] = {
    "error": {
        "message": "Unsupported parameter: 'reasoning_effort' is not supported with this model.",
        "type": "invalid_request_error",
        "param": "reasoning_effort",
        "code": "unsupported_parameter",
    }
}
# Anthropic Messages API, 07.10.2026: message text recorded live (temperature=0.7
# via extra_body on a Claude 5 model); envelope as Anthropic documents its errors.
ANTHROPIC_TEMPERATURE_DEPRECATED: dict[str, Any] = {
    "type": "error",
    "error": {"type": "invalid_request_error", "message": "`temperature` is deprecated for this model."},
}
# Anthropic, 07.10.2026 (temperature=1.5): out of range — must not be learned as unsupported.
ANTHROPIC_TEMPERATURE_RANGE: dict[str, Any] = {
    "type": "error",
    "error": {"type": "invalid_request_error", "message": "temperature: range: 0..1"},
}


@dataclass
class Reply:
    status: int = 200
    body: dict[str, Any] | list[Any] | None = None
    # data payloads (dict -> "data: <json>"); a str is written verbatim, e.g. an SSE comment.
    # "[DONE]" is appended.
    sse: list[dict[str, Any] | str] | None = None
    raw: str | bytes | None = None  # sent verbatim; Content-Type from headers, default text/html
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0  # seconds to wait before answering (timeout tests)


@dataclass
class Recorded:
    method: str
    path: str
    json: Any
    headers: dict[str, str]


def chat_body(
    content: str = "ok",
    *,
    model: str = "test-model",
    tool_calls: list[dict[str, Any]] | None = None,
    finish_reason: str = "stop",
    prompt_tokens: int = 5,
    completion_tokens: int = 2,
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def stream_events(
    pieces: list[str], *, model: str = "test-model", prompt_tokens: int = 5, completion_tokens: int = 2
) -> list[dict[str, Any]]:
    """Content deltas, a finish chunk, then a usage-only chunk (as OpenAI sends them)."""
    base = {"id": "chatcmpl-test", "object": "chat.completion.chunk", "created": 0, "model": model}
    events = [{**base, "choices": [{"index": 0, "delta": {"content": p}, "finish_reason": None}]} for p in pieces]
    events.append({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
    events.append(
        {
            **base,
            "choices": [],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
    )
    return events


def models_body(ids: list[str]) -> dict[str, Any]:
    return {"object": "list", "data": [{"id": i, "object": "model", "created": 0, "owned_by": "test"} for i in ids]}


class WireServer:
    def __init__(self) -> None:
        self.requests: list[Recorded] = []
        self._replies: dict[tuple[str, str], list[Reply]] = {}
        self._lock = threading.Lock()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:  # keep test output clean
                pass

            def _handle(self, method: str) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                path = self.path.split("?", 1)[0]
                try:
                    payload = json.loads(raw) if raw else None
                except ValueError:  # e.g. multipart upload (audio transcription)
                    payload = None
                with server._lock:
                    server.requests.append(Recorded(method, path, payload, dict(self.headers.items())))
                    queue = server._replies.get((method, path), [])
                    reply = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else None)
                if reply is None:
                    reply = Reply(404, {"error": {"message": f"no reply queued for {method} {path}"}})
                if reply.delay:
                    time.sleep(reply.delay)
                try:
                    self._respond(reply)
                except (BrokenPipeError, ConnectionResetError):  # client timed out and left
                    pass

            def _respond(self, reply: Reply) -> None:
                self.send_response(reply.status)
                for name, value in reply.headers.items():
                    self.send_header(name, value)
                if reply.sse is not None:
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for event in reply.sse:
                        line = event if isinstance(event, str) else f"data: {json.dumps(event)}"
                        self.wfile.write(f"{line}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    return
                if reply.raw is not None:
                    payload = reply.raw.encode() if isinstance(reply.raw, str) else reply.raw
                    if not any(n.lower() == "content-type" for n in reply.headers):
                        self.send_header("Content-Type", "text/html")
                else:
                    payload = json.dumps(reply.body if reply.body is not None else {}).encode()
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self) -> None:
                self._handle("GET")

            def do_POST(self) -> None:
                self._handle("POST")

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    @property
    def root_url(self) -> str:
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    @property
    def base_url(self) -> str:
        return f"{self.root_url}/v1"

    def expect(self, method: str, path: str, *replies: Reply) -> None:
        with self._lock:
            self._replies.setdefault((method, path), []).extend(replies)

    def start(self) -> WireServer:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def anthropic_message_body(
    text: str = "ok", *, model: str = "test-model", input_tokens: int = 5, output_tokens: int = 2
) -> dict[str, Any]:
    """A Messages API response (POST /v1/messages)."""
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


def anthropic_stream_events(
    pieces: list[str], *, model: str = "test-model", input_tokens: int = 5, output_tokens: int = 2
) -> list[str]:
    """Messages API SSE frames (``event:`` + ``data:`` lines) for a text answer.

    The server appends ``data: [DONE]``; the anthropic SDK ignores that unnamed event.
    """

    def frame(kind: str, data: dict[str, Any]) -> str:
        return f"event: {kind}\ndata: {json.dumps({'type': kind, **data})}"

    message = {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": {"input_tokens": input_tokens, "output_tokens": 0},
    }
    events = [
        frame("message_start", {"message": message}),
        frame("content_block_start", {"index": 0, "content_block": {"type": "text", "text": ""}}),
    ]
    events += [frame("content_block_delta", {"index": 0, "delta": {"type": "text_delta", "text": p}}) for p in pieces]
    events += [
        frame("content_block_stop", {"index": 0}),
        frame(
            "message_delta",
            {"delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": output_tokens}},
        ),
        frame("message_stop", {}),
    ]
    return events


def anthropic_models_body(models: list[dict[str, Any]]) -> dict[str, Any]:
    """A Models API page (GET /v1/models); each entry needs at least ``id``."""
    data = [{"type": "model", "display_name": m["id"], "created_at": "2026-01-01T00:00:00Z", **m} for m in models]
    return {
        "data": data,
        "has_more": False,
        "first_id": data[0]["id"] if data else None,
        "last_id": data[-1]["id"] if data else None,
    }


def embeddings_body(vectors: list[list[float]], *, model: str = "test-model") -> dict[str, Any]:
    """An embeddings response (POST /v1/embeddings) with float vectors."""
    return {
        "object": "list",
        "model": model,
        "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vectors)],
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }
