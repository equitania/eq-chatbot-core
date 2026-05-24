---
phase: 01-contracts-foundation
reviewed: 2026-05-24T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - pyproject.toml
  - src/eq_chatbot_core/providers/__init__.py
  - src/eq_chatbot_core/providers/base.py
  - src/eq_chatbot_core/realtime/__init__.py
  - src/eq_chatbot_core/realtime/abc.py
  - src/eq_chatbot_core/realtime/contracts.py
  - src/eq_chatbot_core/realtime/factory.py
  - src/eq_chatbot_core/realtime/mock.py
  - src/eq_chatbot_core/realtime/providers/__init__.py
  - src/eq_chatbot_core/realtime/websocket_client.py
  - tests/unit/realtime/__init__.py
  - tests/unit/realtime/conftest.py
  - tests/unit/realtime/test_contracts.py
  - tests/unit/realtime/test_factory.py
  - tests/unit/realtime/test_import_guard.py
  - tests/unit/realtime/test_mock.py
  - tests/unit/realtime/test_pyproject.py
  - tests/unit/realtime/test_websocket_client.py
findings:
  critical: 3
  warning: 5
  info: 4
  total: 12
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-05-24
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

The realtime subsystem introduces clean structural choices: a stdlib-only `MockRealtimeProvider`,
a `@runtime_checkable` Protocol contract, typed event dataclasses with frozen slots, and a
lazy-init registry factory. The broad shape is sound.

Three blockers were found. The most severe is an unbounded `asyncio.Queue` in `MockRealtimeProvider`
that blocks forever when the queue is empty and no more events are enqueued — the iterator never
terminates in production-like usage and any consumer awaiting it will hang. A second blocker is
a silent API key leak in `send_json` / `recv_json`: both operate without checking `self.is_connected`
consistently, but more critically `websocket_client.connect()` silently catches *all* exceptions
from the outer `try/except` block and re-raises them as `RealtimeConnectionError` even when the
inner `TypeError` fallback itself raises — leaking the real error type to callers in an unexpected
way. The third blocker is a protocol-conformance gap: the `_connection_error_endpoint` method is
marked `@abstractmethod` but has a concrete default body — subclasses that do not override it will
inherit the full URL (potentially including embedded API keys) in error messages and logs.

Warnings cover: the factory singleton being process-global and thread-unsafe; `connect_with_backoff`
not retrying on `RealtimeRateLimitError`; the `mock_websockets_module` fixture being session-scoped
yet mutating `sys.modules` permanently; the `ToolDefinition` dataclass being added to `base.py`
without appearing in the existing `__all__` list of `base.py`; and the `NormalizedRealtimeEvent`
TypedDict using `total=False` which makes every key optional including `type`.

---

## Critical Issues

### CR-01: `MockRealtimeProvider._iter_impl` hangs forever when queue is empty

**File:** `src/eq_chatbot_core/realtime/mock.py:72`
**Issue:** `_iter_impl` calls `await self._event_queue.get()` inside an unconditional `while True`
loop. When the queue has been fully drained (`self._event_queue.empty()` is `True` after the
`yield`), the method breaks — but only *after* yielding the last item. However, if the queue starts
empty (no events enqueued) or if the consumer requests the iterator again after draining, the first
`await self._event_queue.get()` will block indefinitely because `asyncio.Queue.get()` suspends
until an item is available. This means any consumer using `async for ev in provider.iter_normalized_events()`
against an un-populated mock will hang forever, not raise, not stop.

This also creates a second subtle bug: the `empty()` check on line 75 is a TOCTOU race under
concurrent usage because `empty()` is checked *after* yielding to the consumer, during which
another coroutine could enqueue a new item. The check is not atomically tied to `get()`.

**Fix:**
```python
async def _iter_impl(self) -> AsyncIterator[dict[str, Any]]:
    """Drain all currently-queued events and stop. Non-blocking."""
    while not self._event_queue.empty():
        yield self._event_queue.get_nowait()
```
If blocking-until-signaled semantics are required in the future, add an explicit sentinel:
```python
SENTINEL = object()

def stop(self) -> None:
    """Signal the iterator to stop."""
    self._event_queue.put_nowait(SENTINEL)

async def _iter_impl(self) -> AsyncIterator[dict[str, Any]]:
    while True:
        event = await self._event_queue.get()
        if event is SENTINEL:
            break
        yield event
```

---

### CR-02: `_connection_error_endpoint` is `@abstractmethod` but has a concrete body — URL (including embedded secrets) leaks into error messages and logs

