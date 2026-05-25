---
milestone: v1.8.0
project: eq-chatbot-core
created: 2026-05-24
granularity: standard
---

# Roadmap: eq-chatbot-core v1.8.0 — Realtime Voice Provider Integration

## Phases

- [x] **Phase 0: Codebase Cleanup** - Export provider-name constants; eliminate 3-file hardcoded-list anti-pattern (completed 2026-05-24)
- [x] **Phase 1: Contracts + Foundation** - Full type system, ABC, WebSocket base class, factory, MockRealtimeProvider, test infrastructure (completed 2026-05-24)
- [x] **Phase 2: OpenAI Realtime Provider** - Port ~391 LOC from GlassAgents; reconcile server_vad flag; integration test (completed 2026-05-24)
- [x] **Phase 3: Gemini Live + Nova Sonic Stub** - Port ~919 LOC GeminiLiveClient; redaction helpers; NovaSonicStub <30 LOC (completed 2026-05-25)
- [ ] **Phase 3.1: ElevenLabs Agents Realtime Provider** *(INSERTED)* - Lean WebSocket adapter; preferred GDPR provider; pulled forward from v1.9.0
- [ ] **Phase 4: CLI, Hardening, Docs, Release** - `realtime-test` CLI command; bilingual docs; GlassAgents migration gate; v1.8.0 tag

## Phase Details

### Phase 0: Codebase Cleanup

**Goal**: `CLOUD_PROVIDERS` and `LOCAL_PROVIDERS` are exported as authoritative constants from `providers/__init__.py`; no hardcoded duplicates remain anywhere in the codebase
**Depends on**: Nothing (pre-condition for all subsequent phases)
**Requirements**: CLN-01, CLN-02, CLN-03, CLN-04

**Success Criteria** (what must be TRUE):

  1. `grep -rn "CLOUD_PROVIDERS\|LOCAL_PROVIDERS" src/` returns exactly one definition site (in `providers/__init__.py`) and zero inline literal lists
  2. `server/app.py` imports both constants from `providers/__init__.py` — no hardcoded provider name list inside that file
  3. `cli.py` imports both constants from `providers/__init__.py` — no hardcoded provider name list inside that file
  4. All existing unit and integration tests pass without modification (zero behavior change)

**Plans**: 3 plans

Plans:
**Wave 1**

- [x] 00-01-PLAN.md — Export CLOUD_PROVIDERS and LOCAL_PROVIDERS from providers/__init__.py

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 00-02-PLAN.md — Replace hardcoded lists in cli.py and server/app.py with imports

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 00-03-PLAN.md — Verify grep gate and unit test suite (read-only verification)

---

### Phase 1: Contracts + Foundation

**Goal**: The complete realtime type system, ABC, WebSocket base class with reconnect/backoff, factory, MockRealtimeProvider, and test infrastructure exist and are verifiable in isolation — every subsequent phase builds on this without touching shared files
**Depends on**: Phase 0
**Requirements**: CON-01, CON-02, CON-03, CON-04, CON-05, CON-06, CON-07, CON-08, CON-09, CON-10, CON-11, CON-12, CON-13, QUAL-02

**Success Criteria** (what must be TRUE):

  1. `test_contracts.py` byte-for-byte string assertions pass for all 12 `NormalizedRealtimeEventTypes` constants — any future string drift is caught immediately in CI
  2. `isinstance(MockRealtimeProvider(), RealtimeAdapterContract)` returns `True` at the Python REPL without installing `[realtime]` extra (MockRealtimeProvider is stdlib-only)
  3. `pip install eq-chatbot-core` (without `[realtime]`) then `from eq_chatbot_core.realtime import get_realtime_provider` raises a friendly `ImportError` with install instructions, not a bare `ModuleNotFoundError`
  4. `pip install eq-chatbot-core[realtime]` succeeds and `from eq_chatbot_core.realtime import get_realtime_provider, RealtimeAdapterContract, INPUT_AUDIO_SAMPLE_RATE` all resolve
  5. A mock-websockets unit test exercising `connect_with_backoff` with 3 failures then success completes without real network calls and asserts retry delays were applied

