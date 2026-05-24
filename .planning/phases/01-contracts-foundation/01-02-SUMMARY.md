---
phase: 01-contracts-foundation
plan: "02"
subsystem: test-infrastructure
tags:
  - realtime
  - test-infrastructure
  - websockets
  - async-mock
  - CON-13
  - QUAL-02
dependency_graph:
  requires:
    - 01-01 (contracts.py — imports NormalizedRealtimeEventTypes, RealtimeAdapterContract, etc.)
  provides:
    - tests/unit/realtime/ — pytest-discoverable test package
    - tests/unit/realtime/conftest.py — session-scoped AsyncMock websockets fixture
    - tests/unit/realtime/test_contracts.py — CON-13 byte-for-byte GlassAgents migration gate
  affects:
    - CI — all subsequent realtime plans can use the conftest.py fixtures
tech_stack:
  added: []
  patterns:
    - AsyncMock session fixture for sys.modules websockets injection (PITFALL-14 fix)
    - Function-scoped mock_ws_instance fixture for state isolation (PITFALL-16 fix)
    - Inline @pytest.mark.unit assertions (no loop/helper — ruff assertion rewriting works best)
key_files:
  created:
    - tests/unit/realtime/__init__.py
    - tests/unit/realtime/conftest.py
    - tests/unit/realtime/test_contracts.py
  modified: []
decisions:
  - Used AsyncMock (not MagicMock) for websockets.connect — required for async with context manager support
  - Added try/except ImportError fallback in conftest.py for real websockets exception classes — allows tests to run before websockets extra is installed
  - All 12 string constant assertions are inline (not in a loop) per RESEARCH.md anti-pattern rule
  - noqa E704 for single-line method stubs in test_adapter_contract_runtime_checkable
metrics:
  duration: "1m 52s"
  completed: "2026-05-24T19:11:46Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 0
---

# Phase 1 Plan 02: Realtime Test Infrastructure Summary

**One-liner:** pytest package with AsyncMock websockets conftest + 12 inline byte-for-byte NormalizedRealtimeEventTypes assertions for GlassAgents migration safety gate (CON-13, QUAL-02)

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create tests/unit/realtime/__init__.py and conftest.py | 319633e | tests/unit/realtime/__init__.py, tests/unit/realtime/conftest.py |
| 2 | Create test_contracts.py — CON-13 byte-for-byte assertions | 7d43a80 | tests/unit/realtime/test_contracts.py |

## Verification Results

All 4 verification checks from the plan passed:

1. `pytest tests/unit/realtime/test_contracts.py -v -m unit` — **7/7 tests passed**
2. `pytest tests/unit/realtime/ --collect-only -q` — package discoverable, 7 tests collected
3. `ruff check tests/unit/realtime/` — exits 0 (all checks passed)
4. `grep -c "AsyncMock" tests/unit/realtime/conftest.py` — returns 15 (>= 2 required)

## Test Functions in test_contracts.py

| Test | Requirement | What It Asserts |
|------|-------------|-----------------|
| `test_event_type_string_values` | CON-13 | 12 inline byte-for-byte string constants |
| `test_event_type_count` | CON-13 | Exactly 12 public string attributes |
| `test_input_audio_sample_rate` | CON-05 | INPUT_AUDIO_SAMPLE_RATE == 24000 |
| `test_normalized_event_typeddict` | CON-02 | TypedDict has type/payload/source/raw keys |
| `test_capabilities_defaults` | CON-03 | session_sample_rate=24000, startup_validation=True |
| `test_capabilities_frozen` | CON-03 | RealtimeProviderCapabilities is frozen |
| `test_adapter_contract_runtime_checkable` | CON-04 | isinstance positive + negative cases |

## Deviations from Plan

None - plan executed exactly as written, with one minor addition:

**[Rule 2 - Missing error handling] Added try/except ImportError for websockets exception classes in conftest.py**
- **Found during:** Task 1 implementation
- **Issue:** Plan noted websockets not yet installed; real exception class import would fail at fixture definition time if websockets absent
- **Fix:** Wrapped the `from websockets.exceptions import ...` block in `try/except ImportError` with a fallback comment — allows conftest.py to load without websockets installed
- **Impact:** MagicMock() fallback for exception classes is acceptable for unit tests using sys.modules mock; except clauses targeting real websockets exceptions won't catch them, but that only matters for integration tests
- **Files modified:** tests/unit/realtime/conftest.py

## Known Stubs

None — all assertions are against real contracts.py values; no placeholder data.

## Threat Flags

None — test infrastructure only. No network I/O, no production code paths, no new trust boundaries.

## Self-Check: PASSED

Files exist:
- tests/unit/realtime/__init__.py: FOUND
- tests/unit/realtime/conftest.py: FOUND
- tests/unit/realtime/test_contracts.py: FOUND

Commits exist:
- 319633e: FOUND (feat(01-02): add realtime test package...)
- 7d43a80: FOUND (feat(01-02): add test_contracts.py...)
