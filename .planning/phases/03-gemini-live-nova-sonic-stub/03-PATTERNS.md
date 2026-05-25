# Phase 3: Gemini Live + Nova Sonic Stub - Pattern Map

**Mapped:** 2026-05-25
**Files analyzed:** 7 (5 new files + 2 modified files)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/eq_chatbot_core/realtime/providers/gemini_live.py` | provider | streaming + event-driven | `src/eq_chatbot_core/realtime/providers/openai.py` | exact |
| `src/eq_chatbot_core/realtime/providers/nova.py` | provider stub | none (NotImplementedError) | `src/eq_chatbot_core/realtime/providers/openai.py` (structure only) | role-match |
| `src/eq_chatbot_core/realtime/factory.py` | factory | request-response | `src/eq_chatbot_core/realtime/factory.py` (self — extend) | exact |
| `tests/unit/realtime/test_realtime_gemini.py` | test | unit | `tests/unit/realtime/test_realtime_openai.py` | exact |
| `tests/unit/realtime/test_realtime_nova.py` | test | unit | `tests/unit/realtime/test_realtime_openai.py` | role-match |
| `tests/unit/realtime/test_factory.py` | test | unit | `tests/unit/realtime/test_factory.py` (self — extend) | exact |
| `tests/integration/test_realtime_gemini_live.py` | test | integration | `tests/integration/test_realtime_openai_live.py` | exact |

---

## Pattern Assignments

### `src/eq_chatbot_core/realtime/providers/gemini_live.py` (provider, streaming + event-driven)

**Analog:** `src/eq_chatbot_core/realtime/providers/openai.py`
**Port source:** `/Users/picard/gitbase/GlassAgents/backend/realtime/providers/gemini_live.py` (920 LOC)

**Imports pattern** (mirror openai.py lines 1-32, adapted for Gemini):
```python
"""Gemini Live API provider.

Port of GlassAgents/backend/realtime/providers/gemini_live.py (~920 LOC) adapted to
eq-chatbot-core library conventions and Phase 1 BaseRealtimeWebsocketClient.

Key differences from the reference:
  - Dual-endpoint: mode="developer" (key-in-URL) + mode="vertex" (OAuth bearer, EU regional)
  - Inherits BaseRealtimeWebsocketClient (url+headers computed in __init__, not lazy)
  - _on_connected is a logging-only no-op (NOT initialize_session — see PITFALL-05)
  - tool.parameters used instead of tool.input_schema (GlassAgents field name difference)
  - now_ms() replaced with time.time_ns() // 1_000_000 (stdlib, no GlassAgents import)
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from eq_chatbot_core.providers.base import ToolDefinition
from eq_chatbot_core.realtime.abc import RealtimeProvider
from eq_chatbot_core.realtime.contracts import (
    NormalizedRealtimeEventFull,
    NormalizedRealtimeEventTypes,
    RealtimeProviderCapabilities,
)
from eq_chatbot_core.realtime.websocket_client import BaseRealtimeWebsocketClient

_logger = logging.getLogger(__name__)
```

**Config dataclass pattern** (mirror openai.py lines 38-66, adapted for dual-endpoint):
```python
@dataclass(frozen=True, slots=True)
class GeminiLiveConfig:
    """Configuration for the Gemini Live API provider.

    mode="developer": api_key required; key-in-URL (?key=...), global/US endpoint.
    mode="vertex":    access_token required; OAuth bearer, regional europe-west* endpoint.

    Source: GlassAgents reference + D-01 dual-endpoint extension.
    """

    # Developer API mode
    api_key: str = ""                             # required when mode="developer"

    # Vertex AI mode
    access_token: str = ""                        # required when mode="vertex"; OAuth bearer
    project: str = ""                             # GCP project ID for x-goog-user-project header
    region: str = "europe-west4"                  # GCP region; default EU for DSGVO compliance

    # Shared fields
    mode: Literal["developer", "vertex"] = "developer"
    # gemini-2.5-flash-preview-native-audio-12-2025 verified 2026-05-25 (D-05 snapshot).
    # Consumers pinning a snapshot must verify against Developer API + Vertex model list
    # before deploying — use: curl "https://generativelanguage.googleapis.com/v1beta/models?key=KEY"
    model: str = "gemini-2.5-flash-preview-native-audio-12-2025"
    instructions: str = ""
    base_url: str | None = None                   # override base URL (e.g. for tests)
    trace_events: bool = False
```

**Capabilities constant pattern** (mirror openai.py lines 68-80):
```python
# Provider capability metadata — immutable constant registered once at module level.
# Source: GlassAgents/backend/realtime/providers/gemini_live.py lines 39-49
GEMINI_LIVE_REALTIME_CAPABILITIES = RealtimeProviderCapabilities(
    streaming_audio_input=True,
    streaming_audio_output=True,
    server_vad=False,                           # Gemini has NO server VAD
    manual_turn_commit_required=True,           # Always required — commit_client_turn() is mandatory
    tool_calling=True,
    tool_result_submission_mode="provider_call_id",  # toolResponse.functionResponses[].id
    voice_selection=False,
    interruption_cancel=False,                  # cancel_response is a no-op
    startup_validation=True,
    # session_sample_rate inherits default 24_000 — matches Gemini Live PCM16 audio format
)
```

**Class header + `__init__` pattern** (mirror openai.py lines 83-111, extended for dual-endpoint):
```python
_GEMINI_DEVELOPER_BASE_URL = "wss://generativelanguage.googleapis.com"
_GEMINI_DEVELOPER_ENDPOINT = "/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
_VERTEX_ENDPOINT = "/ws/google.cloud.aiplatform.v1.LlmBidiService/BidiGenerateContent"


class GeminiLiveClient(BaseRealtimeWebsocketClient, RealtimeProvider):
    """Gemini Live API provider — BidiGenerateContent, manual turn commit, tool calling.

    Supports two endpoints (D-01):
      mode="developer": key-in-URL, global/US endpoint (GlassAgents port path)
      mode="vertex":    OAuth bearer, regional europe-west* endpoint (DSGVO-compliant)

    Port target: GlassAgents/backend/realtime/providers/gemini_live.py (920 LOC)
    """

    def __init__(self, config: GeminiLiveConfig) -> None:
        # D-06: fail fast with library-native exceptions before any network I/O
        if not config.model.strip():
            raise ValueError(
                "GeminiLiveConfig.model must be non-empty. "
                "Valid floating alias: gemini-2.5-flash-preview-native-audio-12-2025"
            )
        if config.mode == "developer":
            if not config.api_key.strip():
                raise ValueError(
                    "GeminiLiveConfig.api_key must be non-empty when mode='developer'."
                )
            base = config.base_url or _GEMINI_DEVELOPER_BASE_URL
            url = f"{base}{_GEMINI_DEVELOPER_ENDPOINT}?key={config.api_key}"
            headers: dict[str, str] = {}
        elif config.mode == "vertex":
            if not config.access_token.strip():
                raise ValueError(
                    "GeminiLiveConfig.access_token must be non-empty when mode='vertex'."
                )
            base = config.base_url or f"wss://{config.region}-aiplatform.googleapis.com"
            url = f"{base}{_VERTEX_ENDPOINT}"
            headers = {
                "Authorization": f"Bearer {config.access_token}",
                "x-goog-user-project": config.project,
            }
        else:
            raise ValueError(f"Unknown GeminiLiveConfig.mode: {config.mode!r}. Must be 'developer' or 'vertex'.")

        # Phase 1 base class takes url + headers (NOT trace_events — mirrors openai.py)
        super().__init__(url=url, headers=headers)

        self._config = config
        self._trace_events = config.trace_events
        # Store raw secret for redaction (Pitfall 3: bearer token redaction in error strings)
        self._secret = config.api_key if config.mode == "developer" else config.access_token
```

**Abstract method overrides** (mirror openai.py lines 113-133, but `_on_connected` is NO-OP for Gemini):
```python
    async def _on_connected(self) -> None:
        """Logging-only hook — Gemini setup is sent explicitly via initialize_session().

        IMPORTANT: Do NOT call initialize_session() here.
        Gemini's setup envelope is sent explicitly by the consumer (or bridge).
        Calling it here would double-initialize if the consumer also calls it.
        Contrast: OpenAI's _on_connected calls initialize_session() automatically.
        Source: GlassAgents reference lines 200-207.
        """
        if self._trace_events:
            _logger.info(
                "Gemini Live websocket connected endpoint=%s model=%s",
                self._connection_error_endpoint(),
                self._config.model,
            )

    async def _on_message(self, raw: str) -> None:
        """Not used in iter_normalized_events flow — required for ABC conformance only."""
        pass

    def _connection_error_endpoint(self) -> str:
        """Return URL without API key or bearer token for error messages (PROV-07).

        NEVER include self._config.api_key or self._config.access_token in the returned string.
        Source: openai.py line 127-133 pattern; extended for dual-endpoint redaction.
        """
        return self._redact_sensitive_url(self._url)
```

**Redaction helpers pattern** (port verbatim from GlassAgents lines 813-860, extended for Vertex):
```python
    @staticmethod
    def _redact_sensitive_url(url: str) -> str:
        """Strip ?key= query param from Developer API URLs.

        Port verbatim from GlassAgents/backend/realtime/providers/gemini_live.py lines 813-835.
        Uses parse_qsl/urlunsplit for correct multi-param URL handling.
        """
        parts = urlsplit(url)
        params = parse_qsl(parts.query, keep_blank_values=True)
        redacted = [(k, "[REDACTED]" if k == "key" else v) for k, v in params]
        new_query = urlencode(redacted)
        return urlunsplit(parts._replace(query=new_query))

    def _redact_sensitive_text(self, text: str) -> str:
        """Replace raw API key / bearer token occurrences in error strings.

        Port from GlassAgents reference lines 836-860; extended for Vertex bearer token (D-02).
        """
        if not text:
            return text
        # Replace the websocket URL (which may embed ?key=...)
        redacted_url = self._redact_sensitive_url(self._url)
        text = text.replace(self._url, redacted_url)
        # Replace the raw secret (api_key or access_token) wherever it appears
        if self._secret:
            text = re.sub(re.escape(self._secret), "[REDACTED]", text)
        return text
```

**`initialize_session` / setup envelope pattern** (from GlassAgents lines 618-648):
```python
    async def initialize_session(
        self,
        *,
        instructions: str | None = None,
        voice: str | None = None,
        tools: list[Any] | None = None,
    ) -> None:
        """Send BidiGenerateContent setup envelope to configure the Gemini Live session."""
        event = self._build_setup_event(
            instructions=instructions or self._config.instructions or None,
            tools=self._normalize_tools(tools),
        )
        await self.send_json(event)

    def _build_setup_event(
        self,
        *,
        instructions: str | None,
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        resolved_model = self._config.model
        # Gemini API requires the 'models/' resource path prefix (Pitfall 4)
        if not resolved_model.startswith("models/"):
            resolved_model = f"models/{resolved_model}"
        setup: dict[str, Any] = {
            "model": resolved_model,
            "generationConfig": {"responseModalities": ["AUDIO"]},
        }
        if instructions:
            setup["systemInstruction"] = {"parts": [{"text": instructions}]}
        if tools:
            setup["tools"] = [{"functionDeclarations": tools}]
        return {"setup": setup}
```

**Tool schema conversion pattern** (port verbatim from GlassAgents lines 661-712, adaptation B):
```python
    @staticmethod
    def _to_gemini_function_declaration(tool: ToolDefinition | dict[str, Any]) -> dict[str, Any]:
        """Convert ToolDefinition to Gemini function declaration format."""
        if isinstance(tool, ToolDefinition):
            # ADAPTATION B: use tool.parameters (library field), NOT tool.input_schema (GlassAgents)
            schema = GeminiLiveClient._to_gemini_schema(tool.parameters)
            decl: dict[str, Any] = {"name": tool.name, "description": tool.description}
            if schema is not None:
                decl["parameters"] = schema
            return decl
        return dict(tool)

    @staticmethod
    def _to_gemini_schema(schema: dict[str, Any] | None) -> dict[str, Any] | None:
        """Sanitize JSON Schema to Gemini's strict subset.

        Port verbatim from GlassAgents reference lines 676-712.
        Strips additionalProperties; empty objects return None.
        """
        if not schema:
            return None
        result = {k: v for k, v in schema.items() if k != "additionalProperties"}
        if "properties" in result:
            result["properties"] = {
                k: GeminiLiveClient._to_gemini_schema(v) or {}
                for k, v in result["properties"].items()
            }
        if "items" in result:
            result["items"] = GeminiLiveClient._to_gemini_schema(result["items"])
        if not result.get("properties") and result.get("type") == "object":
            return None
        return result
```

**`submit_tool_result` pattern — provider_call_id mode** (differs from openai.py conversation_item):
```python
    async def submit_tool_result(self, *, call_id: str, output: str) -> None:
        """Submit tool result using Gemini's provider_call_id schema (toolResponse.functionResponses).

        Source: GlassAgents reference lines 530-558.
        Contrast: OpenAI uses 'conversation.item.create' + 'function_call_output'.
        """
        try:
            output_value = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            output_value = {"output": output}
        await self.send_json({
            "toolResponse": {
                "functionResponses": [
                    {"id": call_id, "response": {"output": output_value}}
                ]
            }
        })
```

**`commit_client_turn` pattern — Gemini audioStreamEnd**:
```python
    async def commit_client_turn(self) -> None:
        """Commit the current audio turn (always required — Gemini has no server VAD).

        Sends realtimeInput.audioStreamEnd. Source: GlassAgents reference.
        Contrast: OpenAI sends input_audio_buffer.commit.
        """
        await self.send_json({"realtimeInput": {"audioStreamEnd": True}})
```

**`append_client_audio` pattern** (mirror openai.py lines 344-358, different wire shape):
```python
    async def append_client_audio(self, pcm16_audio: bytes) -> None:
        """Base64-encode and send a PCM16 audio chunk via realtimeInput.audio.data.

        Source: GlassAgents reference. Contrast: OpenAI uses input_audio_buffer.append.
        """
        if not pcm16_audio:
            return
        await self.send_json({
            "realtimeInput": {
                "audio": {"data": base64.b64encode(pcm16_audio).decode("ascii")}
            }
        })
```

**Event normalization pattern** (mirror openai.py lines 251-318, for Gemini wire types):
```python
    def _to_normalized_runtime_events(
        self, event: dict[str, Any]
    ) -> list[NormalizedRealtimeEventFull]:
        """Route Gemini wire types to NormalizedRealtimeEventTypes constants.

        Port from GlassAgents reference lines 270-510.
        Returns a list (Gemini serverContent may yield multiple audio delta + done events).
        """
        if "setupComplete" in event:
            return [{"type": NormalizedRealtimeEventTypes.SESSION_READY,
                     "payload": event, "source": "setupComplete", "raw": event}]
        if "serverContent" in event:
            results = []
            # ... extract audio deltas from serverContent.modelTurn.parts
            # yields RESPONSE_AUDIO_DELTA* then RESPONSE_DONE when turnComplete
            return results
        if "toolCall" in event:
            return self._normalize_tool_call_events(event)
        if "toolCallCancellation" in event:
            return [{"type": NormalizedRealtimeEventTypes.TOOL_CALL_CANCELLED,
                     "payload": event, "source": "toolCallCancellation", "raw": event}]
        if "error" in event:
            return [{"type": NormalizedRealtimeEventTypes.ERROR,
                     "payload": event, "source": "error", "raw": event}]
        return [{"type": NormalizedRealtimeEventTypes.UNHANDLED,
                 "payload": event, "source": "unknown", "raw": event}]

    def _normalize_tool_call_events(
        self, event: dict[str, Any]
    ) -> list[NormalizedRealtimeEventFull]:
        """Normalize toolCall wire event to TOOL_CALL_COMPLETED items.

        Source: GlassAgents reference lines 490-528.
        ADAPTATION C: replace now_ms() with time.time_ns() // 1_000_000
        """
        results = []
        for fn_call in event.get("toolCall", {}).get("functionCalls", []):
            call_id = fn_call.get("id") or f"tool_call_{time.time_ns() // 1_000_000}"
            results.append({
                "type": NormalizedRealtimeEventTypes.TOOL_CALL_COMPLETED,
                "payload": {
                    "call_id": call_id,
                    "name": fn_call.get("name"),
                    "arguments": json.dumps(fn_call.get("args", {})),
                },
                "source": "toolCall",
                "raw": event,
            })
        return results

    async def iter_normalized_events(self) -> AsyncIterator[NormalizedRealtimeEventFull]:
        """Yield normalized events from the Gemini Live stream.

        Wraps inherited iter_events() with Gemini wire-type routing.
        Note: one wire frame may produce multiple normalized events (e.g. serverContent).
        Mirror: openai.py lines 398-408, but calls _to_normalized_runtime_events (plural).
        """
        async for event in self.iter_events():
            for normalized in self._to_normalized_runtime_events(event):
                yield normalized
```

**`__all__` pattern** (mirror openai.py lines 411-417):
```python
__all__ = [
    "GeminiLiveClient",
    "GeminiLiveConfig",
    "GEMINI_LIVE_REALTIME_CAPABILITIES",
]
```

---

### `src/eq_chatbot_core/realtime/providers/nova.py` (provider stub, no data flow)

**Analog:** `src/eq_chatbot_core/realtime/contracts.py` (Protocol signatures to match exactly)
**Note:** Does NOT inherit `BaseRealtimeWebsocketClient` or `RealtimeProvider` ABC — structural Protocol conformance only (RESEARCH.md Pattern 6).

**Full stub pattern** (D-07: <30 LOC, references v1.9.0):
```python
"""AWS Nova Sonic realtime provider stub.

