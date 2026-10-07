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


@dataclass
class Reply:
    status: int = 200
    body: dict[str, Any] | list[Any] | None = None
    sse: list[dict[str, Any]] | None = None  # data payloads; "[DONE]" is appended
    headers: dict[str, str] = field(default_factory=dict)


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
                with server._lock:
                    server.requests.append(
                        Recorded(method, path, json.loads(raw) if raw else None, dict(self.headers.items()))
                    )
                    queue = server._replies.get((method, path), [])
                    reply = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else None)
                if reply is None:
                    reply = Reply(404, {"error": {"message": f"no reply queued for {method} {path}"}})
                self.send_response(reply.status)
                for name, value in reply.headers.items():
                    self.send_header(name, value)
                if reply.sse is not None:
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for event in reply.sse:
                        self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    return
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
