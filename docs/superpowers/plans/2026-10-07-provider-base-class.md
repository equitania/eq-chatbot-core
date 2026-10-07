# Provider consolidation on `OpenAICompatibleProvider` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Mammouth, Local, OpenAI, OpenRouter and LangDock's `openai` backend onto `OpenAICompatibleProvider`, and teach that base class to learn at runtime whether a model accepts `temperature` and `max_tokens`.

**Architecture:** A small process-wide module (`providers/param_learning.py`) recognises "parameter X unsupported" 400s and remembers them per `(endpoint, model)`. `OpenAICompatibleProvider` uses it around every `chat.completions.create()` call, maps errors by HTTP status, and offers two extension hooks. Each provider then shrinks to a subclass (LangDock: an internal delegate) that keeps its public surface. CI tests run against a real local HTTP server speaking the OpenAI wire protocol; live tests hit the real providers.

**Tech Stack:** Python ≥ 3.12, `openai` SDK 3.26 on `httpx2` 2.13, pytest 9, stdlib `http.server`, uv.

**Spec:** `docs/superpowers/specs/2026-10-07-provider-base-class-design.md`

## Global Constraints

- Public API unchanged: class names, constructor signatures and defaults, extra public methods, UPPER_CASE class constants and their values, `list_models()` key sets. Checked by the compatibility snapshot from Task 1.
- Model IDs and name lists stay in source in this stage (removal is stage 2). New code adds no model IDs to `src/`; tests take models from `tests/model_registry.py`.
- Every outbound HTTP client goes through `build_pinned_transport_for_url` (via the base class `client`).
- No mocking of library code in new tests. The only stand-in is the local wire server, which replaces the remote provider.
- Deleting an existing test file or test function requires the Captain's explicit "ja" first — list them, wait, then delete.
- Coverage gate `fail_under = 83` (pyproject) must hold after every task: `uv run pytest tests/unit/ -q --cov=eq_chatbot_core`.
- `ruff check src/ tests/`, `ruff format --check src/ tests/` and `mypy src/` clean after every task.
- Commit per task, prefix `[ADD]`/`[CHG]`/`[FIX]`, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No push.
- The repo mirrors to GitHub: no customer names, hostnames or keys in code, tests or commit messages.
- Shell snippets the Captain types are Fish syntax; commands run by the agent may be POSIX.

## Review Focus

1. **A 200 response whose body carries `{"error": ...}` instead of `choices`** (LM Studio/Ollama on context overflow) — must raise a typed `ProviderError`, not `TypeError: 'NoneType' object is not subscriptable`. Pinned in Task 3 (`test_error_in_200_body_raises_typed_error`) and Task 5 (local maps it to `ContextLengthError`).
2. **An error event in the middle of a stream** — the caller must get a `ProviderError` with the provider's message, after the chunks already yielded, and no retry. Pinned in Task 3 (`test_stream_error_event_mid_stream`).
3. **A model that rejects both `temperature` and `max_tokens`** — first call must still succeed with two retries, second call with none. Pinned in Task 3 (`test_both_parameters_rejected_learned_in_one_call`).
4. **Two provider instances for the same endpoint** (Odoo builds one per request) — the second instance must not repeat the failed first request. Pinned in Task 3 (`test_learning_shared_across_instances`).
5. **A 400 that mentions `temperature` but is about something else** (e.g. "temperature must be ≤ 1") — must propagate, not trigger a retry that silently drops the user's setting. Pinned in Task 2 (`test_range_error_is_not_a_rejection`).

---

## File Structure

| File | Responsibility |
|---|---|
| `src/eq_chatbot_core/providers/param_learning.py` (new) | Recognise unsupported-parameter 400s, adjust params, process-wide memory |
| `src/eq_chatbot_core/providers/openai_compatible.py` | Wire protocol, learning retry, status-based error mapping, hooks |
| `src/eq_chatbot_core/providers/{mammouth,local,openai,openrouter}_provider.py` | Subclasses keeping only provider-specific behaviour |
| `src/eq_chatbot_core/providers/langdock_provider.py` | `backend="openai"` delegates to `_LangDockOpenAIBackend` |
| `tests/wire_server.py` (new) | Local OpenAI-wire HTTP server + reply builders + recorded provider error bodies |
| `tests/compat/public_api.json` (new) | Public-surface snapshot taken before any change |
| `tests/compat/snapshot.py` (new) | Builds the snapshot by introspection (script + importable function) |
| `tests/unit/test_public_api_compat.py` (new) | Compares the live surface to the snapshot |
| `tests/unit/test_param_learning.py` (new) | Recognition and memory |
| `tests/unit/test_openai_compatible_wire.py` (new) | Base class against the wire server |
| `tests/unit/test_<provider>_wire.py` (new, one per provider) | Provider-specific behaviour against the wire server |
| `tests/integration/test_*_live.py` | Live checks per migrated provider |

---

### Task 1: Wire server and public-API snapshot

**Files:**
- Create: `tests/wire_server.py`
- Create: `tests/compat/__init__.py` (empty), `tests/compat/snapshot.py`, `tests/compat/public_api.json`
- Create: `tests/unit/test_public_api_compat.py`
- Modify: `tests/conftest.py` (append two fixtures)

**Interfaces:**
- Produces: `tests.wire_server.WireServer` with `.base_url: str` (`http://127.0.0.1:<port>/v1`), `.root_url: str` (`http://127.0.0.1:<port>`), `.expect(method: str, path: str, *replies: Reply) -> None`, `.requests: list[Recorded]`; `Reply(status=200, body=None, sse=None, headers={})`; `Recorded(method, path, json, headers)`; builders `chat_body(...)`, `stream_events(...)`, `models_body(ids)`; constants `OPENAI_TEMPERATURE_REJECTION`, `OPENAI_MAX_TOKENS_REJECTION`, `GATEWAY_TEMPERATURE_REJECTION_NO_PARAM`.
- Produces: fixtures `wire_server` (function-scoped, started and stopped) and `clean_param_memory` (autouse in wire tests, added in Task 2).
- Produces: `tests.compat.snapshot.public_surface() -> dict[str, Any]`.

- [ ] **Step 1: Write the wire server**

```python
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
```

- [ ] **Step 2: Add the fixture to `tests/conftest.py` (append at end)**

```python
@pytest.fixture
def wire_server():
    """A local OpenAI-wire HTTP server; see tests/wire_server.py."""
    from tests.wire_server import WireServer

    server = WireServer().start()
    yield server
    server.stop()
```

- [ ] **Step 3: Write the snapshot builder `tests/compat/snapshot.py`**

```python
"""Introspect the public provider surface that consumers (Odoo, CLI, server) rely on.

Run as a script to (re)write tests/compat/public_api.json — only ever before a
deliberate, reviewed API change:  uv run python -m tests.compat.snapshot
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

SNAPSHOT_PATH = Path(__file__).with_name("public_api.json")

CLASSES = [
    ("eq_chatbot_core.providers.openai_provider", "OpenAIProvider"),
    ("eq_chatbot_core.providers.mammouth_provider", "MammouthProvider"),
    ("eq_chatbot_core.providers.openrouter_provider", "OpenRouterProvider"),
    ("eq_chatbot_core.providers.local_provider", "LocalLLMProvider"),
    ("eq_chatbot_core.providers.langdock_provider", "LangDockProvider"),
    ("eq_chatbot_core.providers.langdock_provider", "LangDockAgentManager"),
    ("eq_chatbot_core.providers.langdock_provider", "LangDockKnowledgeManager"),
    ("eq_chatbot_core.providers.ionos_provider", "IonosProvider"),
    ("eq_chatbot_core.providers.melious_provider", "MeliousProvider"),
    ("eq_chatbot_core.providers.litellm_provider", "LiteLLMProvider"),
    ("eq_chatbot_core.providers.privatemode_provider", "PrivatemodeProvider"),
]


def _describe(cls: type) -> dict[str, Any]:
    methods = {}
    for name, member in inspect.getmembers(cls):
        if name.startswith("_") and name != "__init__":
            continue
        if inspect.isfunction(member):
            methods[name] = str(inspect.signature(member))
        elif isinstance(inspect.getattr_static(cls, name), property):
            methods[name] = "property"
    constants = {
        name: repr(value)
        for name, value in vars_all(cls).items()
        if name.isupper() and not callable(value)
    }
    return {"members": methods, "constants": constants}


def vars_all(cls: type) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for klass in reversed(cls.__mro__):
        merged.update(vars(klass))
    return merged


def public_surface() -> dict[str, Any]:
    import importlib

    import eq_chatbot_core.providers as providers

    surface: dict[str, Any] = {"providers.__all__": sorted(providers.__all__)}
    for module_name, class_name in CLASSES:
        cls = getattr(importlib.import_module(module_name), class_name)
        surface[class_name] = _describe(cls)
    return surface


if __name__ == "__main__":
    SNAPSHOT_PATH.write_text(json.dumps(public_surface(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {SNAPSHOT_PATH}")
```

- [ ] **Step 4: Take the snapshot from the unchanged code**

Run: `uv run python -m tests.compat.snapshot && git diff --stat`
Expected: `wrote .../tests/compat/public_api.json`; only new files appear in `git status`. Open the JSON and check that `MammouthProvider.constants` contains `MODELS_URL` and `REASONING_MODEL_PREFIXES`, and `OpenRouterProvider.members.__init__` shows `site_url` and `site_name`.

- [ ] **Step 5: Write the compatibility test `tests/unit/test_public_api_compat.py`**

