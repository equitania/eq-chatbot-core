<!-- refreshed: 2026-05-11 -->
# Architecture

**Analysis Date:** 2026-05-11

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│                         Entry Points                                  │
│  CLI (`src/eq_chatbot_core/cli.py`)                                  │
│  HTTP Sidecar (`src/eq_chatbot_core/server/app.py`)                  │
│  Library import (`src/eq_chatbot_core/__init__.py`)                  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      Provider Layer                                   │
│  `src/eq_chatbot_core/providers/`                                    │
│                                                                      │
│  get_provider() factory  ──►  BaseLLMProvider (ABC)                  │
│                               ├── OpenAIProvider                     │
│                               ├── AnthropicProvider                  │
│                               ├── AzureProvider                      │
│                               ├── VertexProvider                     │
│                               ├── LangDockProvider                   │
│                               ├── OpenRouterProvider                 │
│                               ├── MammouthProvider                   │
│                               └── LocalLLMProvider                   │
└──────┬───────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Supporting Subsystems                              │
│                                                                      │
│  RAG            Security          Services         Utils             │
│  `rag/`         `security/`       `services/`      `utils/`          │
│  ├── chunker    ├── encryption    ├── cost_service  ├── pricing       │
│  ├── embedder   ├── injection     ├── error_handler └── pdf           │
│  ├── retriever  ├── rate_limit    └── knowledge_svc                  │
│  └── ctx_mgr   └── file_validator                                    │
│                                                                      │
│  MCP Client                                                          │
│  `mcp/client.py`                                                     │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    External APIs / Services                           │
│  OpenAI · Anthropic · Azure AI Foundry · Google Vertex · LangDock   │
│  OpenRouter · Mammouth · LM Studio · Ollama · Qdrant                 │
└──────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `get_provider` | Factory: name → concrete provider instance | `src/eq_chatbot_core/providers/__init__.py` |
| `BaseLLMProvider` | Abstract contract for all providers | `src/eq_chatbot_core/providers/base.py` |
| `LLMResponse` | Unified completion response dataclass | `src/eq_chatbot_core/providers/base.py` |
| `StreamChunk` | Streaming delta dataclass | `src/eq_chatbot_core/providers/base.py` |
| `ModelInfo` | Model metadata dataclass | `src/eq_chatbot_core/providers/base.py` |
| `TemperatureConstraints` | Provider-specific temp validation | `src/eq_chatbot_core/providers/temperature_constraints.py` |
| `ContextWindowManager` | Token budget allocation across history/RAG/response | `src/eq_chatbot_core/rag/context_manager.py` |
| `TextChunker` | Splits documents for RAG ingestion | `src/eq_chatbot_core/rag/chunker.py` |
| `Embedder` | Generates embeddings via OpenAI or local models | `src/eq_chatbot_core/rag/embedder.py` |
| `QdrantRetriever` | Vector similarity search against Qdrant | `src/eq_chatbot_core/rag/retriever.py` |
| `FernetEncryption` | At-rest API key encryption | `src/eq_chatbot_core/security/encryption.py` |
| `InjectionDetector` | Prompt injection pattern detection | `src/eq_chatbot_core/security/injection.py` |
| `TokenBucketRateLimiter` | Per-provider request rate limiting | `src/eq_chatbot_core/security/rate_limit.py` |
| `FileValidator` | MIME-type upload validation (optional dep) | `src/eq_chatbot_core/security/file_validator.py` |
| `CostService` | Token cost calculation per model | `src/eq_chatbot_core/services/cost_service.py` |
| `ErrorHandler` | Categorized error recovery with fallback | `src/eq_chatbot_core/services/error_handler.py` |
| `KnowledgeService` | Knowledge export pipeline for vector DBs | `src/eq_chatbot_core/services/knowledge_service.py` |
| `MCPClient` | MCP protocol client (HTTP/SSE + stdio) | `src/eq_chatbot_core/mcp/client.py` |
| FastAPI app | HTTP sidecar gateway for cross-language use | `src/eq_chatbot_core/server/app.py` |
| `BearerTokenMiddleware` | Auth guard for all non-health endpoints | `src/eq_chatbot_core/server/auth.py` |
| Click CLI (`eq-chatbot`) | test-provider, list-models, chat, serve, info | `src/eq_chatbot_core/cli.py` |

