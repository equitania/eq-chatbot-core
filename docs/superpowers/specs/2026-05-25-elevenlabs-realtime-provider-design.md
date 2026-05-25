# Design: ElevenLabs Agents als Realtime-Provider

**Date:** 2026-05-25
**Status:** Approved (design); ready for phase planning
**Requirement:** Promotes `PROV-FUT-03` (ElevenLabs Conversational AI) from future to a first-class, *recommended* realtime provider.

## Motivation

ElevenLabs is to become the **preferred, central** realtime provider for GDPR reasons,
while OpenAI, Gemini Live, and the Nova Sonic stub remain fully supported.

The GDPR rationale holds, but only under explicit conditions (documented below):
ElevenLabs Agents is **not an LLM** — it is a voice orchestrator (ASR + turn-taking + TTS)
that calls an LLM under the hood. Full EU data residency requires an **EU-hosted Custom LLM**
backend; otherwise the LLM processing leaves the EU and the GDPR benefit is lost.

## Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | **Role** | Full speech-to-speech realtime agent — implements `RealtimeAdapterContract` like the other providers |
| 2 | **GDPR enforcement** | Lean transport adapter (`agent_id` + `api_key`); EU Custom-LLM / Zero-Retention / EU region configured externally in the ElevenLabs dashboard and **documented**, not enforced in code |
| 3 | **Positioning** | Equal-rank registration in the factory + ElevenLabs positioned as the recommended GDPR choice in the README. No change to existing factory default behavior. |
| 4 | **Turn control** | `commit_client_turn()` and `create_response()` are **no-ops** — ElevenLabs performs server-side turn-taking (unlike OpenAI's manual commit) |

## Architecture

Follows the existing OpenAI provider pattern exactly (`realtime/providers/openai.py`).

### New file: `src/eq_chatbot_core/realtime/providers/elevenlabs.py`

```python
@dataclass(frozen=True, slots=True)
class ElevenLabsRealtimeConfig:
    api_key: str                          # xi-api-key
    agent_id: str                         # agent pre-exists in the ElevenLabs dashboard
    base_url: str = "wss://api.elevenlabs.io"  # override with EU-residency endpoint
    voice: str | None = None              # optional per-session override
    instructions: str | None = None       # -> conversation_config_override.prompt
    session_sample_rate: int = 16_000      # the override prepared in contracts.py (PROV-FUT-03)


class ElevenLabsRealtimeClient(BaseRealtimeWebsocketClient, RealtimeProvider):
    # __init__: fail-fast (D-03) — api_key + agent_id non-empty BEFORE any network I/O
    # _safe_url(): xi-api-key MUST NEVER appear in logs
```

**Endpoint:** `wss://{base_url}/v1/convai/conversation?agent_id={agent_id}`
Auth via `xi-api-key` header (private agent) or the signed-URL flow.

### Contract mapping

| `RealtimeAdapterContract` method | ElevenLabs behavior |
|----------------------------------|---------------------|
| `connect()` | Open WebSocket, await `conversation_initiation_metadata` → emit `SESSION_READY` |
| `initialize_session()` | Send `conversation_initiation_client_data` with `conversation_config_override` (prompt/voice/language) |
| `append_client_audio()` | `user_audio_chunk` message (base64, **16 kHz**) |
| `commit_client_turn()` | **No-op** — server-side turn-taking |
| `create_response()` | **No-op** — agent responds automatically after the turn |
| `cancel_response()` | Interruption handling |
| `register_tools()` / `submit_tool_result()` | Client tools |
| `iter_normalized_events()` | Event mapping (below) |

### Event mapping (ElevenLabs → `NormalizedRealtimeEventTypes`)

| ElevenLabs event | Normalized type |
|------------------|-----------------|
| `conversation_initiation_metadata` | `SESSION_READY` |
| `audio` | `RESPONSE_AUDIO_DELTA` |
| `agent_response_complete` | `RESPONSE_DONE` |
| `user_transcript` | `INPUT_AUDIO_COMMITTED` |
| VAD / interruption | `INPUT_SPEECH_STARTED` / `INPUT_SPEECH_STOPPED` |
| `client_tool_call` | `TOOL_CALL_COMPLETED` |
| `ping` | Keepalive (respond `pong`) — not emitted |
| unknown | `UNHANDLED` |

### Capabilities

```python
ELEVENLABS_REALTIME_CAPABILITIES = RealtimeProviderCapabilities(
    streaming_audio_input=True,
    streaming_audio_output=True,
    server_vad=True,
    manual_turn_commit_required=False,   # differs from OpenAI
    tool_calling=True,
    tool_result_submission_mode="conversation_item",  # VERIFY in research
    voice_selection=True,
    interruption_cancel=True,
    startup_validation=True,
    session_sample_rate=16_000,
)
```

### Factory wiring (`realtime/factory.py`)

`_build_elevenlabs_provider(**kwargs)` with a deferred import, registered under the
canonical name `"elevenlabs"`, equal-rank alongside `openai` / `gemini_live` / `nova_sonic`.
Requires `agent_id` and `api_key`; raises a library-native error with a usage hint otherwise.

## Testing

- `tests/unit/test_realtime_elevenlabs.py` — mocked WebSocket: event mapping, key redaction,
  fail-fast config validation, no-op turn methods.
- Integration test — skipped when EU credentials are absent (mirrors the Gemini pattern):
  connect → `SESSION_READY` → clean disconnect.

## GDPR setup guide (README / docs)

A dedicated section documenting the four conditions for full EU compliance:

1. **Enterprise plan** (EU data residency is Enterprise-only).
2. **Zero Retention Mode + API** (restricts processing to the EU).
3. **EU-hosted Custom LLM** as the agent backend — otherwise LLM processing leaves the EU.
4. **EU data-residency endpoint** supplied as `base_url`.

ElevenLabs is positioned as the recommended provider; OpenAI/Gemini remain documented and available.

> **Caveat to document:** Voice cloning is *not* Zero-Retention-eligible — cloned voice models persist.

## Open points (resolve during research/planning — do not guess)

- Exact **EU-residency endpoint** (dedicated subdomain vs. account-level setting only).
- **signed-URL** flow vs. direct header auth for private agents.
- Precise **event names** of the current `convai` WebSocket protocol.
- ElevenLabs' actual **`tool_result_submission_mode`** value.

## Roadmap integration

ElevenLabs is currently `PROV-FUT-03` (planned for v1.9.0). Promoting it to a central provider
warrants its own phase in the v1.8.0 milestone. Phase position (before vs. after the Gemini
phase) is decided separately via the GSD roadmap workflow.

## References

- [ElevenLabs Data residency](https://elevenlabs.io/docs/overview/administration/data-residency)
- [ElevenLabs — European Data Residency](https://elevenlabs.io/blog/introducing-european-data-residency)
- [Custom LLM](https://elevenlabs.io/docs/eleven-agents/customization/llm/custom-llm)
- [Agent WebSockets](https://elevenlabs.io/docs/agents-platform/api-reference/agents-platform/websocket)
- [Data Processing Addendum (DPA)](https://elevenlabs.io/dpa)