**File:** `src/eq_chatbot_core/realtime/websocket_client.py:110-116`
**Issue:** The method is declared `@abstractmethod`, which correctly forces subclasses to override
it. However, its concrete default body (`return self._url`) is dead code that Python will never
execute for abstract methods — subclasses that accidentally call `super()._connection_error_endpoint()`
will return the unredacted URL.

More critically: the docstring says "Default returns self._url unchanged (safe only for providers
that don't embed secrets in URL)" and the method is abstract, yet the real production fallback
(if a future subclass does not override) would execute `return self._url` from the *abstract*
method body through `super()`. This inconsistency documents a safe default while the abstract
contract provides no guarantee — and lulls future implementors into thinking the fallback is benign.
Phase 2/3 providers that embed API keys in the WebSocket URL (a common pattern for OpenAI Realtime
`wss://api.openai.com/v1/realtime?model=...&api_key=sk-...`) will leak key fragments into logs and
exception messages if they forget to override this method and Python calls the abstract body.

The real danger: Python *does* allow calling the body of an abstract method via `super()`, so the
"safe fallback" body is reachable and dangerous.

**Fix:** Remove the body from the abstract declaration entirely, making the contract explicit:
```python
@abstractmethod
def _connection_error_endpoint(self) -> str:
    """Return a REDACTED URL string safe for error messages and logs.

    You MUST override this and strip API keys.
    Raise NotImplementedError if called directly (no safe default exists).
    """
    raise NotImplementedError(
        "_connection_error_endpoint must be overridden to redact secrets from URL"
    )
```
Alternatively, make it a non-abstract method that raises, removing the `@abstractmethod` decorator
and relying on subclass responsibility documented in the docstring — but that removes compile-time
enforcement.

---

### CR-03: `connect()` silently swallows the real exception type when `TypeError` fallback itself raises

**File:** `src/eq_chatbot_core/realtime/websocket_client.py:129-154`
**Issue:** The `connect()` method uses a nested try/except to handle the `websockets` API version
difference (`additional_headers` vs `extra_headers`). The structure is:

```python
try:
    try:
        connection = websockets.connect(self._url, additional_headers=self._headers)
    except TypeError:
        connection = websockets.connect(self._url, extra_headers=self._headers)
    self._ws = await connection
except Exception as exc:
    status_code = getattr(...)
    if status_code == 429:
        raise RealtimeRateLimitError(...) from exc
    raise RealtimeConnectionError(...) from exc
```

If `websockets.connect(self._url, extra_headers=self._headers)` also raises `TypeError` (e.g.,
because `self._url` itself is invalid, or both keyword arguments are rejected), that `TypeError`
propagates to the outer `except Exception` block and is wrapped as `RealtimeConnectionError`.
The caller loses the `TypeError` signal entirely. More dangerously: if `websockets.connect()`
raises a non-TypeError `Exception` inside the inner try (e.g., `OSError`, `ValueError`), it
bypasses the fallback attempt entirely and is immediately caught by the outer handler — which is
correct. But if the inner `TypeError` fallback raises `TypeError` again from the `extra_headers`
call, it is re-caught as `RealtimeConnectionError` with a misleading "Failed to connect to..."
message, hiding the real cause (bad argument types, wrong API, etc.).

Additionally, `await connection` is outside both inner try/except arms. If the inner try raises
`TypeError`, execution goes to the `except TypeError` fallback, which sets `connection`, and
then **falls through to `self._ws = await connection`** in the outer try scope. But if the
`except TypeError` block itself raises, `connection` is never assigned, `await connection` is
never reached, and the outer except catches the new exception — which is correct but untestable.

**Fix:** Use explicit version detection instead of exception-as-control-flow:
```python
import websockets

_USES_ADDITIONAL_HEADERS = hasattr(websockets, "connect")  # always True
# Check kwarg at import time
import inspect as _inspect
_ADDITIONAL_HEADERS_KWARG = "additional_headers" in _inspect.signature(websockets.connect).parameters

async def connect(self) -> None:
    if self.is_connected:
        return
    try:
        kwargs = {"additional_headers" if _ADDITIONAL_HEADERS_KWARG else "extra_headers": self._headers}
        self._ws = await websockets.connect(self._url, **kwargs)
    except Exception as exc:
        ...
```
If the try/except fallback approach must be kept, at minimum assert `connection` is bound before
`await connection` and add a test for double-TypeError.

---

## Warnings

### WR-01: Factory `_DEFAULT_REGISTRY` singleton is not thread-safe

