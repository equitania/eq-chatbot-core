# Codebase Concerns

**Analysis Date:** 2026-05-11

## Tech Debt

**`list_models()` return type inconsistency:**
- Issue: `BaseLLMProvider.list_models()` declares `list["ModelInfo"] | list[dict[str, Any]]` but all concrete providers return `list[dict[str, Any]]`. The `ModelInfo` dataclass in `base.py` is exported but never actually returned by any provider. The docstring says "Future versions will standardize on list[ModelInfo]."
- Files: `src/eq_chatbot_core/providers/base.py:169-175`, all provider `list_models()` implementations
- Impact: Callers cannot reliably type-check the return value; `ModelInfo` is dead code that misleads integrators
- Fix approach: Either remove `ModelInfo` from the union and from public exports, or migrate all providers to return `list[ModelInfo]`

**`cost_service.py` pricing table is stale for newer model variants:**
- Issue: Header comment says "Last updated: February 2025" (`cost_service.py:16`). Base families (`gpt-5-mini`, `gpt-5.1-chat`, `gpt-5.2-chat`, `claude-haiku-4-5`, `gpt-4o-mini`) are present, but the **dated aliases** and **5.4-variants** actually used in `tests/model_registry.py` since 2026-05 are missing: `gpt-5.4-nano`, `gpt-5.4-mini`, `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`, `gemini-2.5-flash-lite`. Longest-prefix matching in `calculate_cost()` (`cost_service.py:84-89`) catches some via family prefix but not the dated suffixes — `claude-haiku-4-5-20251001` does match `claude-haiku-4-5` (good), while `gpt-5.4-nano` does **not** match any key starting with `gpt-5.4` (falls back to `DEFAULT_PRICING`).
- Files: `src/eq_chatbot_core/services/cost_service.py:16-58`
- Impact: Silent fallback to `DEFAULT_PRICING` (`$0.01/$0.03 per 1K`) for any `gpt-5.4-*` model — wrong by 10–100× for nano/flash-tier
- Fix approach: Add `gpt-5.4-nano` / `gpt-5.4-mini` / `gemini-2.5-flash-lite` entries; update the "Last updated" comment; add a parametrized test that asserts every model in `tests/model_registry.MODELS` resolves to a non-default `PRICING` entry

**OpenRouter model IDs with provider prefix never match `PRICING`:**
- Issue: OpenRouter model IDs use `provider/model` format (e.g. `mistralai/mistral-nemo`, `openai/gpt-4o-mini`). `calculate_cost()` does prefix matching against plain names like `gpt-4o-mini`. The slash prefix means no key in `PRICING` can ever match, so every OpenRouter cost calculation silently returns the `DEFAULT_PRICING` fallback.
- Files: `src/eq_chatbot_core/services/cost_service.py:81-89`, `src/eq_chatbot_core/providers/openrouter_provider.py`
- Impact: All OpenRouter cost calculations are wrong
- Fix approach: Call `strip_provider_prefix(model)` before lookup in `calculate_cost()`. Helper exists at `src/eq_chatbot_core/providers/temperature_constraints.py:68` and is already used by `openrouter_provider.py:139,213` — same pattern just needs to be applied in the cost path

**`LangDockProvider` is the largest file (1956 lines) with duplicated chat/stream logic:**
- Issue: `langdock_provider.py` contains separate near-identical `_openai_chat_completion` / `_anthropic_chat_completion` / `_google_chat_completion` branches, each ~200 lines. The streaming counterparts are another 200 lines each. The backend dispatch pattern (`chat_completion` → `_dispatch` → `_openai_chat_completion`) duplicates error handling and payload construction.
- Files: `src/eq_chatbot_core/providers/langdock_provider.py`
- Impact: High maintenance burden; bugs in one backend branch don't get fixed in others
- Fix approach: Extract shared payload-building and error-mapping into helpers; or delegate to thin shim instances of the existing providers (OpenAI/Anthropic) pointed at LangDock URLs

