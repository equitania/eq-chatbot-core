---
phase: "02"
plan: "01"
subsystem: realtime
tags: [openai, realtime, websocket, provider, event-normalization]
dependency_graph:
  requires:
    - "01-05: BaseRealtimeWebsocketClient (websocket_client.py)"
    - "01-03: RealtimeAdapterContract, NormalizedRealtimeEventTypes (contracts.py)"
    - "01-01: RealtimeProvider ABC (abc.py)"
    - "01-04: RealtimeProviderRegistry, build_default_realtime_provider_registry (factory.py)"
    - "providers/base.py: ToolDefinition"
  provides:
    - "OpenAIRealtimeClient — full 11-method RealtimeAdapterContract implementation"
    - "OpenAIRealtimeConfig — frozen+slots dataclass (api_key, model, voice, instructions, include_turn_detection)"
    - "OPENAI_REALTIME_CAPABILITIES — RealtimeProviderCapabilities constant"
    - "RealtimeAudioEventNames — frozen dataclass for audio event name constants"
    - "OUTPUT_AUDIO_SAMPLE_RATE — int = 24_000"
    - "'openai' registered in RealtimeProviderRegistry via deferred import"
    - "iter_events() added to BaseRealtimeWebsocketClient (missing from Phase 1)"
  affects:
    - "realtime/__init__.py (re-export + try/except guard)"
    - "realtime/factory.py (openai registration + _build_openai_provider)"
    - "realtime/websocket_client.py (iter_events added)"
tech_stack:
  added: []
  patterns:
    - "Frozen+slots dataclass for config (OpenAIRealtimeConfig)"
    - "Frozen dataclass without slots for named-constant holder (RealtimeAudioEventNames)"
    - "Two-stage event normalization: alias pass + routing table"
    - "Deferred import in factory _build_openai_provider to keep factory importable without [realtime]"
    - "try/except ImportError guard in realtime/__init__.py for re-exports"
    - "Inline ToolDefinition → OpenAI wire format (no to_openai_tool() method)"
key_files:
  created:
    - src/eq_chatbot_core/realtime/providers/openai.py
  modified:
    - src/eq_chatbot_core/realtime/websocket_client.py
    - src/eq_chatbot_core/realtime/factory.py
    - src/eq_chatbot_core/realtime/__init__.py
decisions:
  - "Used NormalizedRealtimeEventFull (not NormalizedRealtimeEvent) as return type for _to_normalized_runtime_event and iter_normalized_events — NormalizedRealtimeEventFull includes source/raw optional fields required by the normalization pipeline; NormalizedRealtimeEvent does not"
  - "Added iter_events() to BaseRealtimeWebsocketClient — method was missing from Phase 1 (Rule 2 deviation) but required for iter_normalized_events; added as async generator over recv_json()"
  - "Kept trace_events as OpenAIRealtimeClient constructor kwarg (not in config dataclass) matching GlassAgents reference; default False"
metrics:
  duration: "5m"
  completed: "2026-05-24T20:45:35Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 3
---

# Phase 2 Plan 01: OpenAI Realtime Provider Implementation Summary

OpenAIRealtimeClient ported from GlassAgents (~391 LOC reference) into the library as a subclass of Phase 1 BaseRealtimeWebsocketClient, implementing all 11 RealtimeAdapterContract methods with PITFALL-28 VAD/turn-detection reconciliation comment and D-02/D-03 model annotation and fail-fast validation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Module-level definitions (config, capabilities, constants) | 4fe88d1 | providers/openai.py |
| 2 | OpenAIRealtimeClient full implementation | 4fe88d1 | providers/openai.py |
| 3 | ruff + mypy + source assertion verification gate | 4fe88d1 | (verification only) |

## What Was Built

