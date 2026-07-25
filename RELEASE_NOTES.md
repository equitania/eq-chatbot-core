# Release Notes

## Version 1.20.0 (25.07.2026)

### Security

- **[FIX] SSRF guard closed on the remaining network entry points** — `OpenAIProvider`,
  `AnthropicProvider`, `OpenAIEmbedder` and `MeliousEmbedder` accepted a caller-supplied
  `base_url` and passed it straight into the SDK client without validation, while every
  other cloud provider already called `validate_url()`. Because the `[server]` sidecar
  forwards the client-supplied `ChatRequest.base_url` into `get_provider()`, an
  authenticated caller could steer requests at internal addresses (e.g. the
  `169.254.169.254` cloud-metadata endpoint). All four now run
  `validate_url(base_url, allow_private_ranges=False)`. Only caller-supplied URLs are
  validated — fixed built-in defaults are trusted and skip the DNS round-trip.
- **[FIX] Secret scrubbing completed across all providers** — `openai`, `anthropic`,
  `azure`, `openrouter`, `vertex` and `mammouth` built `ProviderError(message=str(error))`
  without `scrub_secrets()`, unlike the other five providers. For the HTTP-based providers
  the message is parsed out of the gateway error body, which can echo request credentials.
  All provider error paths now scrub.
- **[FIX] Server error responses scrub defensively** — `server/app.py`'s
  `_provider_error_to_http`, `_provider_error_to_json` and the streaming catch-all handler
  now apply `scrub_secrets()` themselves instead of relying on every provider to have done
  so upstream.
- **[CHG] Dependency floors raised to exclude known CVEs** — `click>=8.3.3`
  (CVE-2026-7246, command injection in `click.edit()`), `cryptography>=46.0.7`
  (CVE-2026-26007 / CVE-2026-39892 / CVE-2026-34073), and `Pillow>=12.3.0` in the
  `[image]` extra (CVE-2026-59205, ImageCmsTransform buffer overflow — affects *every*
  earlier release, so the previous `>=12.2.0` floor did not exclude it). Lock refreshed;
  `pip-audit` is clean.

### Fixed

- **[FIX] `AttributeError` during GC after a rejected `base_url`** — the SSRF check ran
  *before* the HTTP-client attribute was assigned in `LangDockProvider`, `MammouthProvider`,
  `IonosProvider`, `LiteLLMProvider` and `MeliousProvider` (in LangDock's case directly
  contradicting its own "Initialize clients BEFORE validation" comment). A rejected URL left
  the instance without `_client`/`_http_client`, so garbage collection raised inside
  `__del__`. Client attributes are now initialized first in every provider.

### Changed

- **[CHG] New `OpenAICompatibleProvider` base class** (`providers/openai_compatible.py`) —
  `IonosProvider`, `MeliousProvider` and `LiteLLMProvider` carried byte-identical copies of
  `chat_completion`, `stream_completion`, `list_models`, `_handle_error`, `close` and the
  context-manager protocol (ionos vs. melious differed only in docstrings, constants and the
  class name). That duplication is why the two fixes above had to be applied N times and were
  applied inconsistently. Subclasses now declare `PROVIDER_NAME`, `DEFAULT_BASE_URL`,
  `DEFAULT_MODEL` and `ALLOW_PRIVATE_RANGES`; LiteLLM additionally keeps its Audio API
  (`text_to_speech`, `transcribe`). **Public API is unchanged** — class names, constructor
  signatures and the module-level `DEFAULT_BASE_URL` / `DEFAULT_MODEL` constants are
  preserved. ~600 lines of duplication removed.
- **[CHG] CI gates tightened** (`.github/workflows/ci.yml`) — `pip-audit --strict` is now a
  hard gate instead of advisory (this is what let the vulnerable `click` pin sit in the lock).
  `mypy` stays advisory for pre-existing debt but is now *ratcheted*: a change that increases
  the error count fails the job. The stale comment claiming "~108 issues across 21 files" is
  replaced by a measured baseline.

### Documentation

- **[CHG] AGPL notice for `pymupdf`** (`pyproject.toml`) — the `[pdf]` and `[docs]` extras pull
  in an AGPL-3.0-or-later dependency into an otherwise MIT-licensed library. Keeping it optional
  limits the blast radius, but the obligation was previously undocumented.

### Tests

- SSRF regression tests (metadata IP, private range, non-HTTP scheme) for `OpenAIProvider`,
  `AnthropicProvider`, `MeliousEmbedder` and the provider factory; secret-scrubbing regression
  tests for all six newly-hardened providers. Four existing tests used unresolvable placeholder
  hostnames (`custom.openai.com`) and were switched to loopback URLs, matching the hermetic
  convention already used by the ionos/melious/litellm suites. 1738 unit tests pass.

## Version 1.19.0 (11.07.2026)

### Added

- **[ADD] Model capability catalog** (`services/capability_catalog.py`,
  `CapabilityCatalog`) — a curated, Equitania-hosted Single Source of Truth for
  per-model *capabilities* (vision, audio in/out, file input, tools, reasoning),
  context/output *limits* and per-1k-token *pricing*. Mirrors the
  `PricingCatalog` pattern (`from_remote(url)` / `from_snapshot()` with graceful
  offline fallback) and resolves a configured `model_id` to the canonical entry
  via per-provider `aliases`. Bundled snapshot `data/capability_catalog.json`
  (curated seed; will be regenerated by the future `eq-model-catalog` sync tool)
  plus `data/capability_overrides.json` (generator override template).
  Replaces the per-provider name-guessing heuristics as the capability source
  and unifies pricing. Tests: `tests/unit/test_capability_catalog.py`.

