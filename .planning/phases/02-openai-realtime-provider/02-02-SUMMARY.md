---
phase: 02-openai-realtime-provider
plan: "02"
subsystem: realtime
tags: [testing, unit-tests, openai-realtime, vad, event-normalization, tool-calls]
dependency_graph:
  requires:
    - 02-01  # OpenAIRealtimeClient implementation
  provides:
    - PROV-01 unit test coverage
    - PROV-02 unit test coverage
    - PROV-03 unit test coverage (PITFALL-28 VAD payload)
    - PROV-04 unit test coverage
    - QUAL-01 OpenAI unit test coverage (PITFALL-05 tool call shape)
  affects:
    - tests/unit/realtime/
tech_stack:
  added: []
  patterns:
    - pytest async unit testing with AsyncMock websockets fixture
    - Direct _to_normalized_runtime_event call pattern (no WS needed for routing tests)
    - patch.object for initialize_session lifecycle assertion
key_files:
  created:
    - tests/unit/realtime/test_realtime_openai.py
  modified: []
decisions:
  - Import AsyncMock/patch inline inside test methods to keep top-level imports ruff-clean until Task 2 uses them
  - Use _to_normalized_runtime_event directly for event routing tests — no WS mock needed, simpler and faster
  - Use (FrozenInstanceError, AttributeError) guard for frozen test to be runtime-compatible
metrics:
  duration: "~4 minutes"
  completed: "2026-05-24"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 1
---

# Phase 02 Plan 02: OpenAI Unit Test Suite Summary

Unit test suite covering OpenAIRealtimeClient with 56 passing tests in 8 test classes, verifying PROV-01..04 behaviors including VAD session payload logic (PITFALL-28), tool call payload shape (PITFALL-05), and all 11 NormalizedRealtimeEventTypes wire type mappings.

## What Was Built

`tests/unit/realtime/test_realtime_openai.py` — 56 test functions across 8 test classes:

| Class | Tests | Coverage |
|-------|-------|----------|
| TestOpenAIRealtimeConfig | 6 | PROV-02/04: frozen, defaults, custom fields |
| TestCapabilities | 8 | PROV-02: all OPENAI_REALTIME_CAPABILITIES flags |
| TestConstructorValidation | 5 | D-03: empty/whitespace api_key and model |
| TestVADSessionPayload | 5 | PROV-03/PITFALL-28: turn_detection present/absent |
| TestConnectionErrorEndpoint | 3 | T-02T-01: API key not leaked in error URL |
| TestNormalizeTools | 5 | _normalize_tools: ToolDefinition, dict, None, empty |
| TestIterNormalizedEvents | 13 | PROV-01: all 11+ wire type → constant mappings |
| TestToolCallNormalization | 8 | QUAL-01/PITFALL-05: item sub-dict + top-level fields |
| TestConnectLifecycle | 2 | PROV-01: _on_connected, RealtimeAdapterContract |
| TestCloseLifecycle | 1 | PROV-01: close() without connection |

## Key Test Assertions

**PITFALL-28 (VAD payload):**
- `include_turn_detection=True` → `turn_detection` key IS in `session["audio"]["input"]`
- `include_turn_detection=False` → `turn_detection` key is NOT present

**PITFALL-05 (tool call payload):**
- `response.function_call_arguments.done` → `TOOL_CALL_COMPLETED`
- `payload["item"]["call_id"]` accessible (GlassAgents bridge requirement)
- `payload["call_id"]` also present at top level (backward compat)

**Security (T-02T-01):**
- `api_key="secret"` — confirmed "secret" not in `_connection_error_endpoint()` return value

## Verification Results

```
pytest tests/unit/realtime/test_realtime_openai.py: 56 passed
pytest tests/unit/realtime/: 86 passed
pytest tests/unit/: 1229 passed, 1 skipped, 5 xfailed (no regressions)
ruff check: 0 errors
mypy: Success (0 issues)
test function count: 58 (>= 20 requirement)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Frozen dataclass mutation via object.__setattr__ does not raise**
- **Found during:** Task 1 execution
- **Issue:** `object.__setattr__()` bypasses `FrozenInstanceError` — used in `test_frozen` — so the test failed to raise as expected
- **Fix:** Changed to direct attribute assignment `config.api_key = "new-value"` which correctly triggers `FrozenInstanceError` at runtime
- **Files modified:** tests/unit/realtime/test_realtime_openai.py
- **Commit:** f287562

**2. [Rule 1 - Bug] Unused imports causing ruff F401 errors after import cleanup**
- **Found during:** Task 1 ruff check
- **Issue:** `AsyncMock`, `patch`, `NormalizedRealtimeEventTypes`, `RealtimeAdapterContract`, `RealtimeAudioEventNames` were pre-imported for Task 2 but unused in Task 1 scope
- **Fix:** Moved imports to only what Task 1 needs; added back in Task 2. `AsyncMock`/`patch` kept inline in `TestConnectLifecycle.test_on_connected_calls_initialize_session` to avoid top-level unused import
- **Files modified:** tests/unit/realtime/test_realtime_openai.py
- **Commit:** f287562

## Known Stubs

None — test file has no stubs.

## Threat Flags

No new network endpoints, auth paths, or trust boundaries introduced. Unit tests use fake `api_key="test-key"` and `api_key="secret"` only — no real keys in any assertion.

## Self-Check

- [x] tests/unit/realtime/test_realtime_openai.py exists
- [x] Commit f287562 (Task 1) exists
- [x] Commit e21febe (Task 2) exists
- [x] 56 tests pass, 0 failures
- [x] ruff clean, mypy clean
- [x] Full unit suite 1229 passed, no regressions
