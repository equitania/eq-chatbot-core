# Phase 3: Gemini Live + Nova Sonic Stub - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 03-gemini-live-nova-sonic-stub
**Areas discussed:** API Target & EU Residency, Model Alias Strategy, Nova Stub Message, (freeform: alternative/local models)

---

## API Target & EU Residency

| Option | Description | Selected |
|--------|-------------|----------|
| Vertex AI EU primary | Adapt port to Vertex europe-west (ADC), DSGVO-compliant, diverges from 1:1 port | |
| Both (config-driven) | GeminiLiveConfig supports Developer API (api_key) AND Vertex (region+ADC), switchable | ✓ |
| Developer API (1:1 port) | Faithful 919-LOC port, key-in-URL, not EU-compliant by default | |

**User's choice:** Both (config-driven)
**Notes:** Resolves the PROV-07 (key-in-URL redaction) vs SC-3 (europe-west Vertex test) conflict — redaction covers both auth styles. Preserves faithful Developer-API port and adds the EU-compliant Vertex path. Aligns with the ElevenLabs preferred-GDPR-provider decision.

---

## Model Alias Strategy (PITFALL-20)

| Option | Description | Selected |
|--------|-------------|----------|
| Floating like OpenAI D-01/D-02 | Floating alias default, researcher verifies live-valid alias for both endpoints at phase start | ✓ |
| Pinned snapshot | Fixed dated snapshot, byte-reproducible, updates via release | |
| Researcher decides | Leave strategy open, researcher recommends | |

**User's choice:** Floating like OpenAI D-01/D-02
**Notes:** Consistent with Phase 2. Researcher must verify the alias for BOTH Developer API and Vertex (may differ) and record the resolved snapshot in 03-RESEARCH.md.

---

## Nova Stub NotImplementedError Message

| Option | Description | Selected |
|--------|-------------|----------|
| Concise + v1.9.0 reference | Short clear message pointing to v1.9.0, minimal stub <30 LOC | ✓ |
| Verbose + [realtime-aws] hint | Message also explains future boto3 install path | |

**User's choice:** Concise + v1.9.0 reference
**Notes:** Factory registration (SC-5) is mandatory regardless of message verbosity.

---

## Claude's Discretion

- Exact GeminiLiveConfig field names and the developer-vs-vertex mode-switch mechanism.
- Whether GeminiLiveClient extends BaseRealtimeWebsocketClient or stays standalone (prefer reuse without compromising parity).
- Precise wording of the Nova NotImplementedError message (must reference v1.9.0).

## Deferred Ideas

- **Local / on-prem realtime provider** (v1.9.0 backlog). Raised via the Captain's freeform question
  about Ollama/LM Studio and alternative vendors. Conclusion: Ollama/LM Studio have no native
  realtime S2S WebSocket API; local realtime needs either a cascade (STT→LLM→TTS) or a native local
  S2S/omni model (Moshi, Qwen-Omni, GLM-4-Voice, LLaMA-Omni 2) on its own server — a different
  architecture than Phase 3's native-S2S providers. Strongest GDPR option (data stays on-prem).
  Candidate future phase alongside Nova Sonic production (PROV-FUT-01).