## Version 1.18.1 (09.07.2026)

### Removed

- **[CHG] Removed the `langdock-export` CLI command** — the `eq-chatbot langdock-export`
  backup command, the `services/langdock_export.py` module (`LangDockBackupExporter`),
  `tests/unit/test_langdock_export.py`, and `docs/langdock-export.md` have been removed.
  The feature is no longer shipped. **Unaffected:** the LangDock *chat* provider
  (`providers/langdock_provider.py`) and the knowledge-sync helpers
  `services/knowledge_service.py::KnowledgeExporter.prepare_for_langdock` /
  `export_to_langdock` remain fully supported — only the agent/knowledge *backup*
  CLI is gone. References in the README, `docs/README.md`, `docs/cli.md`,
  `usage/AGENT.md`, and the `cli.py` group docstring / `info` output have been
  cleaned up.

## Version 1.18.0 (07.07.2026)

### Added

- **[ADD] Document-to-Markdown extraction** (`services/document_extractor.py`) — converts
  uploaded office documents (PDF, DOCX, PPTX, XLSX, HTML, CSV, MD, TXT) into Markdown for
  knowledge ingestion (consumed by the Odoo `eq_knowledge_ai` module). `extract_markdown()`
  returns an `ExtractionResult` (markdown, embedded images as blobs, warnings);
  `is_document_extraction_available()` / `supported_extensions()` gate rich formats behind the
  new optional extra `eq-chatbot-core[docs]` (markitdown + pymupdf). Plain `.md`/`.txt`
  extraction is dependency-free. Hard resource limits (50 MB input, 50 images, 10 MB/image)
  bound untrusted uploads; embedded-image extraction from PDFs via PyMuPDF is best effort.

## Version 1.17.2 (04.07.2026)

### Fixed

- **[FIX] Pillow security update** (`pyproject.toml`) — the `[image]` extra now requires
  `Pillow>=12.2.0,<13.0` (was `<12.0`). The old upper bound made it impossible to install the
  patched Pillow 12.2.x line and left consumers exposed to six published CVEs in 11.x (PSD
  out-of-bounds write/memory corruption CVE-2026-25990 / CVE-2026-42311, FITS decompression bomb
  CVE-2026-40192, and further DoS issues — all fixed in 12.1.1/12.2.0). `uv.lock` refreshed
  (Pillow 12.3.0, transitive msgpack 1.2.0 → 1.2.1 for GHSA-6v7p-g79w-8964).
- **[FIX] Secret scrubbing applied consistently to log output** — the generic error path in
  `services/error_handler.py` (`_handle_generic_error`, `_try_fallback_provider`) now runs
  exception text through `scrub_secrets()` before logging, matching the already-scrubbed
  `original_error` field; the MCP SSE client (`mcp/client.py`) scrubs the caller-supplied
  SSE URL and error text in its connect/timeout log lines and the `TimeoutError` message; the
  LangDock attachment-upload error path (`langdock_provider.py`) routes log and raised
  `ProviderError` text through `_scrub()` like every other httpx handler in the file.
- **[FIX] SSRF guard extended to all caller-supplied base_urls** — `validate_url()` (blocks
  non-HTTP schemes, private/link-local/cloud-metadata targets) is now enforced in the Azure
  provider (base_url is always caller-supplied) and in LangDock, OpenRouter and Mammouth when a
  non-default `base_url` override is given, closing the gap against the already-guarded
  litellm/ionos/melious/local providers. Explicit localhost URLs remain allowed.
- **[FIX] Circular import on fresh `import eq_chatbot_core.services`** (`utils/__init__.py`) —
  the eager `PRICING`/`calculate_cost` re-export completed the cycle
  `utils → pricing → services.cost_service → providers → local_provider → utils` and broke any
  interpreter that imported `eq_chatbot_core.services` first (e.g.
  `from eq_chatbot_core.services.error_handler import ChatbotErrorHandler`). The re-export is now
  lazy via PEP 562 module `__getattr__`; the public API is unchanged.

### Tests

- New `TestLogScrubbing` (error handler caplog checks) and per-provider `Test*SSRFGuard` classes
  (metadata endpoint rejected, non-HTTP scheme rejected, localhost accepted, default URL exempt).
  Azure/OpenRouter/Mammouth/LangDock unit tests now use hermetic `localhost` base URLs so the new
  `validate_url` call needs no DNS in unit runs.

## Version 1.17.1 (23.06.2026)

### Changed

- **[CHG] `listing-assets --help` examples** (`cli.py`) — the help now opens with a concrete
  `eq-listing-assets/v1` recipe that mixes a **banner carrying rendered title text** with a
  **pure no-text icon**, making the text-and-image batch tangible, plus three realistic CLI
  invocations (`--dry-run` preview, full run, `--only banner --dest …/static/description`).
  Click `\b` no-rewrap markers keep the inline JSON and commands verbatim. No behaviour change —
  the pipeline stays text-to-image. Mirrored into `docs/cli.md` (EN + DE) and `usage/AGENT.md`.

## Version 1.17.0 (22.06.2026)

### Added

- **[ADD] User config file** (`utils/config.py`, `cli.py`) — the CLI now reads a TOML config
  from `~/.config/eq-chatbot/config.toml` (XDG-aware; override with `EQ_CHATBOT_CONFIG`). Per
  provider you can store `api_key`, `base_url` and `model`; globally a `default_provider` and chat
  `[defaults]` (temperature, max_tokens). Resolution order: flag > `<PROVIDER>_API_KEY` env >
  `LLM_API_KEY` env > config (for api_key); flag > config > built-in default (for base_url, model,
  provider, chat defaults). With `default_provider` set, `--provider` becomes optional.
