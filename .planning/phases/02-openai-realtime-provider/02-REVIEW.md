---
phase: 02-openai-realtime-provider
reviewed: 2026-05-24T22:30:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/eq_chatbot_core/realtime/providers/openai.py
  - src/eq_chatbot_core/realtime/websocket_client.py
  - src/eq_chatbot_core/realtime/factory.py
  - src/eq_chatbot_core/realtime/__init__.py
  - tests/unit/realtime/test_realtime_openai.py
  - tests/integration/test_realtime_openai_live.py
findings:
  critical: 3
  warning: 5
  info: 2
  total: 10
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-24T22:30:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

This review covers the OpenAI Realtime WebSocket provider ported from GlassAgents. The
transport layer (`websocket_client.py`) and the provider implementation (`openai.py`) are
well-structured and the API-key-in-URL security requirement (T-02-01) is satisfied —
the API key travels only in the `Authorization` header, never in the WebSocket URL.

Three blockers were identified: (1) the `session.update` payload uses undocumented field
names that diverge from the published OpenAI Realtime API spec, meaning every live session
initialization will either be silently ignored or rejected; (2) `recv_json()` raises an
uncaught `AttributeError` if `close()` races with an active `iter_events()` loop; (3)
the `_build_openai_provider` factory raises a bare `KeyError` instead of a diagnostic
`ValueError` when `api_key` is omitted. Five warnings cover error-handling gaps, an
unreachable error class, `__all__` contract drift, and a brittle integration test assertion.

---

## Critical Issues

### CR-01: Wrong field names in `session.update` payload — API calls will fail silently

**File:** `src/eq_chatbot_core/realtime/providers/openai.py:177-191`

**Issue:** `_build_session_update_event` constructs the inner `session` dict with two
field names that do not exist in the OpenAI Realtime API specification:

1. `session["type"] = "realtime"` — the session configuration object has no `type` field.
   Only the outer event envelope has a `type` key (`"session.update"`). Sending an
   unknown key may be silently ignored or cause validation rejection depending on API
   version.

2. `"output_modalities": ["audio"]` — the correct field name in the OpenAI Realtime API
   is `"modalities"` (not `"output_modalities"`). With the wrong key the session will use
   the server default modalities (text + audio), which may differ from the intended
   audio-only configuration.

Both field names originate verbatim from the GlassAgents internal reference and were
carried over without validation against the published OpenAI API schema. The integration
test (`test_realtime_openai_live.py`) would catch the rejection only if the server returns
an error event, but the test exits after the first `SESSION_READY` event — before the
session configuration is confirmed.

**Fix:**
```python
session: dict[str, Any] = {
    # Remove "type": "realtime" — no such field in the session object
    "model": self._config.model,
    "instructions": resolved_instructions,
    "modalities": ["audio"],          # was "output_modalities"
    "input_audio_format": "pcm16",    # flat string, not nested object
    "output_audio_format": "pcm16",   # flat string, not nested object
    "voice": resolved_voice,
}
# Move voice out of the nested audio.output dict — top-level in OpenAI spec
# Remove the "audio": {"input": {...}, "output": {...}} structure entirely;
# use input_audio_format / output_audio_format top-level keys instead.
```

Cross-reference the OpenAI Realtime API reference at
`https://platform.openai.com/docs/api-reference/realtime-client-events/session/update`
before applying this fix.

---

### CR-02: `recv_json()` raises `AttributeError` when `close()` races with `iter_events()`

**File:** `src/eq_chatbot_core/realtime/websocket_client.py:201`

**Issue:** `recv_json()` directly calls `self._ws.recv()` without a None guard. If
`close()` is called concurrently while `iter_events()` is blocking on `recv_json()`,
the following sequence is possible:

1. `iter_events()` calls `recv_json()` — `self._ws` is not None, loop continues.
2. `close()` sets `self._ws = None` in the `finally` block.
3. `self._ws.recv()` executes with `self._ws` now being `None` — raises `AttributeError`.

`AttributeError` is not caught by the `except Exception` block in `recv_json()` (it is
caught, but the isinstance check for `ws_exceptions.ConnectionClosed` fails, so it
propagates as a raw `AttributeError`). The caller receives an `AttributeError` instead of
`RealtimeClosedError`, breaking the documented exception contract.

**Fix:**
```python
async def recv_json(self) -> dict[str, Any]:
    ws = self._ws  # capture reference to avoid TOCTOU race
    if ws is None:
        raise RealtimeClosedError("WebSocket is not connected", code=None, retriable=False)
    try:
        raw: Any = await ws.recv()
    except Exception as exc:
        if ws_exceptions is not None and isinstance(exc, ws_exceptions.ConnectionClosed):
            code = getattr(exc, "code", None) or getattr(
                getattr(exc, "rcvd", None), "code", None
            )
            retriable = code != 1000
            raise RealtimeClosedError(
                "WebSocket closed", code=code, retriable=retriable
            ) from exc
        raise
    result: dict[str, Any] = json.loads(raw)
    return result
```