**Plans**: 5 plans

Plans:
**Wave 1** *(parallel — no file overlap)*

- [x] 01-01-PLAN.md — realtime/contracts.py, realtime/abc.py, ToolDefinition in providers/base.py, pyproject.toml [realtime] extra
- [x] 01-02-PLAN.md — tests/unit/realtime/__init__.py, conftest.py, test_contracts.py (CON-13 byte-for-byte assertions)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-03-PLAN.md — realtime/websocket_client.py (BaseRealtimeWebsocketClient + error hierarchy + connect_with_backoff), test_websocket_client.py

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-04-PLAN.md — realtime/factory.py, realtime/mock.py, realtime/providers/__init__.py, test_mock.py, test_factory.py

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-05-PLAN.md — realtime/__init__.py (import guard + public API), providers/__init__.py ToolDefinition re-export, test_import_guard.py, test_pyproject.py

---

### Phase 2: OpenAI Realtime Provider

**Goal**: `OpenAIRealtimeClient` is a working production port of the GlassAgents reference implementation (~391 LOC), with the `server_vad`/`include_turn_detection` inconsistency resolved before a single line is written, and a verified current model name as the default
**Depends on**: Phase 1
**Requirements**: PROV-01, PROV-02, PROV-03, PROV-04, QUAL-01 (OpenAI portion), QUAL-03 (OpenAI portion)

> **Split note — QUAL-01 and QUAL-03:** These requirements span two phases. The OpenAI-specific unit test suite (`test_realtime_openai.py`) and the OpenAI integration test (real API key, SESSION_READY → PCM16 chunk → close) are delivered in this phase. The Gemini/Nova portions land in Phase 3.

**Success Criteria** (what must be TRUE):

  1. The `server_vad` capability flag and `include_turn_detection` config default are consistent: the resolved design is documented in a code comment before implementation begins (PITFALL-28 resolved)
  2. `OpenAIRealtimeConfig.model` default is a valid, currently-accepted OpenAI Realtime API model ID — verified live against the OpenAI models list at phase start
  3. An integration test (skipped if `OPENAI_API_KEY` absent) connects to the OpenAI Realtime API, receives a `SESSION_READY` normalized event, sends one PCM16 audio chunk, and disconnects cleanly without errors
  4. Unit tests for connect lifecycle, `iter_normalized_events` replay (scrubbed fixture frames), close lifecycle, and capability flag assertions all pass — no real network calls

**Plans**: 3 plans

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Create OpenAIRealtimeClient + OpenAIRealtimeConfig + OPENAI_REALTIME_CAPABILITIES + full 11-method implementation with PITFALL-28 comment

**Wave 2** *(parallel — no file overlap)*

- [x] 02-02-PLAN.md — Unit test suite for OpenAI provider (test_realtime_openai.py)
- [x] 02-03-PLAN.md — Factory registration + realtime/__init__.py re-exports + integration test

---

### Phase 3: Gemini Live + Nova Sonic Stub

**Goal**: `GeminiLiveClient` (~919 LOC port) and `NovaSonicStub` (<30 LOC) complete the provider set; Gemini API key redaction is present and unit-tested; the Nova stub satisfies `RealtimeAdapterContract` structurally while pointing clearly to v1.9.0
**Depends on**: Phase 2 (recommended sequential; contract shape issues surface earlier; `manual_turn_commit_required` pattern builds on OpenAI patterns)
**Requirements**: PROV-05, PROV-06, PROV-07, PROV-08, QUAL-01 (Gemini + Nova portion), QUAL-03 (Gemini portion)

> **Split note — QUAL-01 and QUAL-03:** Unit tests for Gemini (`test_realtime_gemini.py`) and Nova (`test_realtime_nova.py`) land here, completing QUAL-01. The Gemini integration test (real Vertex EU credentials, SESSION_READY gate) lands here, completing QUAL-03.