**File:** `src/eq_chatbot_core/realtime/factory.py:56-74`
**Issue:** The module-level singleton `_DEFAULT_REGISTRY` is lazily initialized using a
`global` variable with a `None` check. Under concurrent access (multiple threads calling
`_get_realtime_provider_impl` for the first time simultaneously), the `if _DEFAULT_REGISTRY is None`
check and the assignment `_DEFAULT_REGISTRY = build_default_realtime_provider_registry()` are
not atomic. Two threads can both see `None`, both build a registry, and the second assignment
silently clobbers the first. While Phase 1 only registers `"mock"`, Phase 2/3 will add real
providers and the race becomes a correctness issue.

**Fix:**
```python
import threading
_REGISTRY_LOCK = threading.Lock()
_DEFAULT_REGISTRY: RealtimeProviderRegistry | None = None

def _get_realtime_provider_impl(name: str, **kwargs: Any) -> Any:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        with _REGISTRY_LOCK:
            if _DEFAULT_REGISTRY is None:  # double-checked locking
                _DEFAULT_REGISTRY = build_default_realtime_provider_registry()
    ...
```

---

### WR-02: `connect_with_backoff` does not retry on `RealtimeRateLimitError`

**File:** `src/eq_chatbot_core/realtime/websocket_client.py:219-240`
**Issue:** The backoff loop catches only `RealtimeConnectionError`. `RealtimeRateLimitError` is a
sibling class (both inherit `RealtimeClientError`) and is raised by `connect()` on HTTP 429.
A rate-limited connection attempt escapes the retry loop and propagates immediately, even though
the whole point of `connect_with_backoff` is to handle transient failures. A 429 during WebSocket
handshake is exactly the scenario where backoff with `retry_after` is the correct response.

**Fix:**
```python
except (RealtimeConnectionError, RealtimeRateLimitError) as exc:
    last_exc = exc
    if isinstance(exc, RealtimeRateLimitError) and exc.retry_after is not None:
        delay = min(exc.retry_after, max_delay_s)
    elif attempt < max_attempts - 1:
        delay = min(base_delay_s * (2**attempt) + random.uniform(0, 1), max_delay_s)
    else:
        break
    _logger.warning(...)
    await asyncio.sleep(delay)
```
Also update the final `raise` to include `RealtimeRateLimitError` in the error message.

---

### WR-03: `NormalizedRealtimeEvent` TypedDict with `total=False` makes `type` optional — breaks all isinstance/key guards

**File:** `src/eq_chatbot_core/realtime/contracts.py:36-43`
**Issue:** `NormalizedRealtimeEvent` is declared with `total=False`, meaning every key —
including `type` — is optional. Any consumer code doing `event["type"]` will encounter a
`KeyError` for events that do not include the key, and type-checkers will not catch this because
`total=False` says the key is validly absent. The `type` key is the primary dispatch key for
all consumers; it must be required.

**Fix:** Make `type` and `payload` required, and only `source` / `raw` optional:
```python
class NormalizedRealtimeEvent(TypedDict):
    """Required keys."""
    type: str
    payload: dict[str, Any]

class NormalizedRealtimeEventOptional(NormalizedRealtimeEvent, total=False):
    """Optional keys."""
    source: str
    raw: Any
```
Or, if the single-class form is preferred:
```python
class NormalizedRealtimeEvent(TypedDict, total=True):
    type: str
    payload: dict[str, Any]
    source: str      # use NotRequired[str] on Python 3.11+
    raw: Any         # use NotRequired[Any] on Python 3.11+
```
For Python 3.10 compatibility use the inheritance split shown above.

---

### WR-04: `mock_websockets_module` fixture is session-scoped and permanently pollutes `sys.modules`

**File:** `tests/unit/realtime/conftest.py:13-58`
**Issue:** The comment on line 58 explicitly says "do NOT restore sys.modules after session".
This means the mock websockets module is injected permanently for the entire test session.
If any integration test or other unit test in the same pytest session imports `websockets`
expecting the real library (e.g., to test the actual WebSocket handshake), it will receive the
mock. This is intentional for the realtime unit tests, but the comment "do NOT restore" is
wrong guidance — it should at minimum restore after the session ends (yield-fixture semantics
already support this). The fixture yields, so teardown code after `yield` would run correctly.

Additionally, the fixture is `autouse=True` at session scope, which means it fires for *all*
tests in the session, not just the realtime tests. If a non-realtime test imports websockets,
it will get the mock silently.