```python
"""The public provider surface must match the snapshot taken before the base-class migration.

A failure here means a consumer (Odoo module, CLI, server mode) may break. Fix the
code, not the snapshot — regenerating it is a reviewed API change.
"""

import json

import pytest

from tests.compat.snapshot import SNAPSHOT_PATH, public_surface

pytestmark = pytest.mark.unit

# `client` changes type (httpx2.Client -> openai.OpenAI) for providers moving off
# hand-written HTTP; it is an implementation detail, documented in the release notes.
_ALLOWED_DRIFT = {"client"}


def _strip(surface: dict) -> dict:
    return {
        cls: {
            "members": {k: v for k, v in body["members"].items() if k not in _ALLOWED_DRIFT},
            "constants": body["constants"],
        }
        if isinstance(body, dict)
        else body
        for cls, body in surface.items()
    }


def test_public_surface_unchanged():
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    actual = public_surface()
    for cls, body in _strip(expected).items():
        if not isinstance(body, dict):
            assert actual[cls] == body, cls
            continue
        live = _strip(actual)[cls]
        missing = set(body["members"]) - set(live["members"])
        assert not missing, f"{cls} lost public members: {sorted(missing)}"
        changed = {k for k in body["members"] if live["members"][k] != body["members"][k]}
        assert not changed, f"{cls} changed signatures: {sorted(changed)}"
        lost_or_changed = {k for k, v in body["constants"].items() if live["constants"].get(k) != v}
        assert not lost_or_changed, f"{cls} constants lost or changed: {sorted(lost_or_changed)}"
```

Note: members and constants *added* are allowed (new hooks and inherited `PROVIDER_NAME`, `DEFAULT_MODEL` etc. are fine); removed or changed ones are not.

- [ ] **Step 6: Write a smoke test for the wire server itself and run both**

Append to `tests/unit/test_public_api_compat.py`:

```python
def test_wire_server_serves_a_chat_completion(wire_server):
    from openai import OpenAI

    from tests.wire_server import Reply, chat_body

    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("hallo")))
    client = OpenAI(api_key="k", base_url=wire_server.base_url, max_retries=0)
    reply = client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
    assert reply.choices[0].message.content == "hallo"
    assert wire_server.requests[0].json["model"] == "m"
```

Run: `uv run pytest tests/unit/test_public_api_compat.py -q -p no:cacheprovider`
Expected: 2 passed.

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git add tests/wire_server.py tests/compat tests/unit/test_public_api_compat.py tests/conftest.py
git commit -m "[ADD] Tests: OpenAI-Wire-Testserver und Momentaufnahme der öffentlichen Provider-Schnittstelle

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `param_learning` module

**Files:**
- Create: `src/eq_chatbot_core/providers/param_learning.py`
- Create: `tests/unit/test_param_learning.py`
- Modify: `tests/conftest.py` (append `clean_param_memory` fixture)

**Interfaces:**
- Produces (module `eq_chatbot_core.providers.param_learning`):
  - `LEARNABLE: tuple[str, ...] = ("temperature", "max_tokens")`
  - `rejected_parameter(error: BaseException) -> str | None`
  - `adjust(params: dict[str, Any], parameter: str) -> bool`
  - `apply(base_url: str, model: str, params: dict[str, Any]) -> None`
  - `mark_unsupported(base_url: str, model: str, parameter: str) -> None`
  - `seed_temperature_support(base_url: str, model: str, supported: bool) -> None`
  - `clear() -> None`

- [ ] **Step 1: Add the fixture to `tests/conftest.py` (append)**

```python
@pytest.fixture
def clean_param_memory():
    """Forget learned parameter support before and after a test."""
    from eq_chatbot_core.providers import param_learning

    param_learning.clear()
    yield
    param_learning.clear()
```

- [ ] **Step 2: Write the failing tests**

Recognition runs against real `openai` exception objects produced by the real SDK talking to the wire server — the same objects production code sees.

```python
"""Recognition of unsupported-parameter rejections and the process-wide memory."""

import pytest
from openai import OpenAI

from eq_chatbot_core.providers import param_learning
from tests.wire_server import (
    GATEWAY_TEMPERATURE_REJECTION_NO_PARAM,
    OPENAI_MAX_TOKENS_REJECTION,
    OPENAI_TEMPERATURE_REJECTION,
    Reply,
)

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]


def _error_for(wire_server, status, body):
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
    body = {"error": {"message": "Unsupported parameter: 'logprobs'", "param": "logprobs", "code": "unsupported_parameter"}}
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
```

- [ ] **Step 3: Run to see them fail**

Run: `uv run pytest tests/unit/test_param_learning.py -q -p no:cacheprovider`
Expected: collection error `ImportError: cannot import name 'param_learning'`.

- [ ] **Step 4: Implement `src/eq_chatbot_core/providers/param_learning.py`**

