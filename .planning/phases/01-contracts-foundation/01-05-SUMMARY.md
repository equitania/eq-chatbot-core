---
phase: 01-contracts-foundation
plan: "05"
subsystem: realtime
tags: [realtime, import-guard, websockets, providers, public-api, testing]

# Dependency graph
requires:
  - phase: 01-01
    provides: contracts.py (RealtimeAdapterContract, NormalizedRealtimeEventTypes, INPUT_AUDIO_SAMPLE_RATE)
  - phase: 01-02
    provides: abc.py (RealtimeProvider ABC, typed event dataclasses)
  - phase: 01-03
    provides: providers/base.py ToolDefinition class
  - phase: 01-04
    provides: factory.py (_get_realtime_provider_impl, RealtimeProviderRegistry), mock.py (MockRealtimeProvider)
provides:
  - "realtime/__init__.py: single-import public API with get_realtime_provider() import guard"
  - "REALTIME_PROVIDERS constant: ['openai', 'gemini_live', 'nova_sonic', 'mock']"
  - "providers/__init__.py: ToolDefinition re-export in public API"
  - "test_import_guard.py: CON-10 exit gate tests (import guard + always-importable verification)"
  - "test_pyproject.py: CON-12 exit gate tests (pyproject.toml [realtime] extra static check)"
  - "All 5 phase success criteria verified and passing"
affects: [phase-02, phase-03, consumers-of-realtime-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "import-guard: websockets check at call time inside get_realtime_provider(), never at module import time"
    - "deferred-import: factory._get_realtime_provider_impl imported inside function body after guard"
    - "always-importable: contracts + abc + mock re-exported at module level without any extra deps"
    - "REALTIME_PROVIDERS constant: authoritative list of registered provider names in __init__.py"
    - "pytestmark skipif: Python <3.11 guard in test_pyproject.py for tomllib stdlib availability"

key-files:
  created:
    - "tests/unit/realtime/test_import_guard.py"
    - "tests/unit/realtime/test_pyproject.py"
  modified:
    - "src/eq_chatbot_core/realtime/__init__.py"
    - "src/eq_chatbot_core/providers/__init__.py"

key-decisions:
  - "Import guard fires at call time (inside function body), not at module import time — prevents ModuleNotFoundError for consumers without [realtime]"
  - "MockRealtimeProvider and all contracts remain always-importable without any optional extra"
  - "REALTIME_PROVIDERS is the authoritative list in __init__.py; Phase 2/3 must update both factory registry and this list"
  - "test_pyproject.py uses pytestmark skipif (not try/except tomli fallback) to handle Python 3.10 compatibility cleanly"
  - "Pre-existing ruff E402 in providers/__init__.py (line 38 typing import) is out of scope — not introduced by this plan"

patterns-established:
  - "Import guard pattern: check optional dep inside function body, deferred factory import after guard"
  - "Public __all__ in __init__.py lists all re-exported symbols for explicit consumer API surface"

requirements-completed:
  - CON-10
  - CON-12
  - QUAL-02

# Metrics
duration: 15min
completed: 2026-05-24
---

# Phase 1 Plan 5: Contracts + Foundation — Public API Wiring Summary

**realtime/__init__.py wired as consumer-facing entry point with websockets import guard, REALTIME_PROVIDERS constant, and full contract/mock re-exports; ToolDefinition added to providers public API**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-24T21:34:00Z
- **Completed:** 2026-05-24T21:40:00Z
- **Tasks:** 3 auto + 1 checkpoint
- **Files modified:** 4

## Accomplishments

- `realtime/__init__.py` now serves as the single consumer entry point: `get_realtime_provider()` with friendly import guard, `REALTIME_PROVIDERS` constant, and all contracts/mock/abc re-exports always available
- `providers/__init__.py` exports `ToolDefinition` (CON-07 requirement) — importable as `from eq_chatbot_core.providers import ToolDefinition`
- Phase exit gate tests added: `test_import_guard.py` (CON-10) and `test_pyproject.py` (CON-12)
- All 5 phase success criteria verified passing; full unit suite 1173 passed

## Task Commits

Each task was committed atomically:

1. **Task 1: realtime/__init__.py import guard + public re-exports** - `44f810e` (feat)
2. **Task 2: providers/__init__.py ToolDefinition re-export** - `eb1a6c2` (feat)
3. **Task 3: test_import_guard.py + test_pyproject.py** - `48188ea` (test)

## Files Created/Modified

- `src/eq_chatbot_core/realtime/__init__.py` - Complete rewrite: import guard, REALTIME_PROVIDERS, all re-exports
- `src/eq_chatbot_core/providers/__init__.py` - Added ToolDefinition to base imports and __all__
- `tests/unit/realtime/test_import_guard.py` - CON-10: 3 unit tests for import guard behavior
- `tests/unit/realtime/test_pyproject.py` - CON-12: 2 unit tests for pyproject.toml static verification

## Decisions Made

- Import guard placed at call time (inside `get_realtime_provider()` function body) — critical to ensure `from eq_chatbot_core.realtime import MockRealtimeProvider` never fails, even without websockets installed
- `REALTIME_PROVIDERS` declared in `__init__.py` as the authoritative list (not in factory.py) — it's the public API contract; factory registry is the implementation detail
- `test_pyproject.py` uses `pytestmark = pytest.mark.skipif(sys.version_info < (3, 11), ...)` — the only mechanism for Python 3.10 compatibility, no `tomli` fallback added per plan decision

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff I001 import ordering in realtime/__init__.py**
- **Found during:** Task 1 (post-write ruff check)
- **Issue:** ruff required `abc` imports before `contracts` imports (alphabetical order within the import block)
- **Fix:** Reordered the two import blocks so `abc` comes before `contracts`
- **Files modified:** `src/eq_chatbot_core/realtime/__init__.py`
- **Verification:** `ruff check` exits 0 after fix
- **Committed in:** `44f810e` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed ruff I001 import ordering in test_pyproject.py**
- **Found during:** Task 3 (post-write ruff check)
- **Issue:** ruff required `from pathlib import Path` before `import tomllib` (stdlib `from` before `import`)
- **Fix:** Moved `from pathlib import Path` above `import tomllib`, with blank line between per ruff convention
- **Files modified:** `tests/unit/realtime/test_pyproject.py`
- **Verification:** `ruff check` exits 0 after fix
- **Committed in:** `48188ea` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - ruff import ordering)
**Impact on plan:** Both fixes trivial import-order corrections. No scope creep. All acceptance criteria met.

