# Phase 2: OpenAI Realtime Provider - Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 5 (3 new, 2 modified)
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/eq_chatbot_core/realtime/providers/openai.py` | provider (adapter) | streaming / event-driven | `GlassAgents/backend/realtime/client.py` + Phase 1 `realtime/websocket_client.py` | exact (port target) |
| `src/eq_chatbot_core/realtime/factory.py` | registry / factory | request-response | Phase 1 `realtime/factory.py` (self-extension) | exact |
| `src/eq_chatbot_core/realtime/__init__.py` | re-export module | — | Phase 1 `realtime/__init__.py` (self-extension) | exact |
| `tests/unit/realtime/test_realtime_openai.py` | test (unit) | event-driven | `tests/unit/realtime/conftest.py` + Phase 1 test patterns | role-match |
| `tests/integration/test_realtime_openai_live.py` | test (integration) | streaming | `tests/unit/realtime/conftest.py` fixture model, skip pattern | role-match |

---

## Pattern Assignments

### `src/eq_chatbot_core/realtime/providers/openai.py` (provider, streaming/event-driven)

**Primary analog:** `GlassAgents/backend/realtime/client.py` (port target, lines 1–391)
**Secondary analog:** `src/eq_chatbot_core/realtime/websocket_client.py` (Phase 1 base class)

---

#### Imports pattern

Port from GlassAgents `client.py` lines 1–27, adapted to library import paths:

```python
# src/eq_chatbot_core/realtime/providers/openai.py
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Sequence
from urllib.parse import urlencode

from eq_chatbot_core.realtime.abc import RealtimeProvider
from eq_chatbot_core.realtime.contracts import (
    INPUT_AUDIO_SAMPLE_RATE,
    NormalizedRealtimeEvent,
    NormalizedRealtimeEventTypes,
    RealtimeProviderCapabilities,
)
from eq_chatbot_core.realtime.websocket_client import BaseRealtimeWebsocketClient
from eq_chatbot_core.providers.base import ToolDefinition

_logger = logging.getLogger(__name__)
OUTPUT_AUDIO_SAMPLE_RATE: int = 24_000  # matches INPUT_AUDIO_SAMPLE_RATE; both 24kHz PCM16
```

Key divergences from GlassAgents imports:
- Replace `backend.realtime.*` with `eq_chatbot_core.realtime.*`
- Replace `backend.tools.contracts.ToolDefinition` with `eq_chatbot_core.providers.base.ToolDefinition`
- Drop GlassAgents-internal `RealtimeReceiveError`/`RealtimeSendError` — not in Phase 1 error hierarchy

---

#### Config dataclass pattern

Source: `GlassAgents/backend/realtime/providers/openai.py` lines 16–26 + RESEARCH.md §SC-2:

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
    include_turn_detection: bool = True  # see PITFALL-28 comment in _build_session_update_event
```

Analog: `src/eq_chatbot_core/providers/base.py` lines 68–79 (`ToolDefinition`) — same `frozen=True, slots=True` pattern.

---

#### Capabilities constant pattern

Source: `GlassAgents/backend/realtime/providers/openai.py` lines 16–26:

```python
OPENAI_REALTIME_CAPABILITIES = RealtimeProviderCapabilities(
    streaming_audio_input=True,
    streaming_audio_output=True,
    server_vad=True,                          # provider SUPPORTS VAD (hardware capability, static)
    manual_turn_commit_required=False,        # when VAD active (default); see PITFALL-28
    tool_calling=True,
    tool_result_submission_mode="conversation_item",
    voice_selection=True,
    interruption_cancel=True,
    startup_validation=True,
)
```

Analog: `src/eq_chatbot_core/realtime/contracts.py` lines 55–68 (`RealtimeProviderCapabilities` dataclass — all fields must be passed).

---

#### Class declaration and `__init__` pattern

Source: `GlassAgents/backend/realtime/client.py` lines 38–67, **adapted** for Phase 1 base class constructor.

CRITICAL DIVERGENCE — Phase 1 `BaseRealtimeWebsocketClient.__init__` takes `url: str, headers: dict[str, str] | None` (not `trace_events`). The port computes URL and headers before calling `super()`:

