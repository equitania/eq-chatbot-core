---
phase: 01-contracts-foundation
plan: "03"
subsystem: realtime
tags: [websockets, asyncio, backoff, error-hierarchy, abc, transport-layer]

requires:
  - phase: 01-01
    provides: "NormalizedRealtimeEventTypes, RealtimeAdapterContract, RealtimeProviderCapabilities contracts"
  - phase: 01-02
    provides: "AsyncMock websockets fixture in conftest.py; realtime test package infrastructure"

provides:
  - "BaseRealtimeWebsocketClient ABC with connect/send_json/recv_json/close lifecycle"
  - "connect_with_backoff() with truncated exponential backoff and jitter (max_delay_s cap)"
  - "Error hierarchy: RealtimeClientError, RealtimeConnectionError, RealtimeClosedError(code, retriable), RealtimeRateLimitError(retry_after), RealtimeProtocolError"
  - "Connection-leak protection: _on_connected() failure triggers close() via try/finally (PITFALL-04)"
  - "HTTP 429 cross-version detection via attribute introspection (legacy + new asyncio websockets impl)"
  - "_connection_error_endpoint() abstract hook prevents API key leakage in error messages"
  - "__aenter__/__aexit__ async context manager protocol"
  - "6 unit tests: backoff 3-failure-then-success, all-failures-raise, error fields, hierarchy"

affects:
  - "02-openai-realtime (inherits BaseRealtimeWebsocketClient)"
  - "03-gemini-live (inherits BaseRealtimeWebsocketClient)"
  - "consumers of realtime/websocket_client.py error hierarchy"

tech-stack:
  added: []
  patterns:
    - "Import guard: _websockets_available bool flag; no type:ignore needed in strict mypy when library IS installed"
    - "Backoff with deterministic test path: patch asyncio.sleep + random.uniform at module level"
    - "Cross-version attribute introspection for HTTP status from WS handshake exceptions"
    - "Abstract hook _connection_error_endpoint() for URL redaction (security pattern T-03-01/T-03-02)"

key-files:
  created:
    - src/eq_chatbot_core/realtime/websocket_client.py
    - tests/unit/realtime/test_websocket_client.py
  modified: []

key-decisions:
  - "RealtimeClientError inherits from Exception (NOT ProviderError) — transport layer is separate from provider-API layer"
  - "type:ignore comments removed from import guard except-branch None assignments — strict mypy flags them as unused when library is installed; they are not needed"
  - "Task 1 checkpoint auto-approved — websockets dry-run confirmed single clean package (websockets==16.0, no transitive deps)"

patterns-established:
  - "Import guard without type:ignore in except-branch: strict mypy does not analyze unreachable branches; comments would be flagged unused when library is present"
  - "Backoff patch targets: eq_chatbot_core.realtime.websocket_client.asyncio.sleep and .random.uniform"

requirements-completed:
  - CON-08

duration: 7min
completed: "2026-05-24"
---

# Phase 01 Plan 03: WebSocket Base Client + Error Hierarchy Summary

**BaseRealtimeWebsocketClient ABC with connection-leak-safe connect, truncated exponential backoff, cross-version HTTP 429 detection, and a 5-class realtime error hierarchy**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-24T19:16:54Z
- **Completed:** 2026-05-24T19:23:07Z
- **Tasks:** 2 (Task 1 checkpoint auto-approved via dry-run)
- **Files modified:** 2

## Accomplishments

- `BaseRealtimeWebsocketClient` ABC provides the shared transport base for all concrete realtime providers (OpenAI, Gemini Live in later phases)
- `connect_with_backoff()` implements truncated exponential backoff with jitter, fully testable by patching `asyncio.sleep` and `random.uniform` at module level
- 5-class error hierarchy (`RealtimeClientError` → `RealtimeConnectionError`, `RealtimeClosedError`, `RealtimeRateLimitError`, `RealtimeProtocolError`) isolates transport errors from provider-API errors
- `_connection_error_endpoint()` abstract hook enforces URL redaction in error messages (addresses T-03-01/T-03-02 threat model items)
- All 6 unit tests pass including the key backoff test asserting delays of [1.0, 2.0, 4.0] seconds

## Task Commits

Each task was committed atomically:

1. **Task 1: websockets package dry-run checkpoint** - auto-approved (no commit — verification only)
2. **Task 2: Create websocket_client.py** - `51c650d` (feat)
3. **Task 3: Create test_websocket_client.py** - `28d148f` (test)

## Files Created/Modified

- `src/eq_chatbot_core/realtime/websocket_client.py` - BaseRealtimeWebsocketClient ABC + RealtimeClientError hierarchy (259 LOC)
- `tests/unit/realtime/test_websocket_client.py` - 6 unit tests, no network calls (136 LOC)

## Decisions Made

- **RealtimeClientError inherits Exception, not ProviderError** — transport layer (WebSocket) is architecturally separate from provider-API layer (HTTP/SDK). Mixing would create false coupling between these error domains.
- **type:ignore removed from import guard except-branch** — strict mypy (`warn_unused_ignores`) flags them as unused when the library IS installed (the except-branch is considered unreachable). The existing `azure_provider.py` has the same issue. Pattern going forward: no `# type: ignore` in except-ImportError branches for strict mypy.
- **Task 1 checkpoint auto-approved** — `uv pip install "websockets>=13.0,<17.0" --dry-run` confirmed single clean package: `websockets==16.0` with no transitive dependencies.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed stale type:ignore comments from import guard**
- **Found during:** Task 2 (mypy verification)
- **Issue:** Plan's PATTERNS.md specified `# type: ignore[assignment, misc]` on None assignments in the except-ImportError block. Strict mypy (with `warn_unused_ignores=true` implied by `strict=true`) flags these as unused when websockets IS installed, because the except-branch is considered unreachable at type-check time. This caused 4+ mypy errors.
- **Fix:** Removed `# type: ignore` comments from the None assignments entirely. Mypy doesn't flag them even without the ignore (it doesn't analyze the unreachable except-branch for errors). Also removed `# type: ignore[union-attr]` from `websockets.connect()` calls since websockets IS installed when running mypy.
- **Files modified:** `src/eq_chatbot_core/realtime/websocket_client.py`
- **Verification:** `mypy src/eq_chatbot_core/realtime/websocket_client.py` exits 0
- **Committed in:** `51c650d` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** No scope change. The fix is a strict improvement — removes misleading comments that implied errors which didn't exist.

## Issues Encountered

- The worktree's `.venv` editable install points to the main repo's `src/` (not the worktree's `src/`), so verification commands required `PYTHONPATH="$WT_ROOT/src"` prefix. This is expected worktree behavior — the package is editable-installed from the main checkout.

## Next Phase Readiness

- `BaseRealtimeWebsocketClient` is ready for Phase 2 (OpenAI Realtime) and Phase 3 (Gemini Live) to inherit
- Error hierarchy is complete; concrete providers should raise these errors (not define new ones)
- `_connection_error_endpoint()` must be overridden by any provider embedding API keys in the WebSocket URL (e.g., Gemini Live)
- `connect_with_backoff()` is the recommended connect method for production use; `connect()` is for direct control

---
*Phase: 01-contracts-foundation*
*Completed: 2026-05-24*
