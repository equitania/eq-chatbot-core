---
phase: 00-codebase-cleanup
plan: "01"
subsystem: providers
tags: [constants, refactor, single-source-of-truth]
dependency_graph:
  requires: []
  provides: [CLOUD_PROVIDERS, LOCAL_PROVIDERS]
  affects: [src/eq_chatbot_core/providers/__init__.py]
tech_stack:
  added: []
  patterns: [module-level-constants, __all__-export]
key_files:
  created: []
  modified:
    - src/eq_chatbot_core/providers/__init__.py
decisions:
  - "LOCAL_PROVIDERS includes 'lmstudio' alias (present in local_aliases dict but missing from cli.py) — canonical source is get_provider() local_aliases"
metrics:
  duration: "2 minutes"
  completed: "2026-05-24T18:10:11Z"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
requirements:
  - CLN-01
---

# Phase 00 Plan 01: Add Provider Constants Summary

One-liner: Module-level CLOUD_PROVIDERS and LOCAL_PROVIDERS list constants added to providers/__init__.py as single source of truth for wave 2 consumers.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add CLOUD_PROVIDERS and LOCAL_PROVIDERS constants | acbaf34 | src/eq_chatbot_core/providers/__init__.py |

## What Was Built

Two canonical list constants were inserted into `src/eq_chatbot_core/providers/__init__.py`:

- `CLOUD_PROVIDERS: list[str] = ["openai", "anthropic", "langdock", "openrouter", "mammouth", "azure", "vertex"]`
- `LOCAL_PROVIDERS: list[str] = ["local", "lm_studio", "lmstudio", "ollama"]`

Both constants are exported via `__all__`. No other files were modified. The existing `get_provider()` function and its dispatch table remain unchanged — the new constants are derived from but independent of the runtime dispatch logic.

## Decisions Made

- Position: constants inserted immediately after the module docstring, before `from typing import ...`
- `LOCAL_PROVIDERS` includes `"lmstudio"` alias — this fixes the discrepancy between `cli.py` (which omitted it) and `server/app.py`/`local_aliases` (which included it). The authoritative source is `get_provider()`'s `local_aliases` dict.

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All acceptance criteria passed:
- `grep -n "^CLOUD_PROVIDERS"` returns exactly 1 line (line 35)
- `grep -n "^LOCAL_PROVIDERS"` returns exactly 1 line (line 36)
- Import `from eq_chatbot_core.providers import CLOUD_PROVIDERS, LOCAL_PROVIDERS` exits 0
- Both names confirmed in `__all__`

## Known Stubs

None.

## Threat Flags

No new security surface introduced. String-list constants with no secrets, no trust boundary changes.

## Self-Check: PASSED

- [x] `src/eq_chatbot_core/providers/__init__.py` modified with constants
- [x] Commit acbaf34 exists: `git log --oneline | head -1` confirms
- [x] Import verification passed with PYTHONPATH pointing to worktree src/
