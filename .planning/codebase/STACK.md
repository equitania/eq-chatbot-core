# Technology Stack

**Analysis Date:** 2026-05-11

## Languages

**Primary:**
- Python 3.10+ - All library source code (`src/eq_chatbot_core/`)
- Python 3.10–3.13 - Tested matrix (CI runs all four versions)

**Secondary:**
- None (pure Python library)

## Runtime

**Environment:**
- CPython 3.10, 3.11, 3.12, 3.13 (all supported)
- Minimum: Python 3.10 (union-type syntax `X | Y` used throughout)

**Package Manager:**
- UV (astral-sh/uv) — mandatory, never pip
- Lockfile: `uv.lock` (present, committed)

## Frameworks

**Core:**
- None (pure library, no application framework for the library itself)

**HTTP Gateway (optional `[server]` extra):**
- FastAPI `>=0.115.0,<1.0.0` — REST API server (`src/eq_chatbot_core/server/`)
- Uvicorn `>=0.32.0,<1.0.0` — ASGI server for `eq-chatbot serve`
- sse-starlette `>=2.1.0,<3.0.0` — Server-Sent Events streaming

**CLI:**
- Click `>=8.1.0,<9.0.0` — `eq-chatbot` CLI entry point (`src/eq_chatbot_core/cli.py`)

**Testing:**
- pytest `>=8.0.0,<10.0.0` — test runner
- pytest-cov `>=6.0.0,<8.0.0` — coverage
- pytest-asyncio `>=0.24.0,<2.0.0` — async test support
- python-dotenv `>=1.0.0` — loads `tests/.env.test` for integration keys

**Build:**
- hatchling — build backend (`[build-system]` in `pyproject.toml`)
- twine `>=6.0.0` — PyPI upload (run locally, not in CI)

## Key Dependencies

**Critical (always installed):**
- `openai>=2.0.0,<3.0.0` — OpenAI and OpenAI-compatible provider SDK
- `anthropic>=0.90.0,<2.0.0` — Anthropic Claude SDK (supports prompt caching via `cache_control`)
- `httpx>=0.27.0,<1.0.0` — HTTP client (used directly in LangDock provider for raw requests)
- `pydantic>=2.11.0,<3.0.0` — Request/response models in server module
- `tiktoken>=0.9.0,<1.0.0` — Token counting for cost calculation
- `cryptography>=44.0.0,<49.0.0` — Fernet AES-128-CBC encryption for API key storage
- `qdrant-client>=1.12.0,<2.0.0` — Vector database client for RAG retrieval
- `click>=8.1.0,<9.0.0` — CLI

**Optional extras:**
- `[azure]` — `azure-ai-inference>=1.0.0b9`, `azure-core>=1.30.0` — Azure AI Foundry provider
- `[vertex]` — `google-genai>=1.0.0` — Google Vertex AI / Gemini provider
- `[server]` — FastAPI + Uvicorn + sse-starlette — HTTP sidecar gateway
- `[security]` — `puremagic>=1.10,<3.0` — MIME-type validation (Python 3.10/3.11 safe)
- `[pdf]` — `pymupdf>=1.26.0,<2.0.0` — PDF-to-image for vision models
- `[local]` — `sentence-transformers>=3.0.0,<6.0.0` — local embedding generation

## Configuration

**Environment:**
- No runtime `.env` loading in library code — callers pass API keys explicitly
- Integration tests read from `tests/.env.test` (gitignored, copied from `tests/.env.example`)
- Key env vars used in tests: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGDOCK_API_KEY`,
  `MAMMOUTH_API_KEY`, `AZURE_API_KEY`, `AZURE_ENDPOINT`, `SKIP_LIVE_TESTS`, `SKIP_LOCAL_TESTS`, `TEST_MAX_TOKENS`
- Vertex AI auth: `GOOGLE_APPLICATION_CREDENTIALS` (service account) or `gcloud auth application-default login`

**Build:**
- `pyproject.toml` — single source of truth for all dependencies and tooling config
- Version string: `src/eq_chatbot_core/version.py` (`__version__ = "1.7.2"`)
- Hatch version source: `[tool.hatch.version] path = "src/eq_chatbot_core/version.py"`

## Code Quality Tooling

**Linting/Formatting:**
- ruff `>=0.12.0` — lint (E, W, F, I, B, C4, UP rules) + format; line-length 120
- mypy `>=1.15.0` — strict type checking (advisory in CI, ~108 pre-existing errors)
- pre-commit `>=4.0.0` — hooks (configured but optional)

**Ruff config highlights:**
- `target-version = "py310"`
- Ignores: `E501` (line length handled by formatter), `B008`
- Test files allow `E402`, `B017`
- isort: `known-first-party = ["eq_chatbot_core"]`

## Platform Requirements

**Development:**
- UV installed (`astral-sh/setup-uv@v3` in CI)
- Python 3.10–3.13
- For Vertex: Google Cloud SDK (`gcloud`)
- For integration tests: API keys in `tests/.env.test`

**Production (as library):**
- Python >=3.10
- Callers install with desired extras: `pip install eq-chatbot-core[azure,pdf,server]`
- Published to PyPI as `eq-chatbot-core`
- Build/publish done locally by maintainer (not via CI)

---

*Stack analysis: 2026-05-11*
