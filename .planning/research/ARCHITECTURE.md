# Architecture Patterns — Realtime Voice Integration

**Domain:** Library subpackage integration (WebSocket/async realtime onto sync HTTP library)
**Researched:** 2026-05-24
**Confidence:** HIGH (based on direct source inspection of both codebases)

---

## Recommended Architecture

### System Diagram — After v1.8.0

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         Entry Points                                 │
│  CLI  ·  HTTP Sidecar  ·  Library import                            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
             ┌───────────────┴───────────────┐
             ▼                               ▼
┌────────────────────────┐    ┌──────────────────────────────────────┐
│   providers/ (SYNC)    │    │       realtime/  (ASYNC)             │
│                        │    │                                      │
│  get_provider() ──►    │    │  get_realtime_provider() ──►         │
│  BaseLLMProvider (ABC) │    │  RealtimeProvider (ABC, 4 methods)   │
│  8 concrete adapters   │    │  RealtimeAdapterContract (Protocol)  │
│  HTTP chat/stream      │    │  BaseRealtimeWebsocketClient         │
│                        │    │  ├── OpenAIRealtimeClient            │
│                        │    │  ├── GeminiLiveClient                │
│                        │    │  └── NovaSonicStub (ABC conformance) │
└────────────────────────┘    └──────────────────────────────────────┘
             │                               │
             └───────────────┬───────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Shared types (NEW in 1.8.0)                       │
│  ToolDefinition   (providers/tools.py)                              │
│  NormalizedRealtimeEvent + NormalizedRealtimeEventTypes             │
│  RealtimeProviderCapabilities                                       │
│  Audio constants  INPUT_AUDIO_SAMPLE_RATE                           │
└─────────────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Supporting Subsystems (unchanged)                       │
│  rag/  ·  security/  ·  services/  ·  mcp/  ·  server/  ·  cli.py  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Q1 — Module structure

**Recommendation: `src/eq_chatbot_core/realtime/` as a top-level sibling of `providers/`.**

Rationale:

- Realtime is architecturally peer-level to `providers/`, not a sub-feature of it. Both are "LLM transport adapters" but they differ on every axis: sync vs async, HTTP vs WebSocket, stateless vs stateful, request/response vs bidirectional stream.
- A sub-namespace (`providers/realtime/`) would imply realtime providers implement `BaseLLMProvider`, which they do not. Mixing the two ABCs under one namespace creates confusion.
- Top-level placement mirrors the convention used for `rag/`, `security/`, `mcp/` — each a distinct capability domain.
- The `[realtime]` optional extra maps cleanly to one import path: `from eq_chatbot_core.realtime import ...`.

**Resulting directory tree (NEW files marked `+`):**

```
src/eq_chatbot_core/
├── providers/
│   ├── __init__.py            MODIFIED — export ToolDefinition, CLOUD_PROVIDERS, LOCAL_PROVIDERS
│   ├── base.py                MODIFIED — add ToolDefinition dataclass
│   └── ...                   (unchanged)
├── realtime/                  + NEW package
│   ├── __init__.py            + NEW — top-level re-exports
│   ├── contracts.py           + NEW — RealtimeAdapterContract Protocol, NormalizedRealtimeEvent*,
│   │                                   RealtimeProviderCapabilities, INPUT_AUDIO_SAMPLE_RATE
│   ├── abc.py                 + NEW — RealtimeProvider minimal ABC (4 abstract methods)
│   ├── websocket_client.py    + NEW — BaseRealtimeWebsocketClient + error hierarchy
│   ├── factory.py             + NEW — get_realtime_provider(), RealtimeProviderRegistry,
│   │                                   RealtimeProviderDefinition, build_default_registry()
│   ├── mock.py                + NEW — MockRealtimeProvider (queue-backed, no network)
│   └── providers/             + NEW sub-package
│       ├── __init__.py        + NEW
│       ├── openai.py          + NEW — OpenAIRealtimeClient, OpenAIRealtimeConfig, capabilities
│       ├── gemini_live.py     + NEW — GeminiLiveClient, GeminiLiveConfig, capabilities
│       └── nova.py            + NEW — NovaSonicStub (ABC conformance only, raises NotImplemented)
├── server/
│   └── app.py                 MODIFIED — sidecar stays HTTP-only (see Q6)
├── cli.py                     MODIFIED — add `realtime-test` command (see Q7)
└── __init__.py                MODIFIED — re-export ToolDefinition, realtime lazy-import guard
```

