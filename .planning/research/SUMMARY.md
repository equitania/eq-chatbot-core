# Research Summary: v1.8.0 Realtime Voice Provider Integration

**Project:** eq-chatbot-core
**Domain:** Bidirectional realtime voice WebSocket provider abstraction — PyPI library extension
**Researched:** 2026-05-24
**Confidence:** HIGH

---

## Executive Summary

eq-chatbot-core v1.8.0 adds a new `[realtime]` subpackage that ports battle-tested bidirectional voice streaming code (~2 070 LOC) from the GlassAgents reference implementation into the library, making it available to all consumers (GlassAgents, fr-designer, sysReporter, Odoo) via a single factory call. The realtime surface is architecturally peer-level to the existing `providers/` HTTP layer — not a subfeature of it. It introduces a distinct async interface (`RealtimeAdapterContract` Protocol + `RealtimeProvider` ABC), a normalized event schema (12 typed constants), per-provider capability metadata, and a new `realtime/` subpackage. The only new runtime dependency is `websockets>=13.0,<17.0` — the lightest extra in the library (~175 KB wheel, zero transitive deps), and already a transitive dep for consumers using `[vertex]`.

The recommended implementation strategy is a faithful port from GlassAgents rather than a rewrite around SDK namespaces (the openai SDK's `client.realtime.connect()` and google-genai's `client.aio.live.connect()` are both explicitly rejected in favor of raw websockets). Two production providers land in v1.8.0: OpenAI Realtime API and Google Gemini Live — both already reference-implemented in GlassAgents. AWS Nova Sonic ships as an ABC-conformant stub (HTTP/2 transport rules out WebSocket base class reuse; production impl deferred to v1.9.0). The Mock provider ships as a library-resident queue-backed harness for consumer test suites.

The primary risks are infrastructure-level: WebSocket connection leak on exception path, close-code opacity preventing smart reconnect, and asyncio task orphaning in long-lived consumer processes. These must be resolved in the base class (`BaseRealtimeWebsocketClient`) before any concrete provider is ported. A secondary risk is GlassAgents migration breakage — the 12 normalized event type string constants must be byte-for-byte identical to the handoff spec; any drift causes silent audio loss. A pre-release string-assertion test in CI mitigates this entirely.

---

## Key Findings

### Recommended Stack

The `[realtime]` extra needs exactly one new dependency: `websockets>=13.0,<17.0`. Everything else (openai SDK, google-genai SDK, httpx, pydantic, anyio, pytest-asyncio) is already present in core or existing extras. The websockets library is already a transitive dep via google-genai for `[vertex]` users, so for the most common consumer profile `[vertex,realtime]` adds zero bytes to disk.

The upper-bound `<17.0` mirrors google-genai's ceiling so both extras bump together when websockets 17.0 ships. The openai SDK's tighter `<16` bound is automatically enforced by UV's resolver without explicit declaration. boto3 must NOT be added for Nova Sonic — it would impose 25–67 MB on every `[realtime]` installer for a stub-only provider; if a production Nova Sonic impl is built in v1.9.x, create a separate `[realtime-aws]` extra.

**Core technologies:**
- `websockets>=13.0,<17.0`: WebSocket transport for all realtime providers — only new runtime dep; asyncio-native; self-sufficient for mock WS servers in tests via `websockets.serve()`
- `pytest-asyncio>=0.24.0,<2.0.0` (already in `[dev]`): async test support; `asyncio_mode = "auto"` already configured; no new test dep needed
- `unittest.mock.AsyncMock` (stdlib): required for mocking `websockets.connect()` in unit tests; `MagicMock` is insufficient for async context managers

**Explicitly rejected:**
- `openai[realtime]` extra — would pull numpy + sounddevice; eq-chatbot-core uses websockets directly
- `google-genai` SDK realtime surface — leaks Gemini-native types into normalized event layer; raw websockets is simpler
- `aiohttp` — second async HTTP framework with no advantage for pure WS client work
- `websocket-client` — synchronous-only; incompatible with asyncio-first design

### Expected Features

See `.planning/research/FEATURES.md` for full provider evaluations (12 providers assessed).