- **[ADD] `eq-chatbot config` command** — `config init` writes a commented template (mode 0600,
  refuses to overwrite without `--force`), `config show` prints the path/permissions and a
  key-masked view, `config path` prints the resolved path. The template ships as a package resource
  (`data/config.toml.example`).
- Keys are stored in plain text; the loader warns when the file is group/other-readable. New
  dependency `tomli` for Python < 3.11 (stdlib `tomllib` is used on 3.11+).

## Version 1.16.0 (22.06.2026)

### Added

- **[ADD] Provider-specific API-key env vars** (`cli.py`) — the CLI now resolves the API key in the
  order `--api-key` > `<PROVIDER>_API_KEY` > `LLM_API_KEY`. Each cloud provider has its own variable
  (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGDOCK_API_KEY`, `OPENROUTER_API_KEY`, `MAMMOUTH_API_KEY`,
  `AZURE_API_KEY`, `LITELLM_API_KEY`, `IONOS_API_KEY`, `MELIOUS_API_KEY`), so multiple provider keys
  can be stored on the host at once and no call needs `-k`. A key set for one provider never satisfies
  another. Applies to `chat`, `test-provider`, `list-models`, `image`, and `listing-assets`;
  `langdock-export` (own `LANGDOCK_API_KEY`) and local/Vertex providers are unchanged. New helper
  `resolve_api_key()` plus the `PROVIDER_API_KEY_ENV` mapping; the generic `LLM_API_KEY` fallback is
  preserved.

## Version 1.15.0 (21.06.2026)

Security hardening release — resolves all findings from the project security audit
(2 HIGH-priority, 4 further MEDIUM, 2 LOW), plus additive security primitives.

### Security

- **[FIX] LangDock Bearer-token leak** (`providers/langdock_provider.py`) — both `httpx.HTTPError`
  branches now run the error through `scrub_secrets()` before logging/raising, so an
  `Authorization: Bearer <token>` header echoed in an HTTP error is masked.
- **[FIX] SSRF / DNS-rebinding bypass** (`utils/url_validation.py`) — in strict mode an unresolvable
  hostname is rejected (`ValueError`) instead of silently passing with IP pinning disabled. LAN mode
  still allows it without a pin but logs a warning.
- **[FIX] MCP stdio env injection** (`mcp/client.py`) — caller-supplied environment variables are
  refused when they carry loader/startup code-injection keys (`LD_PRELOAD`, `LD_LIBRARY_PATH`,
  `DYLD_INSERT_LIBRARIES`, `PYTHONSTARTUP`, `PYTHONINSPECT`, `BASH_ENV`, …). `PYTHONPATH` remains the
  documented escape hatch for custom module paths.
- **[FIX] Image path traversal** (`utils/image.py`) — `save_png()` accepts an optional `base_dir`
  and refuses to write outside it; the `listing-assets` CLI passes `base_dir=dest_dir` so an
  untrusted asset `out` name (absolute path or `../`) cannot escape `--dest`.
- **[FIX] Knowledge-export filename hardening** (`services/knowledge_service.py`) — export filenames
  are `os.path.basename`-d before joining the temp directory.
- **[FIX] Local-provider error scrubbing** (`providers/local_provider.py`) — connection and timeout
  error messages scrub both `base_url` and the underlying exception text.

### Added

- **[ADD] Race-free rate limiting** (`security/rate_limit.py`) — `enforce_rate_limit()` plus the
  optional `AtomicRateLimitStorage` protocol. Prefers a backend that performs check-and-record
  atomically; the non-atomic fallback documents and logs the TOCTOU window.
- **[ADD] Indirect prompt-injection primitives** (`security/injection.py`) —
  `scan_external_content()` (detection) and `wrap_external_content()` (data-fencing without
  HTML-escaping) for MCP tool results and retrieved RAG passages.

### Changed

- **[CHG] Dependency bounds** — `cryptography` upper bound raised to `<50.0.0`; `azure` and `vertex`
  extras pinned with upper bounds (`azure-ai-inference<2.0.0`, `azure-core<2.0.0`,
  `google-genai<2.0.0`).

### Tests

- New unit tests covering the env denylist, base-dir confinement, atomic/non-atomic rate-limit
  paths, external-content scan/wrap, strict-vs-LAN URL resolution, and error scrubbing.

## Version 1.14.0 (21.06.2026)

### Added

- **[ADD] Text-to-image generation** in the provider layer — new `ImageResult` dataclass +
  `supports_image_generation` flag + a non-abstract `generate_image()` on `BaseLLMProvider`
  (`providers/base.py`). Implemented for **OpenAI** (`gpt-image-1` via the `/images` endpoint,
  base64 decode) and **OpenRouter** (image models such as `google/gemini-2.5-flash-image` via
  `chat/completions` with `modalities`, data-URL parsing). Providers without support raise a clear
  `ProviderError`.
- **[ADD] `eq-chatbot image`** CLI command — generate a single PNG from a text prompt
  (`-p openai|openrouter`, `--prompt`/`--prompt-file`, `--model`, `--size`, `--fit WxH:mode`, `-o`).
- **[ADD] `eq-chatbot listing-assets`** CLI command — batch-generate images from a recipe JSON
  (schema `eq-listing-assets/v1`): per-asset prompt/size/fit, writes each PNG to `--dest`; supports
  `--only`, `--dry-run` and provider/model overrides. Built for App-Store listing assets
  (icon/banner/eyecatchers).
- **[ADD] `utils/image.py`** — `save_png()`, `fit_to()` (cover/contain/stretch crop+resize) and
  `parse_size()`, backed by **Pillow** (new optional extra `[image]`, `Pillow>=10.0,<12.0`).
- Unit tests for the image stack (`test_cli_image.py`, `test_cli_listing_assets.py`,
  `test_openai_image.py`, `test_openrouter_image.py`, `test_utils_image.py` — 76 tests).

## Version 1.13.0 (21.06.2026)

### Added

- **[ADD] `MeliousEmbedder`** (`rag/embedder.py`) — RAG embedding adapter for the Melious.ai
  sovereign EU gateway (OpenAI-compatible). Mirrors `LangDockEmbedder` but, because Melious'
  embedding model ids/dimensions are advertised dynamically via `/v1/models` (no fixed catalog),
  it skips the static `MODELS` validation and takes the vector `dimensions` explicitly
  (default 1536, overridable to match the chosen model). `base_url` defaults to
  `https://api.melious.ai/v1`. Enables Melious as an embedding provider for the `eq_chatbot_rag`
  Odoo add-on alongside OpenAI and LangDock.

## Version 1.12.0 (21.06.2026)

### Added

- **[ADD] Melious.ai provider** — sovereign, EU-hosted, OpenAI-compatible inference gateway
  (GDPR-compliant, green hosting, 60+ open-weight models). Fixed public endpoint
  `https://api.melious.ai/v1`; `base_url` is optional. Default model `minimax-428b-m3`.
  - `get_provider("melious", api_key="sk-mel-...")` — chat completion, streaming, tool calls,
    and dynamic model listing via the OpenAI-compatible Chat Completions / Models API.
  - Built on the existing `openai` SDK (no new dependency); SSRF-guarded `base_url`, shared
    temperature clamping, secret-scrubbed error mapping — mirrors the IONOS provider.
  - Pricing for the default model added to `cost_service.py`; remaining per-model rates are
    filled once the live `/v1/models` ids are confirmed.
  - 28 unit tests + factory test + live integration suite (`test_melious_live.py`).

## Version 1.11.2 (17.06.2026)

### Changed

- **[CHG] Docs:** clarified the document-content limitation in `docs/langdock-export.md` (EN+DE) and
  `usage/AGENT.md` after live export of a real agent. An agent's knowledge lives either in a
  **Knowledge Folder** (metadata + semantic search only — no raw download) or as **attachments**
  (no download endpoint at all — HTTP 404, only the IDs are captured in the agent `.json`). An agent
  can show `knowledgeFolderIds: []` while its documents live as attachments. `langdock-export` backs
  up the agent definition + system prompt + attachment IDs, never the document bytes.

## Version 1.11.1 (17.06.2026)

### Changed

- **[CHG] `langdock-export` UX after live testing against the real LangDock API:**
  - When agent retrieval fails with access errors, the CLI now collapses the per-agent error flood
    (shows the first 3, then a count) and prints a clear hint that **each agent must be shared with
    the API key** in LangDock — the `AGENT_API` scope alone grants no per-agent access. (Discovery
    can list e.g. 58 workspace agents while the key can retrieve 0 until they are shared.)
  - Documented the per-agent sharing prerequisite in `docs/langdock-export.md` (EN+DE) and
    `usage/AGENT.md`.

### Verified

- End-to-end live validation: a shared agent is correctly exported — `.md` carries the real system
  prompt (verified, 4 KB instruction) and `.json` the full raw definition; empty `knowledgeFolderIds`
  are omitted defensively.

## Version 1.11.0 (17.06.2026)

### Added

- **[ADD] LangDock backup/export tool** — decentralised backup of LangDock agents and
  knowledge-folder metadata so they stay portable when LangDock is unavailable (and reusable in
  other AI tools, e.g. as Claude Code subagent prompts).
  - **HTTP layer** (`providers/langdock_provider.py::LangDockExportManager`): `get_agent()` via the
    non-deprecated `GET /agent/v1/get`, `export_report()` via `POST /export/{report}`,
    `download_signed_csv()`. Reuses the existing `_safe_detail()` credential scrubbing and maps
    HTTP status onto `AuthenticationError`/`RateLimitError`/`ProviderError`.
  - **Orchestration** (`services/langdock_export.py::LangDockBackupExporter`): agent discovery via
    the `/export/agents` usage CSV, UI-URL/UUID normalisation, portable Markdown rendering
    (YAML frontmatter + system prompt), per-agent `.md` + `.json` backup, knowledge-folder metadata
    backup, and a run `manifest.json`. A single failed agent never aborts the run.
  - **CLI**: new `eq-chatbot langdock-export` command (`--agent-id` / `--discover` / `--no-discover`
    / `--knowledge-folder-id` / `--format md|json|both` / `--output-dir`, `LANGDOCK_API_KEY` env).
  - **Tests**: 26 new unit tests (`tests/unit/test_langdock_export.py`) — httpx-mock + CliRunner.
- **Agent capability card** (`usage/AGENT.md`): token-efficient, machine-skimmable CLI reference for
  LLM/agent consumers, generated deterministically from the Click command tree.

### Notes

- **API limits (by design):** LangDock exposes no "list all agents" endpoint — ids come from the UI
  URL or the `/export/agents` CSV (which needs an admin key with the `USAGE_EXPORT_API` scope).
  Knowledge-folder *content* cannot be downloaded via the API — only file metadata is backed up.
- No new runtime dependency: `httpx` and `click` are already core.

## Version 1.10.0 (14.06.2026)

### Added

- **[ADD] IONOS AI Model Hub provider** (`ionos_provider.py`, `get_provider("ionos")`): connects to the
  IONOS Cloud AI Model Hub, a German/EU-hosted (Berlin / `de-txl`), OpenAI-compatible inference gateway.
  Built on the existing `openai` SDK, so **no new dependency** is added. Key properties:
  - **`base_url` has a default** (`https://openai.inference.de-txl.ionos.com/v1`) and is optional —
    unlike the `litellm` provider, the official endpoint is used unless an override is passed.
  - Stricter SSRF guard: `validate_url(allow_private_ranges=False)` — IONOS is a fixed public endpoint.
  - API token sent as `Authorization: Bearer <api_key>` (generated in the IONOS DCD Token Manager).
  - Configurable default model via the `model=` constructor arg (soft default
    `meta-llama/Llama-3.3-70B-Instruct`). Catalogue includes Llama 3.x, Mistral Small/Nemo and the
    German `openGPT-X/Teuken-7B-instruct-commercial`.
  - Full chat contract: `chat_completion`, `stream_completion`, `list_models` (no name filtering),
    tool calls, gateway-robust streaming with token usage on the authoritative final chunk.
  - Error messages scrubbed via `utils.scrub_secrets`.
- **Curated IONOS pricing** added to `services/cost_service.py` (real IONOS EUR/1M-token rates,
  converted to USD/1K). Verify against current IONOS rates before relying on exact cost figures.
- **Unit tests** (`tests/unit/test_ionos.py`, factory case in `tests/unit/test_factory.py`) + **live
  integration tests** (`tests/integration/test_ionos_live.py`, gated on `IONOS_API_KEY`).
- Report wiring fix: `litellm` was missing from the test report dictionaries in `conftest.py`
  (`_MODULE_GROUPS`, `_RESOLUTION_LABELS`, etc.) — both `litellm` and `ionos` are now wired in.

### Notes

- DSGVO/GDPR: IONOS hosts in the EU (Germany), making it suitable for EU-regulated workloads.

## Version 1.9.0 (14.06.2026)

### Added

- **[ADD] LiteLLM provider** (`litellm_provider.py`, `get_provider("litellm")`): connects to any
  OpenAI-compatible gateway — a LiteLLM proxy, vLLM, or custom endpoint. Built on the existing `openai`
  SDK, so **no new dependency** is added. Key properties:
  - **`base_url` is required, no default** — the endpoint must be passed explicitly (keeps the provider
    open/extensible; any future gateway works by supplying a different URL).
  - Configurable default model via the `model=` constructor arg (soft default `qwen3.6-35b-a3b`).
  - Full chat contract: `chat_completion`, `stream_completion`, `list_models` (no provider-specific
    name filtering, so non-`gpt-*` models like `qwen3.6-35b-a3b` are kept). Reasoning models'
    `reasoning_content` is preserved in `raw_response`, never merged into `content`.
  - **Gateway-robust streaming:** content/tool deltas are streamed as they arrive, then a single
    authoritative final chunk carries `finish_reason`, accumulated tool calls, and token usage — so
    gateways (LiteLLM/vLLM) that send `finish_reason` and `usage` in *separate* trailing frames still
    report correct token counts on the final chunk.
  - **Audio:** `text_to_speech()` (e.g. `kokoro-tts-1`) and `transcribe()` (e.g. `whisper-large-v3`)
    via the OpenAI Audio API.
  - SSRF guard on `base_url` (reuses `utils.validate_url`); error messages scrubbed via
    `utils.scrub_secrets`.
- **30 unit tests** (`tests/unit/test_litellm.py`) + **live integration tests**
  (`tests/integration/test_litellm_live.py`, gated on `LITELLM_API_KEY` / `LITELLM_BASE_URL`).
- Registry entry in `providers/__init__.py` (`CLOUD_PROVIDERS`, factory, exports); test config in
  `tests/.env.example`, `tests/conftest.py`, `tests/model_registry.py`; docs in `docs/providers.md`
  (EN + DE, incl. TTS/STT and GDPR note).

### Changed

- **Version**: `1.8.1` → `1.9.0`

## Version 1.8.1 (14.06.2026)

### Security

Hardening pass from a structured security review (no remote-exploitable critical issues found;
all changes are fail-safe / defense-in-depth).

- **[FIX] FileValidator no longer fails open**: when the optional `puremagic` dependency
  (`[security]` extra) is missing, `_validate_mime_type` previously returned the file as
  *verified* while silently skipping magic-byte inspection, allowing content/extension spoofing
  (e.g. a script uploaded as `x.pdf`). The validator now surfaces the degradation via a new
  `FileValidationResult.mime_verified` flag and a `WARNING`, and a new `FileValidator(require_magic=True)`
  fails closed when `puremagic` is unavailable.
- **[ADD] Secret scrubbing for logs and error surfaces** (`utils.scrub_secrets`): API-key prefixes
  (`sk-`, `sk-ant-`, `sk-or-`, `ld-`, `mm-`), `Bearer` tokens, and secret query parameters are masked.
  LangDock upstream error bodies are now scrubbed + length-bounded before logging or being embedded
  in raised `ProviderError` messages; `ChatbotErrorHandler.ErrorResult.original_error` is scrubbed too.
- **[FIX] `retry-after` is now clamped** to `MAX_RETRY_AFTER` (3600s) in `ChatbotErrorHandler`,
  preventing a manipulated provider response from forcing an unbounded caller-side wait (self-DoS).
- **[ADD] SSRF validation for the local provider `base_url`** (`utils.validate_url`): non-HTTP schemes
  and cloud-metadata / link-local targets (e.g. `169.254.169.254`) are rejected; private/LAN ranges
  stay allowed since local model servers legitimately live there. The MCP SSE client now shares this
  helper (strict mode, unchanged behavior).
- **[ADD] PDF resource limits** (`utils.pdf`): `MAX_PDF_BYTES` (50 MB), `MAX_PAGES_HARD` (50), and
  `MAX_DPI` (600) bound memory/CPU when rendering untrusted PDFs (decompression-bomb / huge-DPI DoS).
- **[CHG] MCP stdio command validation hardened**: both the literal and PATH-resolved command basenames
  are checked against the allowlist; the PATH trust model is now documented.
- **[CHG] API key encapsulation**: `BaseLLMProvider.api_key` is now a read-only property backed by a
  non-public attribute. Negative token counts in `calculate_cost` raise `ValueError`.
- **[ADD] Supply-chain gate**: `pip-audit` added to CI and dev dependencies; vulnerable transitive
  dependencies (cryptography, urllib3, starlette, requests, idna, protobuf, pygments, pytest) bumped
  to patched versions in `uv.lock`; upper version bounds added to dev tooling.
- Documented caller security responsibilities (injection / rate-limit primitives are not auto-enforced)
  in the README and `security` package docstring.

## Version 1.7.6 (04.06.2026)

### Fixed

- **[FIX] Local provider silently swallowed server-side error bodies**: LM Studio / Ollama
  return **HTTP 200** with an `error` object in the body (chat) or an `event: error` /
  `data: {"error": {...}}` SSE frame (stream) when a request fails — most commonly when the
  prompt exceeds the model's context length. The parser found no `choices`, produced empty
  content and the user saw a **blank chat reply** with no explanation. `chat_completion` and
  `stream_completion` now detect the `error` field and raise `ContextLengthError` (for
  context/token errors) or `ProviderError` with the server message. Added regression tests
  (`test_chat_completion_surfaces_error_body`, `test_stream_completion_surfaces_error_event`).

## Version 1.7.5 (03.06.2026)

### Fixed

- **[FIX] Spurious "Failed to parse SSE chunk" warnings for SSE comment lines**: the
  OpenRouter and Mammouth streaming parsers tried to JSON-parse SSE comment / keep-alive
  lines (which start with `:`, e.g. OpenRouter's `: OPENROUTER PROCESSING` emitted while the
  upstream model warms up), logging a `WARNING` for every ping. Such lines are now skipped
  per the SSE spec. The `local` and `langdock` providers already ignored non-`data:` lines
  and were unaffected. Added a regression test (`test_stream_skips_sse_comment_lines`).

## Version 1.7.4 (02.06.2026)

### Fixed

- **[FIX] OpenRouter `list_models()` crash on null model fields**: `list_models()`
  aborted the entire model listing with `AttributeError: 'NoneType' object has no
  attribute 'get'` whenever OpenRouter returned a model whose `default_parameters`
  field was an explicit JSON `null` (e.g. `openrouter/owl-alpha`). The `dict.get(key,
  default)` fallback only applies when the key is *absent*, not when it is present with
  a `null` value, so `default_params` became `None` and downstream `.get()` calls
  failed. Consumers (e.g. the chatbot application) therefore received an empty model
  list. All container fields (`default_parameters`, `supported_parameters`,
  `input_modalities`, `output_modalities`, `top_provider`) are now coerced with `or`
  to tolerate explicit `null` values. Verified live against all 342 current OpenRouter
  models.

## Version 1.7.3 (02.06.2026)

### Fixed

- **[FIX] Local provider (Ollama/LM Studio) streaming tool calls**: `stream_completion`
  only emitted raw `tool_call_delta` fragments and never populated `chunk.tool_calls`.
  Consumers that read the assembled `tool_calls` (e.g. the Odoo IHA tool loop) therefore
  never saw any tool call, so function calling was effectively dead for local models in
  streaming mode. The provider now accumulates the chunked tool-call deltas by index and
  exposes the complete `tool_calls` list on the final chunk, mirroring the OpenAI provider.

## Version 1.7.0 (07.05.2026)

HTTP/SSE-Server-Mode für cross-language-Integrationen — eq_chatbot_core kann jetzt als lokaler Sidecar gestartet werden, den z.B. Desktop-Apps (Avalonia, Electron) per HTTP ansprechen.

### Added

- **`eq-chatbot serve`-Subcommand** (`src/eq_chatbot_core/cli.py`): startet einen lokalen FastAPI/Uvicorn-Server, der die Provider-Abstraktion über HTTP exponiert. Bind-Default `127.0.0.1:0` (ephemeral Port → in stdout als `LISTENING ON host=H port=P` für Parent-Process). Bearer-Token-Auth via `--auth-token-fd <fd>` (Token aus Datei-Deskriptor lesen, nicht in `argv`/`ps`-Output) oder `--auth-token <token>` (insecure-Fallback) oder `EQ_CHATBOT_AUTH_TOKEN`-Env. Optionaler `--parent-pid <pid>` aktiviert einen Watchdog der den Sidecar killt sobald der Parent-Prozess verschwindet (verhindert Zombie-Sidecars bei Parent-Crash).
- **Server-Modul `eq_chatbot_core/server/`** mit Submodulen:
  - `app.py` — FastAPI-App-Factory mit Endpoints `GET /health` (auth-frei), `GET /providers` (Provider-Catalog), `POST /models` (per-Provider Model-Listing), `POST /chat` (Single-Shot LLMResponse als JSON), `POST /chat/stream` (SSE-Stream). Provider-Errors werden auf passende HTTP-Codes gemappt (`AuthenticationError` → 401, `RateLimitError` → 429 mit `retry_after`, `ContextLengthError` → 413, `OverloadedError` → 503).
  - `auth.py` — `BearerTokenMiddleware` mit `hmac.compare_digest`-Vergleich (constant-time, gegen Timing-Attacks). `/health`, `/docs`, `/openapi.json`, `/redoc` sind auth-frei.
  - `streaming.py` — `StreamChunk` → SSE-Events: `event: chunk` per Token, `tool_call_delta` für Streaming-Tool-Calls, `usage` mit Token-Counts, `tool_calls` mit akkumulierten Tool-Calls, `done` als finaler Marker, `error` bei Provider-Fehlern mid-stream.
  - `lifecycle.py` — Pre-bound Socket für ephemeral-Port-Discovery (uvicorn bekommt den fertigen Socket via `Server.serve(sockets=[...])`), Parent-PID-Watchdog (poll alle 5s `os.kill(parent_pid, 0)`, sendet SIGTERM an sich selbst bei Parent-Exit).
  - `models.py` — Pydantic-Schemas für alle Endpoints (`ChatRequest`, `ChatResponse`, `ListModelsRequest`, `ProviderInfo`, `HealthResponse`).
- **38 neue Unit-Tests** in `tests/unit/server/`: `test_streaming.py` (8 Tests für SSE-Translation), `test_auth.py` (7 Tests für Bearer-Middleware), `test_app.py` (15 Tests für Endpoints, mocked provider), `test_cli_serve.py` (8 Tests für CLI-Auth-Resolution + Subcommand-Wiring). Sse-Starlette-Eventloop-Bind-Workaround (`AppStatus.should_exit_event` zwischen Tests reset) als autouse-Fixture.
- **Optional-Extra `[server]`** (`pyproject.toml`): `fastapi>=0.115`, `uvicorn>=0.32`, `sse-starlette>=2.1` — werden nur installiert wenn explizit angefordert (`pip install eq-chatbot-core[server]`). Pure CLI/RAG/MCP-Imports laufen weiterhin ohne diese Pakete.

### Changed

- **Version**: `1.6.0` → `1.7.0`

### Use case

Designed für Apps die Python nicht direkt einbetten können (Avalonia/.NET, Electron, native iOS/Android). Parent generiert ein Random-Token, pipet es über stdin in den Sidecar, scrappt den gebundenen Port aus stdout, und kommuniziert ab da via HTTP+SSE auf 127.0.0.1. Nächster Schritt (separate Phase): PyInstaller-Frozen-Binary für Plattform-Distribution.

## Version 1.6.0 (06.05.2026)

### Added
- **CI/CD pipeline** (`.github/workflows/ci.yml`) — GitHub Actions workflow with three stages: lint
  (ruff check, ruff format check, mypy), test matrix across Python 3.10–3.13 with coverage, and
  build verification (`python -m build` + `twine check`). Uses `astral-sh/setup-uv@v3` for fast,
  cache-aware UV-based dependency installation. Triggered on push and PR to `main`.
- **7 new unit tests** in `tests/unit/test_mcp.py` covering the security hardening below:
  `test_pythonpath_not_forwarded_to_subprocess`, `test_pythonpath_via_explicit_env_still_works`,
  `test_validate_url_returns_resolved_ips`, `test_validate_url_returns_empty_set_for_unresolvable`,
  `test_pinned_transport_rejects_rebinding`, `test_pinned_transport_passes_when_resolution_matches`,
  `test_pinned_transport_skips_check_for_unpinned_hosts`,
  `test_mcpclient_pins_base_url_on_init`, `test_mcpclient_pins_endpoint_from_sse_event`.

### Changed
- **Dependency floors raised** (`pyproject.toml`): `openai>=2.0` (v2 GA with Responses API),
  `anthropic>=0.90,<2.0` (1.0 GA imminent — defuses the `<1.0.0` time bomb that would have
  broken installs), `pydantic>=2.11`, `cryptography>=44.0,<49.0` (added upper bound),
  `azure-ai-inference>=1.0.0b9`, `pymupdf>=1.26.0,<2.0.0`, `puremagic>=2.0,<3.0`,
  `sentence-transformers>=3.0.0,<6.0.0` (was `>=2.2.0`, three majors behind).

### Fixed
- **Security: DNS rebinding protection in MCP SSE client** (`mcp/client.py`) — `_validate_url()`
  now returns the resolved IP set and the new `_build_pinned_transport()` produces an
  `httpx.HTTPTransport` subclass that re-resolves the hostname on every request and raises
  `httpx.ConnectError("DNS rebinding detected")` if the resolution diverges from the pinned set.
  Both the SSE listener client and the request client share the same `_pinned_ips` map; endpoint
  redirects sent by the server are also pinned. Mitigates the TOCTOU between `__init__`'s
  validation and httpx's actual connect (a small TOCTOU window remains — for complete protection
  deploy network-level egress filtering).
