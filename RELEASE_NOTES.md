# Release Notes

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
