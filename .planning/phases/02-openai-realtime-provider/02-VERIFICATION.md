---
phase: 02-openai-realtime-provider
verified: 2026-05-24T23:10:00Z
status: gaps_found
score: 3/4 success criteria verified
overrides_applied: 0
gaps:
  - truth: "Integration test is skipped when OPENAI_API_KEY is absent AND passes (or skips) cleanly without a broken [realtime] extra"
    status: failed
    reason: "websockets is not installed in the venv — the [realtime] extra is absent. When OPENAI_API_KEY is set via tests/.env.test (which it is), pytest loads the key and the skipif condition is False, so the test attempts a real connection. websockets.connect is None, causing RealtimeConnectionError. The test does NOT skip when the extra is missing — it crashes instead."
    artifacts:
      - path: "tests/integration/test_realtime_openai_live.py"
        issue: "Skip guard only checks OPENAI_API_KEY presence, not [realtime] extra installation. When the key is present but websockets is absent the test raises RealtimeConnectionError instead of skipping."
      - path: "src/eq_chatbot_core/realtime/__init__.py"
        issue: "get_realtime_provider() does check for websockets at call time (ImportError guard), but the integration test imports OpenAIRealtimeClient directly, bypassing that guard."
    missing:
      - "Either install websockets in the dev venv (uv pip install 'eq-chatbot-core[realtime]') OR add a second skipif/pytest.importorskip('websockets') guard at the top of test_realtime_openai_live.py"
  - truth: "D-03 fail-fast is fully satisfied at the public factory surface (get_realtime_provider / _build_openai_provider) for missing api_key"
    status: failed
    reason: "factory._build_openai_provider uses kwargs.pop('api_key') which raises a bare KeyError, not a ValueError. D-03 requires a library-native exception with a clear message. The OpenAIRealtimeClient constructor itself raises a clear ValueError for empty/whitespace keys, but for a completely missing api_key argument the factory surface leaks a raw KeyError('api_key') with no user-friendly message."
    artifacts:
      - path: "src/eq_chatbot_core/realtime/factory.py"
        issue: "Line 74: api_key = kwargs.pop('api_key') raises KeyError when api_key is omitted, not ValueError. Fails D-03 at the factory public surface."
    missing:
      - "Replace kwargs.pop('api_key') with api_key = kwargs.pop('api_key', None); if not api_key: raise ValueError('get_realtime_provider(\"openai\") requires api_key=... keyword argument') to match D-03 library-native fail-fast contract"
---

# Phase 02: OpenAI Realtime Provider Verification Report

**Phase Goal:** `OpenAIRealtimeClient` is a working production port of the GlassAgents reference implementation (~391 LOC), with the `server_vad`/`include_turn_detection` inconsistency (PITFALL-28) resolved before a single line is written, and a verified current model name as the default.
**Verified:** 2026-05-24T23:10:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | PITFALL-28 comment inside `_build_session_update_event` before session payload is built | VERIFIED | `grep -c "PITFALL-28" src/.../openai.py` returns 6; block comment at lines 149-171, explicitly before any session dict construction at line 177 |
| SC-2 | `OpenAIRealtimeConfig.model` defaults to `"gpt-realtime"` floating alias, annotated with `gpt-realtime-2025-08-28` snapshot | VERIFIED | `config.model == "gpt-realtime"` asserted in test and confirmed by live import; `gpt-realtime-2025-08-28` appears 3 times in the file (comment at lines 57-60) |
| SC-3 | `tests/integration/test_realtime_openai_live.py` exists, skips when `OPENAI_API_KEY` absent, covers SESSION_READY flow | FAILED | File exists and skip works when `OPENAI_API_KEY=""`. However when `OPENAI_API_KEY` is set (from `tests/.env.test`) and `websockets` is not installed, the test crashes with `RealtimeConnectionError: 'NoneType' object has no attribute 'connect'` — it does not skip when the `[realtime]` extra is absent |
| SC-4 | Unit tests for connect lifecycle, `iter_normalized_events` replay, close lifecycle, capability flag assertions all pass with no real network calls | VERIFIED | `pytest tests/unit/realtime/ -q` → 86 passed in 1.61s; 56 tests in `test_realtime_openai.py` alone |

**Score:** 3/4 success criteria verified

---

### Locked Decisions Verification

