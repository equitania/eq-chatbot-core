# Changelog

All notable changes to eq-chatbot-core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-08-18

### Breaking

- **Minimum Python is now 3.12** (was 3.10). Aligns the library with the
  interpreter used for Odoo 16 deployments. Python 3.10 reaches end of life on
  2026-10-31; 3.11 is dropped in the same step so there is only one supported
  baseline. Installs on 3.10/3.11 now fail at resolution time instead of
  silently running an untested combination. The CI matrix is 3.12 and 3.13.

### Security

- **DNS rebinding is now blocked for every LLM provider.** `validate_url()` only
  covered the resolution at construction time; the actual requests then went out
  through SDK/httpx clients that re-resolved the hostname unpinned. A caller who
  controls `base_url` — reachable through the server sidecar's `POST /chat`,
  which accepts `base_url` in the request body — could point it at a hostname
  with a near-zero TTL that passed validation as a public address and then
  resolved to `169.254.169.254` or another internal target by the time the
  socket opened, sending the `Authorization` header along with it (TOCTOU SSRF).
  All seven client-constructing providers (`openai`, `anthropic`,
  `openai_compatible` and its `azure`/`ionos`/`litellm`/`melious` subclasses,
  `langdock`, `local`, `mammouth`, `openrouter`) now route through a transport
  that re-checks DNS on every connect.

  The new transport revalidates rather than pinning strictly: an address set
  that diverges from the original resolution is re-run through the same SSRF
  policy and rejected only if it is private/reserved/metadata. Strict pinning
  would have turned the legitimate IP rotation of CDN-fronted provider endpoints
  into hard connection failures in long-lived processes.