---

## Q2 — ABC and Protocol layout

**Ship both as specified in the handoff, in separate files.**

### `realtime/contracts.py` — the rich Protocol

Contains:
- `NormalizedRealtimeEventTypes` (class with 12 string constants)
- `NormalizedRealtimeEvent` (TypedDict)
- `NormalizedRealtimeEventStream` (type alias: `AsyncIterator[NormalizedRealtimeEvent]`)
- `RealtimeProviderCapabilities` (frozen dataclass)
- `RealtimeLifecycleAdapter` (Protocol — 9 async methods)
- `RealtimeEventIterator` (Protocol — `iter_normalized_events()`)
- `RealtimeAdapterContract(RealtimeLifecycleAdapter, RealtimeEventIterator, Protocol)` — composition
- `INPUT_AUDIO_SAMPLE_RATE: int = 24_000`
- `ToolDefinition` import from `providers.base` (re-export, not redefined — see Q5)

The `EnvelopeSender` / `BinarySender` callables from the GlassAgents source are **NOT ported** — those are bridge-layer internals that stay in GlassAgents.

### `realtime/abc.py` — the minimal ABC

Contains:
- `RealtimeProvider(ABC)` with exactly 4 abstract methods:
  - `async connect(self) -> None`
  - `async send_audio(self, chunk: bytes) -> None`
  - `async send_tool_result(self, call_id: str, result: str) -> None`
  - `def iter_events(self) -> AsyncIterator[RealtimeEvent]`
- `close()` as a non-abstract default no-op
- `RealtimeEvent` union (7 frozen dataclass types: SessionStartedEvent, AudioDeltaEvent, TranscriptDeltaEvent, ToolCallEvent, InterruptedEvent, SessionEndedEvent, ErrorEvent)

**Compatibility between ABC and Protocol:**

The ABC is intentionally simpler than the Protocol. The ABC is for:
- Stubs and mock providers (can inherit from it)
- Simple test implementations
- Nova Sonic stub (extends ABC, not Protocol)

The Protocol is for:
- Bridge/relay code in consuming apps (GlassAgents `IOSRealtimeBridge`)
- Type annotations in application code that needs the full 11-method surface

Concrete production providers (`OpenAIRealtimeClient`, `GeminiLiveClient`) implement the **Protocol** surface (11 methods) and thus satisfy both via duck-typing. They do NOT inherit from `RealtimeProvider(ABC)` — they implement the Protocol structurally. This is the same relationship as Python's `typing.Protocol` + runtime conformance check via `isinstance(obj, RealtimeAdapterContract)` with `runtime_checkable` decorator.

**Decision:** Mark `RealtimeAdapterContract` as `@runtime_checkable`. Do NOT add ABC inheritance to concrete providers — the Protocol check at factory time is sufficient.

```python
# contracts.py
@runtime_checkable
class RealtimeAdapterContract(RealtimeLifecycleAdapter, RealtimeEventIterator, Protocol):
    pass
```

```python
# factory.py  — verify conformance at registration time
if not isinstance(instance, RealtimeAdapterContract):
    raise TypeError(f"{type(instance).__name__} does not satisfy RealtimeAdapterContract")
```

---

## Q3 — Sync vs Async: The Core Decision

**Recommendation: Realtime is fully async. No sync wrapper shipped in the library.**

### Reasoning

The existing `providers/` sync decision was made because:
1. HTTP chat completion is short-lived (one request, one response)
2. Sync is simpler for Odoo (gevent-based) and script consumers
3. `asyncio.to_thread()` is a one-liner when needed