```python
@dataclass(frozen=True)
class RealtimeAudioEventNames:
    """Canonical audio event names — use as named constants, not raw strings."""
    delta: str = "response.output_audio.delta"
    done: str = "response.output_audio.done"


class OpenAIRealtimeClient(BaseRealtimeWebsocketClient, RealtimeProvider):
    """OpenAI Realtime API provider — GPT speech-to-speech, server VAD, tool calling."""

    def __init__(self, config: OpenAIRealtimeConfig, *, trace_events: bool = False) -> None:
        # Validate eagerly (D-03: fail fast with library-native exception)
        if not config.api_key.strip():
            raise ValueError("OpenAIRealtimeConfig.api_key must be non-empty")
        if not config.model.strip():
            raise ValueError("OpenAIRealtimeConfig.model must be non-empty")

        # Phase 1 base class takes url + headers (NOT trace_events — see RESEARCH.md Pitfall 1)
        url = f"wss://api.openai.com/v1/realtime?{urlencode({'model': config.model})}"
        headers = {"Authorization": f"Bearer {config.api_key}"}
        super().__init__(url=url, headers=headers)

        self._config = config
        self._trace_events = trace_events          # not in base class — store on subclass
        self.audio_event_names = RealtimeAudioEventNames()
        self._input_audio_append_count: int = 0
        self._output_audio_delta_count: int = 0
```

Analog: `src/eq_chatbot_core/realtime/websocket_client.py` lines 103–106 (`BaseRealtimeWebsocketClient.__init__`).

---

#### Abstract method overrides (Phase 1 compliance)

Source: `src/eq_chatbot_core/realtime/websocket_client.py` lines 113–133 (abstract declarations);
`GlassAgents/backend/realtime/client.py` lines 87–93 (`_on_connected` implementation).

All three abstract methods MUST be overridden or `TypeError` at construction time:

```python
async def _on_connected(self) -> None:
    """Initialize OpenAI session immediately after WebSocket handshake."""
    await self.initialize_session()

async def _on_message(self, raw: str) -> None:
    """Not used in iter_normalized_events flow — required for ABC conformance only."""
    pass  # Production loop uses iter_events() / iter_normalized_events()

def _connection_error_endpoint(self) -> str:
    """Return URL without API key for error messages (PITFALL-04 security rule)."""
    return f"wss://api.openai.com/v1/realtime?model={self._config.model}"
```

Analog: `src/eq_chatbot_core/realtime/websocket_client.py` lines 113–133 (abstract contract).
Note: NEVER embed `self._config.api_key` or `self._headers` in the returned string.

---

#### PITFALL-28: VAD/turn-detection reconciliation comment (SC-1 mandatory)

This block comment MUST appear at the top of `_build_session_update_event()`. It is a
success criterion (SC-1) and must be present before any implementation wave begins.

Source: RESEARCH.md §PITFALL-28; `GlassAgents/backend/realtime/client.py` lines 334–339;
`GlassAgents/backend/realtime/providers/openai.py` lines 16–26.

```python
def _build_session_update_event(self, *, instructions, voice, tools):
    # PITFALL-28 RESOLUTION:
    #
    # OPENAI_REALTIME_CAPABILITIES.server_vad = True
    #   This reflects OpenAI's HARDWARE CAPABILITY — the provider natively supports
    #   server-side Voice Activity Detection. This flag is STATIC and IMMUTABLE.
    #   It answers: "Does this provider have VAD hardware?" → YES, always.
    #
    # OpenAIRealtimeConfig.include_turn_detection = True  (default)
    #   This is a SESSION-LEVEL OPT-IN. When True, the session.update payload
    #   activates VAD via the turn_detection block. When False, the key is
    #   OMITTED entirely — the VAD hardware exists but is NOT activated.
    #   The caller must then invoke commit_client_turn() manually.
    #
    # These are DIFFERENT ABSTRACTIONS at DIFFERENT LEVELS:
    #   server_vad=True           → "The provider CAN do VAD" (static)
    #   include_turn_detection=True → "This session USES VAD" (per-session config)
    #
    # server_vad=True with include_turn_detection=False is a valid intentional state:
    # consumer wants manual turn control on a VAD-capable provider.
    #
    # Reference: GlassAgents/backend/realtime/client.py lines 334-339,
    #            GlassAgents/backend/realtime/providers/openai.py lines 16-26
    ...
```

---

#### `_build_session_update_event` pattern

Source: `GlassAgents/backend/realtime/client.py` lines 301–347:

```python
def _build_session_update_event(
    self,
    *,
    instructions: str | None,
    voice: str | None,
    tools: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    # [PITFALL-28 comment block here — see above]
    resolved_instructions = self._config.instructions if instructions is None else instructions
    resolved_voice = self._config.voice if voice is None else voice

    session: dict[str, Any] = {
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
    if self._config.include_turn_detection:  # PITFALL-28: session-level opt-in
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

---

#### `_normalize_tools` — inline ToolDefinition conversion (Option 2, no `to_openai_tool()`)

Source: `GlassAgents/backend/realtime/client.py` lines 287–299 (reference calls `to_openai_tool()`
which does not exist on Phase 1 `ToolDefinition` — RESEARCH.md Pattern 6 resolves this via inline):

```python
@staticmethod
def _normalize_tools(
    tools: Sequence[ToolDefinition | dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    normalized: list[dict[str, Any]] = []
    for tool in tools:
        if isinstance(tool, ToolDefinition):
            # Inline conversion — Phase 1 ToolDefinition has no to_openai_tool() method.
            # Option 2 per RESEARCH.md Pattern 6: keep Phase 2 self-contained.
            normalized.append({
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "strict": tool.strict,
            })
        else:
            normalized.append(dict(tool))
    return normalized
```

---

#### Event normalization pipeline (two-stage)

Source: `GlassAgents/backend/realtime/client.py` lines 134–154 (stage 1), lines 220–285 (stage 2):

```python
# Stage 1 — wire alias normalization (response.audio.* → response.output_audio.*)
def normalize_event(self, event: dict[str, Any]) -> dict[str, Any]:
    event_type = event.get("type")
    if not isinstance(event_type, str):
        return event
    normalized_type = self.normalize_audio_event_type(event_type)
    if normalized_type == event_type:
        return event
    normalized = dict(event)
    normalized["type"] = normalized_type
    return normalized

def normalize_audio_event_type(self, event_type: str) -> str:
    if event_type == "response.audio.delta":
        return self.audio_event_names.delta   # "response.output_audio.delta"
    if event_type == "response.audio.done":
        return self.audio_event_names.done    # "response.output_audio.done"
    return event_type

# Stage 2 — canonical wire types → NormalizedRealtimeEventTypes constants
def _to_normalized_runtime_event(self, event: dict[str, Any]) -> NormalizedRealtimeEvent:
    event_type = event.get("type")
    if not isinstance(event_type, str):
        return {"type": NormalizedRealtimeEventTypes.UNHANDLED, "payload": event,
                "source": "missing_type", "raw": event}

    if event_type in {"session.created", "session.updated"}:
        normalized_type = NormalizedRealtimeEventTypes.SESSION_READY
    elif event_type == self.audio_event_names.delta:
        normalized_type = NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA
    elif event_type == self.audio_event_names.done:
        normalized_type = NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DONE
    elif event_type == "response.done":
        normalized_type = NormalizedRealtimeEventTypes.RESPONSE_DONE
    elif event_type == "input_audio_buffer.speech_started":
        normalized_type = NormalizedRealtimeEventTypes.INPUT_SPEECH_STARTED
    elif event_type == "input_audio_buffer.speech_stopped":
        normalized_type = NormalizedRealtimeEventTypes.INPUT_SPEECH_STOPPED
    elif event_type == "response.created":
        normalized_type = NormalizedRealtimeEventTypes.RESPONSE_CREATED
    elif event_type == "input_audio_buffer.committed":
        normalized_type = NormalizedRealtimeEventTypes.INPUT_AUDIO_COMMITTED
    elif event_type == "error":
        normalized_type = NormalizedRealtimeEventTypes.ERROR
    elif event_type == "response.function_call_arguments.done":
        # PITFALL-05: custom payload shape — must include item sub-dict + top-level fields
        return {
            "type": NormalizedRealtimeEventTypes.TOOL_CALL_COMPLETED,
            "payload": {
                "type": "response.output_item.done",
                "item": {
                    "type": "function_call",
                    "id": event.get("item_id"),
                    "call_id": event.get("call_id"),
                    "name": event.get("name"),
                    "arguments": event.get("arguments"),
                },
                "call_id": event.get("call_id"),
                "name": event.get("name"),
                "arguments": event.get("arguments"),
                "response_id": event.get("response_id"),
            },
            "source": event_type,
            "raw": event,
        }
    elif event_type == "response.output_item.done":
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "function_call":
            normalized_type = NormalizedRealtimeEventTypes.TOOL_CALL_COMPLETED
        else:
            normalized_type = NormalizedRealtimeEventTypes.UNHANDLED
    else:
        normalized_type = NormalizedRealtimeEventTypes.UNHANDLED

    return {"type": normalized_type, "payload": event, "source": event_type, "raw": event}
```

---

#### 11-method contract surface (simple methods)

Source: `GlassAgents/backend/realtime/client.py` lines 156–214:

```python
async def initialize_session(
    self,
    *,
    instructions: str | None = None,
    voice: str | None = None,
    tools: list[Any] | None = None,
) -> None:
    event = self._build_session_update_event(
        instructions=instructions,
        voice=voice,
        tools=self._normalize_tools(tools),
    )
    await self.send_json(event)

async def update_session(self, payload: dict[str, Any]) -> None:
    await self.send_json(payload)

async def append_client_audio(self, pcm16_audio: bytes) -> None:
    if not pcm16_audio:
        return
    await self.send_json({
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(pcm16_audio).decode("ascii"),
    })

async def commit_client_turn(self) -> None:
    await self.send_json({"type": "input_audio_buffer.commit"})

async def create_response(self) -> None:
    await self.send_json({"type": "response.create"})

async def cancel_response(self, *, response_id: str | None = None) -> None:
    payload: dict[str, Any] = {"type": "response.cancel"}
    if response_id is not None:
        payload["response_id"] = response_id
    await self.send_json(payload)

async def register_tools(self, tools: list[Any]) -> None:
    await self.initialize_session(tools=tools)

async def submit_tool_result(self, *, call_id: str, output: str) -> None:
    await self.send_json({
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": output,
        },
    })

async def iter_normalized_events(self) -> AsyncIterator[NormalizedRealtimeEvent]:
    async for event in self.iter_events():
        yield self._to_normalized_runtime_event(event)
```

Note: `iter_events()` is inherited from `BaseRealtimeWebsocketClient` — do NOT re-implement.

---

#### ABC compliance stub for `connect()` — DO NOT PORT

Source: RESEARCH.md Pitfall 8; `GlassAgents/backend/realtime/client.py` lines 362–369.

The GlassAgents `connect(self, config=None)` stub at lines 362–369 exists for GlassAgents ABC
conformance only. Phase 1's `RealtimeProvider.connect()` signature (no `config` param) is
already compatible with `BaseRealtimeWebsocketClient.connect()`. Do NOT port the stub — it
would shadow the base class method and break the transport layer.

---

### `src/eq_chatbot_core/realtime/factory.py` (registry extension)

**Analog:** `src/eq_chatbot_core/realtime/factory.py` lines 37–54 (self-extension — add "openai" after "mock")

**Extension pattern** (lines 37–54 — append after mock registration):

```python
# In build_default_realtime_provider_registry() — add AFTER mock block:
registry.register(
    RealtimeProviderDefinition(
        name="openai",
        factory_fn=lambda **kwargs: _build_openai_provider(**kwargs),
        description="OpenAI Realtime API — GPT speech-to-speech, server VAD, tool calling.",
    )
)
```

**Deferred import helper** (add as module-level private function, below `build_default_realtime_provider_registry`):

```python
def _build_openai_provider(**kwargs: Any) -> Any:
    """Build an OpenAIRealtimeClient from keyword arguments.

    Deferred import keeps factory.py importable without the [realtime] extra installed.
    """
    from eq_chatbot_core.realtime.providers.openai import (  # noqa: PLC0415
        OpenAIRealtimeClient,
        OpenAIRealtimeConfig,
    )
    api_key = kwargs.pop("api_key")
    config = OpenAIRealtimeConfig(api_key=api_key, **kwargs)
    return OpenAIRealtimeClient(config)
```

Analog: `src/eq_chatbot_core/realtime/factory.py` lines 44–53 (mock registration) + line 44
(`from eq_chatbot_core.realtime.mock import MockRealtimeProvider  # deferred` comment shows
the existing deferred-import idiom).