## Pattern Overview

**Overall:** Provider Factory + Adapter + Sidecar Gateway

**Key Characteristics:**
- Single `get_provider(name, api_key, **kwargs)` factory is the sole entry point to any LLM backend; consumers never instantiate provider classes directly.
- All providers share the same 3-method interface (`chat_completion`, `stream_completion`, `list_models`) — swapping providers requires no caller changes.
- The `server/` subsystem re-exposes the same provider interface over HTTP/SSE, enabling non-Python callers (e.g., C# Avalonia desktop apps) to use any provider as a localhost sidecar.
- Optional extras (`[azure]`, `[vertex]`, `[pdf]`, `[security]`, `[server]`, `[local]`) gate heavy dependencies; core install is lightweight.

## Layers

**Provider Layer:**
- Purpose: Normalize diverse LLM SDKs into a single interface
- Location: `src/eq_chatbot_core/providers/`
- Contains: `BaseLLMProvider` ABC, 8 concrete adapters, response dataclasses, exception hierarchy, `get_provider` factory
- Depends on: External LLM SDKs (openai, anthropic, azure-ai-inference, google-genai, httpx)
- Used by: CLI, server, RAG pipeline, direct library consumers

**RAG Layer:**
- Purpose: Retrieval-Augmented Generation pipeline
- Location: `src/eq_chatbot_core/rag/`
- Contains: Chunker, embedder, Qdrant retriever, context window manager
- Depends on: Provider layer (embeddings), qdrant-client, tiktoken
- Used by: Application-level integrations; not used by server/CLI internally

**Security Layer:**
- Purpose: Cross-cutting protection for API keys, inputs, uploads, and rate control
- Location: `src/eq_chatbot_core/security/`
- Contains: Fernet encryption, injection detector, token bucket rate limiter, file validator
- Depends on: cryptography, puremagic (optional), tiktoken
- Used by: Application-level integrations; not wired into provider layer itself

**Services Layer:**
- Purpose: Shared application services (cost tracking, error recovery, knowledge export)
- Location: `src/eq_chatbot_core/services/`
- Contains: CostService, ErrorHandler (with fallback logic), KnowledgeService
- Depends on: Provider layer, RAG layer
- Used by: Application-level integrations

**MCP Layer:**
- Purpose: Model Context Protocol client for tool integrations
- Location: `src/eq_chatbot_core/mcp/`
- Contains: HTTP/SSE and stdio transport client
- Depends on: httpx
- Used by: Application-level integrations

**Server Layer:**
- Purpose: Localhost HTTP gateway exposing provider interface to non-Python callers
- Location: `src/eq_chatbot_core/server/`
- Contains: FastAPI app factory, Pydantic schemas, BearerToken middleware, SSE streaming helper, lifecycle (uvicorn runner + parent-pid watchdog)
- Depends on: Provider layer, fastapi, uvicorn, sse-starlette (all optional `[server]` extras)
- Used by: `eq-chatbot serve` CLI command; spawned as a sidecar by external processes

**CLI Layer:**
- Purpose: Developer tooling and sidecar launcher
- Location: `src/eq_chatbot_core/cli.py`
- Contains: Click commands: `test-provider`, `list-models`, `chat` (JSON stdin/stdout), `serve`, `info`
- Depends on: Provider layer, server layer (for `serve`)

## Data Flow

### Library Usage (chat_completion)

1. Caller invokes `get_provider("openai", api_key="sk-...")` (`src/eq_chatbot_core/providers/__init__.py:41`)
2. Factory maps name to concrete class, instantiates with api_key/base_url/kwargs
3. Caller calls `provider.chat_completion(messages=[...])` (`src/eq_chatbot_core/providers/base.py:109`)
4. Provider adapter translates to SDK call, handles retries/exceptions
5. Returns `LLMResponse(content, model, input_tokens, output_tokens, tool_calls)` (`src/eq_chatbot_core/providers/base.py:12`)

### HTTP Sidecar (POST /chat)

1. External process spawns `eq-chatbot serve --auth-token-fd 0 --parent-pid <pid>` (`src/eq_chatbot_core/cli.py:478`)
2. Token read from fd, `create_app(auth_token)` builds FastAPI app (`src/eq_chatbot_core/server/app.py:60`)
3. `BearerTokenMiddleware` validates `Authorization: Bearer <token>` on all non-health requests (`src/eq_chatbot_core/server/auth.py`)
4. `POST /chat` receives `ChatRequest` Pydantic model (`src/eq_chatbot_core/server/models.py:36`)
5. `get_provider(req.provider, api_key=req.api_key, **req.provider_extra)` instantiated per-request
6. `provider.chat_completion(messages, model, temperature, ...)` called
7. Response serialized as `ChatResponse` JSON (`src/eq_chatbot_core/server/models.py:64`)

### HTTP Sidecar (POST /chat/stream)

Same as above through step 5, then:
6. `provider.stream_completion(...)` yields `StreamChunk` objects
7. `stream_chunk_to_sse_events()` translates chunks to SSE events (`src/eq_chatbot_core/server/streaming.py`)
8. `EventSourceResponse` streams to client

### CLI chat command (JSON stdin/stdout)

1. `eq-chatbot chat -p openai -k sk-...` reads JSON from stdin
2. Validates `messages` array structure (`src/eq_chatbot_core/cli.py:264`)
3. Calls `get_provider` + `chat_completion`
4. Writes JSON `{content, model, input_tokens, output_tokens}` to stdout

**State Management:**
- No global mutable state. Providers are stateless objects; each request instantiates a fresh provider instance (server layer) or reuses a caller-held instance (library usage).
- `app.state.start_time` is the only app-level state (uptime tracking).

## Key Abstractions

**`BaseLLMProvider`:**
- Purpose: Enforces the 3-method contract every backend must satisfy
- Location: `src/eq_chatbot_core/providers/base.py:68`
- Pattern: Abstract Base Class (ABC) with `@abstractmethod` on `chat_completion`, `stream_completion`, `list_models`, `provider_name`, `default_model`

**`LLMResponse` / `StreamChunk` / `ModelInfo`:**
- Purpose: Typed, provider-neutral response envelopes
- Location: `src/eq_chatbot_core/providers/base.py:11-212`
- Pattern: `@dataclass` with optional fields; `LLMResponse.total_tokens` is a computed property

**`ProviderError` hierarchy:**
- Purpose: Typed exception surfacing that allows callers to handle rate limits, auth failures, context overflows, and overload distinctly
- Location: `src/eq_chatbot_core/providers/base.py:213-250`
- Pattern: Single base with `status_code` and `retry_after` attributes; HTTP sidecar maps subclasses to specific HTTP status codes

**`ChatRequest` / `ChatResponse` (Pydantic):**
- Purpose: Wire-format validation for HTTP sidecar
- Location: `src/eq_chatbot_core/server/models.py`
- Pattern: Pydantic v2 `BaseModel`; `ChatMessage.cache_control` passes Anthropic prompt-caching hints through the wire

## Entry Points

**Library import:**
- Location: `src/eq_chatbot_core/__init__.py`
- Triggers: `import eq_chatbot_core` or `from eq_chatbot_core.providers import get_provider`
- Responsibilities: Exposes `__version__`; all provider symbols exported from `providers/__init__.py`

**CLI:**
- Location: `src/eq_chatbot_core/cli.py` — `main()` Click group
- Triggers: `eq-chatbot <command>` (installed via `[project.scripts]` in pyproject.toml)
- Commands: `test-provider`, `list-models`, `chat`, `serve`, `info`

**HTTP sidecar factory:**
- Location: `src/eq_chatbot_core/server/app.py:60` — `create_app(auth_token)`
- Triggers: Called by `eq-chatbot serve`; returns a FastAPI app bound to the token
- Endpoints: `GET /health`, `GET /providers`, `POST /models`, `POST /chat`, `POST /chat/stream`

## Architectural Constraints

- **No global state:** Provider instances are stateless; no module-level singletons beyond `app.state.start_time` in the running server.
- **Optional heavy deps:** `[azure]`, `[vertex]`, `[pdf]`, `[security]`, `[server]`, `[local]` extras gate imports. Missing extras raise `ImportError` at import time, not at install time.
- **Per-request provider instantiation (server):** `get_provider()` is called on every HTTP request in the sidecar. Instantiation is lightweight (no connection pool pre-warming), but no instance reuse across requests.
- **Sync-only provider interface:** `chat_completion` and `stream_completion` are synchronous. The FastAPI server runs them in the event loop without `run_in_executor`; blocking calls hold the event loop.
- **Hardcoded provider catalog in two places:** `server/app.py:48-57` and `cli.py:32-34` maintain static provider name lists that must be kept in sync with the factory dispatch table in `providers/__init__.py:97-113`.

## Anti-Patterns

### Duplicated provider name lists

**What happens:** Cloud/local provider name strings are hardcoded in `src/eq_chatbot_core/server/app.py:48-57` and `src/eq_chatbot_core/cli.py:32-34`, separately from the authoritative factory dict in `src/eq_chatbot_core/providers/__init__.py:97-113`.

**Why it's wrong:** Adding a new provider requires edits in three files; the server/CLI lists can silently drift from what `get_provider` actually supports.

**Do this instead:** Export `CLOUD_PROVIDERS` and `LOCAL_PROVIDERS` constants from `providers/__init__.py` and import them in `server/app.py` and `cli.py`.

### Sync I/O in async FastAPI handlers

**What happens:** `provider.chat_completion()` and `provider.stream_completion()` are synchronous blocking calls made directly inside `async def` FastAPI route handlers (`src/eq_chatbot_core/server/app.py:96-125`).

**Why it's wrong:** Long LLM calls block the entire uvicorn event loop, preventing other requests from being handled concurrently.

**Do this instead:** Wrap in `asyncio.to_thread()` or `anyio.to_thread.run_sync()` to offload blocking SDK calls to a thread pool.

## Error Handling

**Strategy:** Typed exception hierarchy from provider → HTTP status mapping in server; structured `ErrorResult` with user message in services layer.

**Patterns:**
- Provider adapters raise `ProviderError` subclasses with `provider`, `status_code`, `retry_after` fields
- `server/app.py:_provider_error_to_http()` maps subclasses to HTTP 401/429/413/503/502
- `server/app.py:_provider_error_to_json()` serializes errors as SSE error events for streaming
- `services/error_handler.py` provides `ErrorSeverity` / `ErrorCategory` enums and `ErrorResult` dataclass for application-level recovery logic
- CLI commands catch `ProviderError` and print to stderr with `sys.exit(1)`

## Cross-Cutting Concerns

**Logging:** Standard `logging.getLogger(__name__)` per module. No centralized log configuration; caller controls level/handler.

**Validation:** Pydantic v2 for HTTP server schemas. CLI chat validates message structure manually in `_validate_messages()`. Provider adapters do not validate message shapes (delegated to the SDK).

**Authentication:** Sidecar uses `BearerTokenMiddleware` with a token supplied at server startup via fd (recommended), argv, or env var. Per-request `api_key` is in the POST body (not headers) to avoid URL/log leakage.

---

*Architecture analysis: 2026-05-11*