- **Security: PYTHONPATH removed from `_ENV_WHITELIST`** (`mcp/client.py`) — `StdioMCPClient.start()`
  no longer forwards `PYTHONPATH` from `os.environ` to MCP server subprocesses. `PYTHONPATH`
  inheritance allowed arbitrary module injection that could override stdlib imports inside the
  subprocess, defeating the existing command whitelist. Callers needing a custom Python path
  must now pass it via the explicit `env=` argument.
- **Type hints**: `_validate_url()` and `_build_pinned_transport()` use precise `frozenset[str]`
  types; explicit `str()` cast on `socket.getaddrinfo` sockaddr tuples to satisfy strict mypy.

## Version 1.5.1 (27.04.2026)

### Fixed
- **Security: SSRF protection in MCP SSE endpoint handler** (`mcp/client.py`) — server-supplied
  endpoint URLs are now validated against `_validate_url()`, preventing a hostile MCP server
  from redirecting POST traffic to private/reserved IPs after SSE connection setup. Malformed
  schemes (e.g. `file:///…`) and non-`/`-relative paths are rejected outright.
- **Security: Subprocess env whitelist for stdio MCP** (`mcp/client.py`) — `StdioMCPClient.start()`
  no longer forwards the full caller `os.environ` to MCP server subprocesses. A minimal
  whitelist (`PATH`, `HOME`, `LANG`, `LC_ALL`, `TZ`, `TMPDIR`, `USER`, `LOGNAME`, `SHELL`,
  `PYTHONPATH`, `SystemRoot`/`SYSTEMROOT`) plus the explicitly supplied `self.env` is used
  instead, preventing accidental leakage of API keys to child processes.