---

### `src/eq_chatbot_core/realtime/__init__.py` (re-export extension)

**Analog:** `src/eq_chatbot_core/realtime/__init__.py` lines 44–85 (self-extension)

**Extension pattern** — add to existing `__init__.py` (gated on no extra import guard needed;
the websockets guard at lines 31–37 already gates `get_realtime_provider`):

```python
# Add to the "Always importable" block (after contracts imports, before __all__):
from eq_chatbot_core.realtime.providers.openai import (  # noqa: E402
    OPENAI_REALTIME_CAPABILITIES,
    OpenAIRealtimeClient,
    OpenAIRealtimeConfig,
)

# Add to __all__:
"OpenAIRealtimeClient",
"OpenAIRealtimeConfig",
"OPENAI_REALTIME_CAPABILITIES",
```

Note: `providers/openai.py` imports `websockets` transitively via `BaseRealtimeWebsocketClient`.
Place the import inside a `try/except ImportError` guard — consistent with the existing
`get_realtime_provider` guard pattern at lines 31–37 — so that `from eq_chatbot_core.realtime
import RealtimeAdapterContract` still works without `[realtime]` installed.

---

### `tests/unit/realtime/test_realtime_openai.py` (unit test)

**Analog:** `tests/unit/realtime/conftest.py` lines 1–88 (fixture reuse — do NOT duplicate)