**`temperature_constraints.py` has case-sensitive duplicate entries for same model family:**
- Issue: `MODEL_TEMPERATURE_CONSTRAINTS` contains both `"mistral"` and `"Mistral"` with identical values (lines 42-43), and `"Llama"`, `"Cohere"`, `"Kimi"`, `"MAI-DS-R1"` use capitalized forms that rely on startswith matching. A model ID returned by a provider in unexpected case will silently fall through to `DEFAULT_TEMP_CONSTRAINTS`.
- Files: `src/eq_chatbot_core/providers/temperature_constraints.py:42-58`
- Impact: Silent wrong temperature clamping for models with unexpected capitalisation
- Fix approach: Normalize model ID to lowercase before lookup, remove duplicate entries

**108 mypy errors with `strict = true` (unresolved):**
- Issue: `pyproject.toml` sets `mypy strict = true`, but `uv run mypy src/` (2026-05-11) reports `Found 108 errors in 21 files (checked 39 source files)`. Dominated by `no-untyped-def`, `type-arg`, `no-any-return`. The `**kwargs` signatures throughout providers lack `**kwargs: Any` annotations.
- Repro: `uv run mypy src/ 2>&1 | tail -5`
- Files: `src/eq_chatbot_core/cli.py:264,386,553`, all provider `chat_completion` / `stream_completion` methods
- Impact: CI mypy check is effectively non-enforcing; type safety guarantees are illusory
- Fix approach: Add `**kwargs: Any` to all provider method signatures; type the server / cli modules properly or downgrade mypy config to match actual coverage

## Known Bugs

**`gpt-5.4-nano` via Mammouth requires `max_tokens >= 16`:**
- Symptoms: Calls with `max_tokens < 16` (e.g. `max_tokens=5`) return a 400 error from the Mammouth API. The library has no guard against this.
- Files: `src/eq_chatbot_core/providers/mammouth_provider.py:138` (`if max_tokens: payload["max_tokens"] = max_tokens`), `tests/integration/test_mammouth_live.py:124`
- Trigger: Any caller passing `max_tokens` between 1 and 15 with a model backed by Azure's GPT-5.4-nano deployment
- Workaround: Tests hardcode `max_tokens=20`; library has no automatic floor enforcement

**Mammouth `gpt-5-nano` burns `max_tokens` on empty `content`:**
- Symptoms: Model reports `supports_reasoning=False` in Mammouth's catalog but silently consumes all `max_tokens` on internal reasoning, returning empty `content`. Known since May 2026.
- Files: `tests/model_registry.py:105-111` (documented in notes), no mitigation in `src/`
- Trigger: Any call to `gpt-5-nano` via Mammouth
- Workaround: Model skipped in test registry; no runtime guard prevents user from calling it

**Anthropic `cache_control` only supported on system messages:**
- Symptoms: `_extract_system_prompt` reads `cache_control` from `msg.get("cache_control")` but only for messages with `role == "system"`. User or assistant messages with `cache_control` hints are silently dropped — the field is present on base `ChatMessage` schema but has no effect outside system role.
- Files: `src/eq_chatbot_core/providers/anthropic_provider.py:116-157`
- Trigger: Caller sets `cache_control` on a user or assistant message expecting Anthropic cache-break semantics
- Workaround: None; the feature is silently no-op for non-system roles

## Security Considerations

**MCP client: TOCTOU window on DNS rebinding protection:**
- Risk: `_build_pinned_transport` (MCP client) re-resolves DNS at request time and compares against pinned IPs, but there is a small window between the check and httpx's actual TCP connect. A sufficiently fast DNS swap could bypass the check. The code documents this explicitly (`Note: A small TOCTOU window remains...`).
- Files: `src/eq_chatbot_core/mcp/client.py:118-151`
- Current mitigation: DNS re-check on every request; documentation recommends network-level egress filtering
- Recommendations: Deploy network-level egress controls (e.g. iptables rules blocking RFC-1918 ranges) for production deployments. The in-process check is best-effort only.

**MCP stdio: `PYTHONPATH` excluded from subprocess env but `PATH` is forwarded:**
- Risk: `StdioMCPClient` builds a clean env for subprocesses (excludes secrets, excludes `PYTHONPATH`) but forwards `PATH` from the parent. A manipulated `PATH` in the parent environment could redirect `python` or `node` to a malicious binary even though the command basename passes the whitelist check.
- Files: `src/eq_chatbot_core/mcp/client.py:704-718`
- Current mitigation: Command basename whitelist; `shutil.which` resolution check
- Recommendations: Consider resolving commands to absolute paths at construction time and pinning the resolved path; or validate the resolved binary against a checksum