- **Security: Injection detection runs before HTML escape** (`security/injection.py`) —
  `sanitize_input()` previously escaped HTML before pattern matching, which silently bypassed
  angle-bracket and paren-based patterns. Detection now runs on the raw text.
- **Security: Disable redirect following on direct httpx calls** — added `follow_redirects=False`
  to standalone `httpx.get/post` calls in `mammouth_provider.py:326` and
  `langdock_provider.py:455, 950, 1698` to prevent SSRF via DNS-based redirect manipulation.
- **Test setup: Skip Azure tests cleanly when SDK missing** — `tests/unit/test_azure.py` now uses
  `pytest.importorskip("azure.ai.inference")`, turning 38 cascading `ImportError` failures into
  a single sane skip when the optional `[azure]` extra is not installed. `test_factory.py::test_get_azure_provider`
  patches `_azure_available` analogous to the existing Vertex test pattern.
- **Test: Version assertion no longer hardcoded** (`tests/unit/test_mcp.py`) — switched from
  literal `"1.3.0"` comparison to a PEP-440 regex check so the test does not regress on every
  release bump.

### Added
- 4 regression tests covering the security fixes above:
  `test_handle_endpoint_event_rejects_private_ip`,
  `test_handle_endpoint_event_rejects_non_http_scheme`,
  `test_start_does_not_leak_secrets_to_subprocess`,
  `test_angle_bracket_injection_detected_before_escape`.