```python
"""Runtime-learned request-parameter support, per (endpoint, model).

Models differ in whether they accept ``temperature`` and whether they want the
output limit as ``max_tokens`` or ``max_completion_tokens`` — and the answer
changes between model generations faster than a hand-kept list can follow.
Instead of guessing from the model name alone, the OpenAI-compatible provider
sends what the caller asked for, recognises the provider's "unsupported
parameter" rejection, retries once with the parameter adjusted, and records the
fact here so later requests are right the first time.

The memory is process-wide (consumers such as the Odoo module build a provider
per request), thread-safe, holds two flags per key, and is never persisted.
"""

from __future__ import annotations

import re
import threading
from typing import Any

LEARNABLE: tuple[str, ...] = ("temperature", "max_tokens")

# Codes that mean "this model does not take this parameter" — as opposed to
# "invalid_value" (out of range), which must reach the caller unchanged.
_REJECTION_CODES = frozenset({"unsupported_parameter", "unsupported_value"})
_QUOTED_PARAM = re.compile(r"""['"`](temperature|max_tokens)['"`]""")

_lock = threading.Lock()
_no_temperature: set[tuple[str, str]] = set()
_completion_tokens: set[tuple[str, str]] = set()


def _key(base_url: str, model: str) -> tuple[str, str]:
    return base_url.rstrip("/"), model


def rejected_parameter(error: BaseException) -> str | None:
    """Return the learnable parameter a 400 response rejected, or ``None``.

    Structured form first: ``error.param`` names the parameter and ``code`` is an
    unsupported-* code (OpenAI). Fallback for gateways that drop ``param``: the
    message quotes the parameter name and says "unsupported"/"not supported".
    """
    if getattr(error, "status_code", None) != 400:
        return None
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        param = body.get("param")
        code = body.get("code")
        if param:
            return param if param in LEARNABLE and code in _REJECTION_CODES else None
        message = str(body.get("message") or "")
    else:
        message = str(error)
    lowered = message.lower()
    if "unsupported" not in lowered and "not supported" not in lowered:
        return None
    match = _QUOTED_PARAM.search(message)
    return match.group(1) if match else None


def adjust(params: dict[str, Any], parameter: str) -> bool:
    """Rewrite ``params`` to avoid ``parameter``. Returns False if nothing changed."""
    if parameter == "temperature" and "temperature" in params:
        del params["temperature"]
        return True
    if parameter == "max_tokens" and "max_tokens" in params:
        params["max_completion_tokens"] = params.pop("max_tokens")
        return True
    return False


def apply(base_url: str, model: str, params: dict[str, Any]) -> None:
    """Apply everything learned for (base_url, model) to ``params`` in place."""
    key = _key(base_url, model)
    with _lock:
        drop_temperature = key in _no_temperature
        rename_tokens = key in _completion_tokens
    if drop_temperature:
        adjust(params, "temperature")
    if rename_tokens:
        adjust(params, "max_tokens")


def mark_unsupported(base_url: str, model: str, parameter: str) -> None:
    key = _key(base_url, model)
    with _lock:
        if parameter == "temperature":
            _no_temperature.add(key)
        elif parameter == "max_tokens":
            _completion_tokens.add(key)


def seed_temperature_support(base_url: str, model: str, supported: bool) -> None:
    """Record temperature support reported by the provider's own model list."""
    key = _key(base_url, model)
    with _lock:
        if supported:
            _no_temperature.discard(key)
        else:
            _no_temperature.add(key)


def clear() -> None:
    with _lock:
        _no_temperature.clear()
        _completion_tokens.clear()
```

Note on the GATEWAY case: its body has no `param` and `code` is the integer 400 — the `if param:` branch is skipped and the text fallback applies.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/unit/test_param_learning.py -q -p no:cacheprovider`
Expected: 9 passed.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git add src/eq_chatbot_core/providers/param_learning.py tests/unit/test_param_learning.py tests/conftest.py
git commit -m "[ADD] param_learning: nicht unterstützte Parameter erkennen und je Endpoint/Modell merken

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Base class — learning retry, error mapping, hooks

**Files:**
- Modify: `src/eq_chatbot_core/providers/openai_compatible.py`
- Create: `tests/unit/test_openai_compatible_wire.py`
- Modify (only if they fail, see Step 6): `tests/unit/test_ionos.py`, `test_melious.py`, `test_litellm.py`, `test_privatemode.py`

**Interfaces:**
- Consumes: everything from Task 2.
- Produces on `OpenAICompatibleProvider`:
  - `_token_param(self, model: str) -> str` — default `"max_tokens"`
  - `_default_headers(self) -> dict[str, str]` — default `{}`
  - `_client_kwargs(self) -> dict[str, Any]` — default `{}`
  - `_create(self, params: dict[str, Any]) -> Any` — `chat.completions.create` with learning
  - `_error_from_message(self, message: str) -> ProviderError` — default `ProviderError`
  - `_handle_error(self, error: Exception) -> ProviderError` — status-based
  - `_validate_default_url: ClassVar[bool] = True` — see Steps 4a/4b

- [ ] **Step 1: Write the failing tests `tests/unit/test_openai_compatible_wire.py`**

```python
"""OpenAICompatibleProvider against a real local OpenAI-wire server.

The SDK, transport and error mapping are the production code paths; only the
remote provider is simulated (tests/wire_server.py).
"""

import pytest

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    ContextLengthError,
    OverloadedError,
    ProviderError,
    RateLimitError,
)
from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider
from tests.wire_server import (
    GATEWAY_TEMPERATURE_REJECTION_NO_PARAM,
    OPENAI_MAX_TOKENS_REJECTION,
    OPENAI_TEMPERATURE_REJECTION,
    Reply,
    chat_body,
    stream_events,
)

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]

MSG = [{"role": "user", "content": "x"}]
CHAT = ("POST", "/v1/chat/completions")


class _Gateway(OpenAICompatibleProvider):
    PROVIDER_NAME = "testgateway"


def _provider(wire_server, **kw):
    return _Gateway(api_key="k", base_url=wire_server.base_url, max_retries=0, **kw)


def _sent(wire_server):
    return [r.json for r in wire_server.requests if r.path == CHAT[1]]


# --- learning ---------------------------------------------------------------


def test_temperature_rejection_retried_without_it(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body("ok")))
    response = _provider(wire_server).chat_completion(MSG, model="m", temperature=0.7)

    assert response.content == "ok"
    first, second = _sent(wire_server)
    assert first["temperature"] == 0.7
    assert "temperature" not in second


def test_max_tokens_rejection_retried_as_max_completion_tokens(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_MAX_TOKENS_REJECTION), Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="m", max_tokens=50)

    first, second = _sent(wire_server)
    assert first["max_tokens"] == 50
    assert second["max_completion_tokens"] == 50 and "max_tokens" not in second


def test_both_parameters_rejected_learned_in_one_call(wire_server):
    wire_server.expect(
        *CHAT,
        Reply(400, OPENAI_TEMPERATURE_REJECTION),
        Reply(400, OPENAI_MAX_TOKENS_REJECTION),
        Reply(body=chat_body()),
    )
    provider = _provider(wire_server)
    provider.chat_completion(MSG, model="m", temperature=0.7, max_tokens=50)
    assert len(_sent(wire_server)) == 3

    provider.chat_completion(MSG, model="m", temperature=0.7, max_tokens=50)
    fourth = _sent(wire_server)[3]
    assert "temperature" not in fourth and fourth["max_completion_tokens"] == 50
    assert len(_sent(wire_server)) == 4  # learned: no retry on the second call


def test_learning_shared_across_instances(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="m", temperature=0.7)
    _provider(wire_server).chat_completion(MSG, model="m", temperature=0.7)

    assert len(_sent(wire_server)) == 3
    assert "temperature" not in _sent(wire_server)[2]


def test_same_rejection_twice_propagates(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION))  # repeats forever
    with pytest.raises(ProviderError) as caught:
        _provider(wire_server).chat_completion(MSG, model="m", temperature=0.7)
    assert caught.value.status_code == 400
    assert len(_sent(wire_server)) == 2  # one retry, then give up


def test_gateway_rejection_without_param_field(wire_server):
    wire_server.expect(*CHAT, Reply(400, GATEWAY_TEMPERATURE_REJECTION_NO_PARAM), Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="m", temperature=0.7)
    assert "temperature" not in _sent(wire_server)[1]


def test_stream_retries_before_first_chunk(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(sse=stream_events(["Hal", "lo"])))
    chunks = list(_provider(wire_server).stream_completion(MSG, model="m", temperature=0.7))

    assert "".join(c.content for c in chunks) == "Hallo"
    assert chunks[-1].is_final and chunks[-1].input_tokens == 5
    assert len(_sent(wire_server)) == 2


# --- error mapping ----------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "exc_type"),
    [(429, RateLimitError), (401, AuthenticationError), (403, AuthenticationError), (503, OverloadedError), (529, OverloadedError)],
)
def test_status_mapping(wire_server, status, exc_type):
    wire_server.expect(*CHAT, Reply(status, {"error": {"message": "nope"}}))
    with pytest.raises(exc_type) as caught:
        _provider(wire_server).chat_completion(MSG, model="m")
    assert caught.value.status_code == status


def test_rate_limit_carries_retry_after(wire_server):
    wire_server.expect(*CHAT, Reply(429, {"error": {"message": "slow down"}}, headers={"Retry-After": "7"}))
    with pytest.raises(RateLimitError) as caught:
        _provider(wire_server).chat_completion(MSG, model="m")
    assert caught.value.retry_after == 7


def test_context_length_by_code(wire_server):
    body = {"error": {"message": "This model's maximum context length is 8192 tokens.", "code": "context_length_exceeded"}}
    wire_server.expect(*CHAT, Reply(400, body))
    with pytest.raises(ContextLengthError):
        _provider(wire_server).chat_completion(MSG, model="m")


def test_word_token_alone_is_not_context_length(wire_server):
    body = {"error": {"message": "Invalid token in request", "code": "invalid_request"}}
    wire_server.expect(*CHAT, Reply(400, body))
    with pytest.raises(ProviderError) as caught:
        _provider(wire_server).chat_completion(MSG, model="m")
    assert type(caught.value) is ProviderError


def test_error_in_200_body_raises_typed_error(wire_server):
    wire_server.expect(*CHAT, Reply(200, {"error": {"message": "model crashed"}}))
    with pytest.raises(ProviderError, match="model crashed"):
        _provider(wire_server).chat_completion(MSG, model="m")


def test_stream_error_event_mid_stream(wire_server):
    events = stream_events(["Hal"])[:1] + [{"error": {"message": "upstream died"}}]
    wire_server.expect(*CHAT, Reply(sse=events))
    received = []
    with pytest.raises(ProviderError, match="upstream died"):
        for chunk in _provider(wire_server).stream_completion(MSG, model="m"):
            received.append(chunk.content)
    assert received == ["Hal"]
    assert len(_sent(wire_server)) == 1  # no retry once output has started


def test_secrets_scrubbed_from_errors(wire_server):
    wire_server.expect(*CHAT, Reply(500, {"error": {"message": "bad key sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX"}}))
    with pytest.raises(ProviderError) as caught:
        _provider(wire_server).chat_completion(MSG, model="m")
    assert "ABCDEFGHIJKLMNOPQRSTUVWX" not in str(caught.value)


# --- hooks ------------------------------------------------------------------


def test_default_headers_hook(wire_server):
    class _WithHeaders(_Gateway):
        def _default_headers(self):
            return {"X-Title": "eq-test"}

    wire_server.expect(*CHAT, Reply(body=chat_body()))
    _WithHeaders(api_key="k", base_url=wire_server.base_url, max_retries=0).chat_completion(MSG, model="m")
    assert wire_server.requests[0].headers.get("X-Title") == "eq-test"


def test_token_param_hook_is_initial_guess(wire_server):
    class _NewTokenApi(_Gateway):
        def _token_param(self, model):
            return "max_completion_tokens"

    wire_server.expect(*CHAT, Reply(body=chat_body()))
    _NewTokenApi(api_key="k", base_url=wire_server.base_url, max_retries=0).chat_completion(MSG, model="m", max_tokens=9)
    assert _sent(wire_server)[0]["max_completion_tokens"] == 9
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/unit/test_openai_compatible_wire.py -q -p no:cacheprovider`
Expected: failures in the learning, mapping (403/503/529/retry_after/context/token) and hook tests; `test_secrets_scrubbed_from_errors` may already pass.

- [ ] **Step 3: Add imports and logger to `openai_compatible.py`**

Replace the import block (lines 21-37) with:

```python
import logging
from collections.abc import Iterator
from typing import Any, ClassVar, TypeVar

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.base import (
    AuthenticationError,
    BaseLLMProvider,
    ContextLengthError,
    LLMResponse,
    OverloadedError,
    ProviderError,
    RateLimitError,
    StreamChunk,
    ToolDefinition,
    normalize_tools,
)
from eq_chatbot_core.providers.stream_accumulator import ToolCallAccumulator
from eq_chatbot_core.providers.temperature_constraints import clamp_temperature
from eq_chatbot_core.utils.secret_scrub import scrub_secrets

_logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Change construction, client and add hooks**

4a. In `__init__`, validate only a caller-supplied URL at construction time (the pinned transport validates the default when the client is first built; this keeps offline construction working for Mammouth/OpenAI/OpenRouter, whose current constructors do no DNS lookup for their defaults). Replace lines 100-105:

```python
        # SSRF guard: a caller-supplied base_url is validated now. A built-in
        # default costs no DNS round-trip until the client is created — the
        # pinned transport validates it then. Imported lazily (import cycle).
        if base_url or self._validate_default_url:
            from eq_chatbot_core.utils.url_validation import validate_url

            validate_url(effective_base_url, allow_private_ranges=self.ALLOW_PRIVATE_RANGES)
```

4b. Add the class attribute after `MISSING_BASE_URL_MESSAGE` and document it in the class docstring:

```python
    # Validate DEFAULT_BASE_URL at construction too. True keeps the behaviour of
    # the providers that already inherit this class; providers that never did a
    # DNS lookup for their built-in default set it False.
    _validate_default_url: ClassVar[bool] = True
```

4c. In `client`, pass headers and extra kwargs:

```python
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
                default_headers=self._default_headers() or None,
                http_client=httpx2.Client(
                    transport=build_pinned_transport_for_url(
                        self._effective_base_url,
                        allow_private_ranges=self.ALLOW_PRIVATE_RANGES,
                    ),
                    timeout=self.timeout,
                ),
                **self._client_kwargs(),
            )
```

4d. Add the hooks directly after `client`:

```python
    def _default_headers(self) -> dict[str, str]:
        """Extra HTTP headers for every request (e.g. OpenRouter attribution)."""
        return {}

    def _client_kwargs(self) -> dict[str, Any]:
        """Extra keyword arguments for the ``openai.OpenAI`` constructor."""
        return {}

    def _token_param(self, model: str) -> str:
        """Initial guess for the output-limit parameter name.

        Runtime learning (``param_learning``) corrects a wrong guess; this only
        saves the first failed request where a provider already knows better.
        """
        return "max_tokens"
