---
project_code: ECC
project_title: eq-chatbot-core
---

# eq-chatbot-core

## What This Is

Standalone Python library that provides a unified, provider-agnostic interface to a curated set of cloud and local LLM backends (OpenAI, Anthropic, Azure AI Foundry, Google Vertex/Gemini, LangDock, OpenRouter, Mammouth, LM Studio, Ollama) for chatbot and agent applications. Originally extracted from the Odoo `eq_chatbot` module for independent PyPI publishing; consumed by Odoo, Avalonia/.NET desktop apps (fr-designer), Rust CLI tools (sysReporter), and a Swift/iOS realtime voice agent (GlassAgents).

## Core Value

**One factory call gets the consumer a working LLM client for any supported provider, with consistent response shapes, exception hierarchy, and cost accounting — no SDK lock-in, no provider-specific glue code in the consuming app.**

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Multi-provider chat completion factory (`get_provider`) — v1.0.0
- ✓ Streaming completion support across all providers — v1.0.0
- ✓ Vision / multimodal input (OpenAI, Anthropic, LangDock) — v1.3.0
- ✓ Anthropic prompt caching via `ChatMessage.cache_control` — v1.7.2
- ✓ Tool/function calling (OpenAI, Anthropic, OpenRouter, Mammouth) — v1.5.0
- ✓ Azure AI Foundry provider (`[azure]` extra) — v1.1.0
- ✓ Google Vertex AI / Gemini provider (`[vertex]` extra) — v1.6.0
- ✓ Mammouth AI unified gateway (30+ models) — v1.5.1
- ✓ Local provider (LM Studio / Ollama) — v1.0.0
- ✓ Temperature constraints module (shared clamp logic, reasoning-model skip) — v1.7.0
- ✓ Cost service with OpenRouter provider-prefix stripping — v1.7.2
- ✓ MCP client (HTTP/SSE + stdio) with DNS-rebinding protection — v1.6.0
- ✓ Fernet API-key encryption + prompt-injection detection + token-bucket rate limiter — v1.0.0
- ✓ RAG pipeline (chunker, embedder, Qdrant retriever, context manager) — v1.0.0
- ✓ HTTP/SSE sidecar server (`[server]` extra) for cross-language consumers — v1.7.0
- ✓ `eq-chatbot` CLI: `test-provider`, `list-models`, `chat` (JSON I/O), `serve`, `info` — v1.5.0
- ✓ Knowledge export service for vector DBs and LangDock Knowledge Folders — v1.4.0
- ✓ 1 125+ unit tests + ~30 integration tests + per-run Markdown report — v1.6.0
- ✓ GitHub Actions CI matrix Python 3.10–3.13 — v1.6.0

### Active

<!-- Current scope. Building toward these. -->

See **Current Milestone** below.

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- **Provider-specific business logic** (prompt templates, routing rules, agent loops) — Belongs in consumer apps. Library stays a thin transport layer.
- **Audio-input transcription pipelines (Whisper, etc.)** — Outside scope until a concrete consumer drives it; today realtime voice handles audio end-to-end via provider-native streams.
- **Vector DB write/upsert workflows** — Library retrieves; ingestion is consumer-owned.
- **Conversation persistence / session storage** — Consumers own their state; library is stateless.
- **Browser/UI components** — Pure backend library; no JS, no widgets.
- **Background task scheduling / job queues** — Consumers run loops; library yields chunks.
- **Multi-tenancy / per-user rate-limit accounting** — Token-bucket primitive is provided; tenancy is consumer concern.

## Context

**Origin:** Extracted from the Odoo `eq_chatbot` module (v18) to enable reuse across non-Odoo consumers. Today depended on by:
- `eq_chatbot` Odoo 18 module (primary consumer, server-side LLM)
- `fr-designer` Avalonia/.NET desktop app (via HTTP sidecar `[server]` extra)
- `sysReporter` Rust CLI (via `eq-chatbot chat` JSON I/O)
- `odoo-translator` Python CLI (batch translation via direct import)
- `GlassAgents` Swift/iOS voice agent backend (incoming v1.8.0 consumer for realtime)

**Maintained by:** Equitania Software GmbH (Captain: Martin Schmid).

**Distribution:** PyPI (`eq-chatbot-core`). Build and publish run locally via `/afterwork` workflow — CI handles lint + test only (not publish).

**Development philosophy:**
- UV-only for dependency management (never pip)
- Optional heavy deps gated behind extras (`[azure]`, `[vertex]`, `[server]`, `[pdf]`, `[security]`, `[local]`)
- Sync provider interface (consumers wrap in `asyncio.to_thread` if needed)
- Stateless provider instances; no module-level singletons
- Bilingual docs (DE/EN) with anchored cross-refs

