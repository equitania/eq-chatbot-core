# TASKS.md - eq_chatbot_core Review & Improvement Tracking

## Status Overview

| Sprint | Status | Completion |
|--------|--------|------------|
| Sprint 1: Security Fixes | DONE | 100% |
| Sprint 2: Provider Bug Fixes | DONE | 100% |
| Sprint 3: RAG & Service Hardening | DONE | 100% |
| Sprint 4: Infrastructure & Polish | IN PROGRESS | 90% |
| Sprint 5: Security Remediation & Provider Dedup | DONE | 100% |

**Test Suite**: 1748 passed, 0 failed, 5 xfailed
**Linting**: Clean (ruff)

---

## Sprint 1: Security Fixes (DONE)

- [x] MCP Client thread-safety (`_pending_lock` for `_pending_requests`)
- [x] StdioMCPClient event loop (uses `asyncio.get_running_loop()` correctly)
- [x] Injection detection Unicode normalization (NFKD + zero-width stripping)
- [x] File validator MIME-type strictness (same-category aliases only)
- [x] Security tests: `test_injection.py`, `test_file_validator.py`, `test_encryption.py`, `test_rate_limit.py`

## Sprint 2: Provider Bug Fixes (DONE)

- [x] Anthropic tool input: `json.dumps(block.input)` instead of `str()`
- [x] OpenRouter SSE: Warning logging for JSONDecodeError
- [x] OpenAI token API: Case handling verified (no bug - prefixes already lowercase)
- [x] LangDock agent streaming: `stream: False` is intentional (agent backend limitation)
- [x] Provider tests: All provider test files present and passing

## Sprint 3: RAG & Service Hardening (DONE)

- [x] **Chunker infinite-loop bug**: Fixed `start = max(end - overlap, start + 1)`
- [x] **test_chunker.py**: Complete rewrite with proper mock isolation (27 tests)
- [x] Retriever error handling (try/except for embedder + Qdrant)
- [x] Context manager budget validation (ratio sum > 1.0 check)
- [x] Cost service longest-prefix matching (`best_match_len` tracking)
- [x] Error handler jitter (random +-25% on retry backoff)
- [x] RAG tests: `test_chunker.py`, `test_retriever.py`, `test_context_manager.py`, `test_cost_service.py`

## Sprint 4: Infrastructure & Polish (IN PROGRESS)

- [x] Error handler: Configurable error messages (`messages` parameter)
- [x] Cost service: Updated pricing (Feb 2025, added Claude 4.x, o3, gpt-4o updated)
- [x] TASKS.md tracking document
- [ ] GitLab CI/CD pipeline (`.gitlab-ci.yml`)
- [x] Ruff config modernization (`pyproject.toml` `[tool.ruff.lint]` section: E,W,F,I,B,C4,UP)

## Sprint 5: Security Remediation & Provider Dedup (DONE — v1.20.0 / v2.0.0)

- [x] SSRF guard closed on OpenAI/Anthropic providers and the OpenAI/Melious embedders
      (the `[server]` sidecar forwards a client-supplied `base_url` into `get_provider()`)
- [x] `scrub_secrets()` completed across openai/anthropic/azure/openrouter/vertex/mammouth
      error paths and the `server/app.py` responses
- [x] Fixed `AttributeError` during GC when a `base_url` was rejected before the HTTP-client
      attribute was assigned (LangDock/Mammouth/IONOS/LiteLLM/Melious)
- [x] `OpenAICompatibleProvider` base class — removed ~600 lines of byte-identical duplication
      across IONOS/Melious/LiteLLM (and now Azure); public API unchanged
- [x] Azure migrated off the retired `azure-ai-inference` SDK onto the OpenAI `/v1` endpoint
      (Microsoft retirement 2026-08-26)
- [x] CVE floors: `click>=8.3.3`, `cryptography>=46.0.7`, `Pillow>=12.3.0`, `python-dotenv>=1.2.2`
- [x] `pip-audit --strict` promoted to a hard CI gate; mypy ratcheted against a measured baseline
- [x] CI repaired (was red since at least 2026-07-09): `tomllib` import broke collection on
      Python 3.10; the `[image]` extra was never installed so the Pillow code paths were untested

---

## Remaining Nice-to-Haves (Not Blocking Release)

- [ ] LangDock agent streaming: Implement real streaming when API supports it
- [ ] Async provider support (for FastAPI use cases)
- [ ] German error messages in `langdock_provider.py` lines 389, 945
- [ ] Pricing data auto-update mechanism
- [ ] Coverage target: 80%+ (currently ~60% with new tests)
