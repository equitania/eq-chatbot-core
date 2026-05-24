---
phase: 01-contracts-foundation
fixed_at: 2026-05-24T21:52:00Z
review_path: .planning/phases/01-contracts-foundation/01-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-05-24T21:52:00Z
**Source review:** .planning/phases/01-contracts-foundation/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (3 Critical, 5 Warning — Info findings excluded per fix_scope: critical_warning)
- Fixed: 8
- Skipped: 0

## Fixed Issues

### CR-01: `MockRealtimeProvider._iter_impl` hangs forever when queue is empty

**Files modified:** `src/eq_chatbot_core/realtime/mock.py`
**Commit:** `16c27b1`
**Applied fix:** Replaced the blocking `await self._event_queue.get()` in an unconditional
`while True` loop with a non-blocking drain pattern: `while not self._event_queue.empty():
yield self._event_queue.get_nowait()`. Eliminates both the hang on empty queue and the
TOCTOU race between the `empty()` check and the `yield`.

---

### CR-02: `_connection_error_endpoint` is `@abstractmethod` but has a concrete body — URL including embedded secrets leaks

**Files modified:** `src/eq_chatbot_core/realtime/websocket_client.py`
**Commit:** `1264978`
**Applied fix:** Replaced the `return self._url` concrete body (dead code reachable via
`super()`) with `raise NotImplementedError(...)`. The docstring now explicitly states that
overriding is mandatory and no safe default exists. This closes the super()-call path that
could leak unredacted URLs containing embedded API keys into error messages and logs.

---

### CR-03: `connect()` silently swallows the real exception type when `TypeError` fallback itself raises

**Files modified:** `src/eq_chatbot_core/realtime/websocket_client.py`
**Commit:** `21017af`
**Applied fix:** Added module-level import-time detection of which header kwarg
`websockets.connect` accepts via `inspect.signature` (stored in `_CONNECT_HEADERS_KWARG`).
`connect()` now uses `**{_CONNECT_HEADERS_KWARG: self._headers}` directly, removing the
nested try/except TypeError control-flow that silently wrapped secondary TypeErrors as
`RealtimeConnectionError`. Added `import inspect` at module level.

---

### WR-01: Factory `_DEFAULT_REGISTRY` singleton is not thread-safe

**Files modified:** `src/eq_chatbot_core/realtime/factory.py`
**Commit:** `5cb28d3`
**Applied fix:** Added `import threading` and a module-level `_REGISTRY_LOCK = threading.Lock()`.
Applied double-checked locking in `_get_realtime_provider_impl`: outer check without lock,
inner check inside `with _REGISTRY_LOCK:` block to prevent two threads from both building
the registry on first call.

---

### WR-02: `connect_with_backoff` does not retry on `RealtimeRateLimitError`

**Files modified:** `src/eq_chatbot_core/realtime/websocket_client.py`
**Commit:** `0c1a2ba`
**Applied fix:** Changed the except clause to `except (RealtimeConnectionError, RealtimeRateLimitError)`.
When the caught exception is a `RealtimeRateLimitError` with `retry_after` set, that value is
used as the delay (capped at `max_delay_s`); otherwise standard exponential backoff applies.
Updated `last_exc` type annotation to `RealtimeClientError`. Updated the final raised error
message to include `"(last error: RealtimeRateLimitError)"` when applicable.

---

### WR-03: `NormalizedRealtimeEvent` TypedDict with `total=False` makes `type` optional

**Files modified:** `src/eq_chatbot_core/realtime/contracts.py`, `tests/unit/realtime/test_contracts.py`
**Commit:** `9639282`
**Applied fix:** Split `NormalizedRealtimeEvent` (total=True by default) to contain only
the required keys `type: str` and `payload: dict[str, Any]`. Added a new subclass
`NormalizedRealtimeEventFull(NormalizedRealtimeEvent, total=False)` for the optional keys
`source` and `raw`. Added `NormalizedRealtimeEventFull` to `contracts.py __all__`. Updated
`test_normalized_event_typeddict` to import and assert against both classes, and to explicitly
verify `source`/`raw` are absent from the base class.
**Note:** `NormalizedRealtimeEventFull` is a new exported name. Any consumer code creating
`NormalizedRealtimeEvent` dicts that includes `source` or `raw` should type-annotate with
`NormalizedRealtimeEventFull` instead — this is a forward-compatible widening change.

---

### WR-04: `mock_websockets_module` fixture is session-scoped and permanently pollutes `sys.modules`

**Files modified:** `tests/unit/realtime/conftest.py`
**Commit:** `e8bcef7`
**Applied fix:** Snapshot the original `sys.modules["websockets"]` and
`sys.modules["websockets.exceptions"]` values before installing the mock. Added teardown code
after `yield` that restores the originals (or pops the key if the original was absent).
Removed the incorrect comment "do NOT restore sys.modules after session". Updated the fixture
docstring to document the restore behaviour.

---

### WR-05: `ToolDefinition` added to `base.py` but not exported from `base.py.__all__`

**Files modified:** `src/eq_chatbot_core/providers/base.py`
**Commit:** `29df819`
**Applied fix:** Added an `__all__` list to the end of `base.py` enumerating all public
types and exceptions: `LLMResponse`, `StreamChunk`, `ToolDefinition`, `ModelInfo`,
`BaseLLMProvider`, `ProviderError`, `RateLimitError`, `AuthenticationError`,
`ContextLengthError`, `OverloadedError`. This makes the cross-subsystem `ToolDefinition`
contract explicitly visible in the module surface.

---

## Skipped Issues

None — all 8 in-scope findings were fixed.

---

_Fixed: 2026-05-24T21:52:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