Realtime WebSocket sessions are fundamentally different:
1. A session lasts minutes to hours (open connection)
2. Audio arrives continuously — a sync wrapper would require a background thread and a queue anyway (more complexity, not less)
3. The primary consumer (GlassAgents Swift backend) is already async (FastAPI + asyncio event loop)
4. A "sync wrapper around async" pattern for WebSockets would require `anyio.from_thread.run_sync()` or a persistent `asyncio.run()` call — this is leaky, error-prone, and defeats the purpose of an async protocol

**Consumer impact table:**

| Consumer | Their async situation | What they do |
|---|---|---|
| GlassAgents FastAPI backend | Fully async | `await provider.connect()` natively |
| fr-designer Avalonia/.NET | Uses HTTP sidecar | HTTP sidecar not extended to realtime in 1.8.0 (see Q6) |
| sysReporter Rust | Uses CLI JSON I/O | CLI `realtime-test` uses `asyncio.run()` internally |
| Odoo eq_chatbot module | Sync WSGI/gevent | NOT a realtime consumer — stays on chat providers |
| Unit tests | pytest | `pytest-asyncio` or `asyncio.run()` in test helpers |

**If a consumer needs sync access to realtime:** wrap with `asyncio.run()` for one-shot calls, or manage their own event loop with `asyncio.get_event_loop().run_until_complete()`. The library does not provide this wrapper — it would be misleading for a long-lived connection.

**Implementation pattern for async-native providers:**

```python
# Correct — provider is fully async
async with await get_realtime_provider("openai", api_key="sk-...") as provider:
    await provider.connect()
    await provider.initialize_session(instructions="You are helpful.")
    await provider.append_client_audio(pcm16_bytes)
    async for event in provider.iter_normalized_events():
        if event["type"] == NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA:
            yield event["payload"]["audio"]
```

---

## Q4 — Factory pattern

**Recommendation: Expose BOTH `get_realtime_provider()` AND `RealtimeProviderRegistry`, but make `get_realtime_provider()` the primary public API.**

### `get_realtime_provider()` — mirrors `get_provider()`

```python
# realtime/factory.py

def get_realtime_provider(
    provider_name: str,
    *,
    api_key: str | None = None,
    **kwargs: Any,
) -> RealtimeAdapterContract:
    """
    Factory function to get a realtime voice provider.
    
    Args:
        provider_name: One of "openai", "gemini_live", "nova_sonic", "mock"
        api_key: Provider API key
        **kwargs: Provider-specific config (model, voice, instructions, ...)
    
    Returns:
        Provider instance satisfying RealtimeAdapterContract
    
    Raises:
        ValueError: If provider_name is unrecognized
        ImportError: If [realtime] extra is not installed
    """
    registry = _get_default_registry()
    return registry.build(provider_name, api_key=api_key, **kwargs)
```

The `get_realtime_provider()` function wraps the registry to provide a familiar one-liner for the common case. It uses a module-level `_default_registry` created lazily on first call (the registry itself is stateless — it just holds factory callables, no connections).

`RealtimeProviderRegistry` is also exported for consumers that need to register custom providers or override defaults without touching the module default.

**Note on GlassAgents factory divergence:** The GlassAgents `RealtimeProviderFactory` (in `factory.py`) takes a `Settings` object and builds `BridgeBinding` objects — that's application-layer composition, not provider instantiation. The library factory is simpler: it returns the provider object directly. GlassAgents will build its own factory on top of the library's `get_realtime_provider()` at the app layer.

**Per-provider config dataclasses** (frozen, slots, framework-neutral):

```python
@dataclass(frozen=True, slots=True)
class OpenAIRealtimeConfig:
    api_key: str
    model: str = "gpt-4o-realtime-preview"
    voice: str = "ash"
    instructions: str | None = None
    include_turn_detection: bool = True

@dataclass(frozen=True, slots=True)
class GeminiLiveConfig:
    api_key: str
    model: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    base_url: str | None = None
    endpoint: str | None = None
```

Config dataclasses live in their respective provider files (`providers/openai.py`, `providers/gemini_live.py`) — NOT in a shared config module. This keeps each provider self-contained and avoids a fat shared config file.

---

## Q5 — ToolDefinition reuse and migration path

