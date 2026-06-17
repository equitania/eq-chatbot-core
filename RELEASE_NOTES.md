# Release Notes

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