Production implementation planned for v1.9.0.
get_realtime_provider("nova_sonic") resolves correctly (D-08) but every
method raises NotImplementedError pointing to the target version.

No websockets or boto3 imports — this file is stdlib-only (Pitfall 7).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any


class NovaSonicStub:
    """AWS Nova Sonic placeholder. Production implementation in v1.9.0."""

    async def connect(self) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def close(self) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def initialize_session(
        self,
        *,
        instructions: str | None = None,
        voice: str | None = None,
        tools: list[Any] | None = None,
    ) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def update_session(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def append_client_audio(self, pcm16_audio: bytes) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def commit_client_turn(self) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def create_response(self) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def cancel_response(self, *, response_id: str | None = None) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def register_tools(self, tools: list[Any]) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    async def submit_tool_result(self, *, call_id: str, output: str) -> None:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")

    def iter_normalized_events(self) -> AsyncIterator[Any]:
        raise NotImplementedError("Nova Sonic not implemented; available in v1.9.0")


__all__ = ["NovaSonicStub"]
```

**Critical:** Method signatures — especially `iter_normalized_events` return type `AsyncIterator[Any]` — must match `contracts.py` `RealtimeAdapterContract` Protocol exactly (line 105: `def iter_normalized_events(self) -> AsyncIterator[NormalizedRealtimeEvent]: ...`).

---

### `src/eq_chatbot_core/realtime/factory.py` (modify — extend registry)

**Analog:** `src/eq_chatbot_core/realtime/factory.py` lines 37-84 (self-referential extend)

**Pattern: add two entries in `build_default_realtime_provider_registry`** (after the `openai` registration, lines 54-60):
```python
    registry.register(
        RealtimeProviderDefinition(
            name="gemini_live",
            factory_fn=lambda **kwargs: _build_gemini_live_provider(**kwargs),
            description="Google Gemini Live API — BidiGenerateContent, manual turn commit, tool calling.",
        )
    )
    registry.register(
        RealtimeProviderDefinition(
            name="nova_sonic",
            factory_fn=lambda **kwargs: _build_nova_sonic_provider(**kwargs),
            description="AWS Nova Sonic stub — production implementation in v1.9.0.",
        )
    )
```

**Pattern: two new `_build_*` functions** (mirror `_build_openai_provider` lines 64-84):
```python
def _build_gemini_live_provider(**kwargs: Any) -> Any:
    """Build a GeminiLiveClient from keyword arguments.

    D-06 fail-fast: validate required fields before deferred import.
    Deferred import keeps factory.py importable without [realtime] extra.
    """
    mode = kwargs.get("mode", "developer")
    if mode == "developer" and not kwargs.get("api_key", "").strip():
        raise ValueError(
            "Gemini Live developer mode requires 'api_key'. "
            'Pass it via get_realtime_provider("gemini_live", api_key="...", mode="developer").'
        )
    if mode == "vertex" and not kwargs.get("access_token", "").strip():
        raise ValueError(
            "Gemini Live vertex mode requires 'access_token'. "
            'Pass it via get_realtime_provider("gemini_live", access_token="...", mode="vertex").'
        )
    from eq_chatbot_core.realtime.providers.gemini_live import (  # noqa: PLC0415
        GeminiLiveClient,
        GeminiLiveConfig,
    )
    config = GeminiLiveConfig(**kwargs)
    return GeminiLiveClient(config)


def _build_nova_sonic_provider(**kwargs: Any) -> Any:
    """Build a NovaSonicStub — no kwargs required or consumed.

    Deferred import is stdlib-only; no websockets or AWS extras needed (D-08 / Pitfall 7).
    """
    from eq_chatbot_core.realtime.providers.nova import NovaSonicStub  # noqa: PLC0415
    return NovaSonicStub()
```

**Important:** The `__all__` in factory.py (lines 110-115) does NOT need updating — the new functions are module-internal (`_build_*` prefix).

---

### `tests/unit/realtime/test_realtime_gemini.py` (test, unit)

**Analog:** `tests/unit/realtime/test_realtime_openai.py` (exact mirror structure)
**Key difference:** Uses `mock_websockets_module` fixture from `conftest.py` (autouse=True, session-scoped — already wired, no change needed to conftest).

**File header + import pattern** (mirror test_realtime_openai.py lines 1-29):
```python
"""Unit tests for GeminiLiveClient.

Uses session-scoped mock_websockets_module from conftest.py (autouse=True).
Import provider AFTER the session fixture installs the mock into sys.modules.

Coverage:
  - PROV-05: connect lifecycle, event normalization, manual turn commit, tool schema
  - PROV-06: GeminiLiveConfig defaults, GEMINI_LIVE_REALTIME_CAPABILITIES
  - PROV-07: _redact_sensitive_url strips key=, _redact_sensitive_text strips bearer token
  - QUAL-01: both endpoint modes URL shape, all wire types normalized
"""
import dataclasses

import pytest

from eq_chatbot_core.providers.base import ToolDefinition
from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes, RealtimeAdapterContract
from eq_chatbot_core.realtime.providers.gemini_live import (
    GEMINI_LIVE_REALTIME_CAPABILITIES,
    GeminiLiveClient,
    GeminiLiveConfig,
)
```

**Helper factory** (mirror test_realtime_openai.py lines 29-38):
```python
_FAKE_KEY = "test-api-key"
_FAKE_TOKEN = "ya29.fake-bearer-token"


def _make_developer_client() -> GeminiLiveClient:
    """Construct a developer-mode client with a fake API key (no real network I/O)."""
    config = GeminiLiveConfig(api_key=_FAKE_KEY, mode="developer")
    return GeminiLiveClient(config)


def _make_vertex_client() -> GeminiLiveClient:
    """Construct a vertex-mode client with a fake bearer token."""
    config = GeminiLiveConfig(
        access_token=_FAKE_TOKEN,
        project="my-gcp-project",
        region="europe-west4",
        mode="vertex",
    )
    return GeminiLiveClient(config)
```

**Test class structure** (mirror test_realtime_openai.py class layout):
```python
class TestGeminiLiveConfig:        # frozen, slots, defaults — mirror TestOpenAIRealtimeConfig
class TestCapabilities:            # PROV-06 values — mirror TestCapabilities
class TestConstructorValidation:   # D-06 fail-fast — mirror TestConstructorValidation
class TestEndpointModes:           # QUAL-01 dual-endpoint URL + header shape (NEW — no OpenAI analog)
class TestConnectionErrorEndpoint: # PROV-07 key/token never in endpoint — mirror TestConnectionErrorEndpoint
class TestRedaction:               # PROV-07 _redact_sensitive_url + _redact_sensitive_text (NEW)
class TestSetupEvent:              # _build_setup_event models/ prefix (NEW — Gemini-specific)
class TestToolSchemaConversion:    # _to_gemini_function_declaration, tool.parameters field (NEW)
class TestIterNormalizedEvents:    # all wire types → correct constants — mirror TestIterNormalizedEvents
class TestManualTurnCommit:        # commit_client_turn sends audioStreamEnd (NEW)
class TestToolResult:              # submit_tool_result uses provider_call_id schema (NEW)
class TestConnectLifecycle:        # _on_connected is NO-OP (contrast with OpenAI)
class TestCloseLifecycle:          # close() idempotent — mirror TestCloseLifecycle
```

**Key test: `_on_connected` is NOT `initialize_session`** (anti-OpenAI pattern):
```python
class TestConnectLifecycle:
    """PROV-05: _on_connected is a no-op logging hook, NOT initialize_session (Pitfall 5)."""

    async def test_on_connected_does_not_call_initialize_session(self) -> None:
        """_on_connected() must NOT call initialize_session() (Gemini anti-pattern)."""
        from unittest.mock import AsyncMock, patch

        client = _make_developer_client()
        with patch.object(client, "initialize_session", new_callable=AsyncMock) as mock_init:
            await client._on_connected()
            mock_init.assert_not_awaited()  # Opposite of OpenAI

    def test_implements_contract(self) -> None:
        """GeminiLiveClient must satisfy the RealtimeAdapterContract protocol."""
        client = _make_developer_client()
        assert isinstance(client, RealtimeAdapterContract)
```

**Key test: endpoint modes URL shape** (QUAL-01):
```python
class TestEndpointModes:
    def test_developer_mode_url_contains_key_param(self) -> None:
        """Developer mode: URL must embed ?key= query param."""
        client = _make_developer_client()
        assert f"key={_FAKE_KEY}" in client._url

    def test_developer_mode_has_no_authorization_header(self) -> None:
        """Developer mode: no Authorization header."""
        client = _make_developer_client()
        assert "Authorization" not in client._headers

    def test_vertex_mode_url_contains_aiplatform(self) -> None:
        """Vertex mode: URL must use {region}-aiplatform.googleapis.com."""
        client = _make_vertex_client()
        assert "aiplatform.googleapis.com" in client._url

    def test_vertex_mode_has_authorization_header(self) -> None:
        """Vertex mode: Authorization header must contain Bearer token."""
        client = _make_vertex_client()
        assert client._headers.get("Authorization") == f"Bearer {_FAKE_TOKEN}"

    def test_vertex_mode_has_project_header(self) -> None:
        """Vertex mode: x-goog-user-project header must be set."""
        client = _make_vertex_client()
        assert client._headers.get("x-goog-user-project") == "my-gcp-project"
```

**Key test: redaction** (PROV-07):
```python
class TestRedaction:
    def test_redact_key_param_from_developer_url(self) -> None:
        """_redact_sensitive_url must replace key= value with [REDACTED]."""
        client = _make_developer_client()
        redacted = client._redact_sensitive_url(client._url)
        assert _FAKE_KEY not in redacted
        assert "key=[REDACTED]" in redacted

    def test_redact_bearer_token_from_error_text(self) -> None:
        """_redact_sensitive_text must remove raw bearer token from error strings."""
        client = _make_vertex_client()
        error_text = f"Connection failed: Authorization: Bearer {_FAKE_TOKEN}"
        result = client._redact_sensitive_text(error_text)
        assert _FAKE_TOKEN not in result

    def test_connection_error_endpoint_contains_no_key(self) -> None:
        """_connection_error_endpoint must never expose api_key (PROV-07)."""
        client = _make_developer_client()
        endpoint = client._connection_error_endpoint()
        assert _FAKE_KEY not in endpoint
        assert endpoint.startswith("wss://")
```

---

### `tests/unit/realtime/test_realtime_nova.py` (test, unit)

**Analog:** `tests/unit/realtime/test_realtime_openai.py` (structure), `contracts.py` (11 method names)

**Import pattern** (no websockets mock needed — NovaSonicStub is stdlib-only):
```python
"""Unit tests for NovaSonicStub.

No websockets mock required — NovaSonicStub is stdlib-only.
Coverage: PROV-08 structural conformance, D-08 factory registration.
"""
import pytest

from eq_chatbot_core.realtime.contracts import RealtimeAdapterContract
from eq_chatbot_core.realtime.providers.nova import NovaSonicStub
```

**Test class structure:**
```python
class TestContractConformance:     # isinstance check passes (PROV-08)
class TestAllMethodsRaise:         # every method raises NotImplementedError (PROV-08)
class TestErrorMessages:           # message contains "v1.9.0" (D-07)
```

**Key tests:**
```python
class TestContractConformance:
    def test_isinstance_realtime_adapter_contract(self) -> None:
        """isinstance(NovaSonicStub(), RealtimeAdapterContract) must be True (PROV-08)."""
        stub = NovaSonicStub()
        assert isinstance(stub, RealtimeAdapterContract), (
            "NovaSonicStub must structurally satisfy RealtimeAdapterContract Protocol"
        )


class TestAllMethodsRaise:
    """PROV-08: Every method must raise NotImplementedError."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,kwargs", [
        ("connect", {}),
        ("close", {}),
        ("initialize_session", {}),
        ("update_session", {"payload": {}}),
        ("append_client_audio", {"pcm16_audio": b""}),
        ("commit_client_turn", {}),
        ("create_response", {}),
        ("cancel_response", {}),
        ("register_tools", {"tools": []}),
        ("submit_tool_result", {"call_id": "c1", "output": "{}"}),
    ])
    async def test_async_method_raises(self, method: str, kwargs: dict) -> None:
        stub = NovaSonicStub()
        with pytest.raises(NotImplementedError):
            await getattr(stub, method)(**kwargs)

    def test_iter_normalized_events_raises(self) -> None:
        """iter_normalized_events is sync (returns AsyncIterator) — raises directly."""
        stub = NovaSonicStub()
        with pytest.raises(NotImplementedError):
            stub.iter_normalized_events()


class TestErrorMessages:
    @pytest.mark.asyncio
    async def test_message_references_v190(self) -> None:
        """Error message must contain 'v1.9.0' (D-07 / PROV-08)."""
        stub = NovaSonicStub()
        with pytest.raises(NotImplementedError, match="v1.9.0"):
            await stub.connect()
```

---

### `tests/unit/realtime/test_factory.py` (modify — extend with Gemini + Nova tests)

**Analog:** `tests/unit/realtime/test_factory.py` lines 14-52 (self-extend)

**New test functions to add** (mirror existing `test_registry_contains_mock` and `test_get_realtime_provider_openai_missing_api_key_raises_value_error` patterns):
```python
@pytest.mark.unit
def test_registry_contains_gemini_live() -> None:
    reg = build_default_realtime_provider_registry()
    assert "gemini_live" in reg.registered_names()


@pytest.mark.unit
def test_registry_contains_nova_sonic() -> None:
    reg = build_default_realtime_provider_registry()
    assert "nova_sonic" in reg.registered_names()


@pytest.mark.unit
def test_get_realtime_provider_nova_sonic_returns_stub() -> None:
    """D-08: nova_sonic resolves without any AWS extras installed."""
    from eq_chatbot_core.realtime.providers.nova import NovaSonicStub
    provider = _get_realtime_provider_impl("nova_sonic")
    assert isinstance(provider, NovaSonicStub)


@pytest.mark.unit
def test_get_realtime_provider_gemini_live_developer_missing_api_key_raises() -> None:
    """D-06 fail-fast: omitting api_key for developer mode raises ValueError."""
    with pytest.raises(ValueError, match="api_key"):
        _get_realtime_provider_impl("gemini_live", mode="developer")


@pytest.mark.unit
def test_get_realtime_provider_gemini_live_vertex_missing_access_token_raises() -> None:
    """D-06 fail-fast: omitting access_token for vertex mode raises ValueError."""
    with pytest.raises(ValueError, match="access_token"):
        _get_realtime_provider_impl("gemini_live", mode="vertex")
```

---

### `tests/integration/test_realtime_gemini_live.py` (test, integration)

**Analog:** `tests/integration/test_realtime_openai_live.py` (exact mirror structure)

**Full file pattern** (mirror test_realtime_openai_live.py exactly, adapted for Vertex EU path):
```python
"""
Live integration test for Gemini Live provider — Vertex AI EU endpoint (QUAL-03 / SC-3).

Requires GEMINI_VERTEX_ACCESS_TOKEN and VERTEX_PROJECT_ID environment variables.
VERTEX_REGION defaults to europe-west4 (DSGVO-compliant Netherlands endpoint).
Test is automatically skipped when credentials are absent.

Run with:
    pytest -m integration tests/integration/test_realtime_gemini_live.py -v
"""

import os

import pytest

# Skip when [realtime] extra (websockets) is not installed — same guard as openai live test.
pytest.importorskip("websockets")

from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes  # noqa: E402
from eq_chatbot_core.realtime.providers.gemini_live import (  # noqa: E402
    GeminiLiveClient,
    GeminiLiveConfig,
)

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("GEMINI_VERTEX_ACCESS_TOKEN") or not os.getenv("VERTEX_PROJECT_ID"),
    reason="GEMINI_VERTEX_ACCESS_TOKEN / VERTEX_PROJECT_ID not set — skipping Vertex EU integration test",
)
@pytest.mark.asyncio
async def test_gemini_live_vertex_eu_session_ready_and_pcm_chunk() -> None:
    """QUAL-03 / SC-3: Connect to Gemini Live Vertex EU, receive SESSION_READY, send PCM16, close cleanly.

    Uses europe-west4 (Netherlands) by default — DSGVO-compliant regional endpoint.
    If VERTEX_REGION is set, that region is used instead (fallback: europe-west1 Belgium).

    Flow:
        1. Open WebSocket connection via async context manager
        2. Call initialize_session() explicitly (Gemini requires explicit setup)
        3. Iterate normalized events until SESSION_READY is received
        4. Send 100ms of PCM16 silence (4800 bytes at 24kHz mono)
        5. Commit audio turn (Gemini always requires manual turn commit)
        6. Async context manager __aexit__ triggers clean close()
    """
    config = GeminiLiveConfig(
        mode="vertex",
        access_token=os.environ["GEMINI_VERTEX_ACCESS_TOKEN"],
        project=os.environ["VERTEX_PROJECT_ID"],
        region=os.getenv("VERTEX_REGION", "europe-west4"),
    )
    async with GeminiLiveClient(config) as client:
        # Step 2: Explicitly send setup (Gemini differs from OpenAI here — no auto-init)
        await client.initialize_session()

        # Step 3: Wait for SESSION_READY
        async for event in client.iter_normalized_events():
            assert event["type"] == NormalizedRealtimeEventTypes.SESSION_READY, (
                f"Expected SESSION_READY as first event, got: {event['type']}"
            )
            break

        # Step 4: Send 100ms of silence at 24kHz mono PCM16 = 2400 samples * 2 bytes = 4800 bytes
        silence = b"\x00\x00" * 2400
        await client.append_client_audio(silence)

        # Step 5: Commit audio turn (mandatory — Gemini has no server VAD)
        await client.commit_client_turn()

    # Step 6: async with __aexit__ calls close() — clean disconnect (QUAL-03 verified)
```

---

## Shared Patterns

### Constructor Fail-Fast Validation (D-06 / D-03)
**Source:** `src/eq_chatbot_core/realtime/providers/openai.py` lines 94-105
**Apply to:** `GeminiLiveClient.__init__`, `_build_gemini_live_provider`
```python
if not config.api_key.strip():
    raise ValueError("... must be non-empty. ...")
```
Check field before `super().__init__()` — no network I/O must occur before validation.

### `BaseRealtimeWebsocketClient.__init__` Call Pattern
**Source:** `src/eq_chatbot_core/realtime/websocket_client.py` lines 104-106
**Apply to:** `GeminiLiveClient.__init__`
```python
# Compute url and headers FIRST, then call super().__init__(url=url, headers=headers)
super().__init__(url=url, headers=headers)
```
The base class stores `self._url` and `self._headers`. Access them after super().__init__ via `self._url` and `self._headers`.

### `_connection_error_endpoint` Security Override
**Source:** `src/eq_chatbot_core/realtime/providers/openai.py` lines 127-133
**Apply to:** `GeminiLiveClient._connection_error_endpoint`
```python
def _connection_error_endpoint(self) -> str:
    """Return URL without secrets for error messages."""
    return self._redact_sensitive_url(self._url)
```
Used by `BaseRealtimeWebsocketClient.connect()` in both the `RealtimeRateLimitError` and `RealtimeConnectionError` paths (websocket_client.py lines 158-163).

### Deferred Import in Factory
**Source:** `src/eq_chatbot_core/realtime/factory.py` lines 77-84
**Apply to:** `_build_gemini_live_provider`, `_build_nova_sonic_provider`
```python
from eq_chatbot_core.realtime.providers.gemini_live import (  # noqa: PLC0415
    GeminiLiveClient,
    GeminiLiveConfig,
)
```
Always use `# noqa: PLC0415` comment on deferred imports inside functions.

### Session-Scoped websockets Mock (unit tests only)
**Source:** `tests/unit/realtime/conftest.py` lines 13-87
**Apply to:** `test_realtime_gemini.py` (autouse=True — no action needed in test file)
The `mock_websockets_module` fixture is `autouse=True, scope="session"` — it automatically covers all files in `tests/unit/realtime/`. `test_realtime_nova.py` does NOT need it (NovaSonicStub is stdlib-only).

### `pytest.importorskip("websockets")` Guard
**Source:** `tests/integration/test_realtime_openai_live.py` line 18
**Apply to:** `tests/integration/test_realtime_gemini_live.py`
```python
pytest.importorskip("websockets")
```
Place before all other imports. Ensures graceful skip (not hard error) when `[realtime]` extra is absent.

### `@pytest.mark.unit` on all factory tests
**Source:** `tests/unit/realtime/test_factory.py` lines 15, 22, 27, etc.
**Apply to:** All new factory test functions in `test_factory.py`
```python
@pytest.mark.unit
def test_registry_contains_gemini_live() -> None:
```

---

## No Analog Found

All files have close analogs. No entries in this section.

---

## Port Adaptation Delta Summary (for planner reference)

All 9 adaptation items from RESEARCH.md mapped to concrete code locations:

| Item | File | Location | Pattern Source |
|------|------|----------|----------------|
| A — `super().__init__(url=..., headers=...)` signature | `gemini_live.py.__init__` | Lines 104-105 of `websocket_client.py` | `openai.py` lines 103-105 |
| B — `tool.parameters` not `tool.input_schema` | `gemini_live._to_gemini_function_declaration` | `ToolDefinition` in `providers/base.py` | `openai.py` line 219 |
| C — `time.time_ns() // 1_000_000` not `now_ms()` | `gemini_live._normalize_tool_call_events` | stdlib `time` module | RESEARCH.md Pattern 4 |
| D — Strip all `from backend.*` imports | `gemini_live.py` top | Only `eq_chatbot_core.*` and stdlib | `openai.py` lines 13-31 |
| E — `async def _on_connected` (not sync) | `gemini_live._on_connected` | `websocket_client.py` line 115 abstract | `openai.py` line 117 |
| F — Do not port bridge/settings functions | `gemini_live.py` | GlassAgents-specific wiring excluded | `openai.py` (no bridge wiring) |
| G — Vertex dual-endpoint in `__init__` | `gemini_live.__init__` | New — no openai.py analog | RESEARCH.md Pattern 1 |
| H — `websocket_url` property → `self._url` | `gemini_live._redact_sensitive_text` | `BaseRealtimeWebsocketClient._url` field | `websocket_client.py` line 105 |
| I — Bearer token redaction extension | `gemini_live._redact_sensitive_text` | Store `self._secret` in `__init__` | RESEARCH.md Pitfall 3 |

---

## Metadata

**Analog search scope:** `src/eq_chatbot_core/realtime/`, `tests/unit/realtime/`, `tests/integration/`
**Files scanned:** 10 source files + 9 test files
**Pattern extraction date:** 2026-05-25