**Success Criteria** (what must be TRUE):

  1. `GeminiLiveConfig.model` default is verified as a currently-valid model alias at phase start (PITFALL-20 resolved)
  2. `_redact_sensitive_url` unit test confirms the returned endpoint string contains no `key=` query parameter — Gemini API key never appears in logs
  3. An integration test (skipped if Vertex EU credentials absent) connects to a `europe-west*` Vertex region, receives `SESSION_READY`, and disconnects cleanly
  4. `NovaSonicStub()` satisfies `isinstance(NovaSonicStub(), RealtimeAdapterContract)` and every method raises `NotImplementedError` with a message referencing v1.9.0
  5. `get_realtime_provider("nova_sonic")` resolves via the factory without installing any AWS extras

**Plans**: 5 plans

Plans:
**Wave 1** *(blocking gate — must complete before any code is written)*

- [x] 03-01-PLAN.md — [BLOCKING] Live-verify Gemini Live model alias (D-05 / SC-1 / PITFALL-20)

**Wave 2** *(parallel — no file overlap)*

- [x] 03-02-PLAN.md — GeminiLiveClient + GeminiLiveConfig + GEMINI_LIVE_REALTIME_CAPABILITIES + dual-endpoint + redaction (gemini_live.py)
- [x] 03-03-PLAN.md — NovaSonicStub (<30 LOC, stdlib-only) + test_realtime_nova.py (nova.py)

**Wave 3** *(parallel — no file overlap)*

- [x] 03-04-PLAN.md — Factory registration gemini_live + nova_sonic + test_factory.py extensions
- [x] 03-05-PLAN.md — test_realtime_gemini.py (12 unit test classes) + test_realtime_gemini_live.py (Vertex EU integration test)

---

### Phase 03.1: ElevenLabs Agents Realtime Provider (INSERTED)

**Goal**: `ElevenLabsRealtimeClient` is a lean WebSocket transport adapter for ElevenLabs Agents (speech-to-speech) that satisfies `RealtimeAdapterContract`; it is registered equal-rank in the factory as `"elevenlabs"`, redacts the `xi-api-key` from all logs, and ships a README GDPR setup guide. ElevenLabs is positioned as the preferred GDPR provider; OpenAI/Gemini/Nova remain fully supported. Pulled forward from v1.9.0 (PROV-FUT-03).
**Depends on**: Phase 1 (contracts) + Phase 2 (OpenAI adapter pattern to mirror); sequenced after Phase 3 per roadmap decision (no functional dependency on Gemini)
**Requirements**: PROV-FUT-03 (promoted), QUAL-01 (ElevenLabs unit-test portion), QUAL-03 (ElevenLabs integration-test portion)
**Design**: `docs/superpowers/specs/2026-05-25-elevenlabs-realtime-provider-design.md`

**Success Criteria** (what must be TRUE):

  1. `isinstance(ElevenLabsRealtimeClient(config), RealtimeAdapterContract)` holds; the adapter mirrors the OpenAI provider structure
  2. `commit_client_turn()` and `create_response()` are no-ops (ElevenLabs server-side turn-taking); `manual_turn_commit_required=False` in capabilities
  3. A unit test confirms `_safe_url()` / log output never contains the `xi-api-key` — the key never appears in logs
  4. `ElevenLabsRealtimeConfig.session_sample_rate` defaults to 16000 (the override prepared in `contracts.py`); fail-fast `ValueError` on empty `api_key` or `agent_id` before any network I/O
  5. `get_realtime_provider("elevenlabs", agent_id=..., api_key=...)` resolves via the factory, equal-rank alongside `openai`/`gemini_live`/`nova_sonic`
  6. An integration test (skipped if EU credentials absent) connects to the agent endpoint, receives `SESSION_READY`, and disconnects cleanly
  7. README documents the four EU-residency conditions (Enterprise, Zero Retention Mode, EU-hosted Custom LLM, EU endpoint) plus the voice-cloning retention caveat