```

- [ ] **Step 5: Learning retry, body-error check and status mapping**

5a. In `_build_params`, replace `params["max_tokens"] = max_tokens` with `params[self._token_param(model)] = max_tokens`.

5b. Add `_create` after `_build_params`:

```python
    def _create(self, params: dict[str, Any]) -> Any:
        """``chat.completions.create`` that learns unsupported parameters.

        A 400 naming ``temperature`` or ``max_tokens`` as unsupported is retried
        with that parameter adjusted — at most once per parameter — and the fact
        is remembered for this endpoint and model (see ``param_learning``). For
        streaming the rejection arrives before the first chunk, so no output is
        ever duplicated.
        """
        model = params["model"]
        param_learning.apply(self._effective_base_url, model, params)
        adjusted: set[str] = set()
        while True:
            try:
                return self.client.chat.completions.create(**params)
            except Exception as error:
                parameter = param_learning.rejected_parameter(error)
                if parameter is None or parameter in adjusted or not param_learning.adjust(params, parameter):
                    raise
                adjusted.add(parameter)
                param_learning.mark_unsupported(self._effective_base_url, model, parameter)
                _logger.info(
                    "%s: model %s rejected '%s'; retrying adjusted and remembering it for this endpoint",
                    self.provider_name,
                    model,
                    parameter,
                )
```

5c. In `chat_completion`, replace `response = self.client.chat.completions.create(**params)` and the following `choice = response.choices[0]` with:

```python
            response = self._create(params)

            # getattr: the SDK builds response models without validation, so a body
            # lacking `choices` yields an object without that attribute at all.
            if not getattr(response, "choices", None):
                # Local servers (LM Studio, Ollama) answer 200 with an `error`
                # body instead of choices, e.g. on context overflow.
                error = (getattr(response, "model_extra", None) or {}).get("error")
                if error:
                    message = error.get("message") if isinstance(error, dict) else str(error)
                    raise self._error_from_message(scrub_secrets(str(message)))
                raise ProviderError(message="Response contained no choices", provider=self.provider_name)

            choice = response.choices[0]
```

and change the `except Exception as e:` at the end of `chat_completion` to:

```python
        except ProviderError:
            raise
        except Exception as e:
            raise self._handle_error(e) from e
```

5d. In `stream_completion`, replace `stream = self.client.chat.completions.create(**params)` with `stream = self._create(params)`, and add the same `except ProviderError: raise` before its generic `except`.

5e. Replace `_handle_error` with:

```python
    def _error_from_message(self, message: str) -> ProviderError:
        """Typed error for a provider message that carries no HTTP status."""
        return ProviderError(message=message, provider=self.provider_name)

    def _handle_error(self, error: Exception) -> ProviderError:
        """Map an SDK exception to the ProviderError hierarchy by HTTP status.

        Substring matching is a fallback for errors without a status only; the
        bare word "token" is deliberately not a criterion ("max_tokens is not
        supported" is not a context-length problem).
        """
        if isinstance(error, ProviderError):
            return error
        import openai

        message = scrub_secrets(str(error))
        provider = self.provider_name
        body = error.body if isinstance(getattr(error, "body", None), dict) else {}

        if isinstance(error, openai.APIStatusError):
            status = error.status_code
            if status == 429:
                return RateLimitError(message, provider, status_code=429, retry_after=_retry_after(error.response))
            if status in (401, 403):
                return AuthenticationError(message, provider, status_code=status)
            if status in (503, 529):
                return OverloadedError(message, provider, status_code=status)
            if status == 400 and _is_context_overflow(body, message):
                return ContextLengthError(message, provider, status_code=400)
            return ProviderError(message, provider, status_code=status)

        if isinstance(error, openai.APIError):  # error event inside a stream: no status
            if _is_context_overflow(body, message):
                return ContextLengthError(message, provider)
            return self._error_from_message(message)

        lowered = message.lower()
        if "rate limit" in lowered:
            return RateLimitError(message, provider)
        if "context length" in lowered:
            return ContextLengthError(message, provider)
        return ProviderError(message, provider)
```

5f. Add module-level helpers at the end of the file:

```python
def _retry_after(response: Any) -> int | None:
    value = response.headers.get("retry-after") if response is not None else None
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _is_context_overflow(body: dict[str, Any], message: str) -> bool:
    """OpenAI's code, or the phrasing gateways use when they relay without a code."""
    if body.get("code") == "context_length_exceeded":
        return True
    lowered = message.lower()
    return "context length" in lowered or "context_length" in lowered or "maximum context" in lowered
```

The message-phrase fallback for 400 keeps the behaviour Mammouth and LangDock have today (they map 400 + "context"); the spec's "by code" rule is the primary path.

- [ ] **Step 6: Run the new tests, then the whole unit suite**

Run: `uv run pytest tests/unit/test_openai_compatible_wire.py -q -p no:cacheprovider`
Expected: all passed.

Run: `uv run pytest tests/unit/ -q -p no:cacheprovider 2>&1 | grep -E "FAILED|passed|failed"`
Expected: possible failures in `test_ionos.py`, `test_melious.py`, `test_litellm.py`, `test_privatemode.py` where a mocked SDK raises a plain `Exception("... 401 ...")` and expects the old substring mapping. For each failure, decide:
- if the test asserts *behaviour the spec keeps* (e.g. "auth failure → AuthenticationError"), rewrite it as a wire-server test in `tests/unit/test_openai_compatible_wire.py` style and remove the mocked original;
- if it asserts the *removed substring rule itself*, it is obsolete.
List every test you intend to remove or rewrite (file::name, one line why) and **stop for the Captain's "ja"** before deleting anything. Then apply, re-run until green.

- [ ] **Step 7: Compatibility, coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git add -A src/eq_chatbot_core/providers/openai_compatible.py tests/
git commit -m "[CHG] OpenAICompatibleProvider: Parameter lernen, Fehler nach HTTP-Status, Erweiterungspunkte

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Expected: `Required test coverage of 83.0% reached`; `test_public_api_compat.py` passes (hooks are additions).

---
### Task 4: Mammouth on the base class (+ shared live checks)

**Files:**
- Modify: `src/eq_chatbot_core/providers/mammouth_provider.py` (rewrite)
- Create: `tests/unit/test_mammouth_wire.py`
- Create: `tests/integration/live_checks.py`
- Modify: `tests/integration/test_mammouth_live.py` (append class)
- Remove after approval: obsolete tests in `tests/unit/test_mammouth.py`

**Interfaces:**
- Consumes: `OpenAICompatibleProvider` incl. `_validate_default_url`, `_handle_error`, `client` (Task 3).
- Produces: `tests.integration.live_checks.check_chat(provider, model)`, `check_stream(provider, model)`, `check_tool_call(provider, model)`, `WEATHER_TOOL: dict`.

- [ ] **Step 1: Write the wire tests `tests/unit/test_mammouth_wire.py`**

```python
"""MammouthProvider against the local OpenAI-wire server."""

import pytest

from eq_chatbot_core.providers.mammouth_provider import MammouthProvider
from tests.wire_server import OPENAI_TEMPERATURE_REJECTION, Reply, chat_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]


def _provider(wire_server):
    provider = MammouthProvider(api_key="mm-test", base_url=wire_server.base_url, max_retries=0)
    # MODELS_URL is a separate public endpoint; point this instance at the test server.
    provider.MODELS_URL = f"{wire_server.root_url}/public/models"
    return provider


def test_chat_and_auth_header(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("hallo", model="gpt-x")))
    response = _provider(wire_server).chat_completion(MSG, model="gpt-x")
    assert response.content == "hallo" and response.model == "gpt-x"
    assert wire_server.requests[0].headers["Authorization"] == "Bearer mm-test"


def test_stream(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=stream_events(["a", "b"])))
    chunks = list(_provider(wire_server).stream_completion(MSG, model="gpt-x"))
    assert "".join(c.content for c in chunks) == "ab" and chunks[-1].is_final


def test_temperature_learning(wire_server):
    wire_server.expect(
        "POST", "/v1/chat/completions", Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body())
    )
    _provider(wire_server).chat_completion(MSG, model="gpt-x", temperature=0.5)
    assert "temperature" not in wire_server.requests[1].json


def test_list_models_from_public_endpoint(wire_server):
    wire_server.expect(
        "GET",
        "/public/models",
        Reply(body=[{"id": "gpt-x", "name": "GPT X", "max_input_tokens": 1000, "max_output_tokens": 100}]),
    )
    models = _provider(wire_server).list_models()
    assert models == [
        {
            "id": "gpt-x",
            "name": "GPT X",
            "provider": "mammouth",
            "context_length": 1000,
            "max_output_tokens": 100,
            "supports_temperature": True,
            "min_temperature": 0.0,
            "max_temperature": 2.0,
            "supports_reasoning": False,
            "supports_streaming": True,
        }
    ]
    assert wire_server.requests[0].headers["Authorization"] == "Bearer mm-test"


def test_construction_needs_no_network():
    MammouthProvider(api_key="mm-test")  # default URL is validated lazily, on first request
```

If `test_list_models_from_public_endpoint` fails only on `min_temperature`/`max_temperature` values, take the values `get_temperature_constraints("gpt-x")` returns today — the test pins today's behaviour, not new numbers.

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/unit/test_mammouth_wire.py -q -p no:cacheprovider`
Expected: at least `test_temperature_learning` fails (the current provider has no learning); others may already pass.

- [ ] **Step 3: Rewrite `src/eq_chatbot_core/providers/mammouth_provider.py`**