## Constraints

- **Tech stack:** Python 3.10+ (union-type syntax `X | Y` used throughout); pure Python library
- **Package manager:** UV mandatory (lockfile `uv.lock` committed)
- **Build:** hatchling backend, version source `src/eq_chatbot_core/version.py`
- **Compatibility:** Python 3.10, 3.11, 3.12, 3.13 (CI matrix all four)
- **Provider SDKs:** Pinned major-version ceilings (e.g., `openai>=2.0,<3.0`, `anthropic>=0.90,<2.0`)
- **Security:** Bearer-token auth on HTTP sidecar (constant-time compare); FD-based token passing to avoid `argv`/`ps` leak; DNS-rebinding protection in MCP client
- **Testing:** Unit + integration tests run in **separate pytest sessions** (sys.modules mock-leak workaround); LM Studio required for full coverage
- **Documentation:** Bilingual DE/EN (`docs/*.md` with `#deutsch` / `#english` anchors)
- **Release:** Local-only build/publish; CI does lint+test+build-check (no upload)

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| UV instead of pip | 10-100× faster installs, deterministic lockfile, modern resolver | ✓ Good |
| Sync provider interface (not async) | Simplifies adapter code; consumers wrap with `asyncio.to_thread` when needed | ✓ Good |
| Optional extras for heavy deps | Core install stays <50 MB; Azure/Vertex/PDF/Server users opt-in | ✓ Good |
| Lazy SDK imports inside provider classes | Library installable without all extras; missing-extra fails at use-time not install-time | ✓ Good |
| Shared `temperature_constraints` module | Single source of truth for reasoning-model skip, Claude-clamp, prefix-strip — replaces 6× duplicated logic across providers | ✓ Good (v1.7.0) |
| Bearer-token auth via FD (not argv) | Token never appears in `ps`/process listings; constant-time compare via `hmac.compare_digest` | ✓ Good |
| Local-only build+publish (no CI publish) | Avoids accidental publishes from PRs; release ritual via `/afterwork` | ✓ Good |
| Unit and integration tests in separate pytest sessions | `sys.modules` mocks leak between sessions; documented in skill + conftest | ⚠️ Revisit (consider stronger isolation) |
| Sync I/O in async FastAPI handlers (server) | Pragmatic — most callers spawn 1 sidecar per process | ⚠️ Revisit (anti-pattern noted in CONCERNS.md) |
| Hardcoded provider name lists in 3 places | Duplicated in `providers/__init__.py`, `server/app.py`, `cli.py` | ⚠️ Revisit (refactor to exported constants) |

## Current Milestone: v1.8.0 Realtime Voice Provider Integration

**Goal:** Port bidirectional voice streaming (OpenAI Realtime + Gemini Live) from GlassAgents into `eq-chatbot-core` as a new `[realtime]` extra, plus evaluate alternative providers to avoid vendor lock-in.

**Target features:**
- `RealtimeAdapterContract` + minimal `RealtimeProvider` ABC + `NormalizedRealtimeEvent` schema (12 event constants) + `RealtimeProviderCapabilities` metadata
- `BaseRealtimeWebsocketClient` with reconnect/backoff
- Production providers: OpenAI Realtime, Gemini Live
- Stub provider: AWS Nova Sonic (ABC conformance only)
- Provider-landscape research: DeepGram Voice Agent, ElevenLabs Conversational AI, Hume AI EVI, xAI Grok Voice, Mistral Voxtral — recommendation per provider for inclusion in 1.8.0 or deferral
- Shared `ToolDefinition` dataclass (Chat + Realtime)
- In-process Mock provider for consumer test suites
- Unit tests per provider + `docs/realtime.md` + CHANGELOG + version bump 1.7.2 → 1.8.0

**Key context:**
- Authoritative spec: `/Users/picard/gitbase/GlassAgents/docs/eq-chatbot-core-realtime-handoff.md`
- Reference sources (~2 070 LOC) in `/Users/picard/gitbase/GlassAgents/backend/realtime/` — battle-tested through Phase 3 Window 1
- Captain decisions: PCM16-only audio · Nova Sonic stub-only · single `[realtime]` extra · minimal own reconnect/auth utilities
- OUT of scope (stays in GlassAgents): `bridge.py`, `audio_uplink.py`, `tool_dispatcher.py`, `turn_state.py`, `session_modes.py`
- Consumed after release by GlassAgents (~2 300 LOC delete on their side)

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-24 after bootstrap for milestone v1.8.0*