**v1.8.0 — production (table stakes for milestone):**
- Bidirectional PCM16 audio streaming at 24 kHz mono — library constant `INPUT_AUDIO_SAMPLE_RATE = 24_000`
- Normalized event emission: 12 `NormalizedRealtimeEventTypes` constants, TypedDict envelope
- `RealtimeProviderCapabilities` per-provider metadata (streaming_audio_input/output, server_vad, manual_turn_commit_required, tool_calling, tool_result_submission_mode, voice_selection, interruption_cancel, startup_validation)
- `session_sample_rate: int = 24000` field on `RealtimeProviderCapabilities` — LOCKED CAPTAIN DECISION; pre-empts ElevenLabs 16 kHz breaking change in v1.9.0; default = current OpenAI Realtime rate; minimal-invasive
- Session lifecycle: `connect()`, `initialize_session()`, `close()`, async context manager
- Tool calling via shared `ToolDefinition` dataclass (non-breaking addition to `providers/base.py`)
- Response cancellation (OpenAI native; Gemini close+reconnect)
- In-process `MockRealtimeProvider` for consumer test suites (stdlib-only; available without `[realtime]` extra)
- `eq-chatbot realtime-test` CLI smoke-test command

**v1.8.0 — stub (ABC conformance, raises NotImplemented):**
- AWS Nova Sonic — HTTP/2 transport requires separate `BaseRealtimeBedrocktClient`; stub proves ABC conformance until v1.9.0

**Defer to v1.9.0 (post-RFC where noted):**
- DeepGram Voice Agent — WebSocket compatible, mature Python SDK, BYOLLM; requires EU-residency gate before adoption
- ElevenLabs Conversational AI — requires `session_sample_rate` contract extension (16 kHz) + pre-session REST for agent-centric config; requires EU-residency gate
- Hume AI EVI 3 — requires `EMOTION_SCORES` schema extension; Python 3.12+ SDK compatibility unverified; requires EU-residency gate
- AWS Nova Sonic production — requires `BaseRealtimeBedrocktClient` (HTTP/2 bidi)
- WebSocket relay endpoint in HTTP sidecar for fr-designer / sysReporter

**Permanently excluded (do not re-propose):**
- xAI Grok Voice Agent — EXCLUDED BY CAPTAIN POLICY: only EU/GDPR-compliant providers accepted; Grok cannot meet EU data-residency requirements. This exclusion is permanent. All future realtime provider candidates (DeepGram, Hume EVI, ElevenLabs) must pass the same EU-residency gate before v1.9.0 adoption.
- Mistral Voxtral — no bidirectional speech-to-speech session API; STT+TTS pipeline only
- Cartesia Sonic — TTS-only; no STT or bidirectional session
- LiveKit Agents — application framework, not a provider; consumers use LiveKit + eq-chatbot-core providers together
- Sync wrappers for realtime providers; audio recording/buffering; turn management policy; SIP/PSTN; browser WebRTC; conversation persistence

### Architecture Approach

The `realtime/` subpackage is a top-level sibling of `providers/`, not a sub-namespace of it. Both are LLM transport adapters but differ on every axis: sync vs async, HTTP vs WebSocket, stateless vs stateful, request/response vs bidirectional stream. The subpackage ships two contracts: a rich `RealtimeAdapterContract` Protocol (11 async methods, for bridge/relay code in consuming apps) and a minimal `RealtimeProvider` ABC (4 methods, for stubs and simple test implementations). Production providers implement the Protocol structurally via duck-typing; stubs inherit the ABC. The base class `BaseRealtimeWebsocketClient` owns the WebSocket lifecycle and is shared across all WebSocket-transport providers (OpenAI, Gemini Live, future DeepGram/ElevenLabs). Nova Sonic is excluded from this base class due to HTTP/2 bidi transport.