- **`cryptography` floor raised to 50.0.0**, which excludes PYSEC-2026-3552
  (Bleichenbacher oracle in PKCS#7 decryption). The previous `<50.0.0` ceiling
  actively excluded the fixed release, so `pip-audit --strict` — a hard CI gate —
  could not pass. This library only ever uses Fernet, so the vulnerable code path
  was never reachable here, but the pin held shared environments on a vulnerable
  range.

- `h2` moves to 4.4.1 via the refreshed lockfile, clearing PYSEC-2026-3628
  (HTTP/2 request smuggling). HTTP/2 is not enabled anywhere in this codebase.
- **Three request paths still bypassed the new rebinding guard.** The LangDock
  agent backend built its URL from `base_url` but issued it through the
  module-level `httpx.post()`, so the very backend most likely to run against a
  self-hosted gateway was never covered; both the sync and streaming paths now
  go through the pinned client. `LangDockExportManager.download_signed_csv()`
  fetched a URL taken from an API response with `follow_redirects=True`, and
  `CapabilityCatalog.from_remote()` fetches a caller-supplied URL — both now use
  a new `build_validating_transport()`, which re-applies the SSRF policy to every
  host it is asked to connect to. Pinning cannot help there: it only guards hosts
  it already knows, and a redirect can name a fresh one.

### Fixed

- **A typed `ProviderError` lost its status code.** Every LangDock backend ends
  in a blanket `except Exception` that routes through `_handle_error()`. A
  `ProviderError` raised deliberately inside the `try` — carrying e.g.
  `status_code=429` — was caught by it and flattened into a generic
  `ProviderError` with no status, so callers could not distinguish rate limiting
  from an outage. All ten handlers now re-raise typed errors untouched.
- **An empty `candidates` list crashed the Gemini path.** `data.get("candidates",
  [{}])[0]` defaults only when the key is *absent*; Gemini returns
  `"candidates": []` for a safety-blocked response, which raised `IndexError` and
  surfaced as `ProviderError("list index out of range")`. Same pattern fixed for
  Codestral's `choices`.

### Added

- `utils/url_validation.build_pinned_transport_for_url()` — validates a URL and
  returns an httpx transport that re-checks DNS on every connect.
- `utils/url_validation.build_pinned_transport()` — the strict-pinning transport
  previously private to the MCP client, now shared.
- **`py.typed` marker (PEP 561).** The package is checked under `mypy --strict`
  but shipped without the marker, so every downstream consumer saw `Any` and none
  of that typing work was visible outside the repo.
- Test coverage for three previously untested areas: `server/lifecycle.py`
  (22% -> 93%), `utils/pdf.py` (40% -> 88%) and `providers/langdock_provider.py`
  (29% -> 64%), plus rebinding tests covering both the blocked attack and the
  tolerated legitimate IP rotation. The LangDock suite pins down the agent,
  google and codestral paths, the message converters, model listing and the
  manager classes — it is what surfaced the two bugs above.
- `utils/url_validation.build_validating_transport()` — SSRF-checks every host,
  for targets that are not one fixed endpoint.
- `providers/stream_accumulator.ToolCallAccumulator` — the streamed tool-call
  fold that six providers each implemented inline, now shared and tested. It
  normalizes both delta flavours (typed SDK objects and parsed-JSON dicts), so
  the providers keep their own `tool_call_delta` payloads, which differ on
  purpose. Net -125 lines across the six.

### Changed

- `puremagic` floor raised to 2.0 (the 1.x allowance existed only for 3.10/3.11).
- `websockets` ceiling raised to `<18.0`. Note that `google-genai` caps it at
  `<17.0`, so an install combining `[realtime,vertex]` still resolves to 16.x.
- `tomli` dependency removed — `tomllib` is stdlib on every supported version.
- Pre-commit hooks pinned to the versions the project actually uses (ruff 0.16.3,
  mypy 1.19.1, pre-commit-hooks 6.0.0). They were on ruff 0.1.9 / mypy 1.8.0, so
  the hook formatted by different rules than CI verified.
- `utils/pricing.py` documented as a deliberate backward-compatibility shim and
  covered by tests, rather than left as an unexplained 0%-coverage module.
- `twine` floor raised to 7.0.0: hatchling emits Metadata-Version 2.5, which
  twine 6.x rejects outright, so `twine check dist/*` failed on every build.
- mypy errors reduced 157 -> 122; the CI ratchet baseline is lowered to match.
  Includes real fixes in `realtime/websocket_client.py`, whose optional-import
  fallback assigned `None` to module-typed names.

## [2.0.2] - 2026-08-06

### Fixed

- Do not send `temperature` to Claude models that reject it. Anthropic removed
  the parameter on Claude Opus 4.7 and later; a request carrying it fails with
  `400 "temperature is deprecated for this model"`. The single `"claude"`
  prefix entry in `MODEL_TEMPERATURE_CONSTRAINTS` claimed support for the whole
  family, so every temperature-setting call to those models failed. Explicit
  entries now cover `claude-fable-5`, `claude-mythos-5`,
  `claude-mythos-preview`, `claude-opus-5`, `claude-opus-4-8`,
  `claude-opus-4-7` and `claude-sonnet-5`; `clamp_temperature()` returns `None`
  for them and the providers omit the parameter. Opus 4.6, Sonnet 4.6 and older
  are unchanged.

## [2.0.1] - 2026-07-27

### Fixed

- **SSRF guard no longer rejects IPv4-only endpoints on DNS64/NAT64 networks.**
  A DNS64 resolver synthesizes an AAAA record inside the RFC 6052 well-known
  prefix `64:ff9b::/96` for hosts that only publish an A record. That prefix sits
  inside `::/8`, which Python flags as `is_reserved`, so `validate_url()` rejected
  the synthesized address — and with it every provider without native IPv6
  (Melious, OpenAI, …) with "URL resolves to private/reserved IP". IPv4-mapped
  addresses (`::ffff:0:0/96`) shared the same misclassification.
  `validate_url()` now classifies the embedded IPv4 for both prefixes while still
  pinning the address as resolved, so DNS-rebinding protection is unaffected.
  Rejection messages name both forms: `64:ff9b::a9fe:a9fe (embeds 169.254.169.254)`.

### Security

- NAT64 unwrapping classifies the embedded IPv4 rather than allowing the prefix:
  `64:ff9b::a9fe:a9fe` unwraps to the cloud-metadata endpoint 169.254.169.254 and
  stays blocked in both strict and LAN mode. Covered by regression tests in
  `tests/unit/test_url_validation.py`.

## [2.0.0] - 2026-07-25

### Changed

- **BREAKING — Azure provider migrated off the retired `azure-ai-inference` SDK.**
  Microsoft retires the Azure AI Inference beta SDK on **2026-08-26**; the official
  replacement is the GA OpenAI SDK against the resource's OpenAI `/v1` endpoint.
  `AzureProvider` now derives from `OpenAICompatibleProvider`.
  - `base_url` changes from `https://<res>.services.ai.azure.com/models` to
    `https://<res>.openai.azure.com/openai/v1/`. The old form is rejected at
    construction with a migration hint instead of failing later with a 404.
  - The `[azure]` extra is no longer needed and is kept as an empty no-op so
    existing install commands keep working.
  - `api_version` is obsolete: accepted but ignored, with a `DeprecationWarning`.
  - Model coverage is unchanged — the `/v1` endpoint serves Azure OpenAI models and
    Foundry Models from other providers alike. Reasoning deployments now correctly
    send `max_completion_tokens`. `AzureProvider` gained the shared `model` argument.
- `sse-starlette` ceiling raised to `<4.0.0` and `google-genai` moved to
  `>=2.0.0,<3.0.0`; both verified against the API surface actually used.
- mypy CI baseline lowered 167 → 155.

### Security

- Lock refreshed against the now-hard `pip-audit` gate, which surfaced pins that were
  previously only logged: `python-dotenv` → 1.2.2 (PYSEC-2026-2270, declared floor raised),
  `pyasn1` → 0.6.4 (3 advisories, transitive via `google-auth`), `setuptools` → 83.0.0,
  and behind `[local]`: `torch` → 2.13.0 (incl. CVE-2025-3001), `transformers` → 5.14.1.

### Fixed

- **CI is green again** (it was red before this release). `test_pyproject.py` imported
  `tomllib` at module level behind a `skipif` mark — marks run after the import, so the
  Python 3.10 job died during collection; it now falls back to `tomli`. The CI jobs did not
  install the `[image]` extra, so the two Pillow-dependent CLI tests failed on every Python
  version and the image code paths were never exercised. The mypy baseline was measured with
  Pillow present while CI ran without it; corrected.
- The mypy ratchet no longer reports success when mypy aborts early on a blocking
  syntax/stub error (which would otherwise yield a near-zero, meaningless error count).
- The Azure unit suite no longer begins with `pytest.importorskip("azure.ai.inference")`,
  so it runs always instead of being silently skipped wherever the optional SDK was
  missing — which had hidden the Azure error paths from local test runs.

## [1.20.0] - 2026-07-25

### Security

- **SSRF guard closed on the remaining entry points**: `OpenAIProvider`, `AnthropicProvider`,
  `OpenAIEmbedder` and `MeliousEmbedder` passed a caller-supplied `base_url` into the SDK client
  unvalidated. Since the `[server]` sidecar forwards `ChatRequest.base_url` into `get_provider()`,
  an authenticated caller could reach internal addresses (e.g. `169.254.169.254`). All four now
  call `validate_url(base_url, allow_private_ranges=False)`.
- **Secret scrubbing completed**: the `openai`, `anthropic`, `azure`, `openrouter`, `vertex` and
  `mammouth` error paths now run `scrub_secrets()` like the other five providers already did.
  `server/app.py` scrubs defensively in its own error responses rather than trusting upstream.
- **CVE-excluding dependency floors**: `click>=8.3.3` (CVE-2026-7246), `cryptography>=46.0.7`
  (CVE-2026-26007 / -39892 / -34073), `Pillow>=12.3.0` in `[image]` (CVE-2026-59205 — affects all
  earlier releases, so the previous 12.2.0 floor did not exclude it). `pip-audit` is clean.

### Fixed

- **`AttributeError` during GC after a rejected `base_url`**: the SSRF check ran before the HTTP
  client attribute was assigned in the LangDock, Mammouth, IONOS, LiteLLM and Melious providers,
  so `__del__` raised on instances whose URL was rejected. Client attributes are initialized first.

### Changed

- **`OpenAICompatibleProvider` base class** (`providers/openai_compatible.py`): IONOS, Melious and
  LiteLLM shared byte-identical request/response/error code. Subclasses now declare only their
  constants; LiteLLM keeps its Audio API. Public API unchanged (class names, constructor
  signatures and module-level `DEFAULT_BASE_URL`/`DEFAULT_MODEL` preserved).
- **CI gates**: `pip-audit --strict` is a hard gate instead of advisory; `mypy` is ratcheted
  against a measured baseline so the typing debt cannot grow.

### Documentation

- AGPL-3.0 notice for the `pymupdf` dependency behind the `[pdf]` / `[docs]` extras.

> Note: entries for 1.18.0, 1.18.1 and 1.19.0 are documented in `RELEASE_NOTES.md`
> but were never backfilled into this file.

## [1.17.2] - 2026-07-04

### Security

- **Pillow bumped to `>=12.2.0,<13.0`** (`[image]` extra): the old `<12.0` bound blocked the
  patched 12.2.x line and pinned consumers to a version range with six published CVEs
  (incl. CVE-2026-42311 memory corruption via crafted PSD). Lock refreshed: Pillow 12.3.0,
  msgpack 1.2.1 (GHSA-6v7p-g79w-8964).
- **Consistent secret scrubbing in logs**: `error_handler.py` generic/fallback log lines,
  MCP SSE client URL/error logging and `TimeoutError` message, and the LangDock
  attachment-upload error path now all pass through `scrub_secrets()`/`_scrub()`.
- **SSRF validation for caller-supplied base_urls**: `validate_url()` now also guards the
  Azure provider (always caller-supplied) and LangDock/OpenRouter/Mammouth `base_url`
  overrides; default public endpoints skip the check (no DNS round-trip).

### Fixed

- **Circular import** on fresh `import eq_chatbot_core.services` (`utils/__init__.py`):
  `PRICING`/`calculate_cost` re-export is now lazy (PEP 562), breaking the
  `utils → pricing → cost_service → providers → local_provider → utils` cycle. API unchanged.

## [1.17.1] - 2026-06-23

### Changed

- **`listing-assets --help` examples** (`cli.py`): replaced the abstract `listing.json` snippets
  with a concrete `eq-listing-assets/v1` recipe (a banner with rendered title text + a no-text
  icon) and realistic CLI invocations. Click `\b` no-rewrap blocks keep the inline JSON/commands
  verbatim. Docs-only, no behaviour change. Mirrored into `docs/cli.md` (EN + DE) and
  `usage/AGENT.md`.

## [1.17.0] - 2026-06-22

### Added

- **User config file** (`utils/config.py`, `cli.py`): TOML config at
  `~/.config/eq-chatbot/config.toml` (XDG-aware; `EQ_CHATBOT_CONFIG` override) storing per-provider
  `api_key`/`base_url`/`model`, a global `default_provider` and chat `[defaults]`. Slots into the
  resolution chain after env vars (api_key) / before built-in defaults (base_url, model, provider,
  chat defaults). `--provider` is optional when `default_provider` is set.
- **`eq-chatbot config` command**: `init` (writes a 0600 commented template, `--force` to
  overwrite), `show` (path, permissions, key-masked contents), `path` (resolved path). Template
  bundled as `data/config.toml.example`.
- Plain-text keys with a group/other-readable warning. New dependency `tomli` for Python < 3.11.

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
