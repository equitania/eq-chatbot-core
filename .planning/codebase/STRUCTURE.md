# Codebase Structure

**Analysis Date:** 2026-05-11

## Directory Layout

```
eq_chatbot_core/
├── src/
│   └── eq_chatbot_core/        # Installable package root (src-layout)
│       ├── __init__.py          # Package entry; exports __version__
│       ├── cli.py               # Click CLI: eq-chatbot command group
│       ├── version.py           # Single source of version string
│       ├── providers/           # LLM provider adapters
│       │   ├── __init__.py      # get_provider() factory + public exports
│       │   ├── base.py          # BaseLLMProvider, LLMResponse, StreamChunk, ModelInfo, exceptions
│       │   ├── openai_provider.py
│       │   ├── anthropic_provider.py
│       │   ├── azure_provider.py       # [azure] extra
│       │   ├── vertex_provider.py      # [vertex] extra
│       │   ├── langdock_provider.py
│       │   ├── openrouter_provider.py
│       │   ├── mammouth_provider.py
│       │   ├── local_provider.py       # LM Studio / Ollama
│       │   └── temperature_constraints.py
│       ├── server/              # HTTP sidecar (requires [server] extra)
│       │   ├── __init__.py      # Re-exports create_app, run_server
│       │   ├── app.py           # FastAPI app factory + route handlers
│       │   ├── auth.py          # BearerTokenMiddleware
│       │   ├── lifecycle.py     # uvicorn runner + parent-pid watchdog
│       │   ├── models.py        # Pydantic schemas: ChatRequest/Response, ChatMessage
│       │   └── streaming.py     # StreamChunk → SSE event converter
│       ├── rag/                 # Retrieval-Augmented Generation pipeline
│       │   ├── __init__.py
│       │   ├── chunker.py       # Document splitting strategies
│       │   ├── embedder.py      # Embedding generation (OpenAI or local)
│       │   ├── retriever.py     # Qdrant vector search
│       │   └── context_manager.py  # Token budget: history/RAG/response allocation
│       ├── security/            # Cross-cutting security utilities
│       │   ├── __init__.py
│       │   ├── encryption.py    # FernetEncryption for API key storage
│       │   ├── injection.py     # Prompt injection pattern detection
│       │   ├── rate_limit.py    # Token bucket rate limiter
│       │   └── file_validator.py  # MIME-type upload validation ([security] extra)
│       ├── services/            # Application-level shared services
│       │   ├── __init__.py
│       │   ├── cost_service.py  # Per-model token cost calculation
│       │   ├── error_handler.py # Categorized error recovery with fallback
│       │   └── knowledge_service.py  # Knowledge export for vector DBs
│       ├── mcp/                 # Model Context Protocol client
│       │   ├── __init__.py
│       │   └── client.py        # HTTP/SSE and stdio transports
│       └── utils/               # Standalone helpers
│           ├── __init__.py
│           ├── pricing.py       # Model pricing data tables
│           └── pdf.py           # PDF → image conversion ([pdf] extra)
├── tests/
│   ├── conftest.py              # Shared fixtures, env config loader
│   ├── model_registry.py        # Cheapest/pinned model selections per provider for tests
│   ├── unit/                    # Mocked tests, no external dependencies
│   │   ├── server/              # Server-specific unit tests
│   │   │   ├── test_app.py
│   │   │   ├── test_auth.py
│   │   │   ├── test_cli_serve.py
│   │   │   └── test_streaming.py
│   │   ├── test_anthropic.py
│   │   ├── test_azure.py
│   │   ├── test_chunker.py
│   │   ├── test_cli_chat.py
│   │   ├── test_context_manager.py
│   │   ├── test_cost_service.py
│   │   ├── test_encryption.py
│   │   ├── test_error_handler.py
│   │   ├── test_exceptions.py
│   │   ├── test_factory.py
│   │   ├── test_file_validator.py
│   │   ├── test_injection.py
│   │   ├── test_knowledge_service.py
│   │   └── ...
│   └── integration/             # Real API calls, requires .env.test
│       ├── test_azure_live.py
│       ├── test_local_live.py
│       ├── test_mammouth_live.py
│       ├── test_mcp_live.py
│       ├── test_openai_live.py
│       ├── test_openrouter_live.py
│       └── test_vertex_live.py
├── docs/                        # Topic-based documentation
│   ├── README.md
│   ├── cli.md
│   ├── mcp.md
│   ├── providers.md
│   ├── rag.md
│   ├── security.md
│   ├── server-mode.md
│   └── testing.md
├── .github/
│   └── workflows/
│       └── ci.yml               # Lint + unit tests only (no publish)
├── pyproject.toml               # Single source of truth: deps, extras, build config
├── uv.lock                      # Locked dependency tree
├── CHANGELOG.md
├── RELEASE_NOTES.md
├── TASKS.md
└── CLAUDE.md                    # Project-specific Claude Code instructions
```

## Directory Purposes

**`src/eq_chatbot_core/providers/`:**
- Purpose: All LLM backend adapters. The public API (`get_provider`, response types, exceptions) is exported from `__init__.py`.
- Key files: `base.py` (contract + types), `__init__.py` (factory + exports)
- Pattern: Each provider is one file, named `<name>_provider.py`

**`src/eq_chatbot_core/server/`:**
- Purpose: Optional HTTP sidecar for cross-language integrations. Only importable when `[server]` extras are installed.
- Key files: `app.py` (route definitions), `models.py` (Pydantic schemas), `auth.py` (middleware)
- Guarded by: `try/except ImportError` in `cli.py:serve` command