### Pre-existing Issues (Out of Scope)

- `src/eq_chatbot_core/providers/__init__.py` line 38: `from typing import TYPE_CHECKING, Any` triggers ruff E402 — pre-existing before this plan, not caused by Task 2's change. Logged here, not fixed.

## Issues Encountered

None beyond the ruff ordering auto-fixes above.

## Phase Success Criteria Status

All 5 phase success criteria verified passing:

1. `test_contracts.py::test_event_type_string_values` — 12 byte-for-byte NormalizedRealtimeEventTypes constants correct
2. `isinstance(MockRealtimeProvider(), RealtimeAdapterContract)` — True without [realtime] extra
3. `test_import_guard.py::test_import_guard_friendly_error` — ImportError contains "eq-chatbot-core[realtime]" and "pip install"
4. `from eq_chatbot_core.realtime import get_realtime_provider, RealtimeAdapterContract, INPUT_AUDIO_SAMPLE_RATE` — resolves with [realtime] installed
5. `test_websocket_client.py::test_connect_with_backoff_3_failures_then_success` — delays [1.0, 2.0, 4.0], 4 attempts

Additional: 1173 unit tests passing, 1 skipped, 5 xfailed.

## Next Phase Readiness

- Phase 1 (Contracts + Foundation) is complete. All 5 success criteria met.
- Phase 2 (OpenAI Realtime Provider) can begin: `get_realtime_provider("openai")` will route through factory; must register "openai" in factory registry and update REALTIME_PROVIDERS if needed
- Phase 3 (Gemini Live + Nova Sonic) follows the same pattern

## Self-Check

Files exist:
- `src/eq_chatbot_core/realtime/__init__.py` - present
- `src/eq_chatbot_core/providers/__init__.py` - present (modified)
- `tests/unit/realtime/test_import_guard.py` - present (created)
- `tests/unit/realtime/test_pyproject.py` - present (created)

Commits exist:
- `44f810e` - feat(01-05): wire realtime/__init__.py
- `eb1a6c2` - feat(01-05): add ToolDefinition re-export
- `48188ea` - test(01-05): add test_import_guard.py + test_pyproject.py

## Self-Check: PASSED

---
*Phase: 01-contracts-foundation*
*Completed: 2026-05-24*
