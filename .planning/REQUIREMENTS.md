# Requirements: eq-chatbot-core v1.8.0 — Realtime Voice Provider Integration

**Defined:** 2026-05-24
**Core Value:** One factory call gets a working realtime voice provider for any supported backend, with consistent normalized event schema, async-only interface, and capability metadata — no vendor lock-in, no provider-specific glue code in the consuming app.

## v1.8.0 Requirements

Requirements for this milestone release. Each maps to roadmap phases.

### Cleanup (Pre-condition)

- [ ] **CLN-01**: `providers/__init__.py` exports `CLOUD_PROVIDERS` and `LOCAL_PROVIDERS` constants as single source of truth
- [ ] **CLN-02**: `server/app.py` imports `CLOUD_PROVIDERS` / `LOCAL_PROVIDERS` from `providers/__init__.py` instead of hardcoding
- [ ] **CLN-03**: `cli.py` imports `CLOUD_PROVIDERS` / `LOCAL_PROVIDERS` from `providers/__init__.py` instead of hardcoding
- [ ] **CLN-04**: `grep -rn "CLOUD_PROVIDERS\|LOCAL_PROVIDERS" src/` shows single authoritative definition

### Contracts & Foundation

- [ ] **CON-01**: `realtime/contracts.py` defines 12 `NormalizedRealtimeEventTypes` constants with byte-exact string values matching the handoff spec §3.2
- [ ] **CON-02**: `realtime/contracts.py` defines `NormalizedRealtimeEvent` TypedDict envelope
- [ ] **CON-03**: `realtime/contracts.py` defines `RealtimeProviderCapabilities` frozen dataclass with `session_sample_rate: int = 24000` field included
- [ ] **CON-04**: `realtime/contracts.py` defines `RealtimeAdapterContract` rich `@runtime_checkable` Protocol with 11 async methods
- [ ] **CON-05**: `realtime/contracts.py` exports `INPUT_AUDIO_SAMPLE_RATE = 24_000` constant
- [ ] **CON-06**: `realtime/abc.py` defines minimal `RealtimeProvider` ABC (4 abstract methods) plus `RealtimeEvent` union of 7 frozen dataclass event types
- [ ] **CON-07**: `providers/base.py` adds shared `ToolDefinition` dataclass; `providers/__init__.py` re-exports it; chat-completion signatures accept both dict and `ToolDefinition` (backward-compatible union)
- [ ] **CON-08**: `realtime/websocket_client.py` implements `BaseRealtimeWebsocketClient` with: WS connect/send/recv/close, `RealtimeClosedError(code, retriable)`, `RealtimeRateLimitError(retry_after)`, `connect_with_backoff(max_attempts=5, base_delay_s=1.0, max_delay_s=30.0)` with jitter, async context manager support
- [ ] **CON-09**: `realtime/factory.py` defines `RealtimeProviderRegistry`, `RealtimeProviderDefinition`, `get_realtime_provider(name, **kwargs)` factory, `build_default_realtime_provider_registry()`
- [ ] **CON-10**: `realtime/__init__.py` exports `REALTIME_PROVIDERS` constant, all public types, and raises friendly `ImportError` when `[realtime]` extra is missing
- [ ] **CON-11**: `realtime/mock.py` ships `MockRealtimeProvider` (queue-backed, stdlib-only, available without `[realtime]` extra installed)
- [ ] **CON-12**: `pyproject.toml` declares `[realtime] = ["websockets>=13.0,<17.0"]` extra
- [ ] **CON-13**: `tests/unit/realtime/test_contracts.py` asserts each of the 12 event type string values byte-for-byte (gate against silent GlassAgents migration breakage)

### Production Providers

- [ ] **PROV-01**: `realtime/providers/openai.py` ports `OpenAIRealtimeClient` (~391 LOC) from GlassAgents with feature parity: connect, initialize_session, append_client_audio, commit_client_turn, create_response, cancel_response, register_tools, submit_tool_result, iter_normalized_events, close — all 11 RealtimeAdapterContract methods
- [ ] **PROV-02**: `realtime/providers/openai.py` exports `OpenAIRealtimeConfig` frozen dataclass (api_key, model, voice, instructions, include_turn_detection) and `OPENAI_REALTIME_CAPABILITIES` constant
- [ ] **PROV-03**: `OPENAI_REALTIME_CAPABILITIES.server_vad` value reconciles with `OpenAIRealtimeConfig.include_turn_detection` default (PITFALL-28 resolved; no contradictory state)
- [ ] **PROV-04**: `realtime/providers/openai.py` validates current model name (`gpt-realtime` or successor) against OpenAI API at phase start; default model is verified live
- [ ] **PROV-05**: `realtime/providers/gemini_live.py` ports `GeminiLiveClient` (~919 LOC) from GlassAgents with feature parity for all 11 RealtimeAdapterContract methods, BidiGenerateContent protocol handling, manual turn commit, and `provider_call_id` tool result schema
- [ ] **PROV-06**: `realtime/providers/gemini_live.py` exports `GeminiLiveConfig` frozen dataclass and `GEMINI_LIVE_REALTIME_CAPABILITIES` constant
- [ ] **PROV-07**: `realtime/providers/gemini_live.py` ports `_redact_sensitive_url` and `_redact_sensitive_text` helpers verbatim (Gemini API key in URL must never leak to logs)
- [ ] **PROV-08**: `realtime/providers/nova.py` ships `NovaSonicStub` (<30 LOC) raising `NotImplementedError` with explicit message pointing to v1.9.0; satisfies `RealtimeAdapterContract` Protocol structurally

