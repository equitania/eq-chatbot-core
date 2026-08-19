# TASKS.md - eq_chatbot_core Review & Improvement Tracking

## Status Overview

| Sprint | Status | Completion |
|--------|--------|------------|
| Sprint 1: Security Fixes | DONE | 100% |
| Sprint 2: Provider Bug Fixes | DONE | 100% |
| Sprint 3: RAG & Service Hardening | DONE | 100% |
| Sprint 4: Infrastructure & Polish | IN PROGRESS | 90% |
| Sprint 5: Security Remediation & Provider Dedup | DONE | 100% |
| Sprint 6: Audit Remediation (v2.1.0) | DONE | 100% |
| Sprint 7: Provider & Legacy Cleanup (v3.0.0) | DONE | 100% |

**Test Suite**: 1781 passed, 0 failed, 5 xfailed (Python 3.12 + 3.13) — down from 1935 because
the pricing, Azure, Vertex and Nova suites were removed with their features in v3.0.0
**Linting**: Clean (ruff)
**Typing**: `mypy --strict` clean — 0 errors (was 157)
**Coverage**: 82%

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

## Sprint 6: Audit Remediation (DONE — v2.1.0)

Triggered by a full project health audit. Everything below was found by that
audit or surfaced while fixing what it found.

- [x] **DNS rebinding closed across all providers.** `validate_url()` only covered
      construction time; requests then went out unpinned. The guard existed in
      `mcp/client.py` but had never been applied to the providers. Extracted to
      `utils/url_validation` and wired into all seven client-constructing providers.
      Revalidates rather than pinning strictly, so CDN IP rotation does not turn
      into connection failures.
- [x] **Three further unpinned paths** found while writing tests: the LangDock agent
      backend (used the module-level `httpx.post`), `download_signed_csv` (response-
      supplied URL with `follow_redirects=True`), and `CapabilityCatalog.from_remote`
      (caller-supplied URL). New `build_validating_transport()` covers targets that
      are not one fixed endpoint.
- [x] **LangDock SDK clients pinned** — the guard had reached its raw httpx client
      only, not the OpenAI/Anthropic SDK clients built from the same `base_url`.
- [x] **`ToolDefinition` never worked on any chat provider.** The base class
      advertised it; only the realtime providers converted it. `to_chat_tool()` +
      `normalize_tools()` added, every chat provider normalizes at its entry point.
- [x] **LangDock Liskov violation** — `reasoning_effort` sat as a positional
      parameter ahead of `**kwargs`, so the 6th positional argument meant something
      different there than on every other provider. Keyword-only now.
- [x] **Typed `ProviderError` lost its status code** — a blanket `except Exception`
      re-wrapped it through `_handle_error()`; all ten handlers now re-raise.
- [x] **`IndexError` on empty `candidates`/`choices`** (Gemini safety-block responses).
- [x] **CVE gates unblocked**: `cryptography` ceiling had excluded its own fix
      (PYSEC-2026-3552); `h2` -> 4.4.1 (PYSEC-2026-3628).
- [x] **`pip-audit --strict` failed on every version bump** — the editable install is
      unresolvable on PyPI between bump and release. Gate now uses `--skip-editable`.
- [x] **`twine check` was broken** — hatchling emits Metadata-Version 2.5, twine 6.x
      rejects it. Floor raised to 7.0.0.
- [x] **`py.typed` added** (PEP 561) — the package is mypy-strict but shipped no
      marker, so downstream consumers saw `Any` throughout.
- [x] **mypy strict 157 -> 0**; CI ratchet replaced by a hard gate.
- [x] **Python floor 3.10 -> 3.12**, aligned with the Odoo 16 interpreter.
- [x] **Networking moved to httpx2**, `openai` floor raised to 3.0.0. `httpx` stays
      for the Anthropic SDK, which still requires `httpx<1`; one transport
      implementation serves both via a `http=` parameter.
- [x] **Shared streamed tool-call fold** (`stream_accumulator`) — was copied
      identically into six providers; net -125 lines.
- [x] **Pre-commit pins realigned** with pyproject (ruff 0.1.9 -> 0.16.3,
      mypy 1.8 -> 2.3.1); the hook had been formatting by different rules than CI.
- [x] Test coverage: `server/lifecycle.py` 22% -> 93%, `utils/pdf.py` 40% -> 88%,
      `langdock_provider.py` 29% -> 64%; suite 1748 -> 1935.

---

## Sprint 7: Provider & Legacy Cleanup (DONE — v3.0.0)

Breaking release. Earlier sprints above still reference components that no longer
exist; those entries are kept as history, not as a description of the code today.

- [x] **Cost calculation removed entirely** — `services/cost_service.py`,
      `services/pricing_catalog.py`, `utils/pricing.py`,
      `data/model_prices.json`, `scripts/update_pricing_snapshot.py` and their
      tests. Some providers reported prices, others did not, and the bundled
      rates went stale between releases. Providers bill their own APIs and show
      actual spend in their own dashboards.
- [x] **Azure and Vertex AI providers removed** — the only two providers with a
      hand-maintained static model catalog (37 / 8 entries) while every other
      provider queries `/v1/models` live. Google and Microsoft models stay
      reachable through `langdock` and `openrouter`. The `gemini_live` realtime
      provider is untouched (it never used `google-genai`).
- [x] **`qdrant-client` moved to a new `[rag]` extra** — it pulled grpcio (~37 MB)
      into every install; nothing imports it at module level. Core install drops
      from 113 MB to 48 MB of site-packages.
- [x] **`NovaSonicStub` removed** — a placeholder promising "v1.9.0".
- [x] **`LangDockExportManager` removed** — orphaned since v1.18.1 dropped the
      `langdock-export` CLI.
- [x] **Privatemode.ai added** — end-to-end encrypted via a local attesting proxy,
      with a confidentiality-boundary check on `base_url`.
- [x] `data/capability_overrides.json` no longer shipped in the wheel.

---

## Remaining Nice-to-Haves (Not Blocking Release)

- [ ] LangDock agent streaming: Implement real streaming when API supports it
- [ ] Async provider support (for FastAPI use cases)
- [ ] German error messages in `langdock_provider.py` lines 389, 945
- [x] Coverage target: 80%+ — reached (82% as of v2.1.0)
- [ ] `langdock_provider.py` consolidation onto `OpenAICompatibleProvider`:
      not possible as-is (one class serves five backends). Coverage is now 64%,
      enough to attempt a composition-based split as a separate piece of work.