**Major components:**
1. `realtime/contracts.py` — NormalizedRealtimeEventTypes (12 constants), NormalizedRealtimeEvent (TypedDict), RealtimeProviderCapabilities (frozen dataclass + `session_sample_rate`), RealtimeAdapterContract (@runtime_checkable Protocol), `INPUT_AUDIO_SAMPLE_RATE = 24_000`
2. `realtime/abc.py` — RealtimeProvider minimal ABC (4 abstract methods), RealtimeEvent union (7 frozen dataclass types)
3. `realtime/websocket_client.py` — BaseRealtimeWebsocketClient: WS connect/send/recv/close, error hierarchy (RealtimeClosedError with close code + retriable flag, RealtimeRateLimitError), `connect_with_backoff`, async context manager (`__aenter__`/`__aexit__`)
4. `realtime/factory.py` — RealtimeProviderRegistry, RealtimeProviderDefinition, `get_realtime_provider()` factory, `build_default_realtime_provider_registry()`
5. `realtime/providers/openai.py` — OpenAIRealtimeClient (391 LOC port), OpenAIRealtimeConfig, OPENAI_REALTIME_CAPABILITIES
6. `realtime/providers/gemini_live.py` — GeminiLiveClient (919 LOC port), GeminiLiveConfig, GEMINI_LIVE_REALTIME_CAPABILITIES
7. `realtime/providers/nova.py` — NovaSonicStub (<30 LOC, raises NotImplementedError)
8. `realtime/mock.py` — MockRealtimeProvider (queue-backed, stdlib-only, available without `[realtime]` extra)
9. `providers/base.py` (modified) — ToolDefinition dataclass (shared by chat + realtime)
10. `providers/__init__.py` (modified) — export ToolDefinition, CLOUD_PROVIDERS, LOCAL_PROVIDERS (fixes hardcoded-list anti-pattern per Captain decision)

**Locked Phase 0 cleanup (CAPTAIN DECISION):** Export `CLOUD_PROVIDERS`, `LOCAL_PROVIDERS`, `REALTIME_PROVIDERS` constants from their authoritative modules; remove the 3-file hardcoded duplication in `providers/__init__.py`, `server/app.py`, `cli.py` BEFORE adding realtime so the new layer does not replicate the bug. This is a pre-condition, not optional.

### Critical Pitfalls

Full analysis in `.planning/research/PITFALLS.md` (29 pitfalls catalogued, phase-tagged).

1. **WebSocket close code not surfaced (PITFALL-01)** — `RealtimeClosedError` must carry `code: int | None` and `retriable: bool`; catch `ws_exceptions.ConnectionClosed` before bare `except Exception`; consumers need this to distinguish graceful shutdown (1000) from network death (1006). Must be in base class before any concrete provider is written.

2. **Connection leak on exception path (PITFALL-04)** — If `_on_connected()` raises after `self._ws` is assigned, the socket stays open forever. Fix: wrap post-connect setup in `try/except`; call `await self.close()` before re-raising. The `async with` context manager is the primary consumer-facing mitigation.

3. **Reconnect storm on 429/outage (PITFALL-02)** — No backoff in current base class. `connect_with_backoff(max_attempts=5, base_delay_s=1.0, max_delay_s=30.0)` with jitter is required. HTTP 429 from WS handshake must surface as `RealtimeRateLimitError` with `retry_after`.

4. **Event type string drift breaks GlassAgents migration (PITFALL-27/29)** — The 12 `NormalizedRealtimeEventTypes` string constants must be byte-for-byte identical to handoff spec §3.2. A single-character typo causes silent audio loss in GlassAgents `bridge.py`. Write `test_contracts.py` asserting every string value as the first commit in the contracts phase.

5. **AsyncMock required for websockets mocking (PITFALL-14)** — `MagicMock()` is insufficient for `async with websockets.connect()`; causes `TypeError: object MagicMock can't be used in 'await' expression`. Use `unittest.mock.AsyncMock`. Realtime unit tests must live in `tests/unit/realtime/` with its own `conftest.py` to isolate sys.modules mock state.

6. **server_vad capability vs config mismatch (PITFALL-28)** — `OPENAI_REALTIME_CAPABILITIES.server_vad=True` with `include_turn_detection=False` default is contradictory. Make capabilities an instance attribute reflecting actual config, or change `include_turn_detection` default to `True`. Resolve in Phase 2 design step before writing any OpenAI code.

7. **Gemini API key in proxy logs (PITFALL-17)** — Gemini Live URL contains `?key=AIzaSy...`; port `_redact_sensitive_url` and `_redact_sensitive_text` verbatim from GlassAgents `gemini_live.py`. Not optional.

---

## Implications for Roadmap

Based on combined research, the build has four natural phases with clear dependency ordering. The foundation must be complete before any concrete provider is started; the two production providers can be developed in parallel after foundation.

### Phase 0: Codebase Cleanup (Pre-condition)