```python
"""
Mammouth AI provider implementation.

Mammouth AI (https://mammouth.ai) provides access to 30+ AI models through a
unified OpenAI-compatible API, including OpenAI, Anthropic, Google, Mistral,
xAI, DeepSeek, Meta, and more. The wire protocol is handled by
OpenAICompatibleProvider; only the model listing is Mammouth-specific.
"""

import logging
from typing import Any

from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider
from eq_chatbot_core.providers.temperature_constraints import (
    clamp_temperature as _shared_clamp_temperature,
)
from eq_chatbot_core.providers.temperature_constraints import (
    get_temperature_constraints as _shared_get_temperature_constraints,
)

_logger = logging.getLogger(__name__)


class MammouthProvider(OpenAICompatibleProvider):
    """
    Mammouth AI API provider for 30+ AI models.

    Model IDs use simple names without provider prefix (e.g. "gpt-4o",
    "claude-sonnet-4-5") unlike OpenRouter which uses "provider/model" format.
    """

    PROVIDER_NAME = "mammouth"
    DEFAULT_BASE_URL = "https://api.mammouth.ai/v1"
    # Verified live on 23.08.2026; model IDs leave the source in stage 2.
    DEFAULT_MODEL = "gpt-5.6-luna"
    MODELS_URL = "https://api.mammouth.ai/public/models"
    _validate_default_url = False

    # Reasoning models that don't support temperature parameter
    REASONING_MODEL_PREFIXES = ("o1", "o3", "o4")

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        """
        Initialize the Mammouth AI provider.

        Args:
            api_key: Mammouth AI API key
            base_url: Optional custom base URL (defaults to Mammouth API)
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures
        """
        super().__init__(api_key, base_url, timeout, max_retries)

    def _is_reasoning_model(self, model: str) -> bool:
        """Check if model is a reasoning model (O1, O3, O4)."""
        model_lower = model.lower()
        return any(model_lower.startswith(prefix) for prefix in self.REASONING_MODEL_PREFIXES)

    def _get_temperature_constraints(self, model: str) -> dict[str, Any]:
        """Get temperature constraints for a specific model. Delegates to shared module."""
        return _shared_get_temperature_constraints(model)

    def _clamp_temperature(self, model: str, temperature: float) -> float | None:
        """Clamp temperature to valid range for the model. Delegates to shared module."""
        return _shared_clamp_temperature(model, temperature)

    def list_models(self) -> list[dict[str, Any]]:
        """
        List available models from Mammouth AI.

        Uses the /public/models endpoint (separate from the v1 base URL), fetched
        through the same pinned client as every other request.
        """
        try:
            data = self.client.get(self.MODELS_URL, cast_to=object)
        except Exception as e:
            raise self._handle_error(e) from e

        # Mammouth returns a list directly or wrapped in "data"/"models"
        model_list = data if isinstance(data, list) else data.get("data", data.get("models", []))

        models = []
        for model_data in model_list:
            model_id = model_data.get("id", model_data.get("model", ""))
            if not model_id:
                continue
            temp_constraints = self._get_temperature_constraints(model_id)
            models.append(
                {
                    "id": model_id,
                    "name": model_data.get("name", model_id),
                    "provider": self.provider_name,
                    "context_length": model_data.get("max_input_tokens"),
                    "max_output_tokens": model_data.get("max_output_tokens"),
                    "supports_temperature": temp_constraints["supports_temperature"],
                    "min_temperature": temp_constraints["min"],
                    "max_temperature": temp_constraints["max"],
                    "supports_reasoning": self._is_reasoning_model(model_id),
                    "supports_streaming": True,
                }
            )

        models.sort(key=lambda m: m["id"])
        return models
```

`cast_to=object` makes the SDK return the parsed JSON body (list or dict); an absolute URL bypasses `base_url`.

- [ ] **Step 4: Run wire tests and compatibility test**

Run: `uv run pytest tests/unit/test_mammouth_wire.py tests/unit/test_public_api_compat.py -q -p no:cacheprovider`
Expected: all passed.

- [ ] **Step 5: Shared live checks `tests/integration/live_checks.py`**

```python
"""Assertions shared by the per-provider live tests (real API calls)."""

from typing import Any

WEATHER_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}
# Generous: reasoning models spend part of the budget before answering.
_BUDGET = 512


def check_chat(provider: Any, model: str) -> None:
    r = provider.chat_completion([{"role": "user", "content": "Say 'test' only."}], model=model, max_tokens=_BUDGET)
    assert "test" in r.content.lower(), r.content
    assert r.input_tokens > 0 and r.output_tokens > 0


def check_stream(provider: Any, model: str) -> None:
    chunks = list(
        provider.stream_completion([{"role": "user", "content": "Say 'test' only."}], model=model, max_tokens=_BUDGET)
    )
    assert "test" in "".join(c.content for c in chunks).lower()
    assert chunks[-1].is_final


def check_tool_call(provider: Any, model: str) -> None:
    r = provider.chat_completion(
        [{"role": "user", "content": "What is the weather in Berlin? Use the tool."}],
        model=model,
        tools=[WEATHER_TOOL],
        max_tokens=_BUDGET,
    )
    assert r.tool_calls, f"no tool call; content={r.content!r}"
    assert r.tool_calls[0]["function"]["name"] == "get_weather"
    assert "berlin" in r.tool_calls[0]["function"]["arguments"].lower()
```

- [ ] **Step 6: Append the live class to `tests/integration/test_mammouth_live.py`**

```python
@pytest.mark.integration
class TestMammouthOnBaseClass:
    """Chat, stream and tool call through OpenAICompatibleProvider."""

    @pytest.fixture
    def provider(self, mammouth_api_key):
        if not mammouth_api_key:
            pytest.skip("MAMMOUTH_API_KEY not set")
        return get_provider("mammouth", api_key=mammouth_api_key)

    def test_chat(self, provider, mammouth_resolved_model):
        from tests.integration.live_checks import check_chat

        check_chat(provider, mammouth_resolved_model)

    def test_stream(self, provider, mammouth_resolved_model):
        from tests.integration.live_checks import check_stream

        check_stream(provider, mammouth_resolved_model)

    def test_tool_call(self, provider, mammouth_resolved_model):
        from tests.integration.live_checks import check_tool_call

        check_tool_call(provider, mammouth_resolved_model)
```

Run: `uv run pytest tests/integration/test_mammouth_live.py -q -p no:cacheprovider -m integration`
Expected: all passed (the existing six plus three). A failure here blocks the task — do not continue to Step 7 with a red live test.

- [ ] **Step 7: Obsolete mocked tests**

Run: `uv run pytest tests/unit/test_mammouth.py -q -p no:cacheprovider 2>&1 | grep -E "FAILED|passed|failed"`
For each failure: if it patches `httpx2`/the old `client` and checks request building, SSE parsing or `_handle_http_error`, it tested removed code — candidate for deletion. If it checks behaviour that still exists (e.g. list-model fields, reasoning detection), port it to `test_mammouth_wire.py`. Present the list (`file::test — reason`) and **wait for the Captain's "ja"**. Then delete/port and re-run.

- [ ] **Step 8: Full suite, coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git add -A src/eq_chatbot_core/providers/mammouth_provider.py tests/
git commit -m "[CHG] Mammouth auf OpenAICompatibleProvider umgestellt

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Local servers (LM Studio, Ollama) on the base class

**Files:**
- Modify: `src/eq_chatbot_core/providers/openai_compatible.py` (one class attribute)
- Modify: `src/eq_chatbot_core/providers/local_provider.py` (rewrite)
- Create: `tests/unit/test_local_wire.py`
- Remove after approval: obsolete tests in `tests/unit/test_local.py`

**Interfaces:**
- Consumes: Task 3 hooks; `_error_from_message`.
- Produces: `OpenAICompatibleProvider.STREAM_INCLUDE_USAGE: ClassVar[bool] = True`.

- [ ] **Step 1: Write the wire tests `tests/unit/test_local_wire.py`**

```python
"""LocalLLMProvider against the local OpenAI-wire server (it *is* a local server)."""

import pytest

from eq_chatbot_core.providers.base import ContextLengthError, ProviderError
from eq_chatbot_core.providers.local_provider import LocalLLMProvider
from tests.wire_server import Reply, chat_body, models_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]


def _provider(wire_server):
    return LocalLLMProvider(base_url=wire_server.base_url, max_retries=0)


def test_defaults():
    p = LocalLLMProvider()
    assert p.base_url == "http://localhost:1234/v1" and p.timeout == 120.0 and p.api_key == "not-used"
    assert LocalLLMProvider(base_url="http://localhost:11434/v1")._get_server_type() == "ollama"


def test_chat(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("lokal")))
    assert _provider(wire_server).chat_completion(MSG, model="qwen").content == "lokal"


def test_stream_sends_no_stream_options(wire_server):
    """Unchanged wire behaviour: older LM Studio/Ollama builds reject stream_options."""
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=stream_events(["a"])))
    list(_provider(wire_server).stream_completion(MSG, model="qwen"))
    assert "stream_options" not in wire_server.requests[0].json


def test_context_overflow_in_200_body(wire_server):
    wire_server.expect(
        "POST", "/v1/chat/completions", Reply(200, {"error": "Trying to keep the first 9000 tokens when context overflows"})
    )
    with pytest.raises(ContextLengthError):
        _provider(wire_server).chat_completion(MSG, model="qwen")


def test_context_overflow_as_stream_event(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(sse=[{"error": {"message": "context length exceeded"}}]))
    with pytest.raises(ContextLengthError):
        list(_provider(wire_server).stream_completion(MSG, model="qwen"))


def test_list_models_format(wire_server):
    wire_server.expect("GET", "/v1/models", Reply(body=models_body(["qwen"])))
    (model,) = _provider(wire_server).list_models()
    assert model == {
        "id": "qwen",
        "name": "qwen",
        "provider": "local",
        "context_length": None,
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": False,
        "owned_by": "test",
        "created": 0,
    }


def test_server_availability(wire_server):
    wire_server.expect("GET", "/v1/models", Reply(body=models_body([])))
    assert _provider(wire_server).is_server_available()
    assert not LocalLLMProvider(base_url="http://127.0.0.1:9/v1", max_retries=0).is_server_available()


def test_connection_refused_message():
    with pytest.raises(ProviderError, match="Cannot connect to local LLM server"):
        LocalLLMProvider(base_url="http://127.0.0.1:9/v1", max_retries=0).chat_completion(MSG, model="qwen")
```