**Plans**: TBD (run /gsd:plan-phase 03.1 to break down)

### Phase 4: CLI, Hardening, Docs, Release

**Goal**: All developer-facing surface (CLI command, bilingual documentation, CHANGELOG) is complete, the GlassAgents migration gate is clean, and the wheel is tag-ready for local publish via `/afterwork`
**Depends on**: Phase 3 (all providers must exist before CLI smoke-test and docs can be complete)
**Requirements**: QUAL-04, QUAL-05, QUAL-06, REL-01, REL-02, REL-03, REL-04, REL-05

**Success Criteria** (what must be TRUE):

  1. `eq-chatbot realtime-test -p mock` runs without a real API key and prints a success message — proves the CLI command, factory wiring, and MockRealtimeProvider are all connected end-to-end
  2. A pre-release grep of `GlassAgents/backend/realtime/bridge.py` event-type strings finds zero mismatches against `NormalizedRealtimeEventTypes` library constants (PITFALL-27 gate: silent audio loss on migration is impossible)
  3. `docs/realtime.md` exists with both `#deutsch` and `#english` anchors; contains explicit "not available via HTTP sidecar" and "not available via CLI JSON I/O" sections
  4. Full CI matrix (Python 3.10, 3.11, 3.12, 3.13) is green including the new `tests/unit/realtime/` suite
  5. `python -m build && twine check dist/*` passes on the `1.8.0` wheel — tag is ready for `/afterwork` local publish

**Plans**: TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Codebase Cleanup | 3/3 | Complete   | 2026-05-24 |
| 1. Contracts + Foundation | 5/5 | Complete   | 2026-05-24 |
| 2. OpenAI Realtime Provider | 3/3 | Complete   | 2026-05-24 |
| 3. Gemini Live + Nova Sonic Stub | 5/5 | Complete   | 2026-05-25 |
| 4. CLI, Hardening, Docs, Release | 0/? | Not started | - |

---

## Coverage

**Total v1.8.0 requirements:** 35
**Mapped:** 35
**Unmapped:** 0 ✓

### Full Coverage Map

| Requirement | Phase |
|-------------|-------|
| CLN-01 | Phase 0 |
| CLN-02 | Phase 0 |
| CLN-03 | Phase 0 |
| CLN-04 | Phase 0 |
| CON-01 | Phase 1 |
| CON-02 | Phase 1 |
| CON-03 | Phase 1 |
| CON-04 | Phase 1 |
| CON-05 | Phase 1 |
| CON-06 | Phase 1 |
| CON-07 | Phase 1 |
| CON-08 | Phase 1 |
| CON-09 | Phase 1 |
| CON-10 | Phase 1 |
| CON-11 | Phase 1 |
| CON-12 | Phase 1 |
| CON-13 | Phase 1 |
| QUAL-02 | Phase 1 |
| PROV-01 | Phase 2 |
| PROV-02 | Phase 2 |
| PROV-03 | Phase 2 |
| PROV-04 | Phase 2 |
| QUAL-01 (OpenAI) | Phase 2 |
| QUAL-03 (OpenAI) | Phase 2 |
| PROV-05 | Phase 3 |
| PROV-06 | Phase 3 |
| PROV-07 | Phase 3 |
| PROV-08 | Phase 3 |
| QUAL-01 (Gemini + Nova) | Phase 3 |
| QUAL-03 (Gemini) | Phase 3 |
| QUAL-04 | Phase 4 |
| QUAL-05 | Phase 4 |
| QUAL-06 | Phase 4 |
| REL-01 | Phase 4 |
| REL-02 | Phase 4 |
| REL-03 | Phase 4 |
| REL-04 | Phase 4 |
| REL-05 | Phase 4 |

---

*Roadmap created: 2026-05-24 for milestone v1.8.0*
