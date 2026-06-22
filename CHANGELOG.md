# Changelog

All notable changes to eq-chatbot-core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.16.0] - 2026-06-22

### Added

- **CLI provider-specific API-key env vars** (`cli.py`): API key resolution is now
  `--api-key` > `<PROVIDER>_API_KEY` > `LLM_API_KEY`. Each cloud provider reads its own variable
  (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGDOCK_API_KEY`, `OPENROUTER_API_KEY`, `MAMMOUTH_API_KEY`,
  `AZURE_API_KEY`, `LITELLM_API_KEY`, `IONOS_API_KEY`, `MELIOUS_API_KEY`), letting users store all
  provider keys on the host and drop `-k`. Cross-provider isolation: a key for one provider never
  satisfies another. New `resolve_api_key()` helper and `PROVIDER_API_KEY_ENV` mapping; generic
  `LLM_API_KEY` fallback preserved. Affects `chat`, `test-provider`, `list-models`, `image`,
  `listing-assets`.

## [1.15.0] - 2026-06-21

### Security

- **LangDock** (`providers/langdock_provider.py`): both `httpx.HTTPError` branches now scrub the
  error text before logging/raising, closing a Bearer-token leak in `Authorization` headers.
- **SSRF / DNS rebinding** (`utils/url_validation.py`): in strict mode an unresolvable hostname is
  now rejected (`ValueError`) instead of silently passing with IP-pinning disabled. LAN mode still
  allows it (no pin) but emits a warning.
- **MCP stdio** (`mcp/client.py`): caller-supplied env is rejected when it contains loader/startup
  code-injection keys (`LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`, `PYTHONSTARTUP`, `BASH_ENV`, …);
  `PYTHONPATH` stays the documented escape hatch.
- **Path traversal** (`utils/image.py`): `save_png()` gains an optional `base_dir` that confines the
  write; the `listing-assets` CLI uses it so an untrusted asset `out` name cannot escape `--dest`.
- **Knowledge export** (`services/knowledge_service.py`): export filenames are `os.path.basename`-d
  before joining the temp dir (defense-in-depth against separators in a model name).
- **Local provider** (`providers/local_provider.py`): connection/timeout error messages scrub
  `base_url` and the underlying exception text.

### Added

- `enforce_rate_limit()` and the optional `AtomicRateLimitStorage` protocol
  (`security/rate_limit.py`) — a race-free check-and-record entry point that prefers an atomic
  backend and documents the TOCTOU window of the non-atomic `check_rate_limit` + `record_usage` path.
- `scan_external_content()` and `wrap_external_content()` (`security/injection.py`) — indirect
  prompt-injection primitives for MCP tool results and retrieved RAG passages.

### Changed

- Dependency bounds: `cryptography` upper bound raised to `<50.0.0`; `azure` and `vertex` extras
  pinned with upper bounds (`azure-ai-inference<2.0.0`, `azure-core<2.0.0`, `google-genai<2.0.0`).

## [1.14.0] - 2026-06-21

### Added

- Text-to-image generation in the provider layer: `ImageResult` dataclass,
  `supports_image_generation` flag and a non-abstract `generate_image()` on `BaseLLMProvider`.
  Implemented for OpenAI (`gpt-image-1` via `/images`, base64 decode) and OpenRouter (image models
  such as `google/gemini-2.5-flash-image` via `chat/completions` with `modalities`). Unsupported
  providers raise `ProviderError`.
- `eq-chatbot image` CLI command — generate a single PNG from a text prompt
  (`-p openai|openrouter`, `--prompt`/`--prompt-file`, `--model`, `--size`, `--fit WxH:mode`, `-o`).
- `eq-chatbot listing-assets` CLI command — batch-generate images from an `eq-listing-assets/v1`
  recipe JSON (`--dest`, `--only`, `--dry-run`, provider/model overrides); built for App-Store
  listing assets (icon/banner/eyecatchers).
- `utils/image.py` (`save_png`, `fit_to` cover/contain/stretch, `parse_size`), backed by Pillow —
  new optional extra `[image]` (`Pillow>=10.0,<12.0`).
- 76 unit tests for the image stack.

## [1.13.0] - 2026-06-21

### Added

- `MeliousEmbedder` (`rag/embedder.py`) — RAG embedding adapter for the Melious.ai sovereign EU
  gateway (OpenAI-compatible). Dynamic model ids/dimensions via `/v1/models`, explicit vector
  `dimensions` (default 1536); `base_url` defaults to `https://api.melious.ai/v1`. Enables Melious
  as an embedding provider for the `eq_chatbot_rag` Odoo add-on.

## [1.12.0] - 2026-06-21

### Added

- Melious.ai provider (`get_provider("melious")`) — sovereign, EU-hosted, OpenAI-compatible
  inference gateway (GDPR-compliant, 60+ open-weight models). Fixed endpoint
  `https://api.melious.ai/v1`, optional `base_url`, default model `minimax-428b-m3`. Chat,
  streaming, tool calls and dynamic model listing; built on the existing `openai` SDK (no new
  dependency). SSRF-guarded `base_url`, shared temperature clamping. 28 unit tests + live suite.

## [1.11.2] - 2026-06-17

### Changed

- Docs: clarified the LangDock document-content limitation (`docs/langdock-export.md` EN+DE,
  `usage/AGENT.md`) — an agent's knowledge lives in a Knowledge Folder (metadata + search only) or
  as attachments (no download endpoint); `langdock-export` backs up the agent definition, system
  prompt and attachment IDs, never the document bytes.

## [1.11.1] - 2026-06-17

### Changed

- `langdock-export` UX: collapse per-agent access-error floods (first 3 + count) and surface a clear
  hint that each agent must be shared with the API key (the `AGENT_API` scope alone grants no
  per-agent access). Documented the sharing prerequisite (EN+DE).

## [1.11.0] - 2026-06-17

### Added

- LangDock backup/export tool — decentralised backup of LangDock agents and knowledge-folder
  metadata. HTTP layer (`LangDockExportManager`) + orchestration (`LangDockBackupExporter`), new
  `eq-chatbot langdock-export` CLI command, agent capability card (`usage/AGENT.md`), 26 unit tests.
  No new runtime dependency (`httpx`/`click` are core).

## [1.10.0] - 2026-06-14

### Added

- IONOS AI Model Hub provider (`get_provider("ionos")`): EU-hosted (Berlin/de-txl),
  OpenAI-compatible inference gateway built on the existing `openai` SDK (no new dependency).
  `base_url` defaults to the official IONOS endpoint; default model
  `meta-llama/Llama-3.3-70B-Instruct`. Includes chat, streaming, tool calls and `list_models()`.
- Curated IONOS pricing in `services/cost_service.py` (EUR/1M rates converted to USD/1K).
- Unit tests (`tests/unit/test_ionos.py`) and live integration tests
  (`tests/integration/test_ionos_live.py`, gated on `IONOS_API_KEY`).

### Fixed

- `litellm` was missing from the `conftest.py` test-report dictionaries; both `litellm`
  and `ionos` are now wired into `_MODULE_GROUPS`, `_RESOLUTION_LABELS` and related maps.

## [1.9.0] - 2026-06-14

### Added

- LiteLLM / OpenAI-compatible gateway provider (`get_provider("litellm")`) with TTS/STT support.

## [1.8.0] - 2026-06-05

### Added

- **Model pricing catalog** (`services/pricing_catalog.py`): `PricingCatalog` resolves
  per-1k-token input/output prices for any model across all supported providers, backed
  by the community LiteLLM pricing database (`model_prices_and_context_window.json`, MIT).
  A snapshot is bundled under `data/model_prices.json` (offline fallback); `from_remote()`
  fetches the live file and degrades gracefully to the snapshot on any network error.
  `lookup(model_id, provider=None)` does exact → normalized → longest-prefix matching with
  optional provider scoping.
- **Normalized live pricing**: `openrouter_provider` and `mammouth_provider` `list_models()`
  now also emit `input_cost_per_1k` / `output_cost_per_1k` so consumers read one consistent
  per-1k field regardless of the provider's native pricing unit.
- `scripts/update_pricing_snapshot.py` to regenerate the bundled snapshot at release time.

### Changed

- `services/cost_service.py`: `get_model_pricing()` now falls back to the broader pricing
  catalog before the generic default, widening coverage. The curated static `PRICING` table
  still takes precedence (no behavioral change for known models); `calculate_cost()` now
  delegates to `get_model_pricing()`.

## [1.2.1] - 2026-02-25

### Fixed

- LangDock Knowledge Manager: Upload endpoint corrected (`/knowledge/{folderId}/upload` → `/knowledge/{folderId}`)
- LangDock Knowledge Manager: List files endpoint corrected (`/knowledge/{folderId}/files` → `/knowledge/{folderId}/list`)
- LangDock Knowledge Manager: Delete endpoint corrected (`/knowledge/{folderId}/files/{fileId}` → `/knowledge/{folderId}/{fileId}`)
- LangDock Knowledge Manager: List response parsing corrected (`.get("data", [])` → `.get("result", [])`)

## [1.2.0] - 2026-02-24

### Added

- New model support in Azure provider: DeepSeek-V3, DeepSeek-R1, MAI-DS-R1, Llama (3.3-70B/3.3-8B/4-Scout/4-Maverick), Grok (3/3-mini), Cohere (Command-A/R+/R), Kimi-K2, codex-mini, o3-pro
- Azure API version parameter (`api_version`, default `2025-04-01-preview`)
- OpenRouter and Mammouth to CLI provider choices and info command

### Changed

- LangDock knowledge export switched from JSON to Markdown format
- Azure provider model catalog expanded (8 → 49 models)
- Temperature constraints: GPT-4.1/GPT-5 min corrected from 1.0 to 0.0 (per OpenAI API docs)

### Fixed

- GPT-4.1 minimum temperature was incorrectly set to 1.0 (should be 0.0 per OpenAI API specification)
- CLI missing OpenRouter and Mammouth providers in choices and help text

## [1.1.0] - 2026-02-13

### Added

- **Azure AI Provider**: New provider for Azure AI Foundry models via `azure-ai-inference` SDK
  - Supports models deployed on Azure AI (GPT-4o, GPT-4.1, O1, O3, O4, Claude, Mistral, Llama, Phi, DeepSeek)
  - AzureKeyCredential authentication with required `base_url` endpoint
  - Chat completion and streaming with tool call support
  - Static model catalog via `list_models()` (Azure has no list API)
  - Temperature clamping via shared constraints module
  - Graceful import: works without `azure-ai-inference` installed (raises ImportError on use)
  - Context manager support (`with get_provider("azure", ...) as provider:`)
  - Factory support: `get_provider("azure", api_key="...", base_url="...")`
  - Optional dependency: `pip install eq-chatbot-core[azure]`
  - 38 unit tests + 5 integration tests
- Azure section in CLI `info` command

### Changed

- Unit test count: 1051 passed (up from 1012)
- Updated CLI `--provider` help text to include `azure`
- Updated factory error messages to list `azure` as available provider

## [1.0.0] - 2026-02-10

### Added

- **Mammouth AI Provider**: New provider for 30+ AI models via unified API
  - Supports OpenAI, Anthropic, Google, Mistral, xAI, DeepSeek, Meta models
  - OpenAI-compatible API (simple model IDs without provider prefix)
  - Temperature clamping, streaming, tool calls, model listing with pricing
  - Factory support: `get_provider("mammouth", api_key="mm-...")`
  - 37 unit tests + integration test suite
- **Shared Temperature Constraints Module** (`temperature_constraints.py`)
  - Single source of truth for model-specific temperature limits
  - Exact match + longest-prefix matching for model ID lookup
  - `clamp_temperature()` — returns `None` for reasoning models (skip parameter)
  - `strip_provider_prefix()` — handles OpenRouter `provider/model` format
  - 31 unit tests covering all constraint lookup and clamping logic

### Changed

- **Unified temperature clamping across all providers** (OpenAI, Anthropic, LangDock, OpenRouter, Mammouth)
  - GPT-4.1/GPT-5.x: enforce min temperature=1.0 (was unclamped)
  - Claude models: enforce max temperature=1.0 (was unclamped)
  - Reasoning models (o1/o3/o4, deepseek-reasoner): temperature parameter omitted entirely
  - Unknown models: safe default 0.0–2.0 range
- All providers now delegate to shared `temperature_constraints` module instead of local logic
- Unit test count: 1012 passed (up from 940)

### Fixed

- **OpenAI provider**: Temperature was always sent to reasoning models (o1/o3/o4), causing API errors
- **Anthropic provider**: Temperature above 1.0 was not clamped, causing API errors
- **LangDock provider**: Temperature not clamped for GPT-4.1/5.x models across all backends
- **OpenRouter provider**: Temperature not clamped for GPT-4.1/5.x models (only reasoning skip existed)

## [0.15.0] - 2026-02-09

### Changed

- Tighten dependency version ranges with upper bounds (openai <3, anthropic <1, httpx <1, etc.)
- Replace python-magic with puremagic (pure Python, no libmagic system dependency)
- Replace black dependency, use ruff format exclusively
- Add twine to dev dependencies, add Python 3.13 classifier
- Update pre-commit config: replace black hook with ruff-format

### Added

- MCP client SSRF protection (private IP blocking, HTTP/HTTPS scheme validation)
- MCP stdio command whitelist (python, node, uvx, uv) and shell metachar validation
- 22 new unit tests for MCP validation (940 total, 0 failures)

### Fixed

- Replace bare `except Exception` handlers with specific catches + logging

## [0.14.0] - 2026-02-07

### Added

- Configurable error messages to ChatbotErrorHandler (i18n-ready)
- MCP client thread-safety (`_pending_lock` for concurrent requests)
- Unicode NFKD normalization to injection detection
- Error handling to retriever (embedder + Qdrant failures)
- Context manager budget validation (ratio sum check)
- Longest-prefix matching to cost service
- Jitter to error handler retry backoff
- 9 new unit test modules (918 tests total, 0 failures)
- TASKS.md tracking document

### Fixed

- Chunker infinite-loop bug when `chunk_overlap >= chunk_size`
- Anthropic tool input serialization (`json.dumps` instead of `str`)

### Changed

- Stricter MIME-type aliases in file validator
- Add SSE parse error logging to OpenRouter provider
- Update pricing table (Feb 2025: Claude 4.x, o3, gpt-4o corrected)
- Raise minimum dependency versions (cryptography>=44, openai>=1.58, etc.)
- Modernize ruff config to `[tool.ruff.lint]` section

## [0.13.0] - 2025-01-22

### Added

- **OverloadedError Exception**: New exception type for transient server overload errors (529/503)
  - Distinct from RateLimitError for better retry handling
  - Used by Anthropic provider for overload_error responses
  - Properly exported from providers module

### Fixed

- **CLI AttributeError**: Fixed CLI `list-models` command crashing
  - Changed `m.model_id` to `m.id` (matching ModelInfo dataclass)
  - Removed non-existent `supports_temperature` and `max_tokens` attributes
  - Fixed token usage display using correct `LLMResponse` attributes
- **README Examples**: Updated code examples to use correct API
  - `response.usage.total_tokens` → `response.total_tokens`
  - `model.model_id` → `model.id`
- **Export Completeness**: Added `OverloadedError` to `__all__` in providers module
- **MANIFEST.in**: Added manifest file to include LICENSE, README, CHANGELOG in sdist

### Changed

- Improved JSON output in `list-models` command with more model metadata
  - Now includes: id, name, provider, supports_vision, supports_tools, supports_streaming, context_length

## [0.12.0] - 2025-01-17

### Added

- **OpenRouter Provider**: Access to 400+ AI models through unified API
  - Supports OpenAI, Anthropic, Google, Meta, Mistral, and many more models
  - Model ID format: `provider/model-name` (e.g., `openai/gpt-4o`, `anthropic/claude-3.5-sonnet`)
  - Reasoning model detection for O1/O3/O4 series (auto-disables temperature)
  - Streaming with tool-call accumulation
  - Dynamic model list with constraints and pricing metadata
  - Vision support detection from input_modalities
  - Pricing extraction (input/output/image costs)
- OpenRouter support in provider factory: `get_provider("openrouter", api_key="...")`
- Comprehensive unit tests for OpenRouter provider (31 tests)

## [0.9.1] - 2025-12-30

### Fixed

- LangDock Provider: Added tool call accumulation for Anthropic backend streaming
  - Handles content_block_start events for tool_use blocks
  - Handles input_json_delta events for tool arguments
  - Returns complete tool_calls on final StreamChunk
- MCP tool execution now works correctly with LangDock Anthropic backend

## [0.9.0] - 2025-12-30

### Added

- `StreamChunk.tool_calls` field for complete tool call data on final streaming chunk
- Tool call accumulation in streaming for all providers:
  - OpenAI Provider: Accumulates tool_call_delta into complete tool_calls
  - LangDock Provider: Same accumulation for OpenAI-compatible streaming
  - Anthropic Provider: Handles content_block_start/input_json_delta events

### Fixed

- Streaming with function calling now properly returns accumulated tool calls
- Tool execution loop can now access complete tool call data from final StreamChunk

## [0.6.0] - 2025-12-29

### Added

- First standalone PyPI release
- CLI tool `eq-chatbot` with commands:
  - `test-provider` - Test LLM provider connections
  - `list-models` - List available models from providers
  - `info` - Show package information
- Click framework for CLI implementation
- MIT License

### Changed

- Extracted from v18-chatbot monorepo to standalone package
- License changed from Proprietary to MIT
- Updated project URLs to GitHub
- Development status changed to Beta

### Previous History

This package was previously developed as part of the v18-chatbot project:

- 0.5.6: LangDock attachment upload URL fix
- 0.5.5: LangDock provider upload_attachment wrapper
- 0.5.4: LangDock Agent file upload support
- 0.5.3: Agent multimodal warning
- 0.5.2: Anthropic provider vision detection fix
- 0.5.1: Gemini multimodal format conversion
- 0.5.0: PDF-to-image conversion, model-based content format
- 0.4.2: Vision support detection improvements
- 0.4.1: File validator false positive fixes
- 0.4.0: Initial providers, security, RAG modules
