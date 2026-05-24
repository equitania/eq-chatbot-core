---
phase: 02-openai-realtime-provider
plan: "03"
subsystem: realtime
tags: [openai, realtime, factory, integration-test]
dependency_graph:
  requires: [02-01]
  provides: [factory-openai-registration, realtime-init-exports, openai-realtime-live-test]
  affects: [eq_chatbot_core.realtime, tests.integration]
tech_stack:
  added: []
  patterns: [deferred-import-factory, try-except-importerror-guard, pytest-skipif-api-key]
key_files:
  created:
    - tests/integration/test_realtime_openai_live.py
  modified:
    - src/eq_chatbot_core/realtime/factory.py (already satisfied by 02-01)
    - src/eq_chatbot_core/realtime/__init__.py (already satisfied by 02-01)
decisions:
  - "factory.py and __init__.py wiring already completed by 02-01 executor — recorded as satisfied, no changes made"
  - "get_realtime_provider('openai') correctly raises ImportError when websockets absent (by design); factory layer verified independently"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-24"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 1
---

# Phase 2 Plan 03: Factory Wiring + Integration Test Summary

Wire the OpenAI Realtime provider into the factory/init public API (already done by 02-01) and create the live integration test covering SESSION_READY, PCM16 audio chunk, and clean close.

## Tasks

### Task 1: Register "openai" in factory.py
**Status:** Already satisfied by 02-01 executor.

Verified:
- `build_default_realtime_provider_registry().registered_names()` returns `['mock', 'openai']`
- `registry.get('openai').factory_fn(api_key='test-key')` returns `OpenAIRealtimeClient` instance
- Deferred import via `_build_openai_provider` helper with `# noqa: PLC0415`
- `factory.py` importable without `[realtime]` extra

### Task 2: Re-export OpenAI symbols from realtime/__init__.py
**Status:** Already satisfied by 02-01 executor.

Verified:
- `from eq_chatbot_core.realtime import OpenAIRealtimeClient, OpenAIRealtimeConfig, OPENAI_REALTIME_CAPABILITIES` all resolve
- `try/except ImportError` guard in place at lines 44-51
- All three names in `__all__`
- `OpenAIRealtimeConfig(api_key='x').model == 'gpt-realtime'` confirmed
- `REALTIME_PROVIDERS` already contained `"openai"` — no change needed

### Task 3: Create integration test
**Status:** Complete. Commit: `baa3408`

Created `tests/integration/test_realtime_openai_live.py`:
- `pytestmark = pytest.mark.integration`
- `@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set — skipping live integration test")`
- `@pytest.mark.asyncio` (explicit, even with asyncio_mode=auto)
- Test flow: `OpenAIRealtimeConfig(include_turn_detection=False)` → async context manager → `iter_normalized_events()` → assert `SESSION_READY` → `append_client_audio(b"\x00\x00" * 2400)` → clean close via `__aexit__`
- API key never appears in assertion messages (T-02W-01 mitigated)
- Collects cleanly: `pytest --collect-only -q` shows 1 test collected

## Deviations from Plan

### Already satisfied by 02-01

Tasks 1 and 2 were already fully implemented by the 02-01 executor on this worktree's base branch. The factory.py and __init__.py wiring matched the plan's acceptance criteria exactly. No changes were made to these files. Per the critical prior work notice, this is expected and correct.

**Files verified but not modified:**
- `src/eq_chatbot_core/realtime/factory.py` — "openai" registered, `_build_openai_provider` helper present
- `src/eq_chatbot_core/realtime/__init__.py` — three OpenAI symbols re-exported under `try/except ImportError`

## Verification Results

All plan verification criteria confirmed:

| Check | Result |
|-------|--------|
| `registered_names()` includes `"openai"` | PASS |
| `factory_fn(api_key='x')` returns `OpenAIRealtimeClient` | PASS |
| `OpenAIRealtimeClient` importable from `eq_chatbot_core.realtime` | PASS |
| `OpenAIRealtimeConfig` importable from `eq_chatbot_core.realtime` | PASS |
| `OPENAI_REALTIME_CAPABILITIES` importable from `eq_chatbot_core.realtime` | PASS |
| `cfg.model == "gpt-realtime"` | PASS |
| `pytest --collect-only` on integration test | PASS (1 collected) |
| `pytest tests/unit/ -q` (no regressions) | PASS (1173 passed, 1 skipped, 5 xfailed) |
| `ruff check` on all three files | PASS |
| `mypy` errors in `realtime/factory.py` and `realtime/__init__.py` | PASS (no errors in target files; 79 pre-existing errors in other modules) |

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. The integration test uses the existing OpenAI WSS endpoint via `OpenAIRealtimeClient` — already in scope from plan 02-01. T-02W-01 mitigated: assertion message uses `event['type']` only, never the api_key value.

## Known Stubs

None. The integration test connects to the real OpenAI Realtime API when `OPENAI_API_KEY` is set.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 3 | `baa3408` | feat(02-03): create live integration test for OpenAI Realtime provider |

## Self-Check: PASSED

- FOUND: tests/integration/test_realtime_openai_live.py
- FOUND: commit baa3408
- FOUND: .planning/phases/02-openai-realtime-provider/02-03-SUMMARY.md