Port 9 (discard) is closed on developer machines and CI runners, which gives a real connection refusal.

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/unit/test_local_wire.py -q -p no:cacheprovider`
Expected: several failures (e.g. `test_context_overflow_as_stream_event`, `test_stream_sends_no_stream_options` passes today — fine).

- [ ] **Step 3: Add `STREAM_INCLUDE_USAGE` to the base class**

In `openai_compatible.py` add next to `ALLOW_PRIVATE_RANGES`:

```python
    # Ask for token usage in streams. Off for servers that reject the option.
    STREAM_INCLUDE_USAGE: ClassVar[bool] = True
```

and in `stream_completion` replace `params["stream_options"] = {"include_usage": True}` with:

```python
            if self.STREAM_INCLUDE_USAGE:
                params["stream_options"] = {"include_usage": True}
```

- [ ] **Step 4: Rewrite `src/eq_chatbot_core/providers/local_provider.py`**

Keep the module docstring and the class docstring (with its examples) from the current file; replace everything else with:

```python
import logging
from typing import Any

from eq_chatbot_core.providers.base import AuthenticationError, ContextLengthError, ProviderError
from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider
from eq_chatbot_core.utils.secret_scrub import scrub_secrets

logger = logging.getLogger(__name__)


class LocalLLMProvider(OpenAICompatibleProvider):
    # (class docstring from the current file)

    PROVIDER_NAME = "local"
    DEFAULT_MODEL = "local-model"
    ALLOW_PRIVATE_RANGES = True
    STREAM_INCLUDE_USAGE = False

    # Default URLs for common local LLM servers
    LM_STUDIO_URL = "http://localhost:1234/v1"
    OLLAMA_URL = "http://localhost:11434/v1"
    DEFAULT_BASE_URL = LM_STUDIO_URL

    # Default timeout is higher for local servers (model loading can be slow)
    DEFAULT_TIMEOUT = 120.0

    def __init__(
        self,
        api_key: str = "not-used",
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int = 2,
    ):
        """
        Initialize the local LLM provider.

        Args:
            api_key: API key (usually not required for local servers, defaults to "not-used")
            base_url: Server URL (defaults to LM Studio URL)
            timeout: Request timeout in seconds (defaults to 120s for model loading)
            max_retries: Number of retries on transient failures
        """
        # Always validated (LAN mode): local servers are reachable without DNS
        # surprises, and the old provider validated the default too.
        super().__init__(
            api_key=api_key,
            base_url=base_url or self.LM_STUDIO_URL,
            timeout=timeout or self.DEFAULT_TIMEOUT,
            max_retries=max_retries,
        )

    def _get_server_type(self) -> str:
        """Detect server type based on base_url."""
        if self.base_url and "11434" in self.base_url:
            return "ollama"
        return "lm_studio"

    @staticmethod
    def _extract_error_message(data: Any) -> str | None:
        """Extract an error message from a local-server response body (kept for callers)."""
        if not isinstance(data, dict):
            return None
        err = data.get("error")
        if not err:
            return None
        if isinstance(err, dict):
            return err.get("message") or str(err)
        return str(err)

    def _error_from_message(self, message: str) -> ProviderError:
        """LM Studio/Ollama signal context overflow in the body, without a status."""
        lowered = message.lower()
        if "context" in lowered or "token" in lowered:
            return ContextLengthError(message=f"Context length exceeded: {message}", provider=self.provider_name)
        return ProviderError(message=message, provider=self.provider_name)

    def _handle_error(self, error: Exception) -> ProviderError:
        import openai

        where = scrub_secrets(self.base_url or self.LM_STUDIO_URL)
        if isinstance(error, openai.APITimeoutError):
            return ProviderError(
                message=f"Request timed out after {self.timeout}s. Error: {scrub_secrets(str(error))}",
                provider=self.provider_name,
            )
        if isinstance(error, openai.APIConnectionError):
            return ProviderError(
                message=f"Cannot connect to local LLM server at {where}. "
                f"Ensure the server is running. Error: {scrub_secrets(str(error))}",
                provider=self.provider_name,
            )
        if isinstance(error, openai.APIStatusError) and error.status_code == 401:
            return AuthenticationError(
                message="Authentication failed (local server may require API key)",
                provider=self.provider_name,
                status_code=401,
            )
        return super()._handle_error(error)

    def list_models(self) -> list[dict[str, Any]]:
        """List models from the local server (limited metadata)."""
        try:
            data = self.client.get("/models", cast_to=object)
        except Exception as e:
            raise self._handle_error(e) from e

        models = []
        for model_data in data.get("data", []) if isinstance(data, dict) else []:
            model_id = model_data.get("id", "unknown")
            models.append(
                {
                    "id": model_id,
                    "name": model_id,
                    "provider": self.provider_name,
                    "context_length": model_data.get("context_length"),
                    "supports_streaming": True,
                    "supports_tools": False,  # Most local models don't support tools
                    "supports_vision": False,  # Most local models don't support vision
                    "owned_by": model_data.get("owned_by", "local"),
                    "created": model_data.get("created"),
                }
            )
        return models

    def is_server_available(self) -> bool:
        """Check if the local LLM server is reachable (no retries)."""
        try:
            self.client.with_options(max_retries=0).get("/models", cast_to=object)
            return True
        except Exception as e:
            logger.debug("Local server health check failed: %s", scrub_secrets(str(e)))
            return False
```

`openai.APITimeoutError` subclasses `APIConnectionError`, so it is checked first.

- [ ] **Step 5: Run wire and compatibility tests**

Run: `uv run pytest tests/unit/test_local_wire.py tests/unit/test_openai_compatible_wire.py tests/unit/test_public_api_compat.py -q -p no:cacheprovider`
Expected: all passed.

- [ ] **Step 6: Live check against LM Studio or Ollama**

Start LM Studio (port 1234) or Ollama (11434) with a small model; then:
Run: `uv run pytest tests/integration/test_local_live.py -q -p no:cacheprovider -m "local or integration"`
Expected: all passed. If no local server is running the tests skip — then say so in the task report; this task is not "live-verified" until they ran.

- [ ] **Step 7: Obsolete mocked tests** — same procedure as Task 4 Step 7 for `tests/unit/test_local.py`; wait for "ja".

- [ ] **Step 8: Full suite, coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git add -A src/eq_chatbot_core/providers/ tests/
git commit -m "[CHG] Lokale Server (LM Studio, Ollama) auf OpenAICompatibleProvider umgestellt

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: OpenAI on the base class (+ live learning proof)

**Files:**
- Modify: `src/eq_chatbot_core/providers/openai_provider.py`
- Create: `tests/unit/test_openai_wire.py`
- Modify: `tests/integration/test_openai_live.py` (append class)
- Remove after approval: obsolete tests in `tests/unit/test_openai.py`, `test_gpt5_temperature.py`

**Interfaces:**
- Consumes: `_token_param`, `_client_kwargs`, `_validate_default_url` (Task 3); `check_*` (Task 4).

- [ ] **Step 1: Wire tests `tests/unit/test_openai_wire.py`**

```python
"""OpenAIProvider against the local OpenAI-wire server."""

import base64

import pytest

from eq_chatbot_core.providers.openai_provider import OpenAIProvider
from tests.wire_server import Reply, chat_body, models_body

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]


def _provider(wire_server, **kw):
    return OpenAIProvider(api_key="sk-test", base_url=wire_server.base_url, max_retries=0, **kw)