**Rationale:** LOCKED CAPTAIN DECISION — refactor the hardcoded provider-list anti-pattern (PITFALL-23/24) before adding realtime. Without this, the new `REALTIME_PROVIDERS` constant replicates a known debt in a fourth location. This is a 3-file modification, zero behavior change, and clears the technical debt that would otherwise compound with every new provider.

**Delivers:** `CLOUD_PROVIDERS` and `LOCAL_PROVIDERS` exported from `providers/__init__.py`; `server/app.py` and `cli.py` import from there instead of hardcoding. Verifiable: `grep -rn "CLOUD_PROVIDERS\|LOCAL_PROVIDERS" src/` shows single definitions.

**Avoids:** PITFALL-23 (provider name list duplication), PITFALL-24 (server endpoint list divergence)

**Research flag:** No research needed — pure refactor with established pattern.

---

### Phase 1: Contracts + Foundation

**Rationale:** Everything depends on this. The normalized event schema, capability dataclass, Protocol/ABC definitions, and the WebSocket base class must be locked before any concrete provider is written. The event type string constants must be committed with assertion tests in the same PR — they can never change without a coordinated GlassAgents migration PR.

**Delivers:**
- `providers/base.py`: `ToolDefinition` dataclass (non-breaking; backward-compatible union in `chat_completion` signature)
- `realtime/contracts.py`: full type system (12 string constants, TypedDict, `RealtimeProviderCapabilities` with `session_sample_rate=24000`, `RealtimeAdapterContract` Protocol, `INPUT_AUDIO_SAMPLE_RATE`)
- `realtime/abc.py`: `RealtimeProvider` ABC + `RealtimeEvent` union (7 frozen dataclass types)
- `realtime/websocket_client.py`: `BaseRealtimeWebsocketClient` with close-code surfacing, connection leak fix, `connect_with_backoff`, async context manager
- `realtime/factory.py`: `RealtimeProviderRegistry`, `get_realtime_provider()`, default registry builder
- `realtime/mock.py`: `MockRealtimeProvider` (stdlib-only, ships in installed package)
- `realtime/__init__.py`: `REALTIME_PROVIDERS` constant + re-exports + friendly ImportError for missing extra
- `pyproject.toml`: `[realtime] = ["websockets>=13.0,<17.0"]`; version bump to `1.8.0.dev0`
- `tests/unit/realtime/conftest.py`: AsyncMock patterns, function-scoped provider fixtures, fixture hygiene pre-commit check

**Addresses pitfalls:** 01, 02, 04, 05, 12, 14, 15, 16, 21, 22, 23, 24, 29

**Research flag:** No additional research needed — architecture fully specified; pitfalls pre-catalogued.

**Phase exit gate:** `test_contracts.py` string assertions pass; `isinstance(MockRealtimeProvider(), RealtimeAdapterContract)` is True.

---

### Phase 2: OpenAI Realtime Provider Port

**Rationale:** OpenAI is the reference implementation and the primary GlassAgents consumer target. Port after foundation is locked. Reconcile `server_vad` / `include_turn_detection` discrepancy (PITFALL-28) as the first task of this phase.

**Delivers:**
- `realtime/providers/openai.py`: `OpenAIRealtimeClient` (391 LOC port from GlassAgents `client.py`), `OpenAIRealtimeConfig`, `OPENAI_REALTIME_CAPABILITIES`
- Validated current model name — verify against OpenAI API before hardcoding default (PITFALL-19)
- Pending cancel queue for `cancel_response()` during reconnect (PITFALL-03)
- `tests/unit/realtime/test_realtime_openai.py` with hand-crafted, scrubbed replay fixture frames

**Avoids:** PITFALL-03, 11, 19, 28

**Research flag:** No research needed — GlassAgents `client.py` is authoritative; verify current OpenAI model alias only (15-minute check).

**Phase exit gate:** Integration test with real API key connects, receives `SESSION_READY`, sends audio chunk, disconnects cleanly.

---

### Phase 3: Gemini Live Provider Port + Nova Sonic Stub

**Rationale:** Gemini Live is the second production provider; Nova Sonic stub is trivial (<30 LOC). Port together. Gemini is the heavier lift (919 LOC) but the patterns are established after Phase 2.

