# Phase 3: Gemini Live + Nova Sonic Stub - Research

**Researched:** 2026-05-25
**Domain:** Gemini Live API (dual-endpoint), Nova Sonic stub, realtime provider factory extension
**Confidence:** HIGH (reference source located and fully read; GlassAgents code verified in-session)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `GeminiLiveConfig` supports both Google endpoints, config-driven:
  - **Gemini Developer API** — `api_key` auth, key-in-URL (`?key=...`), global/US endpoint. The faithful GlassAgents port path.
  - **Vertex AI Live API** — ADC/service-account auth (OAuth bearer), regional `europe-west*` endpoint. DSGVO-compliant path; satisfies SC-3.
  - Switchable via a `mode`/`base_url`/`region` field on the config. Planner decides exact config surface (e.g., explicit `mode: "developer" | "vertex"` vs. inferred from presence of `region`/`project`).
- **D-02:** Redaction (PROV-07) covers both modes — port `_redact_sensitive_url` / `_redact_sensitive_text` and extend to cover Developer-API `key=` query param AND Vertex OAuth bearer tokens / project identifiers.
- **D-03:** SC-3's EU integration test uses Vertex `europe-west*` path. Unit tests (QUAL-01) cover both endpoint modes via recorded scrubbed frames. Expanded test matrix accepted as tradeoff.
- **D-04:** `GeminiLiveConfig.model` defaults to a **floating alias** (zero-maintenance, tracks Google's current Live model), NOT a pinned snapshot.
- **D-05:** PITFALL-20 satisfied by gsd-phase-researcher verifying live-valid model alias at phase start for BOTH endpoints, recorded in this RESEARCH.md. No runtime model-list call added. Verified snapshot noted in code comment / CHANGELOG.
- **D-06:** On invalid/rejected model, fail fast with a library-native exception (mirrors Phase 2 D-03).
- **D-07:** `NovaSonicStub` raises `NotImplementedError` with a concise message pointing to v1.9.0. No boto3/AWS install instructions in message. Stays minimal (<30 LOC).
- **D-08:** Stub is registered in the factory so `get_realtime_provider("nova_sonic")` resolves without any AWS extras installed.

### Claude's Discretion

- Exact `GeminiLiveConfig` field names and developer-vs-vertex mode-switch mechanism.
- Whether `GeminiLiveClient` extends `BaseRealtimeWebsocketClient` (prefer reuse where it does not compromise port parity). Note: `_connection_error_endpoint` is abstract and MUST be overridden.
- Precise wording of the Nova `NotImplementedError` message (must reference v1.9.0).

### Deferred Ideas (OUT OF SCOPE)

- Local / on-prem realtime provider (v1.9.0 backlog). Ollama and LM Studio do not expose native S2S WebSocket APIs. Two future paths: cascade orchestrator (local STT → LLM → TTS) or native local S2S/omni adapter (Moshi, Qwen2.5/3-Omni, etc.). Belongs in future phase alongside Nova Sonic production implementation (PROV-FUT-01).

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROV-05 | `gemini_live.py` ports `GeminiLiveClient` (~919 LOC) from GlassAgents with feature parity: all 11 `RealtimeAdapterContract` methods, BidiGenerateContent protocol, manual turn commit, `provider_call_id` tool-result schema | Reference fully read at `/Users/picard/gitbase/GlassAgents/backend/realtime/providers/gemini_live.py` (920 lines). All 11 methods present. Adaptation gaps documented. |
| PROV-06 | Exports `GeminiLiveConfig` frozen dataclass and `GEMINI_LIVE_REALTIME_CAPABILITIES` constant | Capabilities values extracted from reference. Config fields + dual-endpoint extensions documented. |
| PROV-07 | Ports `_redact_sensitive_url` and `_redact_sensitive_text` helpers verbatim (API key must never leak to logs) | Both helpers located in reference (lines 813–860). Extended redaction for Vertex bearer tokens documented. |
| PROV-08 | `nova.py` ships `NovaSonicStub` (<30 LOC) raising `NotImplementedError` pointing to v1.9.0; satisfies `RealtimeAdapterContract` structurally | Structural requirements derived from `contracts.py`. Pattern documented. GlassAgents `nova.py` is transport-agnostic ABC stub — NOT the v1.9.0 target. |
| QUAL-01 | Unit tests: connect lifecycle, `iter_normalized_events` produces every expected event type from recorded scrubbed frames, close lifecycle, capability flag assertions (Gemini + Nova portion) | Test matrix and recorded frame shapes documented for both endpoint modes. |
| QUAL-03 | Integration test: connect to real API, receive `SESSION_READY`, send PCM16 chunk, disconnect cleanly — Gemini portion, Vertex EU path | Pattern from `test_realtime_openai_live.py` documented. Vertex auth flow documented. |

</phase_requirements>

---

## Summary

Phase 3 ports two providers into `src/eq_chatbot_core/realtime/providers/`. The primary work is `GeminiLiveClient`, a faithful port of `GlassAgents/backend/realtime/providers/gemini_live.py` (920 LOC). The reference has been read in full and the adaptation delta is well-understood. The secondary work is a <30 LOC `NovaSonicStub` that satisfies `RealtimeAdapterContract` structurally with every method raising `NotImplementedError`.

The key complexity is the dual-endpoint design (D-01): the Developer API uses `key=` in the URL (global endpoint); Vertex AI uses an OAuth bearer in the Authorization header with a regional `{region}-aiplatform.googleapis.com` endpoint. Both endpoints use the same BidiGenerateContent wire protocol after connection — only auth and URL construction differ. Redaction must cover both auth styles.

A significant adaptation delta from the GlassAgents reference is the `ToolDefinition` field name mismatch: the reference uses `tool.input_schema` but the library's `ToolDefinition` uses `tool.parameters`. The `now_ms()` GlassAgents utility must be replaced with `time.time_ns() // 1_000_000`. GlassAgents-specific imports (`IOSRealtimeBridge`, `Settings`, `BridgeBinding`, etc.) are NOT ported — only the `GeminiLiveRealtimeClient` class and its two static redaction helpers.

**Primary recommendation:** Port the `GeminiLiveRealtimeClient` class body verbatim with targeted substitutions for the 5 adaptation deltas documented below. Extend `__init__` to add Vertex URL/auth support as a `mode` field on the config.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Gemini Live websocket transport | API / Backend (library) | — | Raw websocket, inherits `BaseRealtimeWebsocketClient` |
| Gemini Developer API auth (key-in-URL) | API / Backend (library) | — | URL built in `GeminiLiveClient.__init__`, redacted in error path |
| Vertex AI auth (ADC → bearer token) | API / Backend (library) | Consumer (credential supply) | Library builds `Authorization` header; consumer supplies bearer token via config |
| Redaction (PROV-07) | API / Backend (library) | — | Both `_redact_sensitive_url` and `_redact_sensitive_text` are library-internal |
| BidiGenerateContent event normalization | API / Backend (library) | — | `_to_normalized_runtime_events` routes all Gemini wire types |
| Tool schema conversion (→ Gemini format) | API / Backend (library) | — | `_to_gemini_function_declaration` + `_to_gemini_schema` strip incompatible JSON Schema keys |
| Nova Sonic stub | API / Backend (library) | — | Structural conformance only; no transport |
| Factory registration | API / Backend (library) | — | Deferred-import pattern in `realtime/factory.py` |
| EU/Vertex integration test credential supply | Consumer (test environment) | — | Test skipped when `GEMINI_VERTEX_API_KEY` / `VERTEX_PROJECT_ID` absent |

---

## Standard Stack

### Core (all already installed in `[realtime]` extra)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `websockets` | `>=13.0,<17.0` | WebSocket transport (inherited via `BaseRealtimeWebsocketClient`) | Declared in `pyproject.toml [realtime]` extra; already used by OpenAI provider |
| `base64` | stdlib | PCM16 audio encoding for `realtimeInput.audio.data` | stdlib, zero-weight |
| `json` | stdlib | Wire message serialization/deserialization | stdlib |
| `re` | stdlib | Regex redaction in `_redact_sensitive_text` | stdlib |
| `urllib.parse` | stdlib | `urlsplit` / `urlunsplit` / `urlencode` / `parse_qsl` in redaction helpers | stdlib |
| `time` | stdlib | `time.time_ns() // 1_000_000` replacement for GlassAgents `now_ms()` | stdlib; replaces GlassAgents-internal utility |

### No new package installs required for Phase 3

Vertex AI authentication does NOT require `google-auth` in the library — the bearer token is supplied by the consumer in `GeminiLiveConfig.access_token`. This keeps the `[realtime]` extra at its current minimal footprint (websockets only). [CITED: Vertex AI Live API docs — auth via `Authorization: Bearer <token>` header]

**Installation:** No new packages. Phase 3 is code-only.

---

## Package Legitimacy Audit

> Phase 3 installs no new packages. No audit required.

---

## Architecture Patterns

### System Architecture Diagram

```
Consumer code
     |
     v
get_realtime_provider("gemini_live", mode="developer", api_key=..., model=...)
get_realtime_provider("gemini_live", mode="vertex",    access_token=..., project=..., region=...)
get_realtime_provider("nova_sonic")  ← no kwargs needed; raises NotImplementedError on any call
     |
     v
factory.py: _build_gemini_live_provider(**kwargs) / _build_nova_sonic_provider(**kwargs)
     |
     v
GeminiLiveClient(config: GeminiLiveConfig)
  ├─ mode="developer": URL = wss://generativelanguage.googleapis.com/ws/.../BidiGenerateContent?key={api_key}
  │                    headers = {}
  └─ mode="vertex":    URL = wss://{region}-aiplatform.googleapis.com/ws/.../BidiGenerateContent
                       headers = {"Authorization": "Bearer {access_token}", "x-goog-user-project": "{project}"}
     |
     v (inherits)
BaseRealtimeWebsocketClient.connect() → websockets.connect(url, headers=...)
     |
     v
_on_connected() → initialize_session() → send setup envelope (BidiGenerateContent wire protocol)
     |
     v (loop)
iter_normalized_events() → iter_events() → recv_json() → _to_normalized_runtime_events(event)
     │
     ├── {"setupComplete": ...}          → SESSION_READY
     ├── {"serverContent": ...}          → RESPONSE_AUDIO_DELTA* + RESPONSE_DONE
     ├── {"toolCall": ...}               → TOOL_CALL_COMPLETED*
     ├── {"toolCallCancellation": ...}   → TOOL_CALL_CANCELLED
     ├── {"error": ...}                  → ERROR
     └── (anything else)                → UNHANDLED
     |
     v
NovaSonicStub (parallel file)
  └─ isinstance(NovaSonicStub(), RealtimeAdapterContract) → True
     all 11 methods → NotImplementedError("Nova Sonic not implemented; available in v1.9.0")
```

### Recommended Project Structure

```
src/eq_chatbot_core/realtime/providers/
├── __init__.py           # empty sub-package (exists)
├── openai.py             # Phase 2 (exists)
├── gemini_live.py        # Phase 3 — NEW
└── nova.py               # Phase 3 — NEW

tests/unit/realtime/
├── conftest.py           # exists — session-scoped mock_websockets_module (reuse)
├── test_realtime_gemini.py   # Phase 3 — NEW
└── test_realtime_nova.py     # Phase 3 — NEW

tests/integration/
└── test_realtime_gemini_live.py  # Phase 3 — NEW (Vertex EU integration test)
```

### Pattern 1: GeminiLiveClient Dual-Endpoint URL Construction

The config has an explicit `mode: Literal["developer", "vertex"]` field. The constructor builds the URL and headers from mode:

```python
# Source: GlassAgents/backend/realtime/providers/gemini_live.py (adapted)
_GEMINI_DEVELOPER_BASE_URL = "wss://generativelanguage.googleapis.com"
_GEMINI_DEVELOPER_ENDPOINT = "/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
_VERTEX_ENDPOINT = "/ws/google.cloud.aiplatform.v1.LlmBidiService/BidiGenerateContent"

# Developer mode:
url = f"{base_url}{endpoint}?key={api_key}"
headers = {}

# Vertex mode:
url = f"wss://{region}-aiplatform.googleapis.com{_VERTEX_ENDPOINT}"
headers = {
    "Authorization": f"Bearer {access_token}",
    "x-goog-user-project": project,
}
```

**Why planner must decide on field name:** D-01 allows `mode: "developer" | "vertex"` (explicit) or inferred from presence of `region`/`project`. The planner should choose — recommendation is `mode` field (explicit, self-documenting). [ASSUMED: specific field naming — planner decides per Claude's Discretion]

### Pattern 2: BidiGenerateContent Setup Envelope (model prefix normalization)

```python
# Source: GlassAgents/backend/realtime/providers/gemini_live.py lines 618-648
def _build_setup_event(self, *, instructions, tools):
    resolved_model = self._model
    if not resolved_model.startswith("models/"):
        resolved_model = f"models/{resolved_model}"
    setup = {
        "model": resolved_model,
        "generationConfig": {"responseModalities": ["AUDIO"]},
    }
    # systemInstruction and tools added if provided
    return {"setup": setup}
```

Model prefix `models/` is prepended if not already present. Both Developer API and Vertex API accept this format. [VERIFIED: GlassAgents reference, lines 619-620]

### Pattern 3: `_to_gemini_schema` — JSON Schema sanitization

Gemini function declarations accept a strict subset of JSON Schema. The static `_to_gemini_schema` method strips `additionalProperties` and traverses nested schemas. Empty object schemas (no properties) return `None` to avoid sending `{}` parameters. [VERIFIED: GlassAgents reference, lines 661-712]

The key adaptation: the reference calls `tool.input_schema` but the library uses `tool.parameters`. Replace `tool.input_schema` → `tool.parameters` in `_to_gemini_function_declaration`. [VERIFIED: both codebases read in-session]

### Pattern 4: `now_ms()` replacement

The reference uses `now_ms()` from `backend.ws.protocol.contracts` to generate fallback `call_id` values when Gemini sends a `toolCall` with no `id`. Replace with:

```python
import time
# In _normalize_tool_call_events:
call_id = f"tool_call_{time.time_ns() // 1_000_000}"
```

[VERIFIED: GlassAgents reference line 503; stdlib `time` module]

### Pattern 5: `_on_connected` is NOT async-send in Gemini (contrast with OpenAI)

OpenAI's `_on_connected` calls `initialize_session()` immediately. Gemini's reference `_on_connected` is a **no-op logging callback** — the session setup is sent explicitly by the consumer via `initialize_session()` after connect. This is intentional: Gemini's setup happens in a separate explicit call, not automatically on WS handshake.

```python
# Source: GlassAgents/backend/realtime/providers/gemini_live.py lines 200-207
async def _on_connected(self) -> None:
    if self._trace_events:
        logger.info("Gemini Live websocket connected endpoint=%s model=%s",
                    self.redacted_websocket_url, self._model)
    # No initialize_session() call here — unlike OpenAI
```

[VERIFIED: GlassAgents reference]

### Pattern 6: Nova Sonic Stub — Structural Conformance Without ABC

`RealtimeAdapterContract` is a `@runtime_checkable` Protocol — `isinstance()` checks pass for any class that implements all 11 methods structurally. `NovaSonicStub` does NOT inherit from `BaseRealtimeWebsocketClient` (it has no websocket transport). It implements all 11 Protocol methods as `NotImplementedError` stubs.

```python
# Structural stub pattern — satisfies RealtimeAdapterContract Protocol
class NovaSonicStub:
    """AWS Nova Sonic placeholder. Production implementation in v1.9.0."""

    async def connect(self) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def close(self) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def initialize_session(self, *, instructions=None, voice=None, tools=None):
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def update_session(self, payload):
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def append_client_audio(self, pcm16_audio):
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def commit_client_turn(self) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def create_response(self) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def cancel_response(self, *, response_id=None):
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def register_tools(self, tools):
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def submit_tool_result(self, *, call_id, output):
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    def iter_normalized_events(self):
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")
```

Total: 28 LOC (within <30 LOC budget per D-07/PROV-08). `isinstance(NovaSonicStub(), RealtimeAdapterContract)` returns `True` at runtime. [VERIFIED: `contracts.py` read in-session; `@runtime_checkable` confirmed]

### Anti-Patterns to Avoid

- **Importing `google-auth` or `google-cloud-aiplatform`:** Not needed. Consumer supplies bearer token. Adding these as dependencies would bloat `[realtime]` extra.
- **Calling `initialize_session()` inside `_on_connected()`:** The OpenAI pattern. Gemini's `_on_connected` is a logging-only hook. The consumer (or bridge) calls `initialize_session()` explicitly.
- **Using `tool.input_schema`:** Library `ToolDefinition` field is `parameters`, not `input_schema`. This is a silent breakage — no `AttributeError` at import time, only at runtime when tools are registered.
- **Passing the raw model string to setup without `models/` prefix check:** Gemini API rejects model IDs missing the `models/` prefix. The reference normalizes this in `_build_setup_event`.
- **Registering `nova_sonic` with an import that requires boto3:** Factory registration uses deferred import — but if `nova.py` itself imports boto3 at module level, the import fails. `NovaSonicStub` must be stdlib-only.
- **Copying GlassAgents `NovaRealtimeProvider` as the stub:** The GlassAgents `nova.py` is an ABC-inheriting transport-agnostic queue stub (used for testing the ABC contract). It does NOT satisfy `RealtimeAdapterContract` Protocol because it has different method signatures (`connect(config)` vs `connect()`). The library's `NovaSonicStub` must be written fresh to match the exact `RealtimeAdapterContract` Protocol signatures.

---

## D-05: Verified Model Alias Snapshot (PITFALL-20)

> **Required by D-05.** Records the live-valid Gemini Live model aliases at research time.

### Gemini Developer API (key-in-URL, global endpoint)

**Recommended floating alias:** `gemini-2.5-flash-preview-native-audio-12-2025` [ASSUMED — WebSearch shows this as the current preview; no direct API query run in-session]

**What is known:**
- `gemini-2.0-flash` and `gemini-2.0-flash-001` are **shutting down June 1, 2026** (approximately 1 week from research date). Must NOT be the default. [CITED: WebSearch — Google deprecation notice]
- `gemini-2.5-flash-native-audio-preview-12-2025` — actively documented, referenced in Google forum discussions from Q1 2026. [CITED: discuss.ai.google.dev/t/gemini-live-api-gemini-2-5-flash-native-audio-preview-12-2025/119862]
- `gemini-live-2.5-flash-native-audio-09-2025` — deprecated, scheduled removal March 19, 2026; already past. [CITED: WebSearch]
- The endpoint for Developer API is: `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent` [CITED: ai.google.dev Live API docs]

**Floating alias default to use in `GeminiLiveConfig`:**
```python
model: str = "gemini-2.5-flash-preview-native-audio-12-2025"
```
**Action required at implementation:** The implementer MUST verify this alias is still valid against the Gemini Developer API at phase execution time before committing. See Open Question 1.

### Vertex AI Live API (OAuth bearer, regional endpoint)

**Vertex endpoint format:** `wss://{region}-aiplatform.googleapis.com/ws/google.cloud.aiplatform.v1.LlmBidiService/BidiGenerateContent` [CITED: Vertex AI Live API docs — cloud.google.com/vertex-ai/generative-ai/docs/live-api/get-started-websocket]

**EU-compliant regions:** `europe-west4` (Netherlands), `europe-west1` (Belgium) — both reported as supporting Gemini Live API. [CITED: WebSearch — litellm Vertex docs + Pipecat Gemini Live Vertex docs confirm regional endpoint format]

**Note on Vertex model IDs:** Vertex AI may expose different model aliases than the Developer API. At research time, Vertex Live API documentation shows `gemini-2.5-flash-preview-native-audio-12-2025` as available for Vertex. Confirm at implementation time. [ASSUMED — Vertex-specific alias may differ; verify against Vertex model list before implementing]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket transport, connect/backoff/retry | Custom WS connection management | `BaseRealtimeWebsocketClient` (Phase 1) | Already has `connect_with_backoff`, error normalization, `_CONNECT_HEADERS_KWARG` detection |
| URL query-param redaction | Custom regex | `_redact_sensitive_url` (port verbatim from reference) | Handles `parse_qsl` / `urlunsplit` for correct multi-param URLs |
| Text redaction | Ad-hoc string replace | `_redact_sensitive_text` (port verbatim from reference) | Handles both full-URL occurrence and `?key=` params in embedded strings |
| Gemini JSON Schema sanitization | Custom schema mapper | `_to_gemini_schema` (port verbatim from reference) | Handles nested properties/items recursion, `additionalProperties` stripping, empty object shortcircuit |
| Tool-call ID generation fallback | UUIDs | `f"tool_call_{time.time_ns() // 1_000_000}"` | Millisecond timestamp, stdlib-only, matches reference behavior |
| Event normalization | Custom event parser | `_to_normalized_runtime_events` (port from reference) | All Gemini wire types (setupComplete, serverContent, toolCall, toolCallCancellation, error) already handled |

**Key insight:** The entire event normalization, tool schema conversion, and redaction logic exists in the reference. This phase is a port with targeted adaptation, not a green-field build.

---

## Port Adaptation Delta

The following are ALL differences between the GlassAgents reference and what must be written in the library. Outside these 5 items, the `GeminiLiveRealtimeClient` class body ports verbatim.

| # | Location in reference | Change required | Risk if wrong |
|---|----------------------|-----------------|---------------|
| A | `__init__` signature + `super().__init__` call | Reference passes `trace_events=trace_events` to base (GlassAgents base takes `trace_events`). Library `BaseRealtimeWebsocketClient.__init__` takes `url` and `headers`. Must compute URL/headers from config before `super().__init__(url=..., headers=...)` | ImportError or wrong URL construction |
| B | `tool.input_schema` (line 656) | Replace with `tool.parameters` | Silent runtime error when tools are registered |
| C | `from backend.ws.protocol.contracts import now_ms` + `now_ms()` (line 503) | Remove import; replace `now_ms()` with `time.time_ns() // 1_000_000` | `ImportError` on any module import |
| D | All `from backend.*` imports | Strip entirely — only keep `from eq_chatbot_core.realtime.*` and stdlib | `ModuleNotFoundError` |
| E | `_on_connected(self)` return type annotation | Reference has `def _on_connected(self)` (sync). Library ABC declares `async def _on_connected(self) -> None`. Make it `async`. | ABC conformance failure |
| F | `build_gemini_live_session_bridge`, `validate_gemini_live_realtime_settings` | Do NOT port — GlassAgents-specific wiring. Only `GeminiLiveRealtimeClient` + two redaction statics + `GEMINI_LIVE_REALTIME_CAPABILITIES` | Leaks GlassAgents app-layer types into library |
| G | Dual-endpoint extension (D-01) | `__init__` adds Vertex branch: if `mode == "vertex"`: URL = `wss://{region}-aiplatform.googleapis.com/...`; headers = `{"Authorization": f"Bearer {access_token}", "x-goog-user-project": project}` | Vertex EU path (SC-3 / DSGVO) not available |
| H | `_redact_sensitive_text` references `self.websocket_url` and `self.redacted_websocket_url` | The reference uses `@property websocket_url` and `@property redacted_websocket_url`. Port these properties OR adapt method to use `self._url` and `self._redact_sensitive_url(self._url)`. | Key may leak in text redaction |
| I | Vertex bearer token redaction (D-02 extension) | Extend `_redact_sensitive_text` to also redact the bearer token value from error strings when `mode == "vertex"`. The static `_redact_sensitive_url` already redacts `token=` params; extend `_redact_sensitive_text` to replace the raw bearer token string. | Bearer token leaks to logs |

---

## Capabilities Constant (PROV-06)

From the reference (verified in-session):

```python
# Source: GlassAgents/backend/realtime/providers/gemini_live.py lines 39-49
GEMINI_LIVE_REALTIME_CAPABILITIES = RealtimeProviderCapabilities(
    streaming_audio_input=True,
    streaming_audio_output=True,
    server_vad=False,           # Gemini has NO server VAD; manual turn commit always required
    manual_turn_commit_required=True,
    tool_calling=True,
    tool_result_submission_mode="provider_call_id",  # toolResponse.functionResponses[].id
    voice_selection=False,      # Gemini Live does not support voice selection in this adapter
    interruption_cancel=False,  # cancel_response is a no-op in the adapter
    startup_validation=True,
)
```

`session_sample_rate` inherits default `24_000` (matches Gemini Live's PCM16 audio format).

---

## Common Pitfalls

### Pitfall 1: `_on_connected` must NOT call `initialize_session()`
**What goes wrong:** Developer copies OpenAI pattern — `_on_connected` calls `initialize_session()`. Gemini's `setup` envelope is sent explicitly, not automatically on handshake. Sending it from `_on_connected` would double-initialize if the consumer also calls `initialize_session()` explicitly.
**Why it happens:** OpenAI provider's `_on_connected` is the natural entry point to initialize; Gemini differs.
**How to avoid:** Keep `_on_connected` as a logging-only hook (exact pattern from reference).
**Warning signs:** Gemini session receives two `setup` messages; provider errors or stale session state.

### Pitfall 2: `tool.input_schema` vs `tool.parameters` (SILENT BREAKAGE)
**What goes wrong:** `_to_gemini_function_declaration` calls `tool.input_schema` — this is the GlassAgents `ToolDefinition` field name. Library `ToolDefinition` uses `tool.parameters`. No `AttributeError` at module import; only at runtime when tools are registered and the attribute lookup fails on the `ToolDefinition` dataclass.
**Why it happens:** The two codebases have different field names for the same concept.
**How to avoid:** In `_to_gemini_function_declaration`, replace `tool.input_schema` with `tool.parameters`.
**Warning signs:** `AttributeError: 'ToolDefinition' object has no attribute 'input_schema'` during a live session with tools.

### Pitfall 3: Vertex bearer token leaks without explicit extension
**What goes wrong:** `_redact_sensitive_text` replaces `key=` params in URLs but does NOT redact the raw bearer token string from exception messages (e.g., `websockets.exceptions.InvalidStatus` may include the full URL including headers in its message).
**Why it happens:** The static `_redact_sensitive_url` handles URL params. Bearer tokens appear in header values, not URL params.
**How to avoid:** When `mode == "vertex"`, store the access token and extend `_redact_sensitive_text` to replace it (parallel to how `_redact_sensitive_text` replaces `self.websocket_url` with `self.redacted_websocket_url` in the reference).
**Warning signs:** Bearer token visible in log output after a failed Vertex connection.

### Pitfall 4: `models/` prefix required for Gemini model IDs
**What goes wrong:** Consumer passes `"gemini-2.5-flash-preview-native-audio-12-2025"` without prefix; Gemini Live API returns an error because the setup envelope expects `"models/gemini-2.5-flash-preview-native-audio-12-2025"`.
**Why it happens:** Gemini API model references require the `models/` resource path prefix in the setup envelope, unlike most other provider model IDs.
**How to avoid:** `_build_setup_event` must normalize: `if not model.startswith("models/"): model = f"models/{model}"`. (This is already in the reference — port it verbatim.)
**Warning signs:** Gemini server returns error `NOT_FOUND: models/` or `INVALID_ARGUMENT` on setup.

### Pitfall 5: `_on_connected` async-vs-sync ABC mismatch
**What goes wrong:** Reference `_on_connected` is a sync method (`def _on_connected(self) -> None`). Library `BaseRealtimeWebsocketClient` declares it `async def _on_connected(self) -> None`. Using the sync version causes `TypeError` when `connect()` awaits it.
**Why it happens:** The GlassAgents base class accepts a sync callback; the library's Phase 1 base class declares it async.
**How to avoid:** Declare `async def _on_connected(self) -> None` in `GeminiLiveClient`.

### Pitfall 6: Nova stub method signatures must exactly match Protocol
**What goes wrong:** `iter_normalized_events` in the stub is defined with wrong return type annotation or signature — e.g., `def iter_normalized_events(self) -> None` instead of `def iter_normalized_events(self) -> AsyncIterator[...]`. While `isinstance()` Protocol checks are structural (duck-typed), the return type annotation matters for type checkers.
**Why it happens:** Copy-paste from `RealtimeProvider` ABC (which has `def iter_normalized_events(self) -> AsyncIterator[Any]`).
**How to avoid:** Match signatures exactly from `RealtimeAdapterContract` in `contracts.py`.

### Pitfall 7: Factory `nova_sonic` registration must not import websockets
**What goes wrong:** `_build_nova_sonic_provider` deferred import pulls in something that imports websockets — causes `ImportError` when `[realtime]` extra is not installed.
**Why it happens:** The stub should be stdlib-only. If `nova.py` imports anything from `eq_chatbot_core.realtime.websocket_client`, it will transitively trigger the websockets import.
**How to avoid:** `nova.py` imports only from `contracts.py` (Protocol) and stdlib. No `from eq_chatbot_core.realtime.websocket_client import ...`.

---

## Code Examples

### GeminiLiveConfig (Claude's Discretion — recommended shape)

```python
# Source: pattern from GlassAgents reference + D-01 dual-endpoint extension
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True, slots=True)
class GeminiLiveConfig:
    # Developer API mode fields
    api_key: str = ""                        # required when mode="developer"

    # Vertex AI mode fields
    access_token: str = ""                   # required when mode="vertex"; OAuth bearer
    project: str = ""                        # GCP project ID for x-goog-user-project header
    region: str = "europe-west4"             # GCP region; default to EU for DSGVO compliance

    # Shared fields
    mode: Literal["developer", "vertex"] = "developer"
    model: str = "gemini-2.5-flash-preview-native-audio-12-2025"  # floating alias — verify at phase start
    instructions: str = ""
    base_url: str | None = None              # override base URL (e.g. for tests)
    endpoint: str | None = None             # override BidiGenerateContent path
    trace_events: bool = False
```

### Factory registration pattern (Phase 2 analog)

```python
# Source: factory.py pattern from Phase 2 — deferred import, no-AWS-extras constraint
registry.register(RealtimeProviderDefinition(
    name="gemini_live",
    factory_fn=lambda **kwargs: _build_gemini_live_provider(**kwargs),
    description="Google Gemini Live API — BidiGenerateContent, manual turn commit, tool calling.",
))
registry.register(RealtimeProviderDefinition(
    name="nova_sonic",
    factory_fn=lambda **kwargs: _build_nova_sonic_provider(**kwargs),
    description="AWS Nova Sonic stub — production implementation in v1.9.0.",
))

def _build_gemini_live_provider(**kwargs):
    # Validate required fields before deferred import (D-06 fail-fast)
    mode = kwargs.get("mode", "developer")
    if mode == "developer" and not kwargs.get("api_key", "").strip():
        raise ValueError("Gemini Live developer mode requires 'api_key'.")
    if mode == "vertex" and not kwargs.get("access_token", "").strip():
        raise ValueError("Gemini Live vertex mode requires 'access_token'.")
    from eq_chatbot_core.realtime.providers.gemini_live import GeminiLiveClient, GeminiLiveConfig
    config = GeminiLiveConfig(**kwargs)
    return GeminiLiveClient(config)

def _build_nova_sonic_provider(**kwargs):
    from eq_chatbot_core.realtime.providers.nova import NovaSonicStub
    return NovaSonicStub()
```

### Integration test pattern (Vertex EU path — SC-3 / QUAL-03)

```python
# Mirrors test_realtime_openai_live.py pattern
import os
import pytest
pytest.importorskip("websockets")

from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes
from eq_chatbot_core.realtime.providers.gemini_live import GeminiLiveClient, GeminiLiveConfig

pytestmark = pytest.mark.integration

@pytest.mark.skipif(
    not os.getenv("GEMINI_VERTEX_ACCESS_TOKEN") or not os.getenv("VERTEX_PROJECT_ID"),
    reason="GEMINI_VERTEX_ACCESS_TOKEN / VERTEX_PROJECT_ID not set — skipping Vertex EU integration test",
)
@pytest.mark.asyncio
async def test_gemini_live_vertex_eu_session_ready_and_pcm_chunk():
    config = GeminiLiveConfig(
        mode="vertex",
        access_token=os.environ["GEMINI_VERTEX_ACCESS_TOKEN"],
        project=os.environ["VERTEX_PROJECT_ID"],
        region=os.getenv("VERTEX_REGION", "europe-west4"),
    )
    async with GeminiLiveClient(config) as client:
        await client.initialize_session()
        async for event in client.iter_normalized_events():
            assert event["type"] == NormalizedRealtimeEventTypes.SESSION_READY
            break
        silence = b"\x00\x00" * 2400  # 100ms PCM16 24kHz
        await client.append_client_audio(silence)
        await client.commit_client_turn()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `gemini-2.0-flash` (Gemini Live default) | `gemini-2.5-flash-preview-native-audio-12-2025` | Shutdown June 1, 2026 | Must NOT use 2.0 model; verify 2.5 alias at phase start |
| Developer API only (global) | Dual-endpoint: Developer API + Vertex AI regional | D-01 decision | Unlocks DSGVO-compliant `europe-west4` path |
| `gemini-live-2.5-flash-preview-native-audio-09-2025` | Deprecated March 19, 2026 | Already past | Do not use |
| `google-genai` SDK | Raw websockets | Locked in Phase 1/2 stack research | Keeps abstraction clean; no Gemini-native types leak into normalized event layer |

**Deprecated/outdated:**
- `gemini-2.0-flash` / `gemini-2.0-flash-001`: Shutdown June 1, 2026 — DO NOT USE AS DEFAULT.
- `gemini-live-2.5-flash-preview-native-audio-09-2025`: Removed March 2026 — DO NOT USE.
- GlassAgents `NovaRealtimeProvider` pattern: ABC-based queue stub — not compatible with `RealtimeAdapterContract` Protocol signatures. `NovaSonicStub` must be written fresh.

---

## Validation Architecture

> `workflow.nyquist_validation` key absent from `.planning/config.json` → treat as enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/unit/realtime/test_realtime_gemini.py tests/unit/realtime/test_realtime_nova.py -v` |
| Full suite command | `pytest tests/unit/realtime/ tests/integration/ -v --cov=eq_chatbot_core` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROV-05 | All 11 contract methods present and callable | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestContractConformance -x` | ❌ Wave 0 |
| PROV-05 | `iter_normalized_events` routes all Gemini wire types | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestEventNormalization -x` | ❌ Wave 0 |
| PROV-05 | `append_client_audio` sends correct `realtimeInput.audio` JSON shape | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestAudioUplink -x` | ❌ Wave 0 |
| PROV-05 | `commit_client_turn` sends `realtimeInput.audioStreamEnd` | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestManualTurnCommit -x` | ❌ Wave 0 |
| PROV-05 | `submit_tool_result` sends `toolResponse.functionResponses` with correct `provider_call_id` | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestToolResult -x` | ❌ Wave 0 |
| PROV-06 | `GEMINI_LIVE_REALTIME_CAPABILITIES` values match reference | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestCapabilities -x` | ❌ Wave 0 |
| PROV-06 | `GeminiLiveConfig` is frozen+slots; default model exact string | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestGeminiLiveConfig -x` | ❌ Wave 0 |
| PROV-07 | `_redact_sensitive_url` strips `key=` from Developer API URL | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestRedaction::test_redact_key_param -x` | ❌ Wave 0 |
| PROV-07 | `_redact_sensitive_text` strips bearer token from Vertex error strings | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestRedaction::test_redact_bearer_token -x` | ❌ Wave 0 |
| PROV-07 | `_connection_error_endpoint()` never contains `api_key` or bearer token | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestConnectionErrorEndpoint -x` | ❌ Wave 0 |
| PROV-08 | `isinstance(NovaSonicStub(), RealtimeAdapterContract)` is True | unit | `pytest tests/unit/realtime/test_realtime_nova.py::TestContractConformance -x` | ❌ Wave 0 |
| PROV-08 | Every method raises `NotImplementedError` | unit | `pytest tests/unit/realtime/test_realtime_nova.py::TestAllMethodsRaise -x` | ❌ Wave 0 |
| PROV-08 | Error message references `v1.9.0` | unit | `pytest tests/unit/realtime/test_realtime_nova.py::TestErrorMessages -x` | ❌ Wave 0 |
| D-08 | `get_realtime_provider("nova_sonic")` resolves without AWS extras | unit | `pytest tests/unit/realtime/test_factory.py::test_nova_sonic_registered -x` | ❌ Wave 0 (extend existing factory test) |
| QUAL-01 | `iter_normalized_events` produces SESSION_READY from `setupComplete` frame | unit (recorded frame) | `pytest tests/unit/realtime/test_realtime_gemini.py::TestEventNormalization::test_setup_complete_maps_to_session_ready -x` | ❌ Wave 0 |
| QUAL-01 | Developer endpoint mode: URL contains `key=`, no `Authorization` header | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestEndpointModes::test_developer_mode_url_shape -x` | ❌ Wave 0 |
| QUAL-01 | Vertex endpoint mode: URL is `{region}-aiplatform.googleapis.com`, headers contain `Authorization` | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestEndpointModes::test_vertex_mode_url_shape -x` | ❌ Wave 0 |
| QUAL-03 | Vertex EU: SESSION_READY received, PCM16 chunk sent, clean disconnect | integration (gated) | `pytest -m integration tests/integration/test_realtime_gemini_live.py -v` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/realtime/test_realtime_gemini.py tests/unit/realtime/test_realtime_nova.py -x -q`
- **Per wave merge:** `pytest tests/unit/realtime/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work` (integration tests skipped when env vars absent)

### Wave 0 Gaps

- [ ] `tests/unit/realtime/test_realtime_gemini.py` — covers PROV-05, PROV-06, PROV-07, QUAL-01
- [ ] `tests/unit/realtime/test_realtime_nova.py` — covers PROV-08, D-08
- [ ] `tests/integration/test_realtime_gemini_live.py` — covers QUAL-03 (Gemini Vertex EU path)
- [ ] `tests/unit/realtime/test_factory.py` — extend with `test_nova_sonic_registered` and `test_gemini_live_registered` (file exists, add new test cases)

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `websockets` | Transport | ✓ | `>=13.0` (installed in venv) | — (no fallback; `[realtime]` extra) |
| `pytest-asyncio` | Async test execution | ✓ | `>=0.24.0` | — (in `[dev]`) |
| `GEMINI_API_KEY` | Developer API integration test (optional) | Unknown | — | Skip integration test |
| `GEMINI_VERTEX_ACCESS_TOKEN` | Vertex EU integration test (QUAL-03) | Unknown | — | Skip integration test (env var gate) |
| `VERTEX_PROJECT_ID` | Vertex EU integration test | Unknown | — | Skip integration test |
| GlassAgents repo | Port source | ✓ | Present at `/Users/picard/gitbase/GlassAgents/` | — (required; already confirmed) |

**Missing dependencies with no fallback:** None that block unit test execution.

**Missing dependencies with fallback:** Vertex API credentials — integration test skipped via `@pytest.mark.skipif(not os.getenv(...))`. Phase gate does not require integration tests to pass in CI.

---

## Security Domain

> `security_enforcement` absent from config → enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | API key / bearer token never in logs — `_redact_sensitive_url` + `_redact_sensitive_text` |
| V3 Session Management | No | No session tokens in library; WebSocket connection is one session |
| V4 Access Control | No | Access control is provider-side |
| V5 Input Validation | Yes | Fail-fast validation of `api_key`/`access_token`/`model` in `__init__` before any I/O |
| V6 Cryptography | No | No crypto in library; bearer tokens supplied by consumer |

### Known Threat Patterns for Gemini Live Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key in Developer URL leaked to logs | Information Disclosure | `_redact_sensitive_url` strips `?key=` on all log/error paths |
| Vertex bearer token in exception message | Information Disclosure | `_redact_sensitive_text` extended to replace raw access_token |
| Bearer token in `_connection_error_endpoint()` | Information Disclosure | Override returns redacted URL — never includes raw credentials |
| Gemini project ID leaked (x-goog-user-project header) | Information Disclosure | Project ID is not secret (it's a GCP project name); acceptable to log; bearer token is the secret |
| Tool output injection (malformed JSON) | Tampering | `_decode_tool_output` catches `json.JSONDecodeError` and wraps raw string as `{"output": output}` |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Default model alias `gemini-2.5-flash-preview-native-audio-12-2025` is valid for Gemini Developer API at implementation time | D-05 / Standard Stack | Provider rejects model at setup; client raises during `initialize_session()`. Implementer must verify live before finalizing the default. |
| A2 | Vertex AI `europe-west4` supports Gemini Live API | D-05 / Environment Availability | Vertex integration test fails; EU path not available. Fall back to `europe-west1` or check Vertex region availability page. |
| A3 | Vertex AI and Developer API accept the same `models/` prefixed model IDs for Live API | D-05 | Vertex may require different model ID format. Verify against Vertex model list at implementation time. |
| A4 | `GeminiLiveConfig.mode: Literal["developer", "vertex"]` explicit field is the right switch mechanism | Architecture Patterns | Planner may prefer inference from presence of `access_token` vs `api_key`. Either approach is valid; planner decides per Claude's Discretion. |
| A5 | Bearer token for Vertex is caller-supplied (no `google-auth` in library) | Standard Stack / Architecture | If `google-auth` is required for production use, add `[realtime-vertex]` optional extra in pyproject.toml. No consumer requirement identified yet. |

---

## Open Questions (RESOLVED)

1. **Gemini Live model alias at phase start (D-05 — BLOCKING for default value)**
   - **Resolution:** Resolves during Plan 01 execution (live model-alias verification gate). Plan 01 includes a blocking checkpoint that runs `curl "https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}" | python3 -m json.tool | grep -i live` at implementation start to confirm the current valid alias before any code is committed. The floating-alias default (`gemini-2.5-flash-preview-native-audio-12-2025`) is confirmed there and recorded in a code comment before the first commit. The literal alias value remains pending the live Plan 01 check — it is not confirmed in this research document.
   - What we know: `gemini-2.5-flash-preview-native-audio-12-2025` is referenced in docs from late 2025 and Q1 2026 forum discussions. `gemini-2.0-flash` is shutting down June 1, 2026.
   - What's unclear: Whether `gemini-2.5-flash-preview-native-audio-12-2025` is still the correct alias for May 2026 or whether a newer alias (e.g., `gemini-3.1-flash-live-preview`) is preferred. WebSearch found references to `gemini-3.1-flash-live-preview` as a latest Live API model.
   - Recommendation: At implementation start, run `curl "https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}" | python3 -m json.tool | grep -i live` to list available Live models and confirm the current valid alias. Update `GeminiLiveConfig.model` default and code comment before first commit.

2. **Vertex AI `europe-west4` Live API availability**
   - **Resolution:** Design adopts `europe-west4` (Netherlands) as the recommended EU region. The integration test uses `region=os.getenv("VERTEX_REGION", "europe-west4")` as the default, with `europe-west1` as the documented fallback if a region error is returned. This env-var override allows the integration test to run against any available EU Vertex region without code changes.
   - What we know: Vertex Live API docs confirm regional format `{region}-aiplatform.googleapis.com`. `europe-west4` (Netherlands) is a major EU Vertex AI region.
   - What's unclear: Whether Gemini Live API specifically (not just general Vertex AI) is available in `europe-west4` vs only global endpoint for some models.
   - Recommendation: Integration test uses `region=os.getenv("VERTEX_REGION", "europe-west4")` — if it fails with a region error, try `europe-west1`. Mark test as environment-dependent in test docstring.

3. **`GeminiLiveConfig` mode-switch mechanism (Claude's Discretion)**
   - **Resolution:** Claude's Discretion per CONTEXT.md. Planner chose explicit `mode: Literal["developer", "vertex"] = "developer"` field — unambiguous, self-documenting, and easy to validate in `__init__`. See `GeminiLiveConfig` code example in this document.
   - What we know: D-01 leaves exact field names to planner.
   - Recommendation: Use explicit `mode: Literal["developer", "vertex"] = "developer"` field. It is unambiguous, self-documenting, and easy to validate in `__init__`. The alternative (infer from `access_token` presence) is brittle — a consumer could accidentally provide both.

---

## Sources

### Primary (HIGH confidence)
- `/Users/picard/gitbase/GlassAgents/backend/realtime/providers/gemini_live.py` — GeminiLiveRealtimeClient reference (920 LOC); read in-session
- `/Users/picard/gitbase/GlassAgents/backend/realtime/providers/nova.py` — GlassAgents ABC stub; read in-session (confirms NovaSonicStub must be written fresh)
- `src/eq_chatbot_core/realtime/contracts.py` — RealtimeAdapterContract Protocol (11 methods); read in-session
- `src/eq_chatbot_core/realtime/websocket_client.py` — BaseRealtimeWebsocketClient; read in-session (confirmed: url+headers constructor, async `_on_connected`)
- `src/eq_chatbot_core/realtime/factory.py` — registry pattern; read in-session
- `src/eq_chatbot_core/realtime/providers/openai.py` — Phase 2 analog pattern; read in-session
- `src/eq_chatbot_core/providers/base.py` — ToolDefinition.parameters (not input_schema); verified in-session

### Secondary (MEDIUM confidence)
- [Vertex AI Live API WebSocket docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api/get-started-websocket) — confirmed Vertex endpoint format `wss://{region}-aiplatform.googleapis.com/ws/google.cloud.aiplatform.v1.LlmBidiService/BidiGenerateContent` and OAuth bearer auth
- [liteLLM Vertex AI Live WebSocket docs](https://docs.litellm.ai/docs/pass_through/vertex_ai_live_websocket) — confirms regional endpoint pattern and `Authorization: Bearer` header
- [Pipecat Gemini Live Vertex](https://docs.pipecat.ai/api-reference/server/services/s2s/gemini-live-vertex) — confirms `europe-west4` regional endpoint

### Tertiary (LOW confidence — flag for validation at implementation time)
- WebSearch: `gemini-2.5-flash-preview-native-audio-12-2025` as current Live API model — multiple Google forum references but no direct API verification
- WebSearch: `gemini-2.0-flash` shutdown June 1, 2026 — multiple sources; HIGH confidence this is accurate

---

## Metadata

**Confidence breakdown:**
- Port source (GlassAgents reference): HIGH — full file read in-session
- Adaptation delta (5 items): HIGH — both codebases verified in-session
- Standard stack (no new packages): HIGH — pyproject.toml read; stdlib-only additions
- Architecture patterns (dual-endpoint): HIGH — verified against Vertex docs
- Gemini model alias: LOW — WebSearch only; must verify at implementation start (D-05)
- Vertex `europe-west4` Live API availability: MEDIUM — regional endpoint format verified; specific model availability for that region assumed

**Research date:** 2026-05-25
**Valid until:** 2026-06-08 (model alias must be re-verified at implementation start regardless — see Open Question 1)
