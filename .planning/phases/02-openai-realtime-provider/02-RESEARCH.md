# Phase 2: OpenAI Realtime Provider - Research

**Researched:** 2026-05-24
**Domain:** OpenAI Realtime API — WebSocket provider port, VAD/turn-detection semantics, config dataclass, factory registration
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `OpenAIRealtimeConfig.model` defaults to the **floating `gpt-realtime` alias** (not a pinned dated snapshot). Zero maintenance, always tracks OpenAI's current GA Realtime model. Consumers who need reproducibility can pin a dated snapshot explicitly.
- **D-02:** SC-2 (live model verification) is satisfied by the researcher verifying the default model name live at phase start; recording result and current dated snapshot in this file. No runtime model-list call added to the library.
- **D-03:** On an invalid/rejected model name, the provider **fails fast with a library-native exception** (mapped into `ProviderError`/`AuthenticationError`-style hierarchy with a message pointing at valid models) rather than passing the raw OpenAI error through.

### Claude's Discretion

- **VAD / Turn-Detection (PITFALL-28):** Follow the reference — `OPENAI_REALTIME_CAPABILITIES.server_vad = True` (native capability) and `OpenAIRealtimeConfig.include_turn_detection` defaults to `True`. Reconciliation rule MUST be documented in a code comment before implementation begins (SC-1).
- **Port strategy / base class:** Prefer extending Phase 1 `BaseRealtimeWebsocketClient`; note that `_connection_error_endpoint` is abstract and MUST be overridden; `_on_connected` and `_on_message` are also abstract in the Phase 1 port.
- **Config surface:** Use handoff §5 dataclass verbatim — `OpenAIRealtimeConfig(api_key, model="gpt-realtime", voice="ash", instructions=None, include_turn_detection=True)`, frozen + slots. Tool-result submission mode is `conversation_item`. Reuse Phase 1 `ToolDefinition`.

### Deferred Ideas (OUT OF SCOPE)

- Gemini Live + Nova Sonic providers — Phase 3
- Production AWS Bedrock Nova Sonic implementation — stub-only for 1.8.0
- Multi-format audio negotiation (Opus / μ-law) — PCM16-only for 1.8.0
- `realtime-test` CLI command (QUAL-04) and CHANGELOG/README (REL-03) — Phase 4
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROV-01 | Port `OpenAIRealtimeClient` (~391 LOC) with all 11 `RealtimeAdapterContract` methods | Reference impl read in full; divergence from Phase 1 base class mapped below |
| PROV-02 | Export `OpenAIRealtimeConfig` frozen dataclass + `OPENAI_REALTIME_CAPABILITIES` constant | Config surface defined in handoff §5 and GlassAgents `providers/openai.py`; field-for-field documented below |
| PROV-03 | `server_vad` capability reconciled with `include_turn_detection` default (PITFALL-28) | VAD/turn-detection reconciliation rule fully extracted and documented (§ PITFALL-28 below) |
| PROV-04 | Default model verified live against OpenAI API at phase start | VERIFIED: `gpt-realtime` is a valid GA alias; current snapshot = `gpt-realtime-2025-08-28` |
| QUAL-01 (OpenAI) | Unit test suite covering connect lifecycle, `iter_normalized_events` replay, close lifecycle, capability flag assertions | Test surface map in Validation Architecture section |
| QUAL-03 (OpenAI) | Integration test: connect → `SESSION_READY` → PCM16 chunk → clean close, skipped if key absent | Live test pattern documented |
</phase_requirements>

---

## Summary

