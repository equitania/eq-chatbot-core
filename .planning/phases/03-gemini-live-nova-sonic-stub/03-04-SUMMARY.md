---
phase: 03-gemini-live-nova-sonic-stub
plan: "04"
subsystem: realtime
tags: [factory, registry, gemini_live, nova_sonic, d-06, d-08]
dependency_graph:
  requires: [03-02, 03-03]
  provides: [gemini_live-factory-registration, nova_sonic-factory-registration]
  affects: [realtime/__init__.py, any consumer using get_realtime_provider]
tech_stack:
  added: []
  patterns: [deferred-import, d-06-fail-fast, registry-register]
key_files:
  created: []
  modified:
    - src/eq_chatbot_core/realtime/factory.py
    - tests/unit/realtime/test_factory.py
decisions:
  - D-06 fail-fast validation placed before deferred import in _build_gemini_live_provider
  - _build_nova_sonic_provider uses stdlib-only deferred import (D-08 / SC-5)
  - Singleton _DEFAULT_REGISTRY auto-includes new providers on first lazy build
metrics:
  duration: "~5 minutes"
  completed: "2026-05-25T13:45:44Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 03 Plan 04: Factory Registry Extension Summary

One-liner: Wires GeminiLiveClient and NovaSonicStub into the realtime provider factory via deferred imports with D-06 fail-fast credential validation, verified by 5 new unit tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend factory.py — register gemini_live + nova_sonic | 1e56f24 | src/eq_chatbot_core/realtime/factory.py |
| 2 | Extend test_factory.py — 5 new unit tests | bf5f927 | tests/unit/realtime/test_factory.py |

## What Was Built

### factory.py Changes (+51 lines)

- `_build_gemini_live_provider(**kwargs)`: D-06 fail-fast before deferred import — raises
  `ValueError` mentioning `api_key` for developer mode or `access_token` for vertex mode
  before any network I/O. Deferred import uses `# noqa: PLC0415`.
- `_build_nova_sonic_provider(**kwargs)`: Stdlib-only deferred import of `NovaSonicStub`;
  no websockets or boto3 required (D-08 / SC-5).
- Two `registry.register(RealtimeProviderDefinition(...))` calls inside
  `build_default_realtime_provider_registry()` after the existing openai registration.
- `registered_names()` now returns `['gemini_live', 'mock', 'nova_sonic', 'openai']`.

### test_factory.py Changes (+33 lines)

5 new `@pytest.mark.unit` test functions added after existing tests:

1. `test_registry_contains_gemini_live` — registry presence check
2. `test_registry_contains_nova_sonic` — registry presence check
3. `test_get_realtime_provider_nova_sonic_returns_stub` — D-08: resolves without AWS extras
4. `test_get_realtime_provider_gemini_live_developer_missing_api_key_raises` — D-06 fail-fast
5. `test_get_realtime_provider_gemini_live_vertex_missing_access_token_raises` — D-06 fail-fast

## Verification Results

- `pytest tests/unit/realtime/test_factory.py -v` — 11/11 passed (6 existing + 5 new)
- `pytest tests/unit/ -q` — 1248 passed, 1 skipped, 5 xfailed (no regressions)
- `ruff check src/eq_chatbot_core/realtime/factory.py` — 0 errors
- `mypy src/eq_chatbot_core/realtime/factory.py --ignore-missing-imports` — 0 errors in factory.py (pre-existing errors in other provider files are out of scope)
- `_get_realtime_provider_impl('nova_sonic')` returns `NovaSonicStub` instance
- `_get_realtime_provider_impl('gemini_live', mode='developer')` raises `ValueError` matching `api_key`
- `_get_realtime_provider_impl('gemini_live', mode='vertex')` raises `ValueError` matching `access_token`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None introduced by this plan. `NovaSonicStub` itself is the intentional stub (Plan 03-03);
this plan only wires it into the factory registry.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. D-06 error messages
reference kwarg names (`api_key`, `access_token`) only — never the credential values
themselves. T-03-F01 mitigation confirmed.

## Self-Check

### Created files exist:
- `.planning/phases/03-gemini-live-nova-sonic-stub/03-04-SUMMARY.md` — FOUND (this file)

### Modified files committed:
- `src/eq_chatbot_core/realtime/factory.py` — commit 1e56f24 FOUND
- `tests/unit/realtime/test_factory.py` — commit bf5f927 FOUND

## Self-Check: PASSED