**`src/eq_chatbot_core/rag/`:**
- Purpose: Complete RAG pipeline. Used by application code; not wired into the HTTP server or CLI by default.
- Key files: `context_manager.py` (token budget), `retriever.py` (Qdrant queries)

**`src/eq_chatbot_core/security/`:**
- Purpose: Protection utilities intended to be composed into application code. Not automatically applied by providers.
- Key files: `encryption.py` (Fernet), `injection.py` (pattern detection)

**`src/eq_chatbot_core/services/`:**
- Purpose: Higher-level business logic (cost tracking, error recovery, knowledge export).
- Key files: `error_handler.py` (categorized recovery), `cost_service.py` (pricing)

**`src/eq_chatbot_core/utils/`:**
- Purpose: Leaf-level helpers with no internal dependencies.
- Key files: `pricing.py` (model cost tables), `pdf.py` (requires `[pdf]` extra)

**`tests/unit/`:**
- Purpose: Fast, fully mocked tests. SDK modules are patched via `sys.modules` before provider imports.
- Mirrors source layout: `tests/unit/server/` mirrors `src/eq_chatbot_core/server/`

**`tests/integration/`:**
- Purpose: Real API call tests. Skipped unless API keys present and `SKIP_LIVE_TESTS` unset.

## Key File Locations

**Entry Points:**
- `src/eq_chatbot_core/cli.py`: `main()` — all CLI commands
- `src/eq_chatbot_core/server/app.py`: `create_app(auth_token)` — HTTP server factory
- `src/eq_chatbot_core/__init__.py`: Package root; minimal (version only)

**The Provider Contract:**
- `src/eq_chatbot_core/providers/base.py`: `BaseLLMProvider`, all response types, all exceptions

**Provider Factory:**
- `src/eq_chatbot_core/providers/__init__.py`: `get_provider()` — sole public interface to create providers

**Wire Schemas:**
- `src/eq_chatbot_core/server/models.py`: `ChatRequest`, `ChatResponse`, `ChatMessage`

**Version:**
- `src/eq_chatbot_core/version.py`: Single `__version__` string; referenced by `pyproject.toml` dynamic version

**Dependencies:**
- `pyproject.toml`: All deps, optional extras, build config. Never add `requirements.txt`.

**Test Config/Fixtures:**
- `tests/conftest.py`: All shared fixtures
- `tests/model_registry.py`: Cheapest pinned model per provider (used in integration tests)

## Naming Conventions

**Files:**
- Provider adapters: `<name>_provider.py` (e.g., `openai_provider.py`, `vertex_provider.py`)
- Services: `<name>_service.py` (e.g., `cost_service.py`, `knowledge_service.py`)
- Tests: `test_<subject>.py` — subject matches module name (e.g., `test_encryption.py` tests `security/encryption.py`)
- Integration tests: `test_<provider>_live.py`

**Classes:**
- Providers: `<Name>Provider` (e.g., `OpenAIProvider`, `LangDockProvider`)
- Exceptions: Descriptive noun (e.g., `RateLimitError`, `ContextLengthError`)
- Pydantic schemas: Noun (e.g., `ChatRequest`, `ChatResponse`, `ChatMessage`)
- Dataclasses: Noun (e.g., `LLMResponse`, `StreamChunk`, `ModelInfo`)

**Functions:**
- Factory: `get_provider()` — single function, not a class method
- Route handlers: verb noun matching HTTP semantics (`chat`, `chat_stream`, `list_models`, `health`)

## Where to Add New Code

**New LLM provider:**
1. Create `src/eq_chatbot_core/providers/<name>_provider.py` — class `<Name>Provider(BaseLLMProvider)`
2. Add to factory dict in `src/eq_chatbot_core/providers/__init__.py:97` (`providers` dict)
3. Add name string to `CLOUD_PROVIDERS` in `src/eq_chatbot_core/server/app.py:48` and `src/eq_chatbot_core/cli.py:32`
4. Add `__all__` export in `src/eq_chatbot_core/providers/__init__.py`
5. Add optional extra in `pyproject.toml` if it requires a new SDK
6. Add unit tests: `tests/unit/test_<name>.py`
7. Add integration tests: `tests/integration/test_<name>_live.py`

**New security utility:**
- Implementation: `src/eq_chatbot_core/security/<name>.py`
- Tests: `tests/unit/test_<name>.py`

**New service:**
- Implementation: `src/eq_chatbot_core/services/<name>_service.py`
- Tests: `tests/unit/test_<name>_service.py`

**New HTTP endpoint:**
- Schema: `src/eq_chatbot_core/server/models.py` (add Pydantic model)
- Route: `src/eq_chatbot_core/server/app.py` (add inside `create_app`)
- Tests: `tests/unit/server/test_app.py`

**New utility helper:**
- Implementation: `src/eq_chatbot_core/utils/<name>.py`
- If it requires an optional dep, add a new extra in `pyproject.toml`

## Special Directories

**`src/` (src-layout):**
- Purpose: Prevents accidental import of uninstalled package from repo root
- Generated: No
- Committed: Yes

**`dist/`:**
- Purpose: Built wheel/sdist artifacts
- Generated: Yes (`python -m build`)
- Committed: No (in `.gitignore`)

**`htmlcov/`:**
- Purpose: pytest-cov HTML coverage report
- Generated: Yes
- Committed: No

**`.mypy_cache/`:**
- Purpose: mypy incremental analysis cache
- Generated: Yes
- Committed: No

**`.planning/codebase/`:**
- Purpose: GSD codebase analysis documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: By GSD mapping commands
- Committed: Yes (part of planning artifacts)

---

*Structure analysis: 2026-05-11*