| Decision | Status | Evidence |
|----------|--------|----------|
| D-01: model defaults to `"gpt-realtime"` floating alias (not pinned snapshot) | VERIFIED | `OpenAIRealtimeConfig.model: str = "gpt-realtime"` at line 61 |
| D-02: snapshot recorded in comment, no runtime model-list call | VERIFIED | Comment at lines 57-60 states `gpt-realtime-2025-08-28 (verified 2026-05-24)`; grep confirms no `list_models()` call in the file |
| D-03: invalid/empty model or api_key fails fast with library-native exception | PARTIAL | Constructor raises `ValueError` with clear message for empty/whitespace `api_key` or `model` (VERIFIED at constructor surface). Factory `_build_openai_provider` raises bare `KeyError('api_key')` when `api_key` kwarg is omitted (FAILED at factory surface) |

---

### Requirements Coverage

| Requirement | Phase | Description | Status | Evidence |
|-------------|-------|-------------|--------|----------|
| PROV-01 | Phase 2 | OpenAI Realtime provider ports all 11 contract methods | VERIFIED | 11 async methods confirmed present: initialize_session, update_session, append_client_audio, commit_client_turn, create_response, cancel_response, register_tools, submit_tool_result, iter_normalized_events + connect/close inherited from base |
| PROV-02 | Phase 2 | `OpenAIRealtimeConfig` frozen dataclass and `OPENAI_REALTIME_CAPABILITIES` exported | VERIFIED | Both present in `__all__`; fields verified: api_key, model, voice, instructions, include_turn_detection; capabilities verified: server_vad=True, streaming_audio_input/output=True, tool_result_submission_mode="conversation_item" |
| PROV-03 | Phase 2 | PITFALL-28 reconciled; no contradictory state | VERIFIED | PITFALL-28 block comment at lines 149-171 precisely distinguishes hardware capability (`server_vad=True` static) from session-level opt-in (`include_turn_detection`); unit tests confirm VAD payload present/absent per config |
| PROV-04 | Phase 2 | Default model name verified against OpenAI API at phase start | VERIFIED (per D-02) | Model verification is documented in a code comment (not a runtime call per D-02 decision); `gpt-realtime` verified as valid at 2026-05-24 |
| QUAL-01 (OpenAI portion) | Phase 2 | Unit tests covering connect lifecycle, event normalization, close lifecycle, capability flags | VERIFIED | 56 unit tests in `test_realtime_openai.py`; TestIterNormalizedEvents covers all 11+ event types; TestToolCallNormalization asserts item sub-dict + top-level fields; TestConnectLifecycle and TestCloseLifecycle present |
| QUAL-03 (OpenAI portion) | Phase 2 | Integration test: connect → SESSION_READY → PCM16 chunk → clean close | PARTIAL/FAILED | File exists and skip logic works when key is absent. Fails when key present + `websockets` not installed — integration test is not runnable in the current dev environment without `uv pip install eq-chatbot-core[realtime]` |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/eq_chatbot_core/realtime/providers/openai.py` | OpenAIRealtimeClient, Config, Capabilities (~200+ LOC) | VERIFIED | 423 lines; all symbols exported in `__all__` |
| `src/eq_chatbot_core/realtime/factory.py` | "openai" registered with deferred import builder | VERIFIED | `_build_openai_provider` registered; `registry.get("openai")` returns valid definition |
| `src/eq_chatbot_core/realtime/__init__.py` | OpenAI symbols re-exported in try/except ImportError guard | VERIFIED | try/except block at lines 44-51; all three symbols in `__all__` |
| `tests/unit/realtime/test_realtime_openai.py` | 20+ unit tests, no real network calls | VERIFIED | 56 tests collected; all pass; covers all PROV-01..04 behaviors |
| `tests/integration/test_realtime_openai_live.py` | Skip when key absent; SESSION_READY flow | PARTIAL | File exists; skip guard works for absent key; fails with RealtimeConnectionError when key present + websockets absent |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `OpenAIRealtimeClient` | `BaseRealtimeWebsocketClient` | `super().__init__(url=url, headers=headers)` | VERIFIED | Line 108 in openai.py |
| `_build_session_update_event` | PITFALL-28 comment | block comment at function top (before session dict) | VERIFIED | Comment at lines 149-171; session dict starts at line 177 |
| `iter_normalized_events` | `iter_events()` | `async for event in self.iter_events()` | VERIFIED | Line 412 |
| `get_realtime_provider("openai")` | `_build_openai_provider` | lambda in RealtimeProviderDefinition | VERIFIED | Line 57-60 in factory.py |
| `realtime/__init__.py` | `realtime/providers/openai.py` | try/except ImportError block | VERIFIED | Lines 44-51 in `__init__.py` |

---

### Data-Flow Trace (Level 4)

Not applicable — this phase produces transport/provider code, not rendering components.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| OpenAIRealtimeConfig instantiation with model default | `python -c "from eq_chatbot_core.realtime.providers.openai import OpenAIRealtimeConfig; c=OpenAIRealtimeConfig(api_key='x'); assert c.model=='gpt-realtime'"` | Exit 0 | PASS |
| PITFALL-28: VAD present when include=True | `client._build_session_update_event(...) — 'turn_detection' in audio.input` | Asserted True | PASS |
| PITFALL-28: VAD absent when include=False | `client._build_session_update_event(...) — 'turn_detection' not in audio.input` | Asserted True | PASS |
| D-03: empty api_key raises ValueError | `OpenAIRealtimeClient(OpenAIRealtimeConfig(api_key=''))` | ValueError raised | PASS |
| D-03: factory missing api_key raises | `_build_openai_provider()` | `KeyError('api_key')` — bare passthrough | FAIL |
| _connection_error_endpoint no api_key leak | `"secret-key-123" not in client._connection_error_endpoint()` | True | PASS |
| Factory "openai" registered | `build_default_realtime_provider_registry().registered_names()` | `['mock', 'openai']` | PASS |
| 86 unit tests pass | `pytest tests/unit/realtime/ -q` | 86 passed in 1.61s | PASS |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/eq_chatbot_core/realtime/factory.py` | 74 | `kwargs.pop("api_key")` — bare KeyError passthrough | Warning | D-03 fail-fast not satisfied at factory surface when api_key kwarg is omitted |
| `tests/integration/test_realtime_openai_live.py` | 21-24 | skipif only guards on OPENAI_API_KEY, not on `websockets` installability | Warning | When key is present but `[realtime]` extra absent, test crashes instead of skipping |