**`FernetEncryption` key stored as instance attribute:**
- Risk: `FernetEncryption._key` holds the raw key bytes as a long-lived instance attribute. In a long-lived process this means the key stays in memory indefinitely. If a memory dump or GC introspection is possible (e.g. via a separate vulnerability), the key is recoverable.
- Files: `src/eq_chatbot_core/security/encryption.py:41`
- Current mitigation: `key_fingerprint` property is safe (SHA256 prefix only, does not expose key)
- Recommendations: Low priority for a library; document that callers should limit instance lifetime when possible

**Server bearer token sent over plain HTTP if not behind TLS terminator:**
- Risk: The `BearerTokenMiddleware` validates the token correctly with `hmac.compare_digest`, but the server exposes an HTTP binding by default. If deployed without a TLS terminator the bearer token is transmitted in plaintext.
- Files: `src/eq_chatbot_core/server/auth.py`
- Current mitigation: Token is compared in constant time; the server is intended as a local/sidecar process
- Recommendations: Add a warning to server startup if binding is not localhost

## Performance Bottlenecks

**`StdioMCPClient.call_tool()` spawns a new `ThreadPoolExecutor` per call when in async context:**
- Problem: When called from within a running event loop, `call_tool()` creates a fresh `ThreadPoolExecutor` and calls `asyncio.run()` in that thread. This means each synchronous call from an async context spawns a new executor and event loop. Under load this creates unbounded thread churn.
- Files: `src/eq_chatbot_core/mcp/client.py:892-904`, `src/eq_chatbot_core/mcp/client.py:933-943`, `src/eq_chatbot_core/mcp/client.py:972-978`
- Cause: Design tension between sync public API and async subprocess internals
- Improvement path: Provide `async def call_tool_async()` as the primary public API with a documented sync wrapper; or keep a persistent executor on the instance

**`_get_patterns()` in injection detection uses a module-level global, not thread-safe initialization:**
- Problem: Pattern compilation uses a classic double-check pattern with a module-level `_compiled_patterns` global but no lock. In a multi-threaded server context, two threads could race during first-call compilation.
- Files: `src/eq_chatbot_core/security/injection.py:108-115`
- Cause: Lazy initialization without threading guard
- Improvement path: Use `threading.Lock()` around pattern compilation or compile at module import time (patterns are static)

**`MammouthProvider.list_models()` makes an unauthenticated HTTP request to a separate base URL per call:**
- Problem: `list_models()` calls `https://api.mammouth.ai/public/models` with a one-off `httpx.get()` rather than reusing the lazy-initialized client. No caching — every call to `list_models()` creates a new connection.
- Files: `src/eq_chatbot_core/providers/mammouth_provider.py:325-331`
- Cause: Models endpoint is at a different URL from the chat API; one-off call chosen for simplicity
- Improvement path: Cache the result with a short TTL (e.g. 5 minutes) or reuse the existing `httpx.Client` with an absolute URL

## Fragile Areas

**`LangDockProvider` backend dispatch relies on hardcoded model-name substring matching:**
- Files: `src/eq_chatbot_core/providers/langdock_provider.py` (~line 213-256)
- Why fragile: Backend routing (openai vs anthropic vs google) is determined by prefix/substring checks on the model ID. LangDock rotates model slugs frequently (registry notes document "snapshot 2026-05-08"); new slug formats could silently route to the wrong backend or raise an unhandled error
- Safe modification: When adding new model slugs, verify the `_detect_backend()` (or equivalent) logic covers the new prefix
- Test coverage: Integration tests against live LangDock API; no unit tests for backend-routing edge cases

**`VertexProvider.list_models()` returns a hardcoded static catalog:**
- Files: `src/eq_chatbot_core/providers/vertex_provider.py:58-91`
- Why fragile: Google releases new Gemini models frequently. The static `KNOWN_MODELS` list will fall behind. Unlike OpenAI/Anthropic/OpenRouter, Vertex does not use a live API call for model discovery.
- Safe modification: Treat `KNOWN_MODELS` as a floor; the provider will still work with models not in this list if called directly with a model ID
- Test coverage: Unit tests cover the static list only; no validation against live Vertex API model catalog