**Recommendation: Define `ToolDefinition` once in `providers/base.py` and import it into `realtime/contracts.py`.**

### Current state

The existing library has NO `ToolDefinition` dataclass. Chat providers accept raw `dict` tools:
- `BaseLLMProvider.chat_completion(..., tools: list[dict] | None = None)`
- `LLMResponse.tool_calls: list[dict[str, Any]]`

### New definition (in `providers/base.py`)

```python
@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Typed tool/function definition shared by chat and realtime providers."""
    name: str
    description: str
    parameters: dict[str, Any]   # JSON Schema dict
    strict: bool = False
```

### Migration path for existing chat callers

**Phase 1 (v1.8.0 — non-breaking):** Add `ToolDefinition` to `providers/base.py` and `providers/__init__.py` exports. Update `BaseLLMProvider.chat_completion` signature to accept `list[ToolDefinition] | list[dict] | None` — a union type. All existing callers passing raw dicts continue to work unchanged.

```python
# base.py — backward-compatible union
def chat_completion(
    self,
    messages: list[dict[str, Any]],
    ...
    tools: list["ToolDefinition"] | list[dict[str, Any]] | None = None,
) -> LLMResponse:
```

Internally, providers convert `ToolDefinition` → `dict` at the SDK boundary (a 5-line helper). The dict path stays identical.

**Phase 2 (v1.9.0 — deprecation):** Emit a `DeprecationWarning` when `tools` is `list[dict]`. Docstring says "use ToolDefinition".

**Phase 3 (v2.0.0 — breaking):** Remove `list[dict]` from the union. All callers on `ToolDefinition`.

**Import path for `realtime/contracts.py`:**
```python
from eq_chatbot_core.providers.base import ToolDefinition
```

This means `ToolDefinition` is always available without the `[realtime]` extra — it lives in `providers/`, which is core. Correct: chat tool callers should not need `[realtime]` just to get a typed tool definition.

**Roadmap implication:** "ToolDefinition migration" is NOT its own phase. It is part of the contracts phase (the first realtime build step). The migration is non-breaking and low-risk: add the dataclass, update the type hint, done.

---

## Q6 — HTTP sidecar (`[server]` extra)

**Decision: Realtime is OUT OF SCOPE for the sidecar in v1.8.0. Explicit deferral to v1.9.0.**

### Reasoning

The HTTP sidecar is designed for request/response patterns (POST → JSON or POST → SSE stream). Realtime voice is a long-lived bidirectional WebSocket. Bridging realtime through the sidecar would require:

1. A WebSocket relay endpoint (`/realtime/ws` or `/realtime/connect`)
2. Audio binary framing over WebSocket (not SSE — SSE is text-only)
3. Lifecycle management (connect → session → close) scoped to a WebSocket connection
4. Per-connection state (which is the anti-pattern the library explicitly avoids)

For fr-designer (Avalonia/.NET) and sysReporter (Rust) to use realtime, the correct path at v1.9.0 would be a WebSocket relay endpoint added to `server/app.py`. That relay would:
- Accept a WebSocket from the external consumer
- Instantiate a `RealtimeAdapterContract` provider internally  
- Proxy normalized events back over the consumer WebSocket

**v1.8.0 explicit scope boundary:**
- `server/app.py` is NOT modified for realtime
- No new `/realtime/*` endpoints exist in v1.8.0
- Documentation notes: "Realtime via sidecar: planned for v1.9.0"

**Existing sidecar callers (fr-designer, sysReporter) are unaffected by v1.8.0.**

---

## Q7 — CLI exposure

**Recommendation: Yes, add `eq-chatbot realtime-test` as a smoke-test command in `cli.py`.**

### Why

- Developer ergonomics: verify a realtime provider key and connection work before wiring into an app
- Mirrors `eq-chatbot test-provider` for chat providers — symmetry makes the tool discoverable
- The command is simple: connect → send a tiny audio frame → wait for `session.ready` → disconnect → print result

### Interface

```bash
eq-chatbot realtime-test -p openai -k sk-...
eq-chatbot realtime-test -p gemini_live -k AIza...
eq-chatbot realtime-test -p mock          # no key needed
```

