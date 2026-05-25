"""Gemini Live API provider.

Port of GlassAgents/backend/realtime/providers/gemini_live.py (~920 LOC) adapted to
eq-chatbot-core library conventions and Phase 1 BaseRealtimeWebsocketClient.

Key differences from the reference:
  - Dual-endpoint: mode="developer" (key-in-URL) + mode="vertex" (OAuth bearer, EU regional)
  - Inherits BaseRealtimeWebsocketClient (url+headers computed in __init__, not lazy)
  - _on_connected is a logging-only no-op (NOT initialize_session — see PITFALL-05)
  - tool.parameters used (NOT GlassAgents' tool field — ADAPTATION B)
  - time.time_ns() // 1_000_000 used (NOT GlassAgents utility function — ADAPTATION C)
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from eq_chatbot_core.providers.base import ToolDefinition
from eq_chatbot_core.realtime.abc import RealtimeProvider
from eq_chatbot_core.realtime.contracts import (
    NormalizedRealtimeEventFull,
    NormalizedRealtimeEventTypes,
    RealtimeProviderCapabilities,
)
from eq_chatbot_core.realtime.websocket_client import BaseRealtimeWebsocketClient

_logger = logging.getLogger(__name__)

# WebSocket endpoint constants — dual-endpoint support (D-01)
_GEMINI_DEVELOPER_BASE_URL = "wss://generativelanguage.googleapis.com"
_GEMINI_DEVELOPER_ENDPOINT = "/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
_VERTEX_ENDPOINT = "/ws/google.cloud.aiplatform.v1.LlmBidiService/BidiGenerateContent"


@dataclass(frozen=True, slots=True)
class GeminiLiveConfig:
    """Configuration for the Gemini Live API provider.

    mode="developer": api_key required; key-in-URL (?key=...), global/US endpoint.
    mode="vertex":    access_token required; OAuth bearer, regional europe-west* endpoint.

    Source: GlassAgents reference + D-01 dual-endpoint extension.
    """

    # Developer API mode
    api_key: str = ""  # required when mode="developer"

    # Vertex AI mode
    access_token: str = ""  # required when mode="vertex"; OAuth bearer
    project: str = ""  # GCP project ID for x-goog-user-project header
    region: str = "europe-west4"  # GCP region; default EU for DSGVO compliance

    # Shared fields
    mode: Literal["developer", "vertex"] = "developer"
    # Verified live 2026-05-25 (D-05). See 03-01-SUMMARY.md.
    # Dead aliases: gemini-2.0-flash (shutdown 2026-06-01),
    # gemini-live-2.5-flash-preview-native-audio-09-2025 (removed 2026-03-19).
    model: str = "gemini-3.1-flash-live-preview"
    instructions: str = ""
    base_url: str | None = None  # override base URL (e.g. for tests)
    trace_events: bool = False


# Provider capability metadata — immutable constant registered once at module level.
# Source: GlassAgents/backend/realtime/providers/gemini_live.py lines 39-49
GEMINI_LIVE_REALTIME_CAPABILITIES = RealtimeProviderCapabilities(
    streaming_audio_input=True,
    streaming_audio_output=True,
    server_vad=False,  # Gemini has NO server VAD
    manual_turn_commit_required=True,  # Always required — commit_client_turn() is mandatory
    tool_calling=True,
    tool_result_submission_mode="provider_call_id",  # toolResponse.functionResponses[].id
    voice_selection=False,
    interruption_cancel=False,  # cancel_response is a no-op
    startup_validation=True,
    # session_sample_rate inherits default 24_000 — matches Gemini Live PCM16 audio format
)


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
                "Valid floating alias: gemini-3.1-flash-live-preview"
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

    # ------------------------------------------------------------------
    # Abstract method overrides (BaseRealtimeWebsocketClient)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Redaction helpers (PROV-07 / T-03-01, T-03-02)
    # ------------------------------------------------------------------

    @staticmethod
    def _redact_sensitive_url(url: str) -> str:
        """Strip ?key= query param from Developer API URLs.

        Port verbatim from GlassAgents/backend/realtime/providers/gemini_live.py lines 813-835.
        Uses parse_qsl/urlunsplit for correct multi-param URL handling.
        """
        parts = urlsplit(url)
        params = parse_qsl(parts.query, keep_blank_values=True)
        redacted = [(k, "[REDACTED]" if k == "key" else v) for k, v in params]
        # Use quote_via=quote with safe='[]' to preserve bracket chars in [REDACTED] literal
        new_query = urlencode(redacted, quote_via=quote, safe="[]")
        return urlunsplit(parts._replace(query=new_query))

    def _redact_sensitive_text(self, text: str) -> str:
        """Replace raw API key / bearer token occurrences in error strings.

        Port from GlassAgents reference lines 836-860; extended for Vertex bearer token (D-02).
        ADAPTATION I: covers Vertex bearer token via self._secret substitution.
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

    # ------------------------------------------------------------------
    # Session management (RealtimeAdapterContract)
    # ------------------------------------------------------------------

    async def initialize_session(
        self,
        *,
        instructions: str | None = None,
        voice: str | None = None,
        tools: list[Any] | None = None,
    ) -> None:
        """Send BidiGenerateContent setup envelope to configure the Gemini Live session.

        Must be called explicitly by the consumer after connect().
        NOT called automatically from _on_connected (see PITFALL-05).
        """
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
        """Build the BidiGenerateContent setup message.

        Pitfall 4: Gemini API requires the 'models/' resource path prefix.
        """
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

    async def update_session(self, payload: dict[str, Any]) -> None:
        """Send a session update payload via send_json."""
        await self.send_json(payload)

    # ------------------------------------------------------------------
    # Audio I/O (RealtimeAdapterContract)
    # ------------------------------------------------------------------

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

    async def commit_client_turn(self) -> None:
        """Commit the current audio turn (always required — Gemini has no server VAD).

        Sends realtimeInput.audioStreamEnd. Source: GlassAgents reference.
        Contrast: OpenAI sends input_audio_buffer.commit.
        """
        await self.send_json({"realtimeInput": {"audioStreamEnd": True}})

    async def create_response(self) -> None:
        """No-op for Gemini — server generates response after turn commit."""
        pass

    async def cancel_response(self, *, response_id: str | None = None) -> None:
        """No-op — interruption_cancel=False in GEMINI_LIVE_REALTIME_CAPABILITIES."""
        pass

    async def register_tools(self, tools: list[Any]) -> None:
        """Re-initialize session with updated tools."""
        await self.initialize_session(tools=tools)

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

    # ------------------------------------------------------------------
    # Tool schema conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _to_gemini_function_declaration(tool: ToolDefinition | dict[str, Any]) -> dict[str, Any]:
        """Convert ToolDefinition to Gemini function declaration format.

        ADAPTATION B: use tool.parameters (library field), not the GlassAgents field name.
        """
        if isinstance(tool, ToolDefinition):
            # ADAPTATION B — uses library field, not GlassAgents field name
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

    def _normalize_tools(self, tools: list[Any] | None) -> list[dict[str, Any]] | None:
        """Convert list[ToolDefinition | dict] to list[dict] for Gemini setup envelope."""
        if not tools:
            return None
        return [self._to_gemini_function_declaration(t) for t in tools]

    # ------------------------------------------------------------------
    # Event normalization (RealtimeAdapterContract)
    # ------------------------------------------------------------------

    def _normalize_tool_call_events(
        self, event: dict[str, Any]
    ) -> list[NormalizedRealtimeEventFull]:
        """Normalize toolCall wire event to TOOL_CALL_COMPLETED items.

        Source: GlassAgents reference lines 490-528.
        ADAPTATION C: uses time.time_ns() // 1_000_000 (stdlib, no GlassAgents utility)
        """
        results: list[NormalizedRealtimeEventFull] = []
        for fn_call in event.get("toolCall", {}).get("functionCalls", []):
            # ADAPTATION C — stdlib time.time_ns(), no GlassAgents utility import
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
            results: list[NormalizedRealtimeEventFull] = []
            server_content = event["serverContent"]
            model_turn = server_content.get("modelTurn", {})
            parts = model_turn.get("parts", [])
            for part in parts:
                inline_data = part.get("inlineData", {})
                audio_data = inline_data.get("data")
                if audio_data:
                    results.append({
                        "type": NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA,
                        "payload": {"audio": audio_data},
                        "source": "serverContent",
                        "raw": event,
                    })
            if server_content.get("turnComplete"):
                results.append({
                    "type": NormalizedRealtimeEventTypes.RESPONSE_DONE,
                    "payload": event,
                    "source": "serverContent",
                    "raw": event,
                })
            elif not results:
                # serverContent with no audio parts and no turnComplete
                results.append({
                    "type": NormalizedRealtimeEventTypes.UNHANDLED,
                    "payload": event,
                    "source": "serverContent",
                    "raw": event,
                })
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

    async def iter_normalized_events(self) -> AsyncIterator[NormalizedRealtimeEventFull]:
        """Yield normalized events from the Gemini Live stream.

        Wraps inherited iter_events() with Gemini wire-type routing.
        Note: one wire frame may produce multiple normalized events (e.g. serverContent).
        Mirror: openai.py lines 398-408, but calls _to_normalized_runtime_events (plural).
        """
        async for event in self.iter_events():
            for normalized in self._to_normalized_runtime_events(event):
                yield normalized


__all__ = [
    "GeminiLiveClient",
    "GeminiLiveConfig",
    "GEMINI_LIVE_REALTIME_CAPABILITIES",
]