**Anthropic overload retry in `stream_completion` is a generator — retry re-runs the entire stream:**
- Files: `src/eq_chatbot_core/providers/anthropic_provider.py:386-496`
- Why fragile: The retry loop wraps the entire `with self.client.messages.stream(...) as stream:` block inside a generator function. If an `OverloadedError` is raised mid-stream (after some chunks have already been yielded), the generator retries from the beginning, silently yielding duplicate content to the caller
- Safe modification: Do not retry after the first chunk has been yielded; or document the duplicate-content risk explicitly
- Test coverage: Unit tests mock the client; no test exercises partial-stream overload retry

**Anthropic `_convert_messages` does not handle multi-part user message content (list content):**
- Files: `src/eq_chatbot_core/providers/anthropic_provider.py:233-236`
- Why fragile: The "pass through user/assistant messages as-is" branch passes raw dicts to the Anthropic SDK. If a user message carries a list content (e.g. for vision), it passes through correctly only if it already conforms to Anthropic's schema. An OpenAI-style vision message (`{"type": "image_url", "image_url": {...}}`) is not converted and will cause an Anthropic API error.
- Safe modification: Add image content conversion analogous to the tool_calls conversion branch
- Test coverage: No unit test for vision/image message conversion to Anthropic format

## Scaling Limits

**`MCPClient` uses a single global `_request_id` counter and in-memory `_pending_requests` dict:**
- Current capacity: Single-threaded use; no limit enforced on concurrent in-flight requests
- Limit: Under high concurrency the `_pending_lock`-guarded dict is a contention point; no cleanup of timed-out entries (they are only removed in the `finally` block of `_send_request`)
- Scaling path: Connection pooling and request multiplexing are not supported; each concurrent request blocks on a queue.Queue timeout

## Dependencies at Risk

**`langdock_provider.py` depends on both `openai` SDK and `anthropic` SDK for sub-backends:**
- Risk: `LangDockProvider` instantiates `OpenAI` (openai SDK) for the openai backend and `Anthropic` (anthropic SDK) for the anthropic backend internally. Breaking changes in either SDK simultaneously affect LangDock without a dedicated LangDock SDK pin.
- Impact: A major version bump in openai or anthropic SDK could break LangDock routing silently if the internal SDK calls change
- Migration plan: Pin SDK versions in pyproject.toml with upper bounds; already done (`openai>=1.82.0,<2.0.0` pattern — verify current bounds)

**`google-genai` SDK API surface for Vertex is accessed via duck typing (`getattr` everywhere):**
- Risk: `vertex_provider.py` uses `getattr(response, "usage_metadata", None)` and `getattr(candidate, "finish_reason", None)` patterns extensively. The SDK version is not pinned tightly. Any field renaming in a minor google-genai release silently returns `None` instead of raising.
- Impact: Token counts and finish reasons silently become 0/None without error
- Migration plan: Add explicit SDK version range; add assertions or logging when expected fields are missing

## Missing Critical Features

**No `cache_control` support for user/assistant message turns (Anthropic):**
- Problem: Anthropic supports `cache_control` on user message content blocks (for caching long document turns), not just system prompts. The current implementation only applies it to system messages.
- Blocks: Callers wanting to cache expensive tool results or long user documents cannot do so through this library

**No async provider interface:**
- Problem: All providers implement synchronous `chat_completion` and `stream_completion`. The `StdioMCPClient` has async internals but exposes awkward sync wrappers. There is no `async_chat_completion` / `async_stream_completion` on `BaseLLMProvider`.
- Blocks: Direct use in async frameworks (FastAPI, asyncio-native applications) requires callers to run providers in thread pools manually

## Test Coverage Gaps

**RAG `embedder.py` and `context_manager.py` have no unit tests:**
- What's not tested: `src/eq_chatbot_core/rag/embedder.py` (embedding generation), `src/eq_chatbot_core/rag/context_manager.py` (RAG context assembly)
- Files: `src/eq_chatbot_core/rag/embedder.py`, `src/eq_chatbot_core/rag/context_manager.py`
- Risk: Embedding pipeline bugs (e.g. wrong dimension handling, batch size issues) would only surface in production
- Priority: Medium

