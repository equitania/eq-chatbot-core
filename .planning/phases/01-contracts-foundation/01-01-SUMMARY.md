---
phase: 01-contracts-foundation
plan: "01"
subsystem: realtime-type-system
tags:
  - realtime
  - type-contracts
  - protocol
  - abc
  - frozen-dataclass
  - pyproject
dependency_graph:
  requires: []
  provides:
    - src/eq_chatbot_core/realtime/contracts.py
    - src/eq_chatbot_core/realtime/abc.py
    - src/eq_chatbot_core/realtime/__init__.py
    - ToolDefinition in src/eq_chatbot_core/providers/base.py
    - "[realtime] extra in pyproject.toml"
  affects:
    - src/eq_chatbot_core/providers/base.py
    - pyproject.toml
tech_stack:
  added:
    - "realtime package (src/eq_chatbot_core/realtime/) — new subpackage"
    - "websockets>=13.0,<17.0 declared as [realtime] optional extra"
  patterns:
    - "@dataclass(frozen=True, slots=True) for RealtimeProviderCapabilities, ToolDefinition, and all 7 event types"
    - "@runtime_checkable Protocol for RealtimeAdapterContract"
    - "ABC with 4 abstract methods for RealtimeProvider"
    - "X | Y union syntax (Python 3.10+) for RealtimeEvent type alias"
    - "Backward-compatible union signature for tools parameter in chat/stream_completion"
key_files:
  created:
    - src/eq_chatbot_core/realtime/__init__.py
    - src/eq_chatbot_core/realtime/contracts.py
    - src/eq_chatbot_core/realtime/abc.py
  modified:
    - src/eq_chatbot_core/providers/base.py
    - pyproject.toml
decisions:
  - "Used string annotations ('list[ToolDefinition] | ...') in BaseLLMProvider.chat_completion to avoid forward-reference resolution issues; ToolDefinition is defined in the same file above BaseLLMProvider so both quoted and unquoted work"
  - "Union type alias for RealtimeEvent uses X | Y syntax (UP007) instead of typing.Union to satisfy ruff target-version=py310"
  - "realtime/__init__.py imports both contracts.py and abc.py directly; websockets-dependent symbols (factory, concrete providers) will be gated inside get_realtime_provider() in Plan 05"
metrics:
  duration_seconds: 189
  completed_date: "2026-05-24"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 2
---

# Phase 01 Plan 01: Contracts + Foundation Type System Summary

**One-liner:** Realtime type system foundation — 12 GlassAgents-compatible event constants, NormalizedRealtimeEvent TypedDict, RealtimeProviderCapabilities/RealtimeAdapterContract Protocol, RealtimeProvider ABC with 7 event dataclasses, ToolDefinition shared type, and [realtime] websockets extra.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create realtime/contracts.py | 85dff33 | realtime/__init__.py, realtime/contracts.py |
| 2 | Create realtime/abc.py | 7e1d7f5 | realtime/abc.py |
| 3 | Add ToolDefinition + pyproject.toml | ca617f9 | providers/base.py, pyproject.toml |

## What Was Built

### realtime/contracts.py
- `NormalizedRealtimeEventTypes` — plain class with 12 frozen string constants matching GlassAgents source byte-for-byte (migration safety gate)
- `NormalizedRealtimeEvent` — TypedDict with `total=False`, keys: `type`, `payload`, `source`, `raw`
- `RealtimeProviderCapabilities` — `@dataclass(frozen=True, slots=True)` with 10 fields; `session_sample_rate: int = 24_000` for ElevenLabs 16kHz prep (PROV-FUT-03)
- `RealtimeAdapterContract` — `@runtime_checkable Protocol` with exactly 11 async method stubs; `iter_normalized_events` is a regular `def` returning `AsyncIterator`
- `INPUT_AUDIO_SAMPLE_RATE: int = 24_000` constant

### realtime/abc.py
- 7 frozen event dataclasses: `AudioDeltaEvent`, `AudioDoneEvent`, `ResponseDoneEvent`, `ResponseCreatedEvent`, `SpeechStartedEvent`, `SpeechStoppedEvent`, `ErrorEvent`
- `RealtimeEvent` — union type alias using Python 3.10+ `X | Y` syntax
- `RealtimeProvider(ABC)` — exactly 4 abstract methods: `connect`, `close`, `initialize_session`, `iter_normalized_events`
- No imports from `contracts.py` — independently importable

### providers/base.py
- `ToolDefinition` — `@dataclass(frozen=True, slots=True)` with `name: str`, `description: str`, `parameters: dict[str, Any]`, `strict: bool = False`
- Updated `chat_completion` and `stream_completion` signatures to accept `list[ToolDefinition] | list[dict[str, Any]] | None` (backward-compatible union)

### pyproject.toml
- Added `realtime = ["websockets>=13.0,<17.0"]` under `[project.optional-dependencies]`, between `vertex` and `server`

## Verification Results

- All 6 plan verification checks pass (imports, ruff, mypy)
- 1143 existing unit tests pass, 1 skipped, 5 xfailed — zero regressions
- `ruff check` exits 0 on all 3 modified/created source files
- `mypy --strict` exits 0 on all 3 source files

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Union syntax for ruff UP007 compliance**
- **Found during:** Task 2 (ruff check on abc.py)
- **Issue:** Initial implementation used `typing.Union[...]` for `RealtimeEvent` type alias; ruff UP007 requires `X | Y` syntax for Python 3.10+ target
- **Fix:** Removed `Union` from imports; rewrote `RealtimeEvent` using `( A | B | C | ... )` multi-line syntax
- **Files modified:** `src/eq_chatbot_core/realtime/abc.py`
- **Commit:** 7e1d7f5

None other — plan executed as specified.

## Known Stubs

None — all exported symbols are fully defined type contracts with no hardcoded empty values flowing to UI or callers.

## Threat Flags

No new network endpoints, auth paths, or file access patterns introduced. All code is import-time type declarations only (frozen dataclasses, TypedDict, Protocol, ABC). No new trust boundaries.

## Self-Check: PASSED