### Implementation notes

- The Click command uses `asyncio.run()` internally (since the provider is async). This is the one place in the library where `asyncio.run()` appears — isolated inside the CLI command function.
- Gated behind `[realtime]` extra: if missing, raises a user-friendly `ImportError` message (`"Install eq-chatbot-core[realtime] to use realtime providers"`).
- `REALTIME_PROVIDERS` list in `cli.py` mirrors the registry names: `["openai", "gemini_live", "nova_sonic", "mock"]`.

**Existing file modification: `cli.py`** — add one new `@main.command("realtime-test")` block (~50 lines). Also export `REALTIME_PROVIDERS` constant from the same file (alongside the already-present `CLOUD_PROVIDERS`/`LOCAL_PROVIDERS`).

---

## Q8 — Mock provider location

**Recommendation: `realtime/mock.py` — not in `tests/`.**

### Reasoning

- The mock is a **library-provided** in-process provider, not a test fixture. It ships in the installed package so that consumers (`GlassAgents`, `fr-designer` backends) can use it in THEIR test suites without depending on the library's internal `tests/` directory.
- This mirrors the pattern: `tests/fixtures/` are for the library's own test utilities; re-exported library components belong in `src/`.
- Handoff §7 criterion 11 explicitly says "In-process mock provider for integration tests in consumers."

### Implementation

```python
# realtime/mock.py

class MockRealtimeProvider:
    """Queue-backed in-process provider. No network, no latency.
    
    Usage in consumer tests:
        provider = MockRealtimeProvider()
        provider.enqueue_event({"type": "session.ready", "payload": {}})
        await provider.connect()
        async for event in provider.iter_normalized_events():
            ...  # events come from the queue
    """
```

The mock satisfies `RealtimeAdapterContract` structurally (Protocol check passes). It does NOT inherit from `RealtimeProvider(ABC)` — it's not a stub, it's a full in-process implementation.

**Exported from `realtime/__init__.py`** so consumers can do:
```python
from eq_chatbot_core.realtime import MockRealtimeProvider
```

The mock is available **without** the `[realtime]` extra (no WebSocket deps needed). This is important: consumers that use the mock in CI don't need the full `[realtime]` install. Implement the mock using only `asyncio.Queue` and `collections.deque` — stdlib only.

---

## Q9 — Connection lifecycle

**Recommended pattern: async context manager as primary interface, explicit open/close as fallback.**

```python
# Primary: async context manager (recommended)
async with await get_realtime_provider("openai", api_key="sk-...") as provider:
    await provider.initialize_session(instructions="You are a voice assistant.")
    await provider.append_client_audio(pcm_bytes)
    async for event in provider.iter_normalized_events():
        handle(event)
# provider.close() called automatically on exit

# Fallback: explicit lifecycle (when context manager doesn't fit caller structure)
provider = get_realtime_provider("openai", api_key="sk-...")
await provider.connect()
try:
    await provider.initialize_session(...)
    ...
finally:
    await provider.close()
```

### Implementation in `BaseRealtimeWebsocketClient`

Add `__aenter__` / `__aexit__` to `BaseRealtimeWebsocketClient`:

```python
async def __aenter__(self) -> "BaseRealtimeWebsocketClient":
    await self.connect()
    return self

async def __aexit__(self, *_: Any) -> None:
    await self.close()
```

**`get_realtime_provider()` returns an object** (not a coroutine). The `await` in `async with await ...` is unnecessary — `get_realtime_provider()` is a plain synchronous function that returns an already-constructed provider (just like `get_provider()`). The pattern should be:

```python
async with get_realtime_provider("openai", api_key="sk-...") as provider:
    ...
```

### Lifecycle state machine

```
DISCONNECTED ──► connect() ──► CONNECTED
                                   │
                          initialize_session()
                                   │
                               ACTIVE
                              /        \
                  append_audio()      iter_normalized_events()
                              \        /
                               ACTIVE
                                   │
                              close()
                                   │
                            DISCONNECTED
```