**`LangDockProvider` backend routing has no unit tests:**
- What's not tested: The model-name → backend dispatch logic that determines whether to call the openai, anthropic, or google sub-path
- Files: `src/eq_chatbot_core/providers/langdock_provider.py`
- Risk: New model slugs silently route to wrong backend; only caught by live integration tests
- Priority: High

**Anthropic stream retry with mid-stream overload produces duplicate content:**
- What's not tested: The scenario where an `OverloadedError` occurs after chunks have already been yielded from `stream_completion`
- Files: `src/eq_chatbot_core/providers/anthropic_provider.py:386-496`
- Risk: Silent content duplication to callers in overloaded conditions
- Priority: Medium

**Intermittent Anthropic integration test flakes (overload-related):**
- What's not tested: The retry logic under real API overload conditions; only tested with mocks
- Files: `tests/integration/` Anthropic tests
- Risk: Retry logic bugs masked by mock-based unit tests; real overload behavior untested
- Priority: Low (infrastructure-dependent)

**`cost_service` missing models are not caught by any test:**
- What's not tested: Whether the models in `tests/model_registry.py` MODELS registry all have entries in `PRICING`
- Files: `src/eq_chatbot_core/services/cost_service.py`, `tests/model_registry.py`
- Risk: Silent cost miscalculation for all current primary models
- Priority: High — a simple parametrized test would cover this

## Recent Releases — Open Follow-ups

**Anthropic SDK 0.76.0 → 0.100.0 upgrade (commit `1572` from 2026-05-08):**
- Context: SDK was bumped as part of the test-registry overhaul. `pyproject.toml` pins `anthropic>=0.90.0,<2.0.0` — a wide range that allows further auto-updates without recompat-testing.
- Risk: `cache_control` block construction in `anthropic_provider.py:111-155` and the streaming overload-retry loop (lines 386-496) depend on SDK message-block schema and exception types. A 0.100.x → 0.110.x bump could silently change either.
- Recommendation: Tighten upper bound (`<0.110.0` or `<1.0.0`) or add a smoke test that exercises both cache_control and overload paths against the current SDK.

**`ChatRequest.provider_extra` kwarg-passthrough (Release 1.7.1, commit `3f97b68`):**
- Context: `server/app.py:98-103,132-137` unpacks `req.provider_extra` directly into `get_provider(**provider_extras)`. Any field name the caller sends becomes a constructor kwarg on the chosen provider class.
- Risk: No allowlist of accepted kwarg names. A caller can attempt to pass internal-only fields (e.g. `_client`, `timeout` overrides), and downstream behavior depends entirely on each provider's `__init__` signature tolerance. With `**kwargs` typed as untyped (mypy issue above), the surface is invisible to static analysis.
- Recommendation: Define a per-provider allowlist of `provider_extra` keys (or a typed `ProviderExtras` Pydantic model per provider). At minimum, document the expectation that callers send only documented kwargs.

**`ChatMessage.cache_control` API contract (Release 1.7.2, commit `f9ce426`):**
- Context: Schema exposes `cache_control` on every message, but only system messages honor it (see "Known Bugs" above). The contract is wider than the implementation.
- Risk: Integrators set `cache_control` on user/assistant turns expecting Anthropic-style cache-break and get silent no-ops. Other providers (OpenAI, OpenRouter, etc.) silently ignore the field entirely.
- Recommendation: Either narrow the schema (`cache_control` only on system role) or implement the documented Anthropic behavior for user content blocks.

## Process / Workflow Risks

**Dual-remote push workflow (GitLab origin + GitHub upstream):**
- Context: `eq_chatbot_core` is pushed to both `gitlab.ownerp.io:pypi-projects/eq_chatbot_core.git` and `github.com:equitania/eq-chatbot-core.git`. Every commit must hit both — historical convention enforced manually.
- Risk: A `git push` that only goes to one remote leaves the mirrors out of sync. No CI check enforces parity. PyPI releases are cut locally (per memory `release_workflow_local.md`) which means a desync can ship asymmetric tags.
- Recommendation: Add a pre-release script (`/afterwork` candidate) that checks `git rev-parse origin/main` against `git rev-parse upstream/main` and refuses to publish if they diverge.

---

*Concerns audit: 2026-05-11*