---

### CR-03: `_build_openai_provider` raises `KeyError` when `api_key` is missing

**File:** `src/eq_chatbot_core/realtime/factory.py:74`

**Issue:** `kwargs.pop("api_key")` raises a bare `KeyError` when the caller omits
`api_key`. The public entry point `get_realtime_provider("openai")` will surface a
`KeyError: 'api_key'` to callers, which violates the D-03 fail-fast convention
(library-native exceptions with diagnostic messages) and is especially confusing because
the error gives no indication of which argument is missing or how to fix it.

**Fix:**
```python
def _build_openai_provider(**kwargs: Any) -> Any:
    from eq_chatbot_core.realtime.providers.openai import (  # noqa: PLC0415
        OpenAIRealtimeClient,
        OpenAIRealtimeConfig,
    )

    api_key = kwargs.pop("api_key", None)
    if not api_key:
        raise ValueError(
            "get_realtime_provider('openai', ...) requires api_key=<your OpenAI API key>. "
            "Example: get_realtime_provider('openai', api_key='sk-...')"
        )
    config = OpenAIRealtimeConfig(api_key=api_key, **kwargs)
    return OpenAIRealtimeClient(config)
```

---

## Warnings

### WR-01: `send_json()` does not wrap `ws.send()` exceptions in `RealtimeClientError`

**File:** `src/eq_chatbot_core/realtime/websocket_client.py:193`

**Issue:** `send_json()` guards on `is_connected` before sending, but if the connection
drops between the guard check and `self._ws.send(json.dumps(data))`, the underlying
`websockets` exception (e.g. `ConnectionClosed`) propagates unwrapped. The method's
docstring only documents `RealtimeConnectionError`, creating a broken exception contract.
Callers expecting to catch only `RealtimeClientError` subclasses will have an unhandled
exception from a live session.

**Fix:** Wrap the send call:
```python
async def send_json(self, data: dict[str, Any]) -> None:
    if not self.is_connected:
        raise RealtimeConnectionError("Cannot send: WebSocket is not connected")
    try:
        await self._ws.send(json.dumps(data))
    except Exception as exc:
        if ws_exceptions is not None and isinstance(exc, ws_exceptions.ConnectionClosed):
            raise RealtimeClosedError("WebSocket closed during send") from exc
        raise RealtimeConnectionError(f"Send failed: {exc}") from exc
```

---

### WR-02: `RealtimeProtocolError` is defined but never raised — dead code

**File:** `src/eq_chatbot_core/realtime/websocket_client.py:88-89`

**Issue:** `RealtimeProtocolError` is declared, exported in `__all__`, and documented
("Raised when a malformed or unexpected frame is received"), but it is never raised
anywhere in the codebase. `recv_json()` calls `json.loads()` without a try/except, so a
malformed JSON frame raises `json.JSONDecodeError` — a stdlib exception that is not a
`RealtimeClientError` subclass, silently breaking the exception hierarchy.

**Fix:** Raise `RealtimeProtocolError` on decode failure in `recv_json()`:
```python
try:
    result: dict[str, Any] = json.loads(raw)
except json.JSONDecodeError as exc:
    raise RealtimeProtocolError(f"Invalid JSON frame received: {exc}") from exc
return result
```

---

### WR-03: `__all__` in `realtime/__init__.py` lists names that may not be defined

**File:** `src/eq_chatbot_core/realtime/__init__.py:96-98`

**Issue:** `__all__` unconditionally lists `"OpenAIRealtimeClient"`, `"OpenAIRealtimeConfig"`,
and `"OPENAI_REALTIME_CAPABILITIES"`, but these names are imported inside a bare
`try/except ImportError` block (lines 44-51) that silently swallows `ImportError` when
`websockets` is absent. When the `[realtime]` extra is not installed, `from
eq_chatbot_core.realtime import *` will raise `AttributeError` for each name in `__all__`
that was not bound. The `try/except` suppression is appropriate, but `__all__` must not
advertise names that may be absent.