**Test file header and fixture reuse pattern:**

```python
# tests/unit/realtime/test_realtime_openai.py
"""Unit tests for OpenAIRealtimeClient.

Uses session-scoped mock_websockets_module from conftest.py (autouse=True).
Import provider AFTER the session fixture installs the mock into sys.modules.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# conftest.py installs mock_websockets_module at session scope (autouse=True).
# Import provider here — after conftest fixture has run.
from eq_chatbot_core.realtime.providers.openai import (
    OpenAIRealtimeClient,
    OpenAIRealtimeConfig,
    OPENAI_REALTIME_CAPABILITIES,
    RealtimeAudioEventNames,
)
from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes
```

Analog: `tests/unit/realtime/conftest.py` lines 13–87 — `mock_websockets_module` is session-scoped
and `autouse=True`, meaning every test in `tests/unit/realtime/` receives the mock automatically.
`mock_ws_instance` (function-scoped) must be requested explicitly per test that needs a fresh WS.

**Test class structure pattern** (mirroring RESEARCH.md §Validation Architecture):

```python
class TestOpenAIRealtimeConfig:
    def test_frozen(self): ...
    def test_default_model_is_gpt_realtime(self): ...
    def test_default_voice_is_ash(self): ...
    def test_include_turn_detection_default_true(self): ...

class TestCapabilities:
    def test_server_vad_true(self): ...
    def test_tool_result_mode_conversation_item(self): ...

class TestConnectLifecycle:
    async def test_on_connected_calls_initialize_session(self, mock_ws_instance): ...
    async def test_implements_contract(self, mock_ws_instance): ...

class TestVADSessionPayload:
    def test_turn_detection_present_when_true(self): ...
    def test_turn_detection_absent_when_false(self): ...

class TestIterNormalizedEvents:
    async def test_session_created_maps_to_session_ready(self, mock_ws_instance): ...
    # ... one test per NormalizedRealtimeEventTypes constant ...

class TestToolCallNormalization:
    def test_function_call_arguments_done_payload_shape(self): ...
    # Verify item.call_id, item.name, item.arguments present (Pitfall 5)

class TestCloseLifecycle:
    async def test_close_cleans_up(self, mock_ws_instance): ...
```

---

### `tests/integration/test_realtime_openai_live.py` (integration test)

**Analog:** `tests/unit/realtime/conftest.py` skip pattern + RESEARCH.md §Integration Test Pattern

```python
# tests/integration/test_realtime_openai_live.py
import os
import pytest
import asyncio
from eq_chatbot_core.realtime.providers.openai import OpenAIRealtimeClient, OpenAIRealtimeConfig
from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes

pytestmark = pytest.mark.integration

@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping live integration test",
)
@pytest.mark.asyncio
async def test_openai_realtime_session_ready_and_pcm_chunk():
    config = OpenAIRealtimeConfig(
        api_key=os.environ["OPENAI_API_KEY"],
        include_turn_detection=False,  # manual mode for predictable test flow
    )
    async with OpenAIRealtimeClient(config) as client:
        async for event in client.iter_normalized_events():
            assert event["type"] == NormalizedRealtimeEventTypes.SESSION_READY
            break
        # 100ms of silence at 24kHz mono PCM16 = 4800 bytes
        silence = b"\x00\x00" * 2400
        await client.append_client_audio(silence)
    # async with __aexit__ calls close() — SC-3 clean disconnect
```

