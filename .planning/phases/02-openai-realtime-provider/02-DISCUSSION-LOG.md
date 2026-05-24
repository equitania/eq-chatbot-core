# Phase 2: OpenAI Realtime Provider - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 2-openai-realtime-provider
**Areas discussed:** Default Model Strategy

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| VAD/Turn-Detection (PITFALL-28) | Reconcile static server_vad flag with include_turn_detection config | |
| Default Model Strategy | Floating alias vs pinned snapshot; SC-2 live verification | ✓ |
| Port Strategy / Base-Class | Standalone port vs refactor onto BaseRealtimeWebsocketClient | |
| Config Surface & Defaults | OpenAIRealtimeConfig fields and default voice | |

**User's choice:** Default Model Strategy only. The other three areas left to Claude's discretion (follow handoff reference defaults).

---

## Default Model Strategy

### Q1 — Default for OpenAIRealtimeConfig.model

| Option | Description | Selected |
|--------|-------------|----------|
| Floating 'gpt-realtime' | GA alias, auto-upgrades, zero maintenance, not byte-reproducible | ✓ |
| Pinned dated snapshot | e.g. gpt-realtime-2025-08-28; reproducible but manual bumps | |
| Alias default + snapshot documented | Alias default, verified snapshot noted in comment/CHANGELOG | |

**User's choice:** Floating `gpt-realtime` alias.

### Q2 — How to satisfy SC-2 (live model verification)

| Option | Description | Selected |
|--------|-------------|----------|
| Researcher verifies once at phase start | gsd-phase-researcher checks live, records in RESEARCH.md; no runtime code | ✓ |
| Runtime startup_validation on connect() | Provider checks models API on connect; extra roundtrip per session | |
| Unit test with allowlist | Test asserts default is in a maintained allowlist; no live call | |

**User's choice:** Researcher verifies once at phase start.

### Q3 — Behavior on invalid/rejected model name

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-fast with clear exception | Precise library-native error pointing at valid models; consistent with hierarchy | ✓ |
| Pass-through to OpenAI | Forward raw OpenAI error; less code, inconsistent error quality | |

**User's choice:** Fail-fast with clear, library-native exception.

---

## Claude's Discretion

- **VAD/Turn-Detection (PITFALL-28):** Follow reference — `server_vad=true`, `include_turn_detection=True` default. Exact reconciliation rule to be extracted from reference `client.py` and documented in a code comment before implementation (SC-1, goal-critical).
- **Port strategy / base class:** Planner decides standalone vs extending `BaseRealtimeWebsocketClient`, prioritizing feature parity; prefer base-class reuse where it does not compromise parity.
- **Config surface & defaults:** Use handoff §5 dataclass verbatim (`api_key`, `model="gpt-realtime"`, `voice="ash"`, `instructions=None`, `include_turn_detection=True`); tool-result mode `conversation_item` locked by capability table; reuse Phase 1 `ToolDefinition`.

## Deferred Ideas

- Gemini Live + Nova Sonic providers — Phase 3.
- Production Nova Sonic (AWS Bedrock) — stub-only for 1.8.0 (handoff Q1).
- Multi-format audio negotiation (Opus/μ-law) — PCM16-only for 1.8.0 (handoff Q3).
- `realtime-test` CLI command (QUAL-04) + CHANGELOG/README (REL-03) — milestone-tracked.