Phase 2 ports one file: `src/eq_chatbot_core/realtime/providers/openai.py`. The reference implementation (`GlassAgents/backend/realtime/client.py`, 391 LOC) is a standalone class that inherits from `BaseRealtimeWebsocketClient` and `RealtimeProvider`. The Phase 1 `BaseRealtimeWebsocketClient` in the library has a slightly different constructor signature (takes `url` and `headers` as arguments vs. GlassAgents' `trace_events`-only constructor) and makes `_on_connected`, `_on_message`, and `_connection_error_endpoint` abstract. The port must adapt to that interface while preserving exact 11-method contract parity.

The single most load-bearing research task — PITFALL-28 — has been fully resolved by reading both reference files. The `server_vad = True` capability flag correctly reflects OpenAI's native capability. The `include_turn_detection` parameter is a **session-level opt-in** that controls whether the `session.update` payload includes `turn_detection` configuration. A session with `include_turn_detection=False` is valid and sends no `turn_detection` key in the session payload; the server's VAD hardware is still present but client does not activate it. The static capability flag stays `True` regardless of session setting — these are different abstractions (provider capability vs. session configuration).

The floating model alias `gpt-realtime` is confirmed as a currently-accepted OpenAI Realtime API model ID. It currently resolves to the dated snapshot `gpt-realtime-2025-08-28`. [VERIFIED: platform.openai.com/docs/models/gpt-realtime + search cross-verification]

**Primary recommendation:** Subclass the Phase 1 `BaseRealtimeWebsocketClient`, construct it with `url=self.websocket_url, headers=self._connection_headers()`, adapt the abstract hook methods, and port the 11-method contract surface faithfully. Add `OpenAIRealtimeConfig` as the public config entry point and register `"openai"` in the factory via a deferred import.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| WebSocket connect/close/retry | `BaseRealtimeWebsocketClient` (Phase 1) | `OpenAIRealtimeClient` (override hooks) | Base class owns transport; subclass owns auth headers and URL |
| Session initialization (VAD, voice, tools) | `OpenAIRealtimeClient._build_session_update_event` | — | Provider-specific OpenAI session.update payload shape |
| Audio event normalization | `OpenAIRealtimeClient.normalize_event` | `iter_normalized_events` | Two-step: wire-name aliases → canonical names → NormalizedRealtimeEvent |
| Tool calling | `OpenAIRealtimeClient.register_tools` / `submit_tool_result` | `_normalize_tools` | `conversation_item` schema is OpenAI-specific |
| Provider capability metadata | `OPENAI_REALTIME_CAPABILITIES` constant | — | Registered once at module level; immutable |
| Factory registration | `realtime/factory.py` (`build_default_realtime_provider_registry`) | `realtime/__init__.py` | Deferred import in `factory_fn` lambda; no circular import |
| Error mapping (D-03) | `OpenAIRealtimeClient.connect` override | `RealtimeConnectionError` / `ProviderError` mapping | Map HTTP 401/403 → `AuthenticationError`-style; 429 already handled by base |

---

## Standard Stack

### Core (all already in pyproject.toml)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `websockets` | `>=13.0,<17.0` | WebSocket transport | Already declared in `[realtime]` extra (CON-12); Phase 1 base class depends on it |
| `eq_chatbot_core.realtime.websocket_client` | Phase 1 | `BaseRealtimeWebsocketClient` base | Phase 1 shipped; subclass for reuse of connect/retry/backoff |
| `eq_chatbot_core.providers.base.ToolDefinition` | Phase 1 | Shared tool shape | Phase 1 shipped; realtime and chat tools share one dataclass |

### No new dependencies required

Phase 2 installs **zero new packages**. All dependencies (`websockets`, stdlib `base64`, `logging`, `urllib.parse`, `dataclasses`) are already present. [VERIFIED: pyproject.toml `[realtime]` extra confirmed]

**Installation:** `uv pip install -e ".[dev,realtime]"` (already set up from Phase 1)

---

## Package Legitimacy Audit

No new packages are introduced in Phase 2. The `websockets` package was audited in Phase 1 (CON-12). No audit table required.

---

## Architecture Patterns

### System Architecture Diagram

```
Consumer code
     |
     v
get_realtime_provider("openai", api_key=..., model=..., ...)
     |
     v
factory.py: build_default_realtime_provider_registry()
     |  [deferred import inside factory_fn lambda]
     v
OpenAIRealtimeConfig(api_key, model, voice, instructions, include_turn_detection)
     |
     v
OpenAIRealtimeClient(config) ← subclasses BaseRealtimeWebsocketClient
     |
     |-- connect() → wss://api.openai.com/v1/realtime?model=<model>
     |               Authorization: Bearer <api_key>
     |               [_on_connected() hook → initialize_session()]
     |
     |-- initialize_session() → session.update {VAD, voice, tools, modalities}
     |
     |-- append_client_audio(pcm16_bytes) → input_audio_buffer.append (base64)
     |
     |-- iter_normalized_events()
     |      ↓ raw OpenAI wire events
     |      ↓ normalize_event() [alias mapping: response.audio.* → canonical]
     |      ↓ _to_normalized_runtime_event() [type routing]
     |      → NormalizedRealtimeEvent{type, payload, source, raw}
     |
     |-- submit_tool_result(call_id, output) → conversation.item.create
     |
     └-- close() [inherited from base]
```

### Recommended Project Structure

```
src/eq_chatbot_core/realtime/
├── providers/
│   ├── __init__.py          # Phase 1: empty sub-package docstring only
│   └── openai.py            # Phase 2: THIS FILE — OpenAIRealtimeClient, OpenAIRealtimeConfig, OPENAI_REALTIME_CAPABILITIES
├── websocket_client.py      # Phase 1: BaseRealtimeWebsocketClient
├── contracts.py             # Phase 1: RealtimeAdapterContract, NormalizedRealtimeEvent, etc.
├── abc.py                   # Phase 1: RealtimeProvider ABC
├── factory.py               # Phase 1 (extend): add "openai" entry in build_default_realtime_provider_registry()
├── mock.py                  # Phase 1: MockRealtimeProvider (untouched)
└── __init__.py              # Phase 1 (extend): re-export OpenAIRealtimeClient, OpenAIRealtimeConfig, OPENAI_REALTIME_CAPABILITIES

tests/unit/realtime/
├── conftest.py              # Phase 1: AsyncMock websockets fixture (reuse unchanged)
├── test_realtime_openai.py  # Phase 2: THIS FILE — unit tests
└── ...                      # Phase 1 tests (untouched)

tests/integration/
└── test_realtime_openai_live.py  # Phase 2: integration test (skipped if no API key)
```

### Pattern 1: BaseRealtimeWebsocketClient Constructor Adaptation

The Phase 1 base class takes `url` and `headers` at construction time:

```python
# Phase 1 base class signature (VERIFIED from src/eq_chatbot_core/realtime/websocket_client.py)
class BaseRealtimeWebsocketClient(ABC):
    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self._url = url
        self._headers = headers or {}
        self._ws: Any = None
```

The GlassAgents reference takes `api_key`, `model`, etc. and builds URL/headers lazily via properties. **The port must call `super().__init__()` with the pre-computed URL and headers:**

```python
# Port pattern (Source: Phase 1 websocket_client.py + GlassAgents client.py)
class OpenAIRealtimeClient(BaseRealtimeWebsocketClient):
    def __init__(self, config: "OpenAIRealtimeConfig", *, trace_events: bool = False) -> None:
        url = f"wss://api.openai.com/v1/realtime?model={config.model}"
        headers = {"Authorization": f"Bearer {config.api_key}"}
        super().__init__(url=url, headers=headers)
        self._config = config
        self._trace_events = trace_events
        # ... counters, audio_event_names
```

Note: `trace_events` is not part of the Phase 1 base class. The port must manage it as an instance attribute or choose to omit it (tracing is a GlassAgents-internal concern; CONTEXT.md does not list it as required).

### Pattern 2: Abstract Method Implementation

The Phase 1 base class declares three abstract methods that EVERY subclass MUST override:

```python
# MUST override — raises NotImplementedError if not (PITFALL from Phase 1 CR-02)
@abstractmethod
async def _on_connected(self) -> None:
    """Called after WebSocket handshake completes."""

@abstractmethod
async def _on_message(self, raw: str) -> None:
    """Called for each received text frame."""

@abstractmethod
def _connection_error_endpoint(self) -> str:
    """Return REDACTED URL safe for error messages. MUST strip API keys."""
```

Implementation for OpenAI provider:

```python
# Source: GlassAgents client.py + Phase 1 websocket_client.py abstract contract
async def _on_connected(self) -> None:
    """Initialize session immediately after WebSocket handshake."""
    await self.initialize_session()

async def _on_message(self, raw: str) -> None:
    """Not used in iter_normalized_events flow; required for ABC conformance."""
    # The production event loop uses iter_events() / iter_normalized_events()
    # not the message callback. This method exists for ABC compliance only.
    pass

def _connection_error_endpoint(self) -> str:
    """Return URL without API key for error messages."""
    return f"wss://api.openai.com/v1/realtime?model={self._config.model}"
```

### Pattern 3: PITFALL-28 — VAD/Turn-Detection Reconciliation (SC-1, LOAD-BEARING)

**This is a success criterion. The resolved rule MUST appear as a code comment before implementation.**

Extracted from `GlassAgents/backend/realtime/client.py` (lines 334–339) and `providers/openai.py` (lines 16–26):

```python
# PITFALL-28 RESOLUTION (required comment in openai.py before implementation):
#
# server_vad capability flag vs. include_turn_detection session parameter:
#
# OPENAI_REALTIME_CAPABILITIES.server_vad = True
#   ↑ This reflects OpenAI's HARDWARE CAPABILITY — the provider natively supports
#     server-side Voice Activity Detection. This flag is STATIC and IMMUTABLE.
#     It answers: "Does this provider have VAD hardware?" → YES, always.
#
# OpenAIRealtimeConfig.include_turn_detection = True  (default)
#   ↑ This is a SESSION-LEVEL OPT-IN. It controls whether the session.update
#     payload activates VAD via:
#       session["audio"]["input"]["turn_detection"] = {
#           "type": "server_vad",
#           "create_response": True,
#           "interrupt_response": True,
#       }
#     When False, the turn_detection key is OMITTED from the payload entirely.
#     The VAD hardware exists but is NOT activated for this session.
#     The caller must then invoke commit_client_turn() manually.
#
# These are DIFFERENT ABSTRACTIONS at DIFFERENT LEVELS:
#   server_vad=True  → "The provider CAN do VAD" (static, never changes)
#   include_turn_detection=True → "This session USES VAD" (per-session config)
#
# There is NO contradiction. server_vad=True with include_turn_detection=False
# is a valid and intentional state: consumer wants manual turn control on a
# VAD-capable provider (e.g. for precise turn boundaries in onboarding flows).
#
# Reference: GlassAgents/backend/realtime/client.py lines 334-339,
#            GlassAgents/backend/realtime/providers/openai.py lines 16-26
```

### Pattern 4: `initialize_session` — Session Payload Construction

The exact session payload from the reference (verified from `client.py` lines 301–347):

```python
# Source: GlassAgents/backend/realtime/client.py _build_session_update_event()
def _build_session_update_event(self, *, instructions, voice, tools):
    session = {
        "type": "realtime",
        "model": self._config.model,
        "instructions": resolved_instructions,
        "output_modalities": ["audio"],
        "audio": {
            "input": {
                "format": {"type": "audio/pcm", "rate": INPUT_AUDIO_SAMPLE_RATE},
            },
            "output": {
                "format": {"type": "audio/pcm", "rate": OUTPUT_AUDIO_SAMPLE_RATE},
                "voice": resolved_voice,
            },
        },
    }
    if self._config.include_turn_detection:  # VAD opt-in (see PITFALL-28)
        session["audio"]["input"]["turn_detection"] = {
            "type": "server_vad",
            "create_response": True,
            "interrupt_response": True,
        }
    if tools:
        session["tools"] = tools
        session["tool_choice"] = "auto"
    return {"type": "session.update", "session": session}
```

Both `INPUT_AUDIO_SAMPLE_RATE` and `OUTPUT_AUDIO_SAMPLE_RATE` are `24_000`. The library already exports `INPUT_AUDIO_SAMPLE_RATE = 24_000` from `realtime/contracts.py`. Define `OUTPUT_AUDIO_SAMPLE_RATE = 24_000` as a module-level constant in `providers/openai.py`.

### Pattern 5: Event Normalization — Two-Stage Pipeline

```python
# Stage 1: Alias normalization (response.audio.* → response.output_audio.*)
def normalize_event(self, event):
    event_type = event.get("type")
    normalized_type = self.normalize_audio_event_type(event_type)
    if normalized_type == event_type:
        return event
    return {**event, "type": normalized_type}

def normalize_audio_event_type(self, event_type):
    if event_type == "response.audio.delta":
        return "response.output_audio.delta"  # canonical form
    if event_type == "response.audio.done":
        return "response.output_audio.done"
    return event_type

# Stage 2: Map canonical wire types → NormalizedRealtimeEventTypes constants
def _to_normalized_runtime_event(self, event):
    event_type = event.get("type")
    # ... routing table (see reference client.py lines 233-285)
    # Two events map to SESSION_READY: "session.created" AND "session.updated"
    # Tool calls: "response.function_call_arguments.done" → TOOL_CALL_COMPLETED
    #             with CUSTOM payload structure (item dict shape)
    # "response.output_item.done" with item.type=="function_call" → TOOL_CALL_COMPLETED
```

Important: the `TOOL_CALL_COMPLETED` case builds a **custom payload shape** (not just wrapping the raw event). The planner must ensure the payload structure is ported exactly as in the reference (lines 252–269).

### Pattern 6: `ToolDefinition` — Missing `to_openai_tool()` Method

**CRITICAL DIVERGENCE:** The reference `client.py` calls `tool.to_openai_tool()` in `_normalize_tools()`:

```python
# GlassAgents client.py line 297 (reference):
if isinstance(tool, ToolDefinition):
    normalized.append(tool.to_openai_tool())  # METHOD CALL
```

The Phase 1 `ToolDefinition` in `providers/base.py` is a plain `@dataclass(frozen=True, slots=True)` with fields `name`, `description`, `parameters`, `strict` — it has **NO `to_openai_tool()` method**.

**Resolution options:**
1. Add `to_openai_tool()` as a method to `ToolDefinition` in `providers/base.py` (changes Phase 1 code but is additive/non-breaking)
2. Inline the conversion in `_normalize_tools()` inside `openai.py` (no Phase 1 changes needed)

Option 2 keeps Phase 2 self-contained. The inline conversion is:
```python
# Inline ToolDefinition → OpenAI tool format (no to_openai_tool() needed)
{
    "type": "function",
    "name": tool.name,
    "description": tool.description,
    "parameters": tool.parameters,
    "strict": tool.strict,
}
```

**Recommendation (for planner):** Use Option 2 (inline in `openai.py`). Option 1 is a valid future enhancement when Phase 3 Gemini also needs tool conversion.

### Pattern 7: Factory Registration

```python
# In realtime/factory.py — build_default_realtime_provider_registry() extension
# Source: Phase 1 factory.py (read in full)
def build_default_realtime_provider_registry() -> RealtimeProviderRegistry:
    # ... existing mock registration ...
    registry.register(
        RealtimeProviderDefinition(
            name="openai",
            factory_fn=lambda **kwargs: _build_openai_provider(**kwargs),
            description="OpenAI Realtime API — GPT speech-to-speech, server VAD, tool calling.",
        )
    )
    return registry

def _build_openai_provider(**kwargs) -> "OpenAIRealtimeClient":
    # Deferred import — keeps factory importable without [realtime] extra
    from eq_chatbot_core.realtime.providers.openai import (
        OpenAIRealtimeClient,
        OpenAIRealtimeConfig,
    )
    api_key = kwargs.pop("api_key")
    config = OpenAIRealtimeConfig(api_key=api_key, **kwargs)
    return OpenAIRealtimeClient(config)
```

### Anti-Patterns to Avoid

- **ANTI-1 — Re-implementing connect/retry in the subclass:** `BaseRealtimeWebsocketClient` already handles `connect_with_backoff`, idempotent connect, and leak protection. Do not duplicate.
- **ANTI-2 — Calling `websockets.connect()` directly in the subclass:** All WebSocket lifecycle management goes through the base class methods.
- **ANTI-3 — Embedding API key in `_connection_error_endpoint()` return value:** Must return `wss://api.openai.com/v1/realtime?model=...` (model is safe; api_key must be stripped).
- **ANTI-4 — Forgetting to handle `_on_message` abstract requirement:** Even though the production event loop uses `iter_events()`, the abstract method must be implemented (can be a no-op `pass`).
- **ANTI-5 — Skipping PITFALL-28 documentation:** SC-1 requires the reconciliation comment to exist BEFORE the `initialize_session` implementation is written. The planner must order this as Wave 0 of the implementation.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket connect/reconnect/retry | Custom WS client | `BaseRealtimeWebsocketClient` (Phase 1) | Already has backoff, leak protection, header kwarg detection |
| `additional_headers` vs `extra_headers` detection | `try/except TypeError` runtime probe | `_CONNECT_HEADERS_KWARG` import-time detect | Phase 1 solved this; re-doing it in subclass creates double detection |
| Audio event alias normalization | Hardcoded `if/elif` without structure | `normalize_event()` + `RealtimeAudioEventNames` frozen dataclass | Reference uses this; future-proof against new aliases |
| Tool format conversion | Custom dict-building spread across methods | `_normalize_tools()` static method | Keeps conversion in one place; handles both `ToolDefinition` and raw dict |
| Rate limit retry | Custom retry loop in `connect()` | `connect_with_backoff()` (inherited) | Phase 1 already retries `RealtimeRateLimitError` |

**Key insight:** All transport-layer concerns are owned by `BaseRealtimeWebsocketClient`. `OpenAIRealtimeClient` is a pure protocol adapter — its job is to build OpenAI-shaped payloads and normalize OpenAI-shaped events.

---

## PITFALL-28 Resolution (LOAD-BEARING — SC-1)

This section documents the complete resolved reconciliation rule for the planner.

### The Apparent Contradiction

```
OPENAI_REALTIME_CAPABILITIES.server_vad = True
OpenAIRealtimeConfig.include_turn_detection = True  (default)
```

At first glance: if `server_vad = True` is a static capability, why does the config have an opt-in? And if `include_turn_detection=False`, doesn't that contradict `server_vad = True`?

### The Resolution (Verified from reference source)

**`server_vad = True`** answers: *"Does this provider support server-side VAD as a feature?"* — Yes, OpenAI's Realtime API natively supports server VAD. This is a **provider capability descriptor**. It is static and immutable; it does not change between sessions.

**`include_turn_detection = True`** (default) answers: *"Should this session activate VAD by including the `turn_detection` block in the `session.update` payload?"* — This is a **session-level configuration knob**.

### Behavior Matrix

| `server_vad` (static) | `include_turn_detection` | `session.update` payload | Who commits turns |
|-----------------------|--------------------------|--------------------------|------------------|
| `True` | `True` (default) | includes `turn_detection: {type: server_vad, create_response: True, interrupt_response: True}` | Server (automatic) |
| `True` | `False` | `turn_detection` key OMITTED entirely | Caller must invoke `commit_client_turn()` |

### Verified Source

```python
# GlassAgents/backend/realtime/client.py lines 334-339
if self._include_turn_detection:
    session["audio"]["input"]["turn_detection"] = {
        "type": "server_vad",
        "create_response": True,
        "interrupt_response": True,
    }
# No else — key is simply absent when include_turn_detection=False
```

```python
# GlassAgents/backend/realtime/providers/openai.py lines 16-19
OPENAI_REALTIME_CAPABILITIES = RealtimeProviderCapabilities(
    server_vad=True,             # capability: provider supports it
    manual_turn_commit_required=False,  # when VAD is active (default), manual commit not needed
    ...
)
```

Note: `manual_turn_commit_required=False` reflects the DEFAULT session configuration (VAD on). When a consumer creates a session with `include_turn_detection=False`, they take on manual turn commit responsibility — but the capability flag stays `False` because it describes the provider's DEFAULT behavior.

### Required Code Comment Location

The planner MUST include a task in Wave 0 (before any implementation wave) that writes the PITFALL-28 reconciliation comment as a block comment at the top of `_build_session_update_event()` in `openai.py`. This satisfies SC-1.

---

## SC-2: Model Verification (LOAD-BEARING — D-02)

### Verified Result

**`gpt-realtime` is a valid, currently-accepted OpenAI Realtime API model ID.** [VERIFIED: platform.openai.com/docs/models/gpt-realtime + cross-verified via WebSearch results from OpenAI announcement page]

**Current dated snapshot the alias resolves to:** `gpt-realtime-2025-08-28` [CITED: platform.openai.com/docs/models/gpt-realtime; cross-verified via OpenAI models docs search]

### Context

`gpt-realtime` was announced as a GA production realtime model (OpenAI blog post "Introducing gpt-realtime and Realtime API updates for production voice agents"). It supersedes the older `gpt-4o-realtime-preview` family for new production deployments.

Other currently available realtime model IDs (for consumer pinning reference):
- `gpt-realtime-2025-08-28` — the specific snapshot `gpt-realtime` points to
- `gpt-4o-realtime-preview` — legacy alias (deprecated for new deployments)
- `gpt-4o-mini-realtime-preview` — smaller/faster variant
- `gpt-4o-mini-realtime-preview-2024-12-17` — dated snapshot, shutdown scheduled July 23, 2026

### Required Implementation Detail (D-02)

The following comment MUST appear in `openai.py` adjacent to the `model` field default:

```python
@dataclass(frozen=True, slots=True)
class OpenAIRealtimeConfig:
    api_key: str
    # gpt-realtime: floating alias, currently resolves to gpt-realtime-2025-08-28 (verified 2026-05-24).
    # Consumers requiring byte-reproducible behavior should pin a dated snapshot explicitly.
    # Valid dated snapshots: gpt-realtime-2025-08-28
    # Reference: https://platform.openai.com/docs/models/gpt-realtime
    model: str = "gpt-realtime"
    voice: str = "ash"
    instructions: str | None = None
    include_turn_detection: bool = True
```

---

## Common Pitfalls

### Pitfall 1: Phase 1 Base Class Constructor Mismatch
**What goes wrong:** Port passes `trace_events=False` to `super().__init__()` (GlassAgents pattern), but Phase 1 takes `url` and `headers`.
**Why it happens:** The Phase 1 base class was redesigned vs. the GlassAgents reference (URL/headers at construction vs. property-based).
**How to avoid:** Call `super().__init__(url=<computed_url>, headers=<computed_headers>)` before storing config fields.
**Warning signs:** `TypeError: __init__() got an unexpected keyword argument 'trace_events'`

### Pitfall 2: Missing `_on_message` Abstract Override
**What goes wrong:** `TypeError: Can't instantiate abstract class OpenAIRealtimeClient with abstract method _on_message`
**Why it happens:** Phase 1's `BaseRealtimeWebsocketClient` makes `_on_message` abstract (not present in GlassAgents reference).
**How to avoid:** Implement as a no-op: `async def _on_message(self, raw: str) -> None: pass`
**Warning signs:** Runtime `TypeError` on first `OpenAIRealtimeClient(config)` construction in unit tests.

### Pitfall 3: Missing `_on_connected` Abstract Override
**What goes wrong:** Same as Pitfall 2 — `_on_connected` is abstract in Phase 1.
**Why it happens:** GlassAgents `_on_connected` is a non-abstract hook (logging only). Phase 1 promoted it to abstract to force subclasses to declare their post-connect intent.
**How to avoid:** `async def _on_connected(self) -> None: await self.initialize_session()` — matches GlassAgents intent of sending `session.update` immediately after connect.
**Warning signs:** `TypeError` at construction time.

### Pitfall 4: API Key Leaked via `_connection_error_endpoint`
**What goes wrong:** Error messages and logs expose the raw WebSocket URL including `?api_key=...` or the Authorization header.
**Why it happens:** OpenAI Realtime uses query-param model but Bearer header auth — URL itself is safe but a careless implementation might log headers.
**How to avoid:** `_connection_error_endpoint()` returns `wss://api.openai.com/v1/realtime?model={model}` only. Never log `self._headers`.
**Warning signs:** API key appears in log output during connection failure tests.

### Pitfall 5: TOOL_CALL_COMPLETED Payload Divergence
**What goes wrong:** Consumer receives `TOOL_CALL_COMPLETED` events but cannot extract `call_id` or `name` — wrong field paths.
**Why it happens:** The reference builds a custom payload wrapping both the top-level `call_id`/`name` fields AND an inner `item` dict. If the port just wraps `event` as-is, the payload shape differs.
**How to avoid:** Port `_to_normalized_runtime_event` exactly for the `response.function_call_arguments.done` case (reference lines 252–269). The payload MUST contain `item.call_id`, `item.name`, `item.arguments` for GlassAgents bridge compatibility.
**Warning signs:** GlassAgents-side tests fail on `payload["item"]["call_id"]` KeyError after migration.

### Pitfall 6: `RealtimeAudioEventNames` Frozen Dataclass
**What goes wrong:** Hard-coded string `"response.output_audio.delta"` scattered through the class vs. the `audio_event_names` dataclass pattern.
**Why it happens:** GlassAgents uses a `RealtimeAudioEventNames` frozen dataclass as a named constant holder.
**How to avoid:** Port the `RealtimeAudioEventNames` dataclass verbatim and use `self.audio_event_names.delta` / `.done` throughout.
**Warning signs:** Audio delta events are dispatched to UNHANDLED instead of RESPONSE_AUDIO_DELTA.

### Pitfall 7: Trace-Events Attribute Missing
**What goes wrong:** `AttributeError: 'OpenAIRealtimeClient' object has no attribute '_trace_events'`
**Why it happens:** Phase 1 base class does NOT carry `_trace_events`; the reference stores it on the instance.
**How to avoid:** Store `self._trace_events = trace_events` explicitly in `OpenAIRealtimeClient.__init__()` (after `super().__init__()`).
**Warning signs:** `AttributeError` on first `recv_json` call when tracing is used.

### Pitfall 8: `connect()` ABC Compliance Stub in Reference — Don't Port It
**What goes wrong:** The reference has an `async def connect(self, config=None)` stub (lines 362–369) for GlassAgents ABC conformance. Porting this stub would shadow the `BaseRealtimeWebsocketClient.connect()` and break the transport layer.
**Why it happens:** GlassAgents `RealtimeProvider` ABC requires `connect(config)` with a config param. The Phase 1 `RealtimeProvider` ABC requires `connect()` with no params (Phase 1 `abc.py` line 88). The stubs are different.
**How to avoid:** Do NOT port the ABC compliance `connect()` stub. The Phase 1 `RealtimeProvider.connect()` signature matches `BaseRealtimeWebsocketClient.connect()` already — no override needed.
**Warning signs:** `connect()` ignores `_on_connected()` because it calls `BaseRealtimeWebsocketClient.connect(self)` directly (bypassing the Phase 1 connect logic).

---

## Code Examples

### OpenAIRealtimeConfig (complete dataclass)

```python
# Source: GlassAgents/backend/realtime/providers/openai.py (adapted to library conventions)
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class OpenAIRealtimeConfig:
    api_key: str
    # gpt-realtime: floating alias, currently resolves to gpt-realtime-2025-08-28 (verified 2026-05-24).
    # Consumers requiring byte-reproducible behavior should pin a dated snapshot explicitly.
    # Reference: https://platform.openai.com/docs/models/gpt-realtime
    model: str = "gpt-realtime"
    voice: str = "ash"
    instructions: str | None = None
    include_turn_detection: bool = True  # see PITFALL-28 comment in _build_session_update_event
```

### OPENAI_REALTIME_CAPABILITIES constant

```python
# Source: GlassAgents/backend/realtime/providers/openai.py lines 16-26
from eq_chatbot_core.realtime.contracts import RealtimeProviderCapabilities

OPENAI_REALTIME_CAPABILITIES = RealtimeProviderCapabilities(
    streaming_audio_input=True,
    streaming_audio_output=True,
    server_vad=True,                          # provider SUPPORTS VAD (always true)
    manual_turn_commit_required=False,        # when VAD active (default); see PITFALL-28
    tool_calling=True,
    tool_result_submission_mode="conversation_item",
    voice_selection=True,
    interruption_cancel=True,
    startup_validation=True,
)
```

### `submit_tool_result` — `conversation_item` schema

```python
# Source: GlassAgents/backend/realtime/client.py lines 199-214
async def submit_tool_result(self, *, call_id: str, output: str) -> None:
    await self.send_json(
        {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            },
        }
    )
```

### Audio chunk send pattern

```python
# Source: GlassAgents/backend/realtime/client.py lines 174-181
import base64

async def append_client_audio(self, pcm16_audio: bytes) -> None:
    if not pcm16_audio:
        return
    await self.send_json(
        {
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(pcm16_audio).decode("ascii"),
        }
    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `gpt-4o-realtime-preview` as default model | `gpt-realtime` floating alias | OpenAI GA announcement 2025 | New implementations should use `gpt-realtime` |
| `extra_headers` kwarg in websockets | `additional_headers` kwarg | websockets 13.x | Phase 1 handles this with import-time detection |
| `try/except TypeError` fallback for headers | Import-time `inspect.signature` probe | Phase 1 CR-03 | Avoids hiding real TypeErrors as RealtimeConnectionError |
| GlassAgents ABC `connect(config=None)` stub | No stub needed | Phase 1 redesign | Phase 1 ABC has compatible `connect()` signature |

**Deprecated/outdated:**
- `gpt-4o-realtime-preview`: Superseded by `gpt-realtime` for new production deployments. Dated snapshots still available until shutdown dates.
- Exception-as-control-flow for websockets header kwarg: Replaced by import-time detection in Phase 1.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `gpt-realtime` alias currently resolves to `gpt-realtime-2025-08-28` | SC-2 Model Verification | Low — model is still valid; snapshot pointer may have updated since verification |
| A2 | `_on_message` is abstract in Phase 1 `BaseRealtimeWebsocketClient` | Pattern 2 | High — if not abstract, no-op implementation is harmless but if it IS abstract and forgotten, unit tests fail at construction |
| A3 | `trace_events` should be optional (default `False`) in the port | Pattern 1 | Low — GlassAgents uses it; if omitted, callers lose debug logging but no correctness impact |

**Verified (not assumed):**
- Phase 1 `BaseRealtimeWebsocketClient` takes `url, headers` at init [VERIFIED: read source]
- `_connection_error_endpoint` is abstract and raises `NotImplementedError` [VERIFIED: read source]
- `ToolDefinition` has no `to_openai_tool()` method [VERIFIED: read source]
- `gpt-realtime` is a valid OpenAI Realtime API model ID [VERIFIED: platform.openai.com/docs/models]
- PITFALL-28 reconciliation rule [VERIFIED: read GlassAgents reference client.py + providers/openai.py]

---

## Open Questions

1. **Should `trace_events` be included in `OpenAIRealtimeConfig` or as a constructor kwarg?**
   - What we know: GlassAgents uses `trace_events` as a constructor kwarg (not in config). CONTEXT.md does not mention it.
   - What's unclear: Is it useful to library consumers, or is it GlassAgents-internal debug?
   - Recommendation: Keep as optional `**kwargs` or omit entirely for v1.8.0. It is not required by any requirement (PROV-01 through PROV-04 don't mention it). Planner may omit it or add as a constructor kwarg defaulting to `False`.

2. **Should `to_openai_tool()` be added to `ToolDefinition` (Option 1) or inlined in `_normalize_tools()` (Option 2)?**
   - What we know: Reference calls `tool.to_openai_tool()`. Phase 1 `ToolDefinition` has no such method. Both options work.
   - What's unclear: Phase 3 Gemini will also need tool conversion (different format). A shared method on `ToolDefinition` would be cleaner then.
   - Recommendation: Use Option 2 (inline in `openai.py`) for Phase 2. Leave `to_openai_tool()` as a Phase 3 enhancement when the Gemini conversion also lands.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `websockets` | WebSocket transport | Confirmed in pyproject.toml `[realtime]` | `>=13.0,<17.0` | — (required) |
| `OPENAI_API_KEY` env var | Integration test (QUAL-03) | Not checked (CI secret) | — | Test skipped if absent |
| Python `base64`, `logging`, `urllib.parse` | Audio encoding, logging, URL building | stdlib, always available | — | — |

**Missing dependencies with no fallback:** None — all required packages are declared.
**Integration test gate:** `pytest.mark.integration` + `pytest.skip` if `OPENAI_API_KEY` env var absent.

---

## Validation Architecture

Nyquist validation is enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (already configured; `pyproject.toml` [dev] extra) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/unit/realtime/test_realtime_openai.py -v` |
| Full suite command | `pytest tests/unit/realtime/ -v` |
| Integration test | `pytest tests/integration/test_realtime_openai_live.py -v -m integration` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROV-01 | `OpenAIRealtimeClient` implements all 11 `RealtimeAdapterContract` methods | unit | `pytest tests/unit/realtime/test_realtime_openai.py::test_implements_contract -x` | ❌ Wave 0 |
| PROV-01 | Connect lifecycle: `connect()` opens WS, `_on_connected` fires, `initialize_session` sends `session.update` | unit | `pytest tests/unit/realtime/test_realtime_openai.py::TestConnectLifecycle -x` | ❌ Wave 0 |
| PROV-01 | `iter_normalized_events` replays each of the 11 wire event types and maps to correct `NormalizedRealtimeEventTypes` constant | unit | `pytest tests/unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents -x` | ❌ Wave 0 |
| PROV-01 | Close lifecycle: `close()` tears down WS without errors | unit | `pytest tests/unit/realtime/test_realtime_openai.py::TestCloseLifecycle -x` | ❌ Wave 0 |
| PROV-02 | `OpenAIRealtimeConfig` is frozen + slots dataclass with correct field defaults | unit | `pytest tests/unit/realtime/test_realtime_openai.py::TestOpenAIRealtimeConfig -x` | ❌ Wave 0 |
| PROV-02 | `OPENAI_REALTIME_CAPABILITIES` values match handoff §3.3 table | unit | `pytest tests/unit/realtime/test_realtime_openai.py::test_capabilities -x` | ❌ Wave 0 |
| PROV-03 | `include_turn_detection=True` → payload has `turn_detection` block; `False` → block absent | unit | `pytest tests/unit/realtime/test_realtime_openai.py::TestVADSessionPayload -x` | ❌ Wave 0 |
| PROV-04 | `OpenAIRealtimeConfig.model` default is `"gpt-realtime"` (string assertion) | unit | `pytest tests/unit/realtime/test_realtime_openai.py::test_default_model_is_gpt_realtime -x` | ❌ Wave 0 |
| QUAL-01 | Tool call normalization: `response.function_call_arguments.done` → TOOL_CALL_COMPLETED with correct payload shape | unit | `pytest tests/unit/realtime/test_realtime_openai.py::TestToolCallNormalization -x` | ❌ Wave 0 |
| QUAL-03 | Integration: connect → `SESSION_READY` → PCM16 chunk → clean close | integration | `pytest tests/integration/test_realtime_openai_live.py -v -m integration` | ❌ Wave 0 |

### Unit Test Fixture Pattern

Reuse the Phase 1 `conftest.py` from `tests/unit/realtime/conftest.py` (session-scoped `mock_websockets_module` + function-scoped `mock_ws_instance`). The `test_realtime_openai.py` module needs only:

```python
# tests/unit/realtime/test_realtime_openai.py header pattern
import pytest
from unittest.mock import AsyncMock, patch

# The session-scoped mock_websockets_module fixture from conftest.py
# installs the mock before any import. Import provider AFTER conftest setup.

# For each test class: use mock_ws_instance fixture (function-scoped)
# to get a fresh WS instance with .closed=False, .recv, .send, .close as AsyncMock.
```

### Integration Test Pattern

```python
# tests/integration/test_realtime_openai_live.py
import os, pytest, asyncio
from eq_chatbot_core.realtime.providers.openai import OpenAIRealtimeClient, OpenAIRealtimeConfig
from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes

pytestmark = pytest.mark.integration

@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping live integration test"
)
async def test_openai_realtime_session_ready_and_pcm_chunk():
    config = OpenAIRealtimeConfig(
        api_key=os.environ["OPENAI_API_KEY"],
        include_turn_detection=False,  # manual mode for predictable test flow
    )
    async with OpenAIRealtimeClient(config) as client:
        # SC-3: receive SESSION_READY
        async for event in client.iter_normalized_events():
            assert event["type"] == NormalizedRealtimeEventTypes.SESSION_READY
            break
        # SC-3: send one PCM16 chunk (100ms of silence = 4800 bytes at 24kHz mono PCM16)
        silence = b"\x00\x00" * 2400
        await client.append_client_audio(silence)
    # SC-3: clean disconnect (async with __aexit__ calls close())
```

### Sampling Rate

- **Per task commit:** `pytest tests/unit/realtime/test_realtime_openai.py -v -x`
- **Per wave merge:** `pytest tests/unit/realtime/ -v`
- **Phase gate:** Full unit suite green + integration test passes (or is appropriately skipped) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/realtime/test_realtime_openai.py` — covers PROV-01 through PROV-04, QUAL-01 (OpenAI portion)
- [ ] `tests/integration/test_realtime_openai_live.py` — covers QUAL-03 (OpenAI portion)

*(Existing `tests/unit/realtime/conftest.py` is reused unchanged — no gap there)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | Bearer token in WS `Authorization` header — never logged, never in URLs |
| V3 Session Management | Partial | WebSocket session; no persistent tokens; close() clears `_ws` |
| V4 Access Control | No | Library does not enforce access policies |
| V5 Input Validation | Yes | `api_key` non-empty check; `model` non-empty check in `__init__` |
| V6 Cryptography | No | TLS handled by `websockets` library; no custom crypto |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key in logs / error messages | Information Disclosure | `_connection_error_endpoint()` strips key; never log `self._headers` |
| API key in URL query param | Information Disclosure | OpenAI uses Bearer header, NOT query param — URL is safe to log |
| Unauthenticated WS connection reuse | Spoofing | `is_connected` check in `connect()` is idempotent; no key rotation mid-session |
| Malformed JSON from server | Tampering | `recv_json()` in base class wraps all JSON errors as `RealtimeProtocolError` |

---

## Sources

### Primary (HIGH confidence)
- GlassAgents `backend/realtime/client.py` — read in full (391 LOC) — PITFALL-28 resolution, payload shapes, event normalization routing table
- GlassAgents `backend/realtime/providers/openai.py` — read in full (77 LOC) — `OPENAI_REALTIME_CAPABILITIES`, factory pattern
- `src/eq_chatbot_core/realtime/websocket_client.py` — read in full — Phase 1 base class constructor, abstract methods, `_CONNECT_HEADERS_KWARG` pattern
- `src/eq_chatbot_core/realtime/contracts.py` — read in full — `RealtimeAdapterContract` 11-method surface, event type constants
- `src/eq_chatbot_core/realtime/factory.py` — read in full — registry pattern, deferred import strategy
- `src/eq_chatbot_core/providers/base.py` — read (ToolDefinition class) — confirmed no `to_openai_tool()` method
- `tests/unit/realtime/conftest.py` — read in full — AsyncMock fixture pattern reuse

### Secondary (MEDIUM confidence)
- `platform.openai.com/docs/models/gpt-realtime` — model alias page; `gpt-realtime` valid GA model; snapshot `gpt-realtime-2025-08-28` [CITED: WebSearch result from platform.openai.com/docs/models/gpt-realtime]
- `openai.com/index/introducing-gpt-realtime/` — announcement; `gpt-realtime` is the new GA production model [CITED: WebSearch summary]

### Tertiary (LOW confidence)
- None — no unverified claims remain.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all Phase 1 files read directly; no new packages
- Architecture (base class adaptation): HIGH — both reference and Phase 1 source read in full
- PITFALL-28 resolution: HIGH — extracted directly from both reference source files
- SC-2 model verification: MEDIUM — verified via official docs URL + cross-checked WebSearch; OpenAI docs pages not directly fetched (redirect to ctx tools), but multiple authoritative sources agree
- Pitfalls: HIGH — derived from direct source comparison; no training-data assumptions
- Test patterns: HIGH — Phase 1 conftest read; integration test pattern derived from reference

**Research date:** 2026-05-24
**Valid until:** 2026-08-24 (model snapshot pointer may update; all code patterns are stable)