---

## Shared Patterns

### Frozen+slots dataclass (config objects)

**Source:** `src/eq_chatbot_core/providers/base.py` lines 68–79 (`ToolDefinition`)
**Apply to:** `OpenAIRealtimeConfig`, `RealtimeAudioEventNames`

```python
@dataclass(frozen=True, slots=True)
class OpenAIRealtimeConfig:
    ...
```

Note: `RealtimeAudioEventNames` uses `@dataclass(frozen=True)` without `slots=True` to match
the GlassAgents reference (lines 30–35). `OpenAIRealtimeConfig` uses `slots=True` per handoff §5.

---

### Deferred import in factory (extras guard)

**Source:** `src/eq_chatbot_core/realtime/factory.py` line 44 (`from eq_chatbot_core.realtime.mock import ...  # deferred`)
**Apply to:** `_build_openai_provider()` in `factory.py`; OpenAI re-export block in `__init__.py`

Pattern: heavy/optional imports live inside a function or `try/except ImportError` block so
that the module stays importable without `[realtime]` extra installed.

---

### Abstract method override trio (BaseRealtimeWebsocketClient subclasses)

**Source:** `src/eq_chatbot_core/realtime/websocket_client.py` lines 113–133 (declarations)
**Apply to:** `OpenAIRealtimeClient` — all three must be overridden:

| Method | Phase 1 declaration | Required override |
|---|---|---|
| `_on_connected()` | `abstractmethod`, line 113 | `await self.initialize_session()` |
| `_on_message(raw)` | `abstractmethod`, line 118 | `pass` (no-op; iter_events loop is used instead) |
| `_connection_error_endpoint()` | `abstractmethod`, line 123 | URL without api_key |

---

### WebSocket mock fixture (unit tests)

**Source:** `tests/unit/realtime/conftest.py` lines 13–87
**Apply to:** `test_realtime_openai.py`

- `mock_websockets_module` — session-scoped, `autouse=True`; installs mock before any import
- `mock_ws_instance` — function-scoped; fresh `AsyncMock` with `.closed=False`, `.recv`, `.send`, `.close`
- Do NOT replicate these fixtures in `test_realtime_openai.py` — request them from conftest

---

### Error hierarchy (D-03 fail-fast)

**Source:** `src/eq_chatbot_core/realtime/websocket_client.py` lines 45–90
**Apply to:** `OpenAIRealtimeClient.__init__` (api_key/model validation)

```python
# D-03: fail fast with library-native exceptions; do NOT pass raw OpenAI errors through
if not config.api_key.strip():
    raise ValueError("OpenAIRealtimeConfig.api_key must be non-empty")
```

HTTP-level errors (401/403) during WebSocket handshake are caught by
`BaseRealtimeWebsocketClient.connect()` (lines 154–166) and raised as `RealtimeConnectionError`.
Map 429 → `RealtimeRateLimitError` (already handled by base, lines 159–163). The subclass
does NOT need to re-implement error mapping for transport-level failures.

---

## No Analog Found

All 5 files have close analogs. No files require falling back to RESEARCH.md patterns exclusively.

---

## Anti-Patterns (do not copy)

| Anti-pattern | Source in GlassAgents | Why not applicable |
|---|---|---|
| `super().__init__(trace_events=trace_events)` | `client.py` line 57 | Phase 1 base class takes `url, headers` — not `trace_events` |
| `async def connect(self, config=None)` stub | `client.py` lines 362–369 | GlassAgents ABC has different signature; Phase 1 ABC is already compatible |
| `tool.to_openai_tool()` | `client.py` line 296 | Phase 1 `ToolDefinition` has no such method; use inline conversion instead |
| `from backend.realtime.*` imports | `client.py` lines 9–23 | GlassAgents-internal paths; replace with `eq_chatbot_core.*` |

---

## Metadata

**Analog search scope:** `src/eq_chatbot_core/realtime/`, `tests/unit/realtime/`, `src/eq_chatbot_core/providers/`, `GlassAgents/backend/realtime/`
**Files scanned:** 10 (6 Phase 1 library files + 4 GlassAgents reference files)
**Pattern extraction date:** 2026-05-24