**Delivers:**
- `realtime/providers/gemini_live.py`: `GeminiLiveClient` (919 LOC port), `GeminiLiveConfig`, `GEMINI_LIVE_REALTIME_CAPABILITIES`
- Redaction helpers ported verbatim: `_redact_sensitive_url`, `_redact_sensitive_text` (PITFALL-17)
- Tool name lookup with WARNING log on stale reconnect state (PITFALL-10)
- Verified current Gemini model name (PITFALL-20)
- `realtime/providers/nova.py`: `NovaSonicStub` raising `NotImplementedError` with message pointing to v1.9.0
- `tests/unit/realtime/test_realtime_gemini.py`, `tests/unit/realtime/test_realtime_nova.py`

**Avoids:** PITFALL-09, 10, 13, 17, 20

**Research flag:** No research needed — GlassAgents `gemini_live.py` is authoritative; verify model name at phase start.

**Phase exit gate:** Integration test with Vertex EU region (`europe-west*`) connects and receives `SESSION_READY`; `_connection_error_endpoint()` unit test confirms no API key in returned URL.

---

### Phase 4: CLI + Hardening + Docs

**Rationale:** All providers exist; ship the developer-facing surface, validate the GlassAgents migration path, and document consumer constraints before cutting the v1.8.0 tag.

**Delivers:**
- `cli.py` `realtime-test` command: `eq-chatbot realtime-test -p openai|gemini_live|nova_sonic|mock`
- `docs/realtime.md`: async-only interface contract, PCM16 requirement, sidecar exclusion, Rust CLI exclusion, tool-calling consumer patterns (RESPONSE_CREATED before tool result), reconnect semantics
- GlassAgents string cross-reference check: grep validates all 12 constants match hardcoded strings in GlassAgents `bridge.py` (PITFALL-27)
- `CHANGELOG.md` v1.8.0 entry; version bump `1.8.0.dev0` → `1.8.0` in `version.py`
- CI passing on Python 3.10–3.13 matrix

**Avoids:** PITFALL-25, 26, 27

**Research flag:** No research needed.

**Phase exit gate:** Full CI matrix green; GlassAgents grep check clean; `twine check dist/*` passes on built wheel.

---

### Phase Ordering Rationale

- Phase 0 before Phase 1: both touch `providers/__init__.py` and `cli.py`. Doing the refactor first keeps diffs clean and avoids merge conflicts; 3 files, zero behavior change.
- Phase 1 before any provider: `contracts.py` defines the types every provider implements. Writing providers before contracts means writing against a moving target.
- Phase 2 (OpenAI) before Phase 3 (Gemini): OpenAI is GlassAgents' primary provider; contract shape issues surface earlier. The `manual_turn_commit_required` pattern in Gemini builds on OpenAI patterns.
- Phase 4 last: docs depend on implementation details being locked; CLI `realtime-test` depends on factory (Phase 1) and at least one production provider (Phase 2).

### Research Flags

No additional research required before any phase — all architecture is fully specified from the GlassAgents reference implementation and existing codebase analysis.

**Validation gates per phase (not research, but must complete before phase exit):**
- Phase 1: string assertion tests pass; MockRealtimeProvider Protocol check passes
- Phase 2: `server_vad`/`include_turn_detection` reconciled; integration test with real key succeeds
- Phase 3: Gemini redaction unit test passes; Vertex EU region integration test succeeds
- Phase 4: GlassAgents string cross-reference grep clean; full CI matrix green

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Dependencies verified via PyPI METADATA; version constraints cross-checked against google-genai and openai SDK source; websockets version resolution confirmed via UV constraints |
| Features | HIGH | Provider evaluations based on official API docs + GlassAgents production code; all 12 providers assessed with concrete fit-to-contract ratings |
| Architecture | HIGH | Based on direct inspection of GlassAgents source (~2 070 LOC) and existing eq-chatbot-core codebase; component boundaries derived from production code, not speculation |
| Pitfalls | HIGH | 29 pitfalls sourced from actual GlassAgents code paths (line-number referenced), existing CONCERNS.md anti-patterns, and TESTING.md documented bugs |

**Overall confidence:** HIGH

### Gaps to Address