**Per-call instantiation vs reuse:** Unlike chat providers (which are per-request in the sidecar), realtime providers MUST be reused across the lifetime of a session. Each `connect()` → `close()` cycle is one session. Applications manage this lifetime — the library makes no assumption about how long a provider lives.

**Connection state guard:** `BaseRealtimeWebsocketClient.connect()` is idempotent — calling it on an already-connected instance returns immediately (`if self.is_connected: return`).

---

## Q10 — Anti-patterns NOT to replicate

From CONCERNS.md, these active problems must not be reproduced in `realtime/`:

### Anti-pattern 1: Sync I/O in async handlers (CRITICAL — must not repeat)

The existing sidecar runs `provider.chat_completion()` directly in `async def` FastAPI handlers, blocking the event loop. Realtime is async-native — this problem does not arise. But: if a future `realtime-test` CLI command calls `asyncio.run()`, wrap it correctly as a single top-level call, never nested.

**Rule for realtime:** All WebSocket I/O uses `await`. Never call `websockets.connect()` synchronously. Never call `asyncio.run()` inside a provider method.

### Anti-pattern 2: Hardcoded provider name lists in multiple places

The existing library has `CLOUD_PROVIDERS` / `LOCAL_PROVIDERS` duplicated in `providers/__init__.py`, `server/app.py`, and `cli.py`. Realtime must not repeat this.

**Fix applied in v1.8.0:** Export `REALTIME_PROVIDERS` as a constant from `realtime/__init__.py`. The `cli.py` `realtime-test` command imports this constant — it does not hardcode provider names.

**Also fix the existing anti-pattern** as part of v1.8.0 cleanup: export `CLOUD_PROVIDERS` and `LOCAL_PROVIDERS` from `providers/__init__.py` and import them into `server/app.py` and `cli.py`. Three files to touch, zero behavior change.

### Anti-pattern 3: No async provider interface (CONCERNS.md — "Missing Critical Features")

Realtime resolves this for the realtime surface. Do NOT use the same "add async later" logic here. All realtime methods are async from day one.

### Anti-pattern 4: `sys.modules` mock leaks between test sessions

The library works around mock leaks by running unit and integration tests in separate pytest sessions. For realtime, follow the same isolation:
- `tests/unit/realtime/` — fully mocked, no network
- `tests/integration/realtime/` — requires real API keys + separate pytest session

### Anti-pattern 5: Missing `__all__` exports

Several existing modules export symbols inconsistently. Realtime submodules MUST define `__all__` in every `*.py` file and in `realtime/__init__.py`. This is the public API surface — be explicit.

### Anti-pattern 6: Partial-stream retry on error (from Anthropic stream retry concern)

The existing Anthropic `stream_completion` retries from the beginning if `OverloadedError` occurs mid-stream, silently yielding duplicate content. Realtime `iter_normalized_events()` must handle connection errors by raising, not by silently retrying from the start. Reconnect logic (if provided in `BaseRealtimeWebsocketClient`) must be explicit and documented — callers opt in.

---

## Component Boundaries — Complete Table