**Fix:** Remove the three conditional names from `__all__`, or add a guard:
```python
# Only advertise OpenAI provider names when websockets is available
try:
    from eq_chatbot_core.realtime.providers.openai import (
        OPENAI_REALTIME_CAPABILITIES,
        OpenAIRealtimeClient,
        OpenAIRealtimeConfig,
    )
    _OPENAI_EXPORTS = ["OpenAIRealtimeClient", "OpenAIRealtimeConfig", "OPENAI_REALTIME_CAPABILITIES"]
except ImportError:
    _OPENAI_EXPORTS = []

__all__ = [
    "get_realtime_provider",
    ...  # non-conditional exports
    *_OPENAI_EXPORTS,
]
```

---

### WR-04: `connect_with_backoff` does not validate `max_attempts >= 1`

**File:** `src/eq_chatbot_core/realtime/websocket_client.py:230-277`

**Issue:** If called with `max_attempts=0`, `range(0)` is empty — the loop body never
executes, `last_exc` remains `None`, and the code falls through to
`raise RealtimeConnectionError(...) from last_exc` where `last_exc` is `None`. This
raises an error before any connection attempt, with the misleading message "Failed to
connect after 0 attempts" and no chained cause. While not a crash, callers using 0 to
mean "unlimited" (a common misuse) will be silently broken.

**Fix:** Add a precondition guard at the start of the method:
```python
if max_attempts < 1:
    raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
```

---

### WR-05: Integration test asserts first event type without timeout — test can hang indefinitely

**File:** `tests/integration/test_realtime_openai_live.py:41-44`

**Issue:** The `async for event in client.iter_normalized_events()` loop has no timeout.
If the OpenAI Realtime API never sends a `session.created` or `session.updated` event
(e.g. due to a delayed response or network stall), the test hangs indefinitely. The
`break` after the assertion means only one event is consumed, but `iter_normalized_events`
calls `iter_events()` → `recv_json()` → `self._ws.recv()` which blocks forever without a
timeout.

Additionally, the assertion `assert event["type"] == SESSION_READY` fires on the first
event only — if the API sends any other event first (e.g. an `error` event due to model
validation failure from CR-01), the test fails with a misleading message about the event
type rather than the underlying cause.

**Fix:**
```python
import asyncio

async with OpenAIRealtimeClient(config) as client:
    session_ready = False
    try:
        async with asyncio.timeout(10):  # Python 3.11+; use asyncio.wait_for for 3.10
            async for event in client.iter_normalized_events():
                if event["type"] == NormalizedRealtimeEventTypes.SESSION_READY:
                    session_ready = True
                    break
                if event["type"] == NormalizedRealtimeEventTypes.ERROR:
                    pytest.fail(f"Provider returned error: {event['payload']}")
    except TimeoutError:
        pytest.fail("Timed out waiting for SESSION_READY event")
    assert session_ready
```

---

## Info

### IN-01: `_on_message` is a required ABC stub with no production use — document intent

**File:** `src/eq_chatbot_core/realtime/providers/openai.py:124-128`

**Issue:** `_on_message` is implemented as a pass-through stub with a comment explaining
it exists for "ABC conformance only." The base class `@abstractmethod` declaration forces
all subclasses to implement it even when the production path uses `iter_events()` instead.
This is not a bug but creates maintainer confusion: future subclass authors may implement
logic here and be surprised it is never called by the production event loop.

**Fix:** The comment is partially mitigating this. Consider making the non-use explicit:
```python
async def _on_message(self, raw: str) -> None:
    """Not called in production — iter_normalized_events() is the primary event loop.
    Exists only to satisfy BaseRealtimeWebsocketClient ABC. Do not add logic here.
    """
```

---

### IN-02: `NormalizedRealtimeEventFull` is not exported from `realtime/__init__.py`

**File:** `src/eq_chatbot_core/realtime/__init__.py:74-99`

**Issue:** `NormalizedRealtimeEventFull` is defined in `contracts.py`, used as the return
type annotation of `iter_normalized_events()` and `_to_normalized_runtime_event()` in
`openai.py`, and exported from `contracts.py`'s `__all__`. However, it is not included
in `realtime/__init__.py`'s `__all__` and cannot be imported via
`from eq_chatbot_core.realtime import NormalizedRealtimeEventFull`. Callers who want to
type-annotate event handlers have to reach into the internal submodule
`eq_chatbot_core.realtime.contracts` directly.

**Fix:** Add `NormalizedRealtimeEventFull` to the imports and `__all__` in `__init__.py`:
```python
from eq_chatbot_core.realtime.contracts import (  # noqa: E402
    INPUT_AUDIO_SAMPLE_RATE,
    NormalizedRealtimeEvent,
    NormalizedRealtimeEventFull,   # add this
    NormalizedRealtimeEventTypes,
    RealtimeAdapterContract,
    RealtimeProviderCapabilities,
)
```

---

_Reviewed: 2026-05-24T22:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