## Version 1.5.0 (30.03.2026)

### Added
- New `chat` CLI command for programmatic single-turn LLM interaction with JSON I/O
  - Reads `{"messages": [...]}` from stdin, writes `{"content": "...", "model": "...", "input_tokens": N, "output_tokens": N}` to stdout
  - Supports all providers via `--provider`, `--model`, `--temperature`, `--max-tokens` flags
  - Designed for integration with external tools (e.g., sysReporter Rust CLI)
  - Error responses as JSON on stderr with non-zero exit code
  - Input validation: message schema (role, content), stdin size limit (1 MB)
  - 16 unit tests covering all error paths and success scenarios

## Version 1.4.0 (23.03.2026)

### Changed
- LangDock Agent API migration: `/assistant/v1/` → `/agent/v1/` endpoints
- LangDock payload field: `assistantId` → `agentId`
- LangDock chat/completions: Vercel AI SDK UIMessage format (parts[], metadata.attachments)
- LangDock response parsing: `result[]` → `messages[]` format
- LangDock Knowledge search: `/knowledge/{folder_id}/search` → `/knowledge/search` (API-key scoped)
- LangDock AgentManager CRUD: camelCase field names (`agentId`, `knowledgeFolderIds`, `instruction`)
- New `_convert_to_agent_messages()` method extracts duplicated message conversion logic
- Simplified streaming code (removed legacy SSE fallback)

## Version 1.3.0 (17.03.2026)

### Added
- Google Vertex AI provider with Gemini 2.0/2.5 model support via `google-genai` SDK
- Vertex AI uses Application Default Credentials (ADC) — no API key needed
- EU region support (europe-west1, europe-west3, europe-west4) for GDPR compliance
- 44 unit tests + 5 integration tests for Vertex provider
- `[vertex]` optional dependency group in pyproject.toml
- Gemini 2.0-flash and 2.0-flash-lite pricing in cost_service

### Changed
- CLI: Added `vertex` to cloud providers with API-key bypass (uses ADC)
- Factory: `get_provider("vertex", project="...", location="...")` registration
- README.md: Bilingual documentation with Vertex AI usage examples
- Test infrastructure: Vertex module group in conftest.py report generation

### Fixed
- LangDock Knowledge Manager endpoint corrections (from v1.2.1)

## Version 1.2.1 (14.03.2026)

### Fixed
- LangDock Knowledge Manager endpoint corrections

## Version 1.2.0 (13.03.2026)

### Changed
- Azure model catalog expansion + temperature constraint fixes
- LangDock export: switch from JSON to Markdown format