**Fix:** Scope the autouse to the `tests/unit/realtime/` directory by moving the fixture to
a `conftest.py` that is *only* in that directory (which it already is — but `autouse=True`
propagates upward if the session shares the root conftest). Add teardown:
```python
yield mock_ws_module
# Restore after session so integration tests in same run get real websockets
if original_websockets is not None:
    sys.modules["websockets"] = original_websockets
else:
    sys.modules.pop("websockets", None)
if original_ws_exc is not None:
    sys.modules["websockets.exceptions"] = original_ws_exc
else:
    sys.modules.pop("websockets.exceptions", None)
```

---

### WR-05: `ToolDefinition` added to `base.py` but not exported from `base.py.__all__`

**File:** `src/eq_chatbot_core/providers/base.py`
**Issue:** `ToolDefinition` is defined in `base.py` (line 68) and explicitly re-exported in
`providers/__init__.py` (line 187), but `base.py` does not define `__all__`. While this is
not a runtime error, it means `from eq_chatbot_core.providers.base import *` would not include
`ToolDefinition`, and static analysis tools that rely on `__all__` for module surface discovery
will miss it. More importantly, the new `ToolDefinition` dataclass is the first type shared
between the chat and realtime subsystems — it deserves explicit documentation in the export
surface of `base.py` to make the cross-subsystem contract visible.

**Fix:** Add `__all__` to `base.py`:
```python
__all__ = [
    "LLMResponse",
    "StreamChunk",
    "ToolDefinition",
    "ModelInfo",
    "BaseLLMProvider",
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    "ContextLengthError",
    "OverloadedError",
]
```

---

## Info

### IN-01: `test_connect_with_backoff_all_failures_raises` makes real `asyncio.sleep` calls

**File:** `tests/unit/realtime/test_websocket_client.py:75-81`
**Issue:** The test passes `base_delay_s=0.0` to minimize sleep duration, but does not patch
`asyncio.sleep`. With `max_attempts=5` and no real WebSocket available, the test will call
`asyncio.sleep(0.0)` four times. While this is nearly instantaneous, it is a side-effect-leaking
pattern that slows test suites under load and should be patched for correctness.

**Fix:** Add `patch("eq_chatbot_core.realtime.websocket_client.asyncio.sleep")` as the
companion tests do, or at minimum document the intent with a comment.

---

### IN-02: `_connection_error_endpoint` in `test_websocket_client.py` returns a hardcoded string, not `self._url`

**File:** `tests/unit/realtime/test_websocket_client.py:32-35`
**Issue:** `ConcreteTestClient._connection_error_endpoint` returns `"ws://test-endpoint"` while
the constructor is called with `url="ws://test"`. The test is therefore testing a disconnect
between the URL used and the endpoint string in error messages. This is fine for unit tests but
means that no test actually verifies that error messages reflect the real URL, and the redaction
contract is never exercised by the test suite.

**Fix:** Minor: Add a dedicated test that constructs a client with a URL containing a mock
"api_key" query parameter and asserts the error message does not include the key value.

---

### IN-03: `test_import_guard_friendly_error` relies on module-level caching artifact

**File:** `tests/unit/realtime/test_import_guard.py:13-32`
**Issue:** The test pops `websockets` from `sys.modules`, then re-imports `get_realtime_provider`
from `eq_chatbot_core.realtime`. Because `eq_chatbot_core.realtime` is already cached in
`sys.modules` from a previous test, the `from eq_chatbot_core.realtime import get_realtime_provider`
does not re-execute the module-level code — it just fetches the already-cached function object.
The test only works because `get_realtime_provider` does the `import websockets` check lazily
at call time (inside the function body), not at module import time. This is correct behavior,
but the test comment does not document this dependency. If `get_realtime_provider` were
refactored to eager-import websockets at module level, the test would silently stop testing
what it claims.

**Fix:** Add a comment: `# This test relies on get_realtime_provider performing the websockets
# import lazily inside the function body, not at module import time.`

---

### IN-04: `openai>=2.0.0,<3.0.0` version constraint is unusually broad

**File:** `pyproject.toml:34`
**Issue:** The openai SDK made breaking changes between 0.x and 1.x, and between 1.x and 2.x.
Allowing all `2.x` versions up to (but not including) `3.0` means the library will silently
accept openai 2.x releases that may not yet exist and may introduce breaking changes. The
`anthropic>=0.90.0,<2.0.0` constraint is similarly broad. This is a packaging policy concern
rather than a hard bug, but could cause unexpected breakage when new major-minor releases ship.

**Fix:** Either tighten to `openai>=2.0.0,<2.1.0` (pinning to tested minor), or document in
CHANGELOG/README that the upper bound is intentionally loose and tested across minor versions.

---

_Reviewed: 2026-05-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