def test_new_token_api_is_initial_guess(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    _provider(wire_server).chat_completion(MSG, model="gpt-5.6-luna", max_tokens=20)
    assert wire_server.requests[0].json["max_completion_tokens"] == 20


def test_organization_header(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    _provider(wire_server, organization="org-test").chat_completion(MSG, model="gpt-4.1")
    assert wire_server.requests[0].headers.get("OpenAI-Organization") == "org-test"


def test_list_models_filters_and_annotates(wire_server):
    wire_server.expect("GET", "/v1/models", Reply(body=models_body(["gpt-4.1", "whisper-1", "o3"])))
    ids = [m["id"] for m in _provider(wire_server).list_models()]
    assert ids == ["gpt-4.1", "o3"]


def test_generate_image(wire_server):
    png = b"\x89PNG\r\n"
    wire_server.expect(
        "POST", "/v1/images/generations", Reply(body={"created": 0, "data": [{"b64_json": base64.b64encode(png).decode()}]})
    )
    result = _provider(wire_server).generate_image("a cat")
    assert result.data == png and result.provider == "openai"
    assert wire_server.requests[0].json["model"] == "gpt-image-1"


def test_default_base_url_and_offline_construction():
    assert OpenAIProvider(api_key="sk-test").base_url == "https://api.openai.com/v1"
```

- [ ] **Step 2: Run to see the failures**

Run: `uv run pytest tests/unit/test_openai_wire.py -q -p no:cacheprovider`
Expected: `test_default_base_url_and_offline_construction` fails (today `base_url` is `None` for the default); the others may pass. That one difference is intended: the base class stores the effective URL. Note it for the release notes.

- [ ] **Step 3: Change the class head and constructor of `openai_provider.py`**

- Base class: `class OpenAIProvider(OpenAICompatibleProvider):`
- Imports: drop `BaseLLMProvider`, `LLMResponse`, `StreamChunk`, `ToolDefinition`, `normalize_tools`, `clamp_temperature`, `AuthenticationError`, `ContextLengthError`, `RateLimitError` if unused afterwards (ruff will tell); add `from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider`.
- Class attributes, added under `DEFAULT_BASE_URL`:

```python
    PROVIDER_NAME = "openai"
    # Model IDs leave the source in stage 2.
    DEFAULT_MODEL = "gpt-5.6-luna"
    _validate_default_url = False
```

- Replace `__init__`, `provider_name`, `default_model` and `client` with:

```python
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        organization: str | None = None,
    ):
        self.organization = organization
        super().__init__(api_key, base_url, timeout, max_retries)

    def _client_kwargs(self) -> dict[str, Any]:
        return {"organization": self.organization} if self.organization else {}

    def _token_param(self, model: str) -> str:
        return "max_completion_tokens" if self._uses_new_token_api(model) else "max_tokens"
```

- Delete `chat_completion`, `stream_completion` and `_handle_error`. Keep `_uses_new_token_api`, `CHAT_MODEL_PREFIXES`, `MODEL_CONTEXT_LENGTHS`, `_get_model_constraints`, `list_models`, `generate_image` unchanged.

- [ ] **Step 4: Run wire, base and compatibility tests**

Run: `uv run pytest tests/unit/test_openai_wire.py tests/unit/test_openai_image.py tests/unit/test_public_api_compat.py -q -p no:cacheprovider`
Expected: all passed except possibly mocked image tests — handle in Step 7.

- [ ] **Step 5: Live learning proof — append to `tests/integration/test_openai_live.py`**

```python
# Probed 07.10.2026: rejects temperature (unsupported_value) and max_tokens
# (unsupported_parameter). Test data, not library configuration.
PARAMETER_REJECTING_MODEL = "gpt-5.6-luna"


@pytest.mark.integration
class TestOpenAIOnBaseClass:
    @pytest.fixture
    def provider(self, openai_api_key):
        if not openai_api_key:
            pytest.skip("OPENAI_API_KEY not set")
        return get_provider("openai", api_key=openai_api_key)

    def test_chat(self, provider, openai_resolved_model):
        from tests.integration.live_checks import check_chat

        check_chat(provider, openai_resolved_model)

    def test_stream(self, provider, openai_resolved_model):
        from tests.integration.live_checks import check_stream

        check_stream(provider, openai_resolved_model)

    def test_tool_call(self, provider, openai_resolved_model):
        from tests.integration.live_checks import check_tool_call

        check_tool_call(provider, openai_resolved_model)

    def test_learning_without_name_lists(self, openai_api_key, clean_param_memory, caplog):
        """The stage-2 situation: no name-based first guess. Must still work, and learn once."""
        if not openai_api_key:
            pytest.skip("OPENAI_API_KEY not set")
        from eq_chatbot_core.providers.openai_provider import OpenAIProvider

        class _NoGuesses(OpenAIProvider):
            def _token_param(self, model):
                return "max_tokens"

            def _build_params(self, messages, model, temperature, max_tokens, tools, **kwargs):
                params = super()._build_params(messages, model, temperature, max_tokens, tools, **kwargs)
                params["temperature"] = temperature
                return params

        provider = _NoGuesses(api_key=openai_api_key)
        msg = [{"role": "user", "content": "Say 'test' only."}]
        with caplog.at_level("INFO", logger="eq_chatbot_core.providers.openai_compatible"):
            first = provider.chat_completion(msg, model=PARAMETER_REJECTING_MODEL, temperature=0.7, max_tokens=512)
        assert "test" in first.content.lower()
        retried = {p for p in ("temperature", "max_tokens") if f"'{p}'" in caplog.text}
        assert retried == {"temperature", "max_tokens"}

        caplog.clear()
        with caplog.at_level("INFO", logger="eq_chatbot_core.providers.openai_compatible"):
            provider.chat_completion(msg, model=PARAMETER_REJECTING_MODEL, temperature=0.7, max_tokens=512)
        assert "rejected" not in caplog.text
```

Run: `uv run pytest tests/integration/test_openai_live.py -q -p no:cacheprovider -m integration -k "OnBaseClass or TestOpenAILive"`
Expected: all passed.

- [ ] **Step 6: Full unit run** — `uv run pytest tests/unit/ -q -p no:cacheprovider 2>&1 | grep -E "FAILED|passed|failed"`

- [ ] **Step 7: Obsolete mocked tests** — same procedure as Task 4 Step 7 for `tests/unit/test_openai.py`, `test_gpt5_temperature.py`, `test_openai_image.py`; wait for "ja".

- [ ] **Step 8: Coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git add -A src/eq_chatbot_core/providers/openai_provider.py tests/
git commit -m "[CHG] OpenAI auf OpenAICompatibleProvider umgestellt; Lernen live belegt

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: OpenRouter on the base class (+ seeding from the model list)

**Files:**
- Modify: `src/eq_chatbot_core/providers/openrouter_provider.py`
- Create: `tests/unit/test_openrouter_wire.py`
- Modify: `tests/integration/test_openrouter_live.py` (append class)
- Remove after approval: obsolete tests in `tests/unit/test_openrouter.py`, `test_openrouter_error_handling.py`, `test_openrouter_image.py`

**Interfaces:**
- Consumes: `_default_headers` (Task 3), `param_learning.seed_temperature_support` (Task 2), `check_*` (Task 4).

- [ ] **Step 1: Wire tests `tests/unit/test_openrouter_wire.py`**

```python
"""OpenRouterProvider against the local OpenAI-wire server."""

import base64

import pytest

from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider
from tests.wire_server import Reply, chat_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]


def _provider(wire_server, **kw):
    return OpenRouterProvider(api_key="sk-or-test", base_url=wire_server.base_url, max_retries=0, **kw)


def test_attribution_headers(wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body()))
    _provider(wire_server, site_url="https://example.com", site_name="eq-test").chat_completion(MSG, model="a/b")
    headers = wire_server.requests[0].headers
    assert headers.get("HTTP-Referer") == "https://example.com" and headers.get("X-Title") == "eq-test"


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
```

- [ ] **Step 2: Run to see failures**

Run: `uv run pytest tests/unit/test_openrouter_wire.py -q -p no:cacheprovider`
Expected: `test_model_list_seeds_temperature_support` fails at least.

- [ ] **Step 3: Rewrite the provider parts**

- `class OpenRouterProvider(OpenAICompatibleProvider):` with, under `DEFAULT_BASE_URL`:

```python
    PROVIDER_NAME = "openrouter"
    # Model IDs leave the source in stage 2.
    DEFAULT_MODEL = "openai/gpt-5.6-luna"
    _validate_default_url = False
```

- Replace `__init__`, `provider_name`, `default_model`, `client`:

```python
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        site_url: str | None = None,
        site_name: str | None = None,
    ):
        """(keep the current docstring)"""
        self.site_url = site_url
        self.site_name = site_name
        super().__init__(api_key, base_url, timeout, max_retries)

    def _default_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-Title"] = self.site_name
        return headers
```

- `list_models` becomes:

```python
    def list_models(self) -> list[dict[str, Any]]:
        """List models; seeds parameter learning from `supported_parameters`."""
        try:
            data = self.client.get("/models", cast_to=object)
        except Exception as e:
            raise self._handle_error(e) from e

        models = []
        for model_data in data.get("data", []) if isinstance(data, dict) else []:
            model_id = model_data.get("id", "")
            constraints = self._get_model_constraints(model_data)
            if model_data.get("supported_parameters"):
                param_learning.seed_temperature_support(
                    self._effective_base_url, model_id, constraints["supports_temperature"]
                )
            models.append(
                {
                    "id": model_id,
                    "name": model_data.get("name", model_id),
                    "description": model_data.get("description", ""),
                    "context_length": model_data.get("context_length"),
                    "provider": self.provider_name,
                    "created": model_data.get("created"),
                    **constraints,
                }
            )
        models.sort(key=lambda m: m["id"])
        return models
```

- In `generate_image`, replace the request/`raise_for_status`/`json()` lines with `data = self.client.post("/chat/completions", body=payload, cast_to=object)` and the trailing `except httpx2.HTTPStatusError` clause with nothing (keep `except ProviderError: raise` and `except Exception as e: raise self._handle_error(e) from e`).
- Delete `chat_completion`, `stream_completion`, `_handle_http_error`, `_handle_error`, `close`, `__enter__`, `__exit__`. Keep `_is_reasoning_model`, `_get_model_constraints`, `REASONING_MODEL_PREFIXES`, `DEFAULT_IMAGE_MODEL`, `supports_image_generation`.
- Imports: add `from eq_chatbot_core.providers import param_learning` and `from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider`; remove what ruff reports unused (`httpx2`, `json`, the old exception imports).

`clamp_temperature` already strips the `provider/` prefix (`get_temperature_constraints` → `strip_provider_prefix`), so the base `_build_params` gives the same result the old `bare_model` call did — verify with `uv run python -c "from eq_chatbot_core.providers.temperature_constraints import clamp_temperature as c; print(c('openai/o3', 0.7), c('o3', 0.7))"` (expected: both `None`).

- [ ] **Step 4: Run wire and compatibility tests**

Run: `uv run pytest tests/unit/test_openrouter_wire.py tests/unit/test_public_api_compat.py -q -p no:cacheprovider`
Expected: all passed.

- [ ] **Step 5: Live check (needs a valid key)**

The configured key was rejected on 07.10.2026 (HTTP 401 "User not found"). First run:
`uv run python -c "import tomllib,pathlib,openai; k=tomllib.loads(pathlib.Path('~/.config/eq-chatbot/config.toml').expanduser().read_text())['providers']['openrouter']['api_key']; print(len(openai.OpenAI(api_key=k, base_url='https://openrouter.ai/api/v1').models.list().data))"`
If it raises 401: **stop and ask the Captain for a valid key**; commit the task with the commit message saying "live unverified", and record it in the final report. If it works, append the same three-test class as Task 4 Step 6 to `tests/integration/test_openrouter_live.py` (fixture `openrouter_api_key`, model fixture `openrouter_resolved_model`, provider `get_provider("openrouter", api_key=...)`) and run:
`uv run pytest tests/integration/test_openrouter_live.py -q -p no:cacheprovider -m integration` — expected all passed.

- [ ] **Step 6: Obsolete mocked tests** — Task 4 Step 7 procedure for the three OpenRouter unit files; wait for "ja".

- [ ] **Step 7: Coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git add -A src/eq_chatbot_core/providers/openrouter_provider.py tests/
git commit -m "[CHG] OpenRouter auf OpenAICompatibleProvider umgestellt; Modellliste füllt den Parameterspeicher vor

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: LangDock `openai` backend via delegate

**Files:**
- Modify: `src/eq_chatbot_core/providers/langdock_provider.py`
- Create: `tests/unit/test_langdock_openai_wire.py`
- Remove after approval: obsolete tests in `tests/unit/test_langdock.py`, `test_langdock_backends.py` that mock `openai_client` for the openai backend

**Interfaces:**
- Consumes: `OpenAICompatibleProvider`, `_token_param`, `_build_params` (Task 3).
- Produces: `_LangDockOpenAIBackend(owner: LangDockProvider)`; `LangDockProvider._get_openai_backend() -> _LangDockOpenAIBackend`.

- [ ] **Step 1: Wire tests `tests/unit/test_langdock_openai_wire.py`**

```python
"""LangDock's openai backend against the local OpenAI-wire server.

LangDock builds backend URLs as `<base_url>/openai/<region>/v1`, so the test
server answers on that path.
"""

