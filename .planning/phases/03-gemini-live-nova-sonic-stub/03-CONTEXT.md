# Phase 3: Gemini Live + Nova Sonic Stub - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Two production-set completions for the v1.8.0 realtime provider family:

1. **`GeminiLiveClient`** — a faithful port (~919 LOC from GlassAgents) of the Gemini Live
   speech-to-speech provider implementing all 11 `RealtimeAdapterContract` methods, with
   BidiGenerateContent protocol handling, manual turn commit, and `provider_call_id` tool-result
   schema. Built on raw websockets (NOT the google-genai SDK — locked in Phase 1/2 stack research).
2. **`NovaSonicStub`** — a minimal (<30 LOC) stub satisfying `RealtimeAdapterContract`
   structurally, every method raising `NotImplementedError` pointing to v1.9.0.

**In scope:** Gemini provider (both endpoints), Nova stub, factory registration for both,
unit tests (`test_realtime_gemini.py`, `test_realtime_nova.py`), Gemini EU integration test.
**Out of scope:** Nova Sonic production implementation (v1.9.0, PROV-FUT-01), CLI/docs/release (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### API Target & EU Residency (the key decision — resolves PROV-07 vs SC-3 conflict)
- **D-01:** `GeminiLiveConfig` supports **both** Google endpoints, **config-driven**:
  - **Gemini Developer API** — `api_key` auth, key-in-URL (`?key=...`), global/US endpoint. This is
    the faithful GlassAgents port path.
  - **Vertex AI Live API** — ADC/service-account auth (OAuth bearer), regional `europe-west*`
    endpoint (`{region}-aiplatform.googleapis.com`). The DSGVO-compliant path; satisfies SC-3.
  - Switchable via a `mode`/`base_url`/`region` field on the config. Planner decides the exact
    config surface (e.g., explicit `mode: "developer" | "vertex"` vs. inferred from presence of
    `region`/`project`).
- **D-02:** **Redaction (PROV-07) covers both modes.** Port `_redact_sensitive_url` /
  `_redact_sensitive_text` and extend so they redact the Developer-API `key=` query param AND
  Vertex OAuth bearer tokens / project identifiers. The "API key never leaks to logs" guarantee
  applies to both auth styles.
- **D-03:** SC-3's EU integration test uses the **Vertex `europe-west*`** path. Unit tests
  (QUAL-01) cover **both** endpoint modes via recorded scrubbed frames. Expanded test matrix is
  an accepted tradeoff for the flexibility + EU compliance.

### Model Alias Strategy (PITFALL-20 — mirrors Phase 2 D-01/D-02)
- **D-04:** `GeminiLiveConfig.model` defaults to a **floating alias** (zero-maintenance, tracks
  Google's current Live model), NOT a pinned snapshot — consistent with the OpenAI provider.
- **D-05:** PITFALL-20 is satisfied by the **gsd-phase-researcher verifying the live-valid model
  alias at phase start** for BOTH endpoints (Developer API and Vertex may expose different aliases),
  recording the resolved snapshot(s) in `03-RESEARCH.md`. No runtime model-list call added to the
  library. Verified snapshot noted in a code comment / CHANGELOG for consumers who want to pin.
- **D-06:** On invalid/rejected model, **fail fast with a library-native exception** (mirrors
  Phase 2 D-03) rather than passing the raw Google error through.

### Nova Sonic Stub
- **D-07:** `NovaSonicStub` raises `NotImplementedError` with a **concise message pointing to
  v1.9.0** (satisfies PROV-08 / SC-4 exactly). No `[realtime-aws]`/boto3 install instructions in
  the message — keep the stub minimal (<30 LOC).
- **D-08:** Stub **is registered in the factory** so `get_realtime_provider("nova_sonic")` resolves
  without installing any AWS extras (SC-5 — mandatory regardless).

### Claude's Discretion
- Exact `GeminiLiveConfig` field names and the developer-vs-vertex mode-switch mechanism.
- Whether `GeminiLiveClient` extends `BaseRealtimeWebsocketClient` (sharing auth/retry/reconnect)
  or stays standalone — prefer base-class reuse where it does not compromise port parity
  (carry-forward from Phase 2). Note: `BaseRealtimeWebsocketClient._connection_error_endpoint` is
  abstract and MUST be overridden.
- Precise wording of the Nova `NotImplementedError` message (must reference v1.9.0).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 3: Gemini Live + Nova Sonic Stub" — goal + 5 success criteria
- `.planning/REQUIREMENTS.md` — PROV-05, PROV-06, PROV-07, PROV-08, QUAL-01 (Gemini+Nova), QUAL-03 (Gemini)

### Patterns to mirror (Phase 2 establishes the analog)
- `.planning/phases/02-openai-realtime-provider/02-CONTEXT.md` — D-01/D-02/D-03 model + port decisions this phase mirrors
- `src/eq_chatbot_core/realtime/providers/openai.py` — closest analog: config dataclass, capabilities constant, `_safe_url()` redaction, fail-fast `__init__`, factory wiring
- `src/eq_chatbot_core/realtime/contracts.py` — `RealtimeAdapterContract`, `NormalizedRealtimeEventTypes`, `RealtimeProviderCapabilities`
- `src/eq_chatbot_core/realtime/abc.py` — `BaseRealtimeWebsocketClient` (abstract `_connection_error_endpoint`)
- `src/eq_chatbot_core/realtime/factory.py` — registry pattern, deferred-import `_build_*_provider`

### Source of the port
- GlassAgents reference `GeminiLiveClient` (~919 LOC) + `_redact_sensitive_url`/`_redact_sensitive_text` — researcher to locate per the Phase 2 handoff pattern (same source repo as the OpenAI port).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `providers/openai.py` (Phase 2): direct template for config/capabilities/redaction/factory structure.
- `contracts.py`: `session_sample_rate` default 24_000 (Gemini default) — no override needed for Gemini (the 16k override was ElevenLabs-specific).
- Phase 1 `ToolDefinition` dataclass: shared across chat + realtime; Gemini uses `provider_call_id` tool-result mode.

### Established Patterns
- Factory registers providers under canonical names with deferred imports — add `gemini_live` and `nova_sonic`.
- Fail-fast in `__init__` before network I/O (D-03 pattern from Phase 2).

### Integration Points
- `get_realtime_provider("gemini_live", ...)` and `get_realtime_provider("nova_sonic")` — both wired in `factory.py`.

</code_context>

<specifics>
## Specific Ideas

- The dual-endpoint design directly serves the project's GDPR posture: Vertex `europe-west*` is the
  EU-compliant path, aligned with the ElevenLabs preferred-provider decision (see
  `docs/superpowers/specs/2026-05-25-elevenlabs-realtime-provider-design.md`).

</specifics>

<deferred>
## Deferred Ideas

- **Local / on-prem realtime provider (v1.9.0 backlog candidate).** Ollama and LM Studio do NOT
  expose a native realtime speech-to-speech WebSocket API — they are text/vision LLM servers and
  do not fit `RealtimeAdapterContract` directly. Two future paths, both a *different architecture*
  than the native-S2S providers: (1) a **cascade** orchestrator (local STT → local LLM → local TTS;
  e.g., faster-whisper → Ollama → Piper/Kokoro/Qwen3-TTS), or (2) a **native local S2S/omni**
  adapter (Moshi/Kyutai, Qwen2.5/3-Omni, GLM-4-Voice, LLaMA-Omni 2 — run on their own servers).
  This is the **strongest** GDPR option (data never leaves premises; self-hosted open weights are
  DSGVO-unproblematic). Belongs in its own future phase alongside the Nova Sonic production
  implementation (PROV-FUT-01), not Phase 3.

</deferred>

---

*Phase: 03-gemini-live-nova-sonic-stub*
*Context gathered: 2026-05-25*