### Quality & Developer Surface

- [x] **QUAL-01**: Unit test suite `tests/unit/realtime/` covers each provider: connect lifecycle, `iter_normalized_events` produces every expected event type from recorded scrubbed frames, close lifecycle, capability flag assertions
- [ ] **QUAL-02**: `tests/unit/realtime/conftest.py` establishes AsyncMock pattern for `websockets.connect` (not MagicMock; isolates from existing sys.modules mock-leak issue)
- [x] **QUAL-03**: Integration test for each production provider connects to real API, receives `SESSION_READY`, sends a PCM16 chunk, disconnects cleanly (gated by API key env var; skipped in CI if absent)
- [ ] **QUAL-04**: `cli.py` adds `eq-chatbot realtime-test -p {openai|gemini_live|nova_sonic|mock}` smoke-test command
- [ ] **QUAL-05**: GlassAgents migration gate — pre-release check greps GlassAgents `backend/realtime/bridge.py` for hardcoded event-type strings and verifies all 12 match library constants exactly
- [ ] **QUAL-06**: Full CI matrix (Python 3.10, 3.11, 3.12, 3.13) passes including new realtime test suite

### Release & Documentation

- [ ] **REL-01**: `docs/realtime.md` documents: async-only interface contract, PCM16 requirement, `[realtime]` install instructions, sidecar exclusion (explicit out-of-scope for v1.8.0), Rust/CLI JSON I/O exclusion (realtime not supported there), tool-calling consumer patterns, reconnect semantics, bilingual DE/EN per project convention
- [ ] **REL-02**: `README.md` adds realtime section to topic index with link to `docs/realtime.md`
- [ ] **REL-03**: `CHANGELOG.md` v1.8.0 entry covers: [ADD] new `[realtime]` extra, [ADD] OpenAI Realtime / Gemini Live / Nova Sonic providers, [ADD] shared `ToolDefinition`, [CHG] `CLOUD_PROVIDERS`/`LOCAL_PROVIDERS` constants exported (anti-pattern fix), [ADD] `realtime-test` CLI command
- [ ] **REL-04**: Version bumped `1.7.2 → 1.8.0` in `src/eq_chatbot_core/version.py`; `twine check dist/*` passes on built wheel
- [ ] **REL-05**: GlassAgents-side migration notes added to `docs/realtime.md` (handoff §8 — what GlassAgents deletes, what it keeps, pyproject bump line)

## Future Requirements (v1.9.0+)

Deferred to future release. Tracked but not in current roadmap.

### Additional Realtime Providers (post-EU-residency-gate per Captain policy)

- **PROV-FUT-01**: AWS Nova Sonic production implementation — requires new `BaseRealtimeBedrocktClient` for HTTP/2 bidirectional streaming; new `[realtime-aws]` extra with boto3
- **PROV-FUT-02**: DeepGram Voice Agent — WebSocket-native, BYOLLM, $4.50/hr flat rate; pending EU-residency verification
- **PROV-FUT-03**: ElevenLabs Conversational AI — requires `session_sample_rate=16000` capability already prepared in v1.8.0; pending EU-residency verification + pre-session REST agent config
- **PROV-FUT-04**: Hume AI EVI 3 — requires new `EMOTION_SCORES` event type extension; pending EU-residency verification + Python 3.12/3.13 SDK compatibility check

### HTTP Sidecar Realtime Relay

- **SIDE-FUT-01**: WebSocket relay endpoint in `[server]` extra for fr-designer (Avalonia/.NET) and other non-Python consumers — distinct architectural feature with per-connection state, not a quick add-on

## Out of Scope