| Component | Status | Responsibility | File |
|---|---|---|---|
| `ToolDefinition` | NEW | Typed tool definition (chat + realtime shared) | `providers/base.py` |
| `CLOUD_PROVIDERS`, `LOCAL_PROVIDERS` | MODIFIED | Exported constants (fix hardcoded-list anti-pattern) | `providers/__init__.py` |
| `RealtimeAdapterContract` | NEW | Rich Protocol (11-method full surface) | `realtime/contracts.py` |
| `NormalizedRealtimeEventTypes` | NEW | 12 event type string constants | `realtime/contracts.py` |
| `NormalizedRealtimeEvent` | NEW | TypedDict event envelope | `realtime/contracts.py` |
| `RealtimeProviderCapabilities` | NEW | Per-provider feature flags | `realtime/contracts.py` |
| `INPUT_AUDIO_SAMPLE_RATE` | NEW | PCM16 mono sample rate constant (24000) | `realtime/contracts.py` |
| `RealtimeProvider` | NEW | Minimal ABC (4 methods + typed events) | `realtime/abc.py` |
| `RealtimeEvent` union + typed events | NEW | 7 frozen dataclass event types | `realtime/abc.py` |
| `BaseRealtimeWebsocketClient` | NEW | WS connect/send/recv/close + error hierarchy | `realtime/websocket_client.py` |
| `RealtimeProviderRegistry` | NEW | Registry: register, resolve, build | `realtime/factory.py` |
| `RealtimeProviderDefinition` | NEW | Name + factory callable + capabilities | `realtime/factory.py` |
| `get_realtime_provider()` | NEW | Public factory function | `realtime/factory.py` |
| `build_default_realtime_provider_registry()` | NEW | Pre-populated registry | `realtime/factory.py` |
| `OpenAIRealtimeClient` | NEW | Production OpenAI Realtime adapter | `realtime/providers/openai.py` |
| `OpenAIRealtimeConfig` | NEW | Typed config for OpenAI | `realtime/providers/openai.py` |
| `OPENAI_REALTIME_CAPABILITIES` | NEW | Frozen capabilities constant | `realtime/providers/openai.py` |
| `GeminiLiveClient` | NEW | Production Gemini Live adapter | `realtime/providers/gemini_live.py` |
| `GeminiLiveConfig` | NEW | Typed config for Gemini Live | `realtime/providers/gemini_live.py` |
| `GEMINI_LIVE_REALTIME_CAPABILITIES` | NEW | Frozen capabilities constant | `realtime/providers/gemini_live.py` |
| `NovaSonicStub` | NEW | ABC-conformant stub, raises NotImplemented | `realtime/providers/nova.py` |
| `MockRealtimeProvider` | NEW | Queue-backed in-process provider for tests | `realtime/mock.py` |
| `cli.py` `realtime-test` | MODIFIED | Smoke-test CLI command | `cli.py` |
| `server/app.py` | NOT MODIFIED | HTTP sidecar — realtime deferred to v1.9.0 | `server/app.py` |

---

## Data Flow — Realtime Session

```
get_realtime_provider("openai", api_key=...)  [factory.py]
    └── builds OpenAIRealtimeConfig
    └── instantiates OpenAIRealtimeClient(config)

provider.connect()                             [websocket_client.py]
    └── BaseRealtimeWebsocketClient.connect()
    └── websockets.connect(wss://api.openai.com/v1/realtime?model=...)
    └── _connection_headers() → {"Authorization": "Bearer sk-...", "openai-beta": "realtime=v1"}
    └── self._ws assigned

provider.initialize_session(instructions=..., tools=[ToolDefinition(...)])   [providers/openai.py]
    └── sends "session.update" event via send_json()
    └── registers tools (serialized ToolDefinition → dict)

provider.append_client_audio(pcm16_bytes)     [providers/openai.py]
    └── base64-encodes bytes
    └── sends "input_audio_buffer.append" event

async for event in provider.iter_normalized_events():  [providers/openai.py]
    └── receives raw ws frames via recv_json()
    └── maps provider-native event type → NormalizedRealtimeEventTypes constant
    └── yields NormalizedRealtimeEvent TypedDict

provider.close()                              [websocket_client.py]
    └── BaseRealtimeWebsocketClient.close()
    └── ws.close()
    └── self._ws = None
```

---

## Build Order (Phase Dependencies)

This is the critical sequencing for the roadmap. Each step must land before the next.

### Foundation (must land first — everything else depends on it)

1. **`ToolDefinition` in `providers/base.py`** — shared type needed by contracts
2. **`realtime/contracts.py`** — event schema, capabilities, Protocol definition
3. **`realtime/abc.py`** — minimal ABC with typed event union
4. **`realtime/websocket_client.py`** — base WS client + error hierarchy

### Core factory (depends on foundation)

5. **`realtime/factory.py`** — registry + `get_realtime_provider()` + empty default registry
6. **`realtime/__init__.py`** — re-export all public symbols, lazy import guard

### Providers (depend on foundation + factory, can develop in parallel)

