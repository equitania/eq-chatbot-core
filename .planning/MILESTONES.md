# Milestones

Retroactive milestone log reconstructed from git tags on 2026-05-24 for GSD bootstrap. Pre-1.0 history compressed.

## v0.x — Initial extraction (pre-2026)

**v0.15.0** and earlier — Extraction from Odoo `eq_chatbot` module. Multi-provider factory, base classes, OpenAI + Anthropic + LangDock + Local providers, RAG primitives, security primitives, MCP client foundations, knowledge export skeleton.

## v1.0.0 — Stable factory + streaming + security (2026-01)

- `BaseLLMProvider` ABC frozen as public contract
- All cloud + local providers ship streaming completion
- Vision support across OpenAI, Anthropic, LangDock
- Fernet encryption, prompt-injection detection, token-bucket rate limiter
- Pricing module per model
- 1.x SemVer commitment

## v1.1.0 — Azure AI Foundry (2026-02)

- New `[azure]` extra with `azure-ai-inference` SDK
- Static model catalog (Phi-4, DeepSeek-R1, Llama-3.3-70B)
- Endpoint format `https://<resource>.services.ai.azure.com/models`
- 38 unit tests + 5 integration tests

## v1.3.0 — Vision parity (2026-02)

- Multimodal input normalization across all cloud providers
- PDF → image conversion via `[pdf]` extra (pymupdf)

## v1.4.0 — Knowledge export service (2026-03)

- `KnowledgeService` orchestrator
- Targets: Qdrant chunks, LangDock Knowledge Folders
- Schema/relations/instructions doc generation from Odoo model configs

## v1.5.0 — Tool calling + CLI maturity (2026-03)

- Tool/function calling across OpenAI, Anthropic, OpenRouter, Mammouth
- `eq-chatbot chat` JSON I/O command for cross-language integration
- Stream chunk tool-call accumulation

## v1.5.1 — Mammouth AI provider (2026-03)

- Unified gateway for 30+ models (OpenAI/Anthropic/Google/Mistral/xAI/DeepSeek/Meta)
- Simple model IDs without provider prefix

## v1.6.0 — Vertex AI + CI hardening (2026-04)

- Google Vertex AI / Gemini provider (`[vertex]` extra) with `google-genai` SDK
- ADC (Application Default Credentials) auth
- GitHub Actions CI matrix Python 3.10–3.13
- MCP client SSRF/DNS-rebinding protection (3 layers)
- 1 125+ unit tests

## v1.7.0 — Shared temperature constraints + HTTP server mode (2026-04)

- `providers/temperature_constraints.py`: exact + longest-prefix match, reasoning-model skip, Claude clamp, provider-prefix strip
- All providers delegate to shared `clamp_temperature()`
- New `[server]` extra: FastAPI + Uvicorn + sse-starlette
- `eq-chatbot serve` localhost HTTP/SSE sidecar
- BearerToken auth via FD (no argv leak), parent-pid watchdog
- Documentation split: README hub + `docs/{server-mode,providers,cli,security,mcp,rag,testing}.md`

## v1.7.1 — Hotfix (2026-05)

- Bug fixes carried over from v1.7.0

## v1.7.2 — Anthropic cache_control + cost service fixes (2026-05) — **current**

- `ChatMessage.cache_control` field for Anthropic prompt-caching pass-through
- `cost_service`: strip OpenRouter `provider/` prefix before pricing lookup
- `temperature_constraints`: case-insensitive lookup, duplicate cleanup

## v1.8.0 — Realtime Voice Provider Integration (in planning)

See `.planning/PROJECT.md` Current Milestone for goals and target features.