- `src/eq_chatbot_core/realtime/providers/openai.py` (~300 LOC): complete OpenAI Realtime provider
  - `OpenAIRealtimeConfig` frozen+slots dataclass with D-02 model annotation
  - `OPENAI_REALTIME_CAPABILITIES` constant with all 9 RealtimeProviderCapabilities fields
  - `RealtimeAudioEventNames` frozen dataclass for canonical audio event name constants
  - `OUTPUT_AUDIO_SAMPLE_RATE = 24_000` module-level constant
  - `OpenAIRealtimeClient` subclassing `BaseRealtimeWebsocketClient` + `RealtimeProvider`
  - Three abstract overrides: `_on_connected`, `_on_message` (no-op), `_connection_error_endpoint`
  - PITFALL-28 reconciliation block comment at top of `_build_session_update_event` (SC-1)
  - Two-stage event normalization: `normalize_event` + `_to_normalized_runtime_event`
  - PITFALL-05 custom `TOOL_CALL_COMPLETED` payload shape with `item` sub-dict
  - All 11 contract methods: `connect`, `close` (inherited), `initialize_session`, `update_session`,
    `append_client_audio`, `commit_client_turn`, `create_response`, `cancel_response`,
    `register_tools`, `submit_tool_result`, `iter_normalized_events`
  - D-03 fail-fast `ValueError` on empty `api_key` or `model`
  - T-02-01: `_connection_error_endpoint` strips api_key, returns model-only URL
- Factory registration: `"openai"` → `_build_openai_provider` with deferred import
- Re-exports in `realtime/__init__.py` with `try/except ImportError` guard

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added iter_events() to BaseRealtimeWebsocketClient**
- **Found during:** Task 2 implementation
- **Issue:** `iter_events()` referenced by plan and PATTERNS.md as "inherited from BaseRealtimeWebsocketClient" but was absent from the Phase 1 implementation. Without it, `iter_normalized_events` could not be implemented as specified.
- **Fix:** Added `iter_events()` as an async generator over `recv_json()` to `websocket_client.py`. Also added `from collections.abc import AsyncIterator` import.
- **Files modified:** `src/eq_chatbot_core/realtime/websocket_client.py`
- **Commit:** 4fe88d1

**2. [Rule 1 - Bug] Used NormalizedRealtimeEventFull instead of NormalizedRealtimeEvent**
- **Found during:** mypy type check
- **Issue:** `NormalizedRealtimeEvent` TypedDict only has `type` and `payload` keys. The normalization pipeline builds dicts with `source` and `raw` fields, which are only present in `NormalizedRealtimeEventFull`. mypy reported "Extra keys" errors.
- **Fix:** Changed return type annotations in `_to_normalized_runtime_event` and `iter_normalized_events` to use `NormalizedRealtimeEventFull`. Removed unused `NormalizedRealtimeEvent` import.
- **Files modified:** `src/eq_chatbot_core/realtime/providers/openai.py`
- **Commit:** 4fe88d1

## Verification Results

All 7 success criteria verified:

| Criterion | Status |
|-----------|--------|
| `from ... import OpenAIRealtimeClient, OpenAIRealtimeConfig, OPENAI_REALTIME_CAPABILITIES` | PASS |
| `isinstance(client, RealtimeAdapterContract)` is True | PASS |
| `ruff check` exits 0 | PASS |
| `mypy` exits 0 on openai.py | PASS |
| `grep PITFALL-28` finds 6 occurrences | PASS |
| `grep gpt-realtime-2025-08-28` finds 3 occurrences | PASS |
| `pytest tests/unit/ -q` — 1173 passed, 0 regressions | PASS |

## Known Stubs

None — all methods are fully implemented. The `_on_message` no-op `pass` is intentional ABC compliance (documented in code comment) and does not prevent the plan's goal (iter_normalized_events uses iter_events, not _on_message).

## Threat Flags

No new threat surface introduced beyond what the PLAN.md threat model anticipated. All T-02-01 through T-02-04 mitigations are implemented:
- `_connection_error_endpoint` verified to not expose api_key
- `self._headers` never logged or surfaced in error messages
- Empty api_key raises ValueError before network I/O
- Malformed server JSON handled by base class `recv_json` as `RealtimeProtocolError`

## Self-Check: PASSED

- `src/eq_chatbot_core/realtime/providers/openai.py` exists: FOUND
- commit 4fe88d1 exists: FOUND
- 1173 unit tests pass: VERIFIED
