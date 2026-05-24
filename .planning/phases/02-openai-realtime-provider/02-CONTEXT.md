# Phase 2: OpenAI Realtime Provider - Context

**Gathered:** 2026-05-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Port `OpenAIRealtimeClient` (~391 LOC) from the GlassAgents reference implementation into `src/eq_chatbot_core/realtime/providers/openai.py` with feature parity across all 11 `RealtimeAdapterContract` methods. Ship `OpenAIRealtimeConfig` (frozen dataclass) and the `OPENAI_REALTIME_CAPABILITIES` constant, register the provider in the Phase 1 factory, and deliver the OpenAI-specific unit suite (`test_realtime_openai.py`) plus one live integration test.

Requirements in scope: PROV-01, PROV-02, PROV-03, PROV-04, QUAL-01 (OpenAI portion), QUAL-03 (OpenAI portion). Gemini Live and Nova Sonic are Phase 3 — not this phase.

This phase clarifies HOW to port (model strategy was the discussed gray area). Gemini/Nova, multi-format audio negotiation, and the GlassAgents-side migration are explicitly out of scope.

</domain>

<decisions>
## Implementation Decisions

### Default Model Strategy
- **D-01:** `OpenAIRealtimeConfig.model` defaults to the **floating `gpt-realtime` alias** (not a pinned dated snapshot). Rationale: zero maintenance, always tracks OpenAI's current GA Realtime model. Accepted tradeoff: server-side behavior can shift without a library release (not byte-reproducible). Consumers who need reproducibility can pin a dated snapshot explicitly.
- **D-02:** SC-2 (live model verification) is satisfied by the **gsd-phase-researcher verifying the default model name live against the OpenAI models list at phase start**, recording the result (and the current dated snapshot the alias resolves to) in `02-RESEARCH.md`. No runtime model-list call is added to the library — keeps it lean and avoids a per-session network roundtrip. The verified snapshot SHOULD be noted in a code comment / CHANGELOG for consumers who want to pin.
- **D-03:** On an invalid/rejected model name, the provider **fails fast with a clear, library-native exception** (mapped into the existing `ProviderError`/`AuthenticationError`-style hierarchy with a message pointing at valid models) rather than passing the raw OpenAI error through. Rationale: consistent error quality with the chat-completion providers.

### Claude's Discretion (areas not selected for discussion — follow the handoff reference)
The Captain chose to discuss only the model strategy. The following follow the GlassAgents handoff spec defaults; the researcher/planner should confirm exact semantics against the reference `client.py` and may refine:

- **VAD / Turn-Detection (PITFALL-28 — SC-1, goal-critical):** Follow the reference — `OPENAI_REALTIME_CAPABILITIES.server_vad = true` (reflects the provider's native capability) and `OpenAIRealtimeConfig.include_turn_detection` defaults to `true` (server VAD on, `manual_turn_commit_required = false`). The reconciliation rule (what `include_turn_detection=False` does to the session payload, and whether the static capability flag stays `true` while the session disables VAD) **MUST be resolved and documented in a code comment before implementation begins** — this is success criterion SC-1. Researcher to extract the exact intended behavior from the reference `client.py` and `providers/openai.py`.
- **Port strategy / base class:** Priority is faithful feature parity of the 11-method surface. The reference `client.py` is a standalone client; the planner decides whether to extend the Phase 1 `BaseRealtimeWebsocketClient` (sharing auth/retry/reconnect) or keep it standalone — preferring reuse of the base class where it does not compromise parity. Note: Phase 1's CR-02 fix makes `BaseRealtimeWebsocketClient._connection_error_endpoint` abstract (`NotImplementedError`), so any subclass MUST override it; and the CR-03 fix added import-time `inspect.signature` kwarg detection for the websockets headers argument.
- **Config surface & defaults:** Use the handoff §5 dataclass verbatim — `OpenAIRealtimeConfig(api_key, model="gpt-realtime", voice="ash", instructions=None, include_turn_detection=True)`, frozen + slots. Tool-result submission mode is `conversation_item` (locked by the capability table in handoff §3.3). Reuse the Phase 1 `ToolDefinition` dataclass — realtime and chat tools share one shape.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Handoff spec (authoritative)
- `/Users/picard/gitbase/GlassAgents/docs/eq-chatbot-core-realtime-handoff.md` — full implementation handoff; §3 contract surface, §3.3 capability table, §4.1 OpenAI port notes, §5 proposed config dataclasses, §7 acceptance criteria, §9 open questions (Q2 reuse of existing primitives).

### OpenAI reference sources (GlassAgents `develop`) — port targets
- `/Users/picard/gitbase/GlassAgents/backend/realtime/client.py` (391 LOC) — `OpenAIRealtimeClient` reference implementation to port.
- `/Users/picard/gitbase/GlassAgents/backend/realtime/providers/openai.py` (77 LOC) — OpenAI provider builder + `OPENAI_REALTIME_CAPABILITIES` values + `OpenAIRealtimeConfig`.
- `/Users/picard/gitbase/GlassAgents/backend/realtime/contracts.py` (101 LOC) — `RealtimeAdapterContract` Protocol + event schema + capabilities (authoritative shapes).
- `/Users/picard/gitbase/GlassAgents/backend/realtime/abc.py` (137 LOC) — minimal `RealtimeProvider` ABC variant.
- `/Users/picard/gitbase/GlassAgents/backend/realtime/websocket_client.py` (174 LOC) — reference `BaseRealtimeWebsocketClient` (compare against the Phase 1 port).
- `/Users/picard/gitbase/GlassAgents/backend/realtime/factory.py` (177 LOC) — registry + `build_default_realtime_provider_registry()`.

### Project planning refs
- `.planning/ROADMAP.md` §"Phase 2: OpenAI Realtime Provider" — goal, requirements, success criteria.
- `.planning/REQUIREMENTS.md` — PROV-01…PROV-04, QUAL-01/QUAL-03 split notes.
- `.planning/phases/01-contracts-foundation/01-SUMMARY.md` … `01-05-SUMMARY.md` — what Phase 1 shipped that this builds on.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phase 1)
- `src/eq_chatbot_core/realtime/websocket_client.py` — `BaseRealtimeWebsocketClient` with `connect`/`send`/`recv`/`close`, async context manager, leak protection, and `connect_with_backoff` (post-fix: now retries `RealtimeRateLimitError`; headers kwarg resolved at import time via `inspect.signature`; `_connection_error_endpoint` is abstract and MUST be overridden).
- `src/eq_chatbot_core/realtime/contracts.py` — `RealtimeAdapterContract` Protocol, `NormalizedRealtimeEvent` (type+payload required) / `NormalizedRealtimeEventFull` (adds source/raw), 12 `NormalizedRealtimeEventTypes` constants, `RealtimeProviderCapabilities`, `INPUT_AUDIO_SAMPLE_RATE = 24000`.
- `src/eq_chatbot_core/realtime/abc.py` — `RealtimeProvider` ABC + 7 event dataclasses.
- `src/eq_chatbot_core/realtime/factory.py` — `RealtimeProviderRegistry` + `get_realtime_provider`; register `"openai"` here.
- `src/eq_chatbot_core/realtime/providers/__init__.py` — empty sub-package; `openai.py` lands here.
- `src/eq_chatbot_core/providers/base.py` — `ToolDefinition` frozen dataclass (re-exported); reuse for realtime tools.
- `tests/unit/realtime/conftest.py` — AsyncMock websockets fixture (restores `sys.modules`); reuse for `test_realtime_openai.py` unit tests.
- Existing chat-provider exception hierarchy (`ProviderError`, `RateLimitError`, `AuthenticationError`, `ContextLengthError`, `OverloadedError`) — map OpenAI Realtime failures into it (supports D-03 fail-fast).

### Established Patterns
- Optional heavy deps gated behind extras — realtime uses the `[realtime]` extra (websockets); the import guard lives in `realtime/__init__.py`.
- Unit tests mock the websockets SDK at module level (no real network); integration tests are skipped when the API key is absent.

### Integration Points
- Register the OpenAI provider in `realtime/factory.py` so `get_realtime_provider("openai", ...)` resolves.
- Re-export `OpenAIRealtimeClient`, `OpenAIRealtimeConfig`, `OPENAI_REALTIME_CAPABILITIES` per handoff §5 API surface.
- WebSocket endpoint: `wss://api.openai.com/v1/realtime?model=...`.

</code_context>

<specifics>
## Specific Ideas

- Default voice `"ash"`, default model alias `"gpt-realtime"` (per handoff §5).
- Integration test (SC-3): connect → receive `SESSION_READY` normalized event → send one PCM16 chunk → clean disconnect; skipped when `OPENAI_API_KEY` is absent.

</specifics>

<deferred>
## Deferred Ideas

- Gemini Live + Nova Sonic providers — Phase 3.
- Production AWS Bedrock Nova Sonic implementation (handoff Q1) — stub-only for 1.8.0; promote later if a user lands.
- Multi-format audio negotiation (Opus / μ-law, handoff Q3) — PCM16-only for 1.8.0; defer to a later minor.
- `realtime-test` CLI command (QUAL-04) and CHANGELOG/README (REL-03) — tracked in the milestone; sequence per ROADMAP.

</deferred>

---

*Phase: 2-openai-realtime-provider*
*Context gathered: 2026-05-24*