import pytest

from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.langdock_provider import LangDockProvider
from tests.wire_server import OPENAI_TEMPERATURE_REJECTION, Reply, chat_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]
CHAT = ("POST", "/openai/eu/v1/chat/completions")


def _provider(wire_server, **kw):
    return LangDockProvider(api_key="ld-test", base_url=wire_server.root_url, max_retries=0, **kw)


def test_chat_goes_to_backend_path(wire_server):
    wire_server.expect(*CHAT, Reply(body=chat_body("hallo")))
    assert _provider(wire_server).chat_completion(MSG, model="gpt-6-luna").content == "hallo"


def test_reasoning_effort_only_for_reasoning_models(wire_server):
    wire_server.expect(*CHAT, Reply(body=chat_body()))
    provider = _provider(wire_server, reasoning_effort="high")
    provider.chat_completion(MSG, model="o3")
    provider.chat_completion(MSG, model="gpt-4.1")
    assert wire_server.requests[0].json["reasoning_effort"] == "high"
    assert "reasoning_effort" not in wire_server.requests[1].json


def test_learning_and_stream(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(sse=stream_events(["o", "k"])))
    chunks = list(_provider(wire_server).stream_completion(MSG, model="gpt-6-luna", temperature=0.7))
    assert "".join(c.content for c in chunks) == "ok"


def test_errors_carry_langdock_as_provider(wire_server):
    wire_server.expect(*CHAT, Reply(500, {"error": {"message": "boom"}}))
    with pytest.raises(ProviderError) as caught:
        _provider(wire_server).chat_completion(MSG, model="gpt-6-luna")
    assert caught.value.provider == "langdock" and caught.value.status_code == 500


def test_openai_client_property_still_exists(wire_server):
    from openai import OpenAI

    assert isinstance(_provider(wire_server).openai_client, OpenAI)
```

- [ ] **Step 2: Run to see failures**

Run: `uv run pytest tests/unit/test_langdock_openai_wire.py -q -p no:cacheprovider`
Expected: at least `test_learning_and_stream` fails.

- [ ] **Step 3: Add the delegate class above `class LangDockProvider`**

```python
class _LangDockOpenAIBackend(OpenAICompatibleProvider):
    """LangDock's `/openai/{region}/v1` backend, driven by the shared base class.

    LangDockProvider serves five different APIs; only this one is OpenAI wire,
    so it is delegated rather than inherited.
    """

    PROVIDER_NAME = "langdock"

    def __init__(self, owner: "LangDockProvider"):
        self._owner = owner
        super().__init__(owner.api_key, owner._get_backend_url(), owner.timeout, owner.max_retries)

    def _token_param(self, model: str) -> str:
        return "max_completion_tokens" if self._owner._uses_new_token_api(model) else "max_tokens"

    def _build_params(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        effort = kwargs.pop("reasoning_effort", None) or self._owner.reasoning_effort
        params = super()._build_params(messages, model, temperature, max_tokens, tools, **kwargs)
        if effort and self._owner._is_reasoning_model(model):
            params["reasoning_effort"] = effort
        return params
```

Add `from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider` to the imports.

- [ ] **Step 4: Wire `LangDockProvider` to the delegate**

- In `__init__`, replace `self._openai_client: Any = None` with `self._openai_backend: _LangDockOpenAIBackend | None = None`.
- Replace the `openai_client` property with:

```python
    def _get_openai_backend(self) -> _LangDockOpenAIBackend:
        if self._openai_backend is None:
            self._openai_backend = _LangDockOpenAIBackend(self)
        return self._openai_backend

    @property
    def openai_client(self) -> Any:
        """OpenAI SDK client for the openai backend (pinned transport, shared base class)."""
        return self._get_openai_backend().client
```

- Replace the bodies of `_openai_chat_completion` and `_openai_stream_completion` (keep their signatures):

```python
        extra = dict(kwargs)
        if reasoning_effort:
            extra["reasoning_effort"] = reasoning_effort
        return self._get_openai_backend().chat_completion(
            messages, model=model, temperature=temperature, max_tokens=max_tokens, tools=tools, **extra
        )
```

```python
        extra = dict(kwargs)
        if reasoning_effort:
            extra["reasoning_effort"] = reasoning_effort
        yield from self._get_openai_backend().stream_completion(
            messages, model=model, temperature=temperature, max_tokens=max_tokens, tools=tools, **extra
        )
```

- In `__del__`, after the `_http_client` block, add:

```python
        backend = getattr(self, "_openai_backend", None)
        if backend is not None:
            try:
                backend.close()
            except (OSError, RuntimeError):
                pass  # Ignore cleanup errors during interpreter shutdown
```

- `_list_openai_models` keeps using `self.openai_client.models.list()` — unchanged. `_uses_new_token_api` and `_is_reasoning_model` stay.

- [ ] **Step 5: Run LangDock wire, existing LangDock unit and compatibility tests**

Run: `uv run pytest tests/unit/test_langdock_openai_wire.py tests/unit/test_public_api_compat.py -q -p no:cacheprovider`
Expected: all passed.
Run: `uv run pytest tests/unit/ -q -p no:cacheprovider -k langdock 2>&1 | grep -E "FAILED|passed|failed"`
Expected: failures only in tests mocking `openai_client`/`_openai_client` for the openai backend — handle in Step 7.

- [ ] **Step 6: Live check**

Run: `uv run pytest tests/integration/test_openai_live.py -q -p no:cacheprovider -m integration -k "LangDock or langdock"`
Expected: the openai-backend tests pass. `test_backend_defaults_are_actually_available` is expected to FAIL for the openai backend (its default `gpt-5.6-luna` is no longer offered — see spec, Evidence). Record that; it is stage 2's job, not a regression of this task.

- [ ] **Step 7: Obsolete mocked tests** — Task 4 Step 7 procedure for the LangDock unit files (only tests of the openai backend); wait for "ja".

- [ ] **Step 8: Coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git add -A src/eq_chatbot_core/providers/langdock_provider.py tests/
git commit -m "[CHG] LangDock: OpenAI-Schiene über die gemeinsame Basisklasse

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Documentation and final verification

**Files:**
- Modify: `CLAUDE.md` and `AGENTS.md` (identical apart from title and line 3)
- Modify: `docs/providers.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: CLAUDE.md / AGENTS.md**

In the module tree change the `openai_compatible.py` comment to `# OpenAICompatibleProvider: shared base for every OpenAI-wire provider` and add `│   ├── param_learning.py   # Learns per endpoint/model whether temperature / max_tokens are accepted`. Under "Provider Base Class" add:

```markdown
Every OpenAI-wire provider (OpenAI, Mammouth, OpenRouter, Local, IONOS, Melious, LiteLLM,
Privatemode, LangDock's `openai` backend) inherits `OpenAICompatibleProvider`. Do not add a
provider with its own request/stream/error code — subclass and override a hook
(`_build_params`, `_token_param`, `_default_headers`, `_client_kwargs`, `list_models`,
`_error_from_message`). Whether a model accepts `temperature` or wants `max_completion_tokens`
is learned at runtime (`providers/param_learning.py`); never add a model to a list to fix it.
```

Apply the same edits to AGENTS.md; verify with `diff CLAUDE.md AGENTS.md` (only lines 1 and 3 differ).

- [ ] **Step 2: `docs/providers.md`** — add a section "Parameter learning" with the paragraph above in user terms, the two adjusted parameters, the one-request cost, and that `list_models()` on OpenRouter pre-seeds it.

- [ ] **Step 3: `CHANGELOG.md`** — add at the top, in the format of the 3.3.0 entry, an `## [Unreleased]` section:
  - Changed: Mammouth, Local, OpenAI, OpenRouter and LangDock's openai backend run on the shared base class; `temperature`/`max_tokens` rejections are retried once and learned per endpoint and model; errors mapped by HTTP status (403 → AuthenticationError, 503/529 → OverloadedError, "token" no longer means context length).
  - Behaviour notes: Mammouth/OpenRouter/Local now use the OpenAI SDK (automatic retries on 429/5xx up to `max_retries`, different message wording); `client` returns an `openai.OpenAI` for those; `OpenAIProvider().base_url` is the effective URL instead of `None`.

- [ ] **Step 4: Final verification**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run pytest tests/integration/ -q -p no:cacheprovider -m integration 2>&1 | grep -E "FAILED|passed|failed|skipped"
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/
wc -l src/eq_chatbot_core/providers/{mammouth,local,openai,openrouter,langdock}_provider.py
```

Expected: unit green with coverage ≥ 83 %; integration failures only where recorded in earlier tasks (OpenRouter key, LangDock default model); line counts clearly below the starting 467 / 520 / 496 / 597 / 2188.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md AGENTS.md docs/providers.md CHANGELOG.md
git commit -m "[CHG] Doku: gemeinsame Basisklasse und lernende Parameter

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Report** — what was verified live and what was not, the list of deleted tests, line-count delta, and the proposal to run the Odoo chatbot module against this state before the 3.4.0 release.