- **OpenAI current model alias:** `gpt-realtime` in handoff spec may not be a valid API model ID. Verify at Phase 2 start. 15-minute check against OpenAI models list.
- **Gemini model name rotation:** `gemini-2.5-flash-native-audio-preview-12-2025` is a dated preview alias. Verify at Phase 3 start and set up integration test to catch future retirement.
- **ElevenLabs EU residency:** Standard SaaS GDPR DPA confirmed; EU-sovereign inference node NOT confirmed. Must pass Captain's EU-gate before v1.9.0 consideration.
- **DeepGram EU residency:** Same gate — verify before v1.9.0 RFC.
- **Hume EVI Python 3.12/3.13 SDK compatibility:** Not confirmed as of research date. Must verify before v1.9.0 RFC.
- **`server_vad` vs `include_turn_detection` reconciliation:** Architectural ambiguity in OpenAI provider — capabilities are currently module-level constants but should reflect per-config state. Resolve in Phase 2 design step, not during coding.

---

## Permanently Excluded Providers

The following providers are OUT OF SCOPE for all versions of eq-chatbot-core's realtime layer:

| Provider | Reason | Revisit? |
|---|---|---|
| xAI Grok Voice Agent | CAPTAIN POLICY: EU/GDPR non-compliant; no EU data-residency | No — permanent exclusion |
| Mistral Voxtral | No bidirectional speech-to-speech session API; STT+TTS pipeline only | Only if Mistral ships a session-based conversational API |
| Cartesia Sonic | TTS-only; no STT or bidirectional session | Only if Cartesia ships a full pipeline conversational API |
| LiveKit Agents | Application framework, not a provider | Never — correct relationship is consumer uses LiveKit + library providers |

---

## Sources

### Primary (HIGH confidence)
- GlassAgents `backend/realtime/websocket_client.py` (174 LOC) — base class error paths, line-level analysis
- GlassAgents `backend/realtime/client.py` (391 LOC) — OpenAI production implementation
- GlassAgents `backend/realtime/providers/gemini_live.py` (919 LOC) — Gemini Live production implementation
- GlassAgents `backend/realtime/abc.py` (137 LOC) — minimal ABC reference
- GlassAgents `backend/realtime/contracts.py` (101 LOC) — Protocol + event schema reference
- GlassAgents `backend/realtime/factory.py` (177 LOC) — registry reference
- GlassAgents `docs/eq-chatbot-core-realtime-handoff.md` — authoritative migration spec
- `eq-chatbot-core/.planning/codebase/CONCERNS.md` — known anti-patterns (hardcoded lists, sync I/O in async handlers)
- `eq-chatbot-core/.planning/codebase/TESTING.md` — sys.modules mock patterns, pytest-asyncio scope behaviour
- PyPI METADATA `openai==2.38.0` — `websockets<16,>=13; extra == "realtime"` confirmed
- PyPI METADATA `google-genai==2.6.0` — `websockets<17.0,>=13.0.0` (core dep) confirmed

### Secondary (MEDIUM confidence)
- [OpenAI Realtime API docs](https://openai.com/index/advancing-voice-intelligence-with-new-models-in-the-api/) — GA status, model names, pricing, EU/GDPR DPA requirement
- [Gemini Live API docs](https://ai.google.dev/gemini-api/docs/live-api) — WebSocket protocol, Vertex EU regions, VAD behaviour
- [AWS Nova Sonic docs](https://docs.aws.amazon.com/nova/latest/userguide/speech-bidirection.html) — HTTP/2 bidi transport confirmed; EU sovereign cloud (eu-north-1, Germany)
- [DeepGram Voice Agent API](https://deepgram.com/product/voice-agent-api) — WebSocket transport, BYOLLM, $4.50/hr flat pricing
- [ElevenLabs Agent WebSocket API](https://elevenlabs.io/docs/eleven-agents/api-reference/eleven-agents/websocket) — 16 kHz audio format, agent-centric config model
- [Hume EVI 3 announcement](https://www.hume.ai/blog/announcing-evi-3-api) — emotion output events, conditional tool calling
- [xAI Voice Agent API docs](https://docs.x.ai/developers/model-capabilities/audio/voice-agent) — OpenAI-compatible protocol; EU DPA stated but sovereign cloud status unverified
- [websockets changelog](https://websockets.readthedocs.io/en/stable/project/changelog.html) — version history, Python compatibility matrix

### Tertiary (LOW confidence)
- google/genai live.py `from websockets.asyncio.client import connect` — inferred from PyPI dep graph + WebSearch; MEDIUM confidence via dep graph confirmation
- ElevenLabs EU-sovereign inference node — NOT confirmed; needs direct vendor verification before v1.9.0

---

*Research completed: 2026-05-24*
*Ready for roadmap: yes*
