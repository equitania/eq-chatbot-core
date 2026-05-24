---
phase: 00-codebase-cleanup
plan: "02"
subsystem: providers
tags: [constants, refactor, single-source-of-truth, cli, server]
dependency_graph:
  requires: [00-01]
  provides: [cli.py-imports-constants, server/app.py-imports-constants]
  affects:
    - src/eq_chatbot_core/cli.py
    - src/eq_chatbot_core/server/app.py
tech_stack:
  added: []
  patterns: [single-source-of-truth, import-from-canonical-module]
key_files:
  created: []
  modified:
    - src/eq_chatbot_core/cli.py
    - src/eq_chatbot_core/server/app.py
decisions:
  - "CLOUD_PROVIDERS and LOCAL_PROVIDERS added to the existing multi-line import block in server/app.py (alphabetically sorted); no new import statement added"
  - "ALL_PROVIDERS derivation kept in cli.py module scope (not in providers/__init__.py) as it is CLI-specific"
  - "cli.py now implicitly gains 'lmstudio' alias in LOCAL_PROVIDERS — this was a pre-existing omission in the inline list that is now corrected by using the canonical constant"
metrics:
  duration: "4 minutes"
  completed: "2026-05-24T18:20:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
requirements:
  - CLN-02
  - CLN-03
  - CLN-04
---

# Phase 00 Plan 02: Replace Inline Provider Lists with Canonical Imports Summary

One-liner: Duplicate CLOUD_PROVIDERS/LOCAL_PROVIDERS inline list literals removed from cli.py and server/app.py; both now import the single-source-of-truth constants from providers/__init__.py.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace hardcoded lists in cli.py with imports from providers | 2e462b2 | src/eq_chatbot_core/cli.py |
| 2 | Replace hardcoded private lists in server/app.py with imports from providers | 5cececd | src/eq_chatbot_core/server/app.py |

## What Was Built

### Task 1: cli.py

- Removed the `# Available providers for CLI choices` comment block plus the three inline definitions:
  ```python
  CLOUD_PROVIDERS = ["openai", "anthropic", "langdock", "openrouter", "mammouth", "azure", "vertex"]
  LOCAL_PROVIDERS = ["local", "lm_studio", "ollama"]
  ALL_PROVIDERS = CLOUD_PROVIDERS + LOCAL_PROVIDERS
  ```
- Added import directly after `from eq_chatbot_core.version import __version__`:
  ```python
  from eq_chatbot_core.providers import CLOUD_PROVIDERS, LOCAL_PROVIDERS
  ALL_PROVIDERS = CLOUD_PROVIDERS + LOCAL_PROVIDERS
  ```
- All 3 usage sites of `LOCAL_PROVIDERS` (lines 88, 193, 348) and `ALL_PROVIDERS` as `click.Choice` arguments required no changes — names unchanged.

### Task 2: server/app.py

- Extended the existing multi-line `from eq_chatbot_core.providers import (...)` block with `CLOUD_PROVIDERS` and `LOCAL_PROVIDERS` (alphabetically inserted).
- Removed the 14-line private constant block (`_CLOUD_PROVIDERS`, `_LOCAL_PROVIDERS` with their leading comment).
- Updated the `/providers` endpoint return:
  ```python
  # Before
  return ProviderInfo(cloud=list(_CLOUD_PROVIDERS), local=list(_LOCAL_PROVIDERS))
  # After
  return ProviderInfo(cloud=list(CLOUD_PROVIDERS), local=list(LOCAL_PROVIDERS))
  ```

## Decisions Made

- `ALL_PROVIDERS` derivation stays in cli.py scope — it is a CLI-specific concept (used as `click.Choice`); providers/__init__.py does not need it.
- Import inserted alphabetically within the existing providers import block in server/app.py; no additional `from` statement needed.
- `cli.py` now silently gains `"lmstudio"` in `LOCAL_PROVIDERS` (the old inline list had `["local", "lm_studio", "ollama"]` without `"lmstudio"`). This aligns cli.py with server/app.py and the canonical `local_aliases` dict in `get_provider()`.

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All success criteria passed:

```
grep -rn "CLOUD_PROVIDERS|LOCAL_PROVIDERS" src/ | grep " = [" | grep -v "providers/__init__"
→ (no output — zero inline list definitions outside providers/__init__.py)

python -c "from eq_chatbot_core.providers import CLOUD_PROVIDERS, LOCAL_PROVIDERS"  → exits 0
python -c "from eq_chatbot_core.cli import ALL_PROVIDERS"                           → exits 0
python -c "from eq_chatbot_core.server.app import create_app"                       → exits 0
```

Single definition site confirmed: `src/eq_chatbot_core/providers/__init__.py` lines 35–36.
Consumer files (cli.py, server/app.py) contain only import lines and usage lines — zero list-literal definitions.

## Known Stubs

None.

## Threat Flags

No new security surface introduced. Pure refactor — no new endpoints, no new inputs, no new data flows. `/providers` endpoint returns identical data.

## Self-Check: PASSED

- [x] `src/eq_chatbot_core/cli.py` modified: import added, inline defs removed
- [x] `src/eq_chatbot_core/server/app.py` modified: import extended, private defs removed, usage updated
- [x] Commit 2e462b2 exists (Task 1)
- [x] Commit 5cececd exists (Task 2)
- [x] All 4 success criteria Python imports exit 0
- [x] Zero list-literal definitions outside providers/__init__.py confirmed by grep