7a. **`realtime/providers/openai.py`** — OpenAI Realtime client (391 LOC port)
7b. **`realtime/providers/gemini_live.py`** — Gemini Live client (919 LOC port)
7c. **`realtime/providers/nova.py`** — Nova Sonic stub (trivial, <30 LOC)

### Quality / DX layer (depends on providers)

8. **`realtime/mock.py`** — MockRealtimeProvider (depends on contracts)
9. **`cli.py` realtime-test command** — depends on factory
10. **Unit tests** — can be written alongside providers (TDD preferred)

### Existing file modifications (can happen alongside foundation)

- `providers/__init__.py` — export `ToolDefinition`, `CLOUD_PROVIDERS`, `LOCAL_PROVIDERS`
- `cli.py` — import `CLOUD_PROVIDERS`/`LOCAL_PROVIDERS` from providers (fix anti-pattern)
- `server/app.py` — import `CLOUD_PROVIDERS`/`LOCAL_PROVIDERS` from providers (fix anti-pattern)
- `pyproject.toml` — add `[realtime]` optional extra: `websockets>=12.0,<14.0`

**Roadmap phase boundary:** "ToolDefinition migration" is NOT its own phase. It is the first commit of the "contracts" phase — it takes ~30 minutes and is non-breaking. The roadmap should group it with contracts (Phase 1 of the realtime milestone), not in isolation.

---

## Scalability Considerations

| Concern | Current state | With realtime |
|---|---|---|
| Connection pooling | N/A (stateless HTTP) | Each `connect()` opens one WS; provider instance = one session |
| Per-request instantiation | Sidecar creates one per request | Realtime providers MUST be reused; don't create per-audio-chunk |
| Thread safety | Providers are single-threaded | WS providers are single-task; do not share across asyncio tasks |
| Memory | Stateless, no accumulation | Audio buffers in flight — callers manage accumulation |

---

## Existing Modules That Must Be Touched

**MUST modify:**
1. `src/eq_chatbot_core/providers/base.py` — add `ToolDefinition` dataclass
2. `src/eq_chatbot_core/providers/__init__.py` — export `ToolDefinition`, `CLOUD_PROVIDERS`, `LOCAL_PROVIDERS`
3. `src/eq_chatbot_core/cli.py` — add `realtime-test` command, import `REALTIME_PROVIDERS`
4. `pyproject.toml` — add `[realtime]` extra dependency group, bump version to `1.8.0`

**SHOULD modify (fix existing anti-pattern):**
5. `src/eq_chatbot_core/server/app.py` — replace hardcoded `_CLOUD_PROVIDERS` / `_LOCAL_PROVIDERS` with imports from `providers/__init__.py`
6. `src/eq_chatbot_core/cli.py` — replace hardcoded `CLOUD_PROVIDERS` / `LOCAL_PROVIDERS` with imports (same lines, just sourced differently)

**Must NOT touch:**
- `server/app.py` — no realtime endpoints (deferred v1.9.0)
- Any existing provider file — `ToolDefinition` addition to `base.py` is non-breaking

---

## Sources

- `/Users/picard/gitbase/GlassAgents/docs/eq-chatbot-core-realtime-handoff.md` (handoff spec)
- `/Users/picard/gitbase/GlassAgents/backend/realtime/abc.py` (137 LOC — minimal ABC reference)
- `/Users/picard/gitbase/GlassAgents/backend/realtime/contracts.py` (101 LOC — Protocol + event schema reference)
- `/Users/picard/gitbase/GlassAgents/backend/realtime/factory.py` (177 LOC — registry reference)
- `/Users/picard/gitbase/GlassAgents/backend/realtime/websocket_client.py` (174 LOC — WS base reference)
- `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/.planning/codebase/ARCHITECTURE.md` (existing arch)
- `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/.planning/codebase/CONCERNS.md` (existing anti-patterns)
- `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/src/eq_chatbot_core/providers/__init__.py` (factory source)
- `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/src/eq_chatbot_core/providers/base.py` (ABC source)
- `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/src/eq_chatbot_core/server/app.py` (sidecar source)
- `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/src/eq_chatbot_core/cli.py` (CLI source)

---

*Architecture research: 2026-05-24*
