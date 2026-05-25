---
phase: 03-gemini-live-nova-sonic-stub
plan: "03"
subsystem: realtime
tags: [nova-sonic, aws, stub, protocol, realtime, unit-tests]

requires:
  - phase: 03-01
    provides: RealtimeAdapterContract Protocol, contracts.py with @runtime_checkable

provides:
  - NovaSonicStub: stdlib-only structural Protocol conformance stub (<30 LOC) for AWS Nova Sonic
  - test_realtime_nova.py: 13 unit tests covering PROV-08 (isinstance, all-methods-raise, v1.9.0 message)

affects:
  - 03-04 (factory registration of nova_sonic)
  - future v1.9.0 implementation plan

tech-stack:
  added: []
  patterns:
    - "Structural Protocol conformance without inheritance: class with matching signatures satisfies @runtime_checkable Protocol"
    - "Stdlib-only stub pattern: no external imports, raises NotImplementedError with version target"

key-files:
  created:
    - src/eq_chatbot_core/realtime/providers/nova.py
    - tests/unit/realtime/test_realtime_nova.py
    - tests/unit/realtime/__init__.py
  modified: []

key-decisions:
  - "NovaSonicStub uses no base class — pure structural Protocol conformance via duck-typing"
  - "Error message constant _MSG centralizes the v1.9.0 reference (DRY, compact)"
  - "iter_normalized_events return type annotation is AsyncIterator[Any] to match Protocol structurally (Pitfall 6)"
  - "TestAllMethodsRaise uses @pytest.mark.parametrize over 10 async methods + separate sync test for iter_normalized_events"

patterns-established:
  - "Stub provider pattern: stdlib-only, no imports beyond collections.abc + typing, all methods raise with version target"
  - "PROV-08 test structure: 3 classes (TestContractConformance, TestAllMethodsRaise, TestErrorMessages)"

requirements-completed:
  - PROV-08
  - QUAL-01

duration: 15min
completed: 2026-05-25
---

# Phase 03, Plan 03: NovaSonicStub Summary

**stdlib-only NovaSonicStub in 25 LOC satisfies RealtimeAdapterContract via structural Protocol duck-typing; 13 unit tests verify PROV-08 isinstance, all-methods-raise, and v1.9.0 error message**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-25T15:30:00Z
- **Completed:** 2026-05-25T15:45:00Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- NovaSonicStub (25 LOC, stdlib-only) satisfies `isinstance(NovaSonicStub(), RealtimeAdapterContract)` — True at runtime without inheriting from any base class
- All 11 RealtimeAdapterContract methods raise NotImplementedError with "v1.9.0" reference (D-07)
- 13 unit tests in 3 classes (TestContractConformance, TestAllMethodsRaise, TestErrorMessages) — all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Create NovaSonicStub and test_realtime_nova.py** - `d0bf1a3` (feat)

## Files Created/Modified

- `src/eq_chatbot_core/realtime/providers/nova.py` — NovaSonicStub: 25 LOC, stdlib-only, structural Protocol conformance
- `tests/unit/realtime/test_realtime_nova.py` — 13 unit tests for PROV-08
- `tests/unit/realtime/__init__.py` — Package init for realtime test module

## Decisions Made

- Used a module-level `_MSG` constant to DRY up the 11 identical error strings while keeping LOC count minimal
- `iter_normalized_events` return annotation is `AsyncIterator[Any]` (not `AsyncIterator[NormalizedRealtimeEvent]`) — this is intentional per Pitfall 6: using the concrete TypedDict here would break structural Protocol matching
- No `__init__.py` existed in `tests/unit/realtime/` in the worktree — added to match main repo structure

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added missing tests/unit/realtime/__init__.py**
- **Found during:** Task 1 (test execution setup)
- **Issue:** The worktree's `tests/unit/realtime/` directory lacked `__init__.py`, preventing proper pytest collection
- **Fix:** Created `tests/unit/realtime/__init__.py` matching main repo content (`"""Realtime unit tests."""`)
- **Files modified:** tests/unit/realtime/__init__.py
- **Verification:** File created, matches pattern from main repo
- **Committed in:** d0bf1a3 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking)
**Impact on plan:** Missing `__init__.py` is standard package infrastructure. No scope creep.

## Issues Encountered

The worktree (`agent-a0028af49de3e1c52`) was created from base commit `b80878d`, which predates the realtime module introduction. The worktree's `src/eq_chatbot_core/realtime/` directory only contained `providers/nova.py` (the new file), not the full realtime package. This made direct pytest execution within the worktree fail with `ModuleNotFoundError: No module named 'eq_chatbot_core.realtime.contracts'`.

Resolution: Temporarily copied nova.py and test_realtime_nova.py to the main repo (which has the full realtime package via editable install), ran tests there to confirm all 13 pass, then removed the temporary copies. The files are committed in the worktree and will be available in the full project context after merge.

## Next Phase Readiness

- NovaSonicStub is ready for factory registration in Plan 04 (`get_realtime_provider("nova_sonic")`)
- No AWS extras needed — stub is stdlib-only
- PROV-08 and QUAL-01 (Nova portion) are satisfied

---
*Phase: 03-gemini-live-nova-sonic-stub*
*Completed: 2026-05-25*