No TBD/FIXME/XXX/HACK/PLACEHOLDER markers found in modified files.

---

### Human Verification Required

None — no items require human testing for this phase. All behavioral checks are automatable.

---

### Gaps Summary

Two gaps block the full VERIFIED status:

**Gap 1 (BLOCKER — SC-3 / QUAL-03 partial failure): Integration test not skip-safe when `[realtime]` extra absent**

The skip guard `not os.getenv("OPENAI_API_KEY")` only checks for the key, not for `websockets` being installed. The `tests/.env.test` file (gitignored, present on this machine) sets a valid `OPENAI_API_KEY`, so the skip condition is False. But `websockets` is not installed in the venv (`ModuleNotFoundError: No module named 'websockets'`). The result: the integration test crashes with `RealtimeConnectionError` rather than skipping. This means SC-3 "is skipped when OPENAI_API_KEY is absent" is technically satisfied — but SC-3 also requires "covers connect → SESSION_READY → one PCM16 chunk → clean close", which cannot be verified because the test cannot run.

Fix options (either is acceptable):
- Option A: Install the extra — `uv pip install -e ".[realtime]"` in the project venv (the simplest fix)
- Option B: Add `pytest.importorskip("websockets")` at the top of the integration test file, before the test function, so the test is skipped when websockets is absent regardless of the API key

**Gap 2 (WARNING — D-03 partial failure): Factory surface raises bare `KeyError` for missing `api_key`**

`_build_openai_provider(**kwargs)` at line 74 of `factory.py` calls `kwargs.pop("api_key")`. When `api_key` is not provided, Python raises `KeyError: 'api_key'` — a raw Python dict error with no guidance. The D-03 decision requires a "library-native exception (clear message), not a raw passthrough." The `OpenAIRealtimeClient.__init__()` correctly raises `ValueError` for empty/whitespace keys, but this gap is at the factory level for a completely missing kwarg.

The code review (02-REVIEW.md CR-03) already flagged this. This is a WARNING-level finding because the primary consumer surface (`get_realtime_provider("openai", api_key="...")`) passes the kwarg explicitly, and the error message `KeyError: 'api_key'` is somewhat self-documenting. However it does not meet the stated D-03 contract.

Fix: Replace line 74 with:
```python
api_key = kwargs.pop("api_key", None)
if not api_key:
    raise ValueError(
        'get_realtime_provider("openai") requires api_key=... keyword argument. '
        "Provide a valid OpenAI API key."
    )
```

---

_Verified: 2026-05-24T23:10:00Z_
_Verifier: Claude (gsd-verifier)_