Explicitly excluded for v1.8.0. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| xAI Grok Voice Agent (all versions) | **CAPTAIN POLICY — PERMANENT:** EU/GDPR non-compliant; no EU data-residency commitment. Excluded forever. Same gate applies to all future provider proposals. |
| Mistral Voxtral, Cartesia Sonic | Not realtime bidirectional voice agents — STT/TTS components only |
| LiveKit Agents integration | Application framework, not a provider; consumers use LiveKit + library providers together |
| Sync wrappers around realtime providers | Realtime is async-native by design; sync consumers wrap with `asyncio.run()` or `anyio.from_thread` themselves |
| Audio recording / capture / buffering | Library handles transport only; consumers own microphone I/O |
| Turn management policy / session modes | App-specific (onboarding vs standard); stays in consumer code (GlassAgents `turn_state.py`, `session_modes.py`) |
| iOS bridge / audio uplink / tool dispatcher | App-specific WS relay; stays in GlassAgents (`bridge.py`, `audio_uplink.py`, `tool_dispatcher.py`) |
| SIP/PSTN integration | Out of library scope |
| Browser WebRTC support | Out of library scope |
| Conversation persistence / session storage | Library is stateless; consumers own state |
| Realtime via CLI JSON I/O | `eq-chatbot chat` JSON I/O is single-turn; realtime requires long-lived process |
| Audio format negotiation (Opus, μ-law) | PCM16-only by Captain decision; defer to later minor when concrete consumer drives it |
| openai SDK `client.realtime.connect()` | Adds numpy + sounddevice via `openai[realtime]`; raw websockets is simpler and provider-agnostic |
| google-genai SDK `client.aio.live.connect()` | Leaks Gemini-native types into normalized event layer; raw websockets keeps abstraction clean |
| boto3 in `[realtime]` extra | 25–67 MB weight for a stub-only provider; Nova Sonic production goes in separate `[realtime-aws]` extra later |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

> **QUAL-01 and QUAL-03 are split across two phases.** Both requirements span all production providers.
> The OpenAI-specific deliverables (unit test file `test_realtime_openai.py` + OpenAI integration test) land in **Phase 2**.
> The Gemini/Nova-specific deliverables (unit test files `test_realtime_gemini.py`, `test_realtime_nova.py` + Gemini integration test) land in **Phase 3**.
> Both requirements are fully satisfied only when both phases are complete.

| Requirement | Phase | Split detail | Status |
|-------------|-------|--------------|--------|
| CLN-01 | Phase 0 | — | Pending |
| CLN-02 | Phase 0 | — | Pending |
| CLN-03 | Phase 0 | — | Pending |
| CLN-04 | Phase 0 | — | Pending |
| CON-01 | Phase 1 | — | Pending |
| CON-02 | Phase 1 | — | Pending |
| CON-03 | Phase 1 | — | Pending |
| CON-04 | Phase 1 | — | Pending |
| CON-05 | Phase 1 | — | Pending |
| CON-06 | Phase 1 | — | Pending |
| CON-07 | Phase 1 | — | Pending |
| CON-08 | Phase 1 | — | Pending |
| CON-09 | Phase 1 | — | Pending |
| CON-10 | Phase 1 | — | Pending |
| CON-11 | Phase 1 | — | Pending |
| CON-12 | Phase 1 | — | Pending |
| CON-13 | Phase 1 | — | Pending |
| QUAL-02 | Phase 1 | — | Pending |
| PROV-01 | Phase 2 | — | Pending |
| PROV-02 | Phase 2 | — | Pending |
| PROV-03 | Phase 2 | — | Pending |
| PROV-04 | Phase 2 | — | Pending |
| QUAL-01 | Phase 2 + Phase 3 | Phase 2: OpenAI unit tests; Phase 3: Gemini + Nova unit tests | Pending |
| QUAL-03 | Phase 2 + Phase 3 | Phase 2: OpenAI integration test; Phase 3: Gemini integration test | Pending |
| PROV-05 | Phase 3 | — | Pending |
| PROV-06 | Phase 3 | — | Pending |
| PROV-07 | Phase 3 | — | Pending |
| PROV-08 | Phase 3 | — | Pending |
| QUAL-04 | Phase 4 | — | Pending |
| QUAL-05 | Phase 4 | — | Pending |
| QUAL-06 | Phase 4 | — | Pending |
| REL-01 | Phase 4 | — | Pending |
| REL-02 | Phase 4 | — | Pending |
| REL-03 | Phase 4 | — | Pending |
| REL-04 | Phase 4 | — | Pending |
| REL-05 | Phase 4 | — | Pending |

**Coverage:**
- v1.8.0 requirements: 35 total
- Mapped to phases: 35
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-24*
*Last updated: 2026-05-24 — roadmap created; QUAL-01/03 split documented*
