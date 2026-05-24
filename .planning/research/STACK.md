# Technology Stack — [realtime] Extra Research

**Project:** eq-chatbot-core v1.8.0 — Realtime Voice Provider Integration
**Researched:** 2026-05-24
**Scope:** NEW dependencies only for the `[realtime]` optional extra.
         Existing validated stack (openai, anthropic, httpx, google-genai, pytest-asyncio,
         pydantic, etc.) is NOT re-evaluated here.

---

## Critical Pre-Condition: websockets Is Already a Transitive Dep

Before evaluating what to ADD, the most important finding is what is already
present:

| Package | Version in project | websockets dep |
|---------|-------------------|----------------|
| `google-genai>=1.0.0` (`[vertex]` extra) | 2.6.0 (latest) | `websockets<17.0,>=13.0.0` — CORE, always pulled |
| `openai>=2.0.0,<3.0.0` (core dep) | 2.38.0 (latest) | `websockets<16,>=13` — OPTIONAL, only with `openai[realtime]` |

**Consequence:** Any consumer who installs `eq-chatbot-core[vertex,realtime]` already
has websockets in their environment via google-genai's hard dependency. The `[realtime]`
extra does not need to declare websockets itself — but see the version conflict note below.

---

## WebSocket Library Decision

### Recommendation: `websockets>=13.0,<17.0`

**Declare it explicitly in `[realtime]`**, even though google-genai pulls it as a
transitive dep. Explicit declaration:
1. Documents the dependency for maintainers who install without `[vertex]`
2. Communicates the compatible version range precisely
3. Allows UV's resolver to pick the optimal version upfront

### Why websockets, not httpx WebSocket or websocket-client

| Library | Verdict | Reason |
|---------|---------|--------|
| `websockets` (aaugustin/websockets) | **USE** | Battle-tested, pure Python, no deps, asyncio-native, `websockets.serve()` built in (needed for test fixtures), already a transitive dep via google-genai and openai SDK |
| `httpx` WebSocket | **SKIP** | httpx 0.x does NOT expose a WebSocket client at all — WebSocket support was a planned feature that never shipped in the 0.x series. httpx is HTTP/1.1 + HTTP/2 only. |
| `websocket-client` | **SKIP** | Synchronous-only. Requires threading for async use. Not a good fit for an async-first realtime interface. |
| `aiohttp` WebSocket | **SKIP** | Would pull aiohttp as an extra dep (~3 MB), adds a second async HTTP framework alongside httpx. No advantage over websockets for pure WS client work. |

### Version Conflict: openai SDK pins `websockets<16`

- `openai[realtime]` 2.38.0 pins `websockets<16,>=13` (confirmed via PyPI METADATA)
- `google-genai` 2.6.0 pins `websockets<17.0,>=13.0.0`
- websockets 16.0 (released Jan 2026) satisfies google-genai but NOT openai[realtime]
- **UV resolves to websockets 15.0.1** when both constraints are present — this is fine

**Action for roadmapper:** The `[realtime]` extra should declare `websockets>=13.0,<17.0`
to match google-genai's ceiling. The openai SDK's tighter `<16` bound will be enforced
automatically by UV's resolver. Do NOT add `openai[realtime]` as a dependency of
`eq-chatbot-core[realtime]` — the eq-chatbot-core code will use websockets directly
via `BaseRealtimeWebsocketClient`, which already works against the GlassAgents reference
implementation. The openai SDK `client.realtime.connect()` namespace is NOT used.

---

## OpenAI Realtime: SDK Namespace vs. Raw websockets

### Decision: Raw websockets via `BaseRealtimeWebsocketClient` (port from GlassAgents)

The openai SDK v2 does expose `client.realtime.connect(model=...)` as an async context
manager (confirmed: `AsyncOpenAI.realtime.connect`). It uses websockets under the hood.

**However, do NOT use it.** Reasons:

1. **GlassAgents reference implementation (`client.py`, 391 LOC) is battle-tested** and
   already uses raw `websockets.connect()` via `BaseRealtimeWebsocketClient`. Porting it
   as-is is lower risk than rewriting around the SDK namespace.

2. **The SDK's realtime surface is an optional extra** (`openai[realtime]`). Adding that
   to eq-chatbot-core's core deps or to `[realtime]` would pull in numpy and sounddevice
   if the consumer also uses `voice-helpers`. We avoid that by going direct.

3. **Control over reconnect/backoff logic.** The library's `BaseRealtimeWebsocketClient`
   needs to own the reconnect strategy. The SDK namespace doesn't expose lifecycle hooks.

4. **xAI Grok Voice Agent is OpenAI-Realtime-compatible.** It speaks the same WebSocket
   protocol. Using `BaseRealtimeWebsocketClient` directly means xAI works with the same
   client code — no SDK abstraction layer to fight.

**openai SDK usage in realtime module:** Zero. The realtime providers talk directly to
the WebSocket endpoints. The existing `openai` SDK (already in core) is used only by
the chat-completion provider — untouched.

---

## Gemini Live: SDK vs. Raw websockets

### Decision: Raw websockets via `BaseRealtimeWebsocketClient` (port from GlassAgents)

`google-genai` 2.6.0 exposes `client.aio.live.connect(model=...)` — a high-level async
session that wraps the BidiGenerateContent WebSocket protocol. It internally uses
`from websockets.asyncio.client import connect as ws_connect` (confirmed from google-genai
source).

**However, do NOT use it.** Reasons:

1. **GlassAgents' `GeminiLiveRealtimeClient` (919 LOC) is the authoritative reference.**
   It implements the raw BidiGenerateContent protocol directly, handling setup envelopes,
   manual turn commits, tool response schemas, and event normalization. This code is
   production-tested.

2. **SDK abstraction leaks Gemini-native types** (`GenerateContentResponse`, etc.) that
   would prevent clean normalization to `NormalizedRealtimeEvent`. The library's entire
   value is provider-agnostic normalized events — the SDK would undercut that.

3. **The `google-genai` SDK already in `[vertex]` is for HTTP-based chat completion
   (Gemini Flash, etc.).** Realtime connects to a different endpoint family
   (`generativelanguage.googleapis.com/ws/...`). The Gemini Live WS connection is
   structurally identical to OpenAI's WS connection; both fit the same base class.

**google-genai SDK usage in realtime module:** Zero. The realtime module uses websockets
directly. The `[vertex]` extra and google-genai are for the HTTP Gemini chat provider —
entirely separate code path.

---

## AWS Nova Sonic: boto3 Assessment

### Decision: Pure-Python no-op stub. boto3 MUST NOT be added.

GlassAgents' `nova.py` (91 LOC, confirmed by reading the file) has **zero boto3 imports**.
It is a pure asyncio queue-backed stub proving ABC conformance. The ported version should
stay identical.

**Why not add boto3 for a future production Nova Sonic:**

| Factor | Detail |
|--------|--------|
| Install weight | botocore: 25–65 MB (compressed); boto3 itself: ~1.3 MB; combined: imposes ~27–67 MB on every `[realtime]` installer |
| Granularity | boto3 cannot be split — it ships service JSON data for ALL AWS services, not just Bedrock |
| Usage reality | Nova Sonic stub-only in 1.8.0; zero production consumers today |
| Future path | If a production Nova Sonic implementation is built in 1.9.x, create a separate `[realtime-aws]` extra with boto3. Do NOT bundle it with `[realtime]`. |

**pyproject.toml action:** No boto3 in any extra for 1.8.0.

---

## Test Infrastructure: Mock WebSocket Server

### Decision: Use `websockets.serve()` directly — no new test dependency

`pytest-asyncio>=0.24.0,<2.0.0` is already in `[dev]` and `asyncio_mode = "auto"` is
set in `pytest.ini_options`. This is sufficient for async test functions.

For normalized-event unit tests, the pattern is:

```python
import asyncio
import pytest
import websockets
from websockets.asyncio.server import serve

@pytest.fixture
async def fake_openai_ws(unused_tcp_port):
    async def handler(ws):
        # replay recorded provider frames
        for frame in RECORDED_FRAMES:
            await ws.send(frame)
        await ws.wait_closed()

    async with serve(handler, "localhost", unused_tcp_port) as server:
        yield f"ws://localhost:{unused_tcp_port}"
```

`websockets.serve()` spins up a real TCP server on localhost — no separate library
needed. The `unused_tcp_port` fixture can be provided by `pytest-asyncio` or a simple
`socket.bind(('', 0))` helper.

**No `aioresponses`, `pytest-mock-server`, or `pywsitest` needed.** The websockets
library is self-sufficient for this use case.

One optional addition worth considering for the test layer (NOT a production dep,
already in `[dev]`):

- `pytest-asyncio` — already present, no change needed
- `unittest.mock.AsyncMock` — stdlib, no import needed

---

## [realtime] Extra: Final Dependency Declaration

```toml
[project.optional-dependencies]
realtime = [
    "websockets>=13.0,<17.0",
]
```

**That is the complete list.** One dependency.

Rationale: everything else (openai SDK, google-genai SDK, httpx, pydantic, anyio) is
already in core deps or other extras. The realtime providers implement the WebSocket
protocol directly using websockets, which is the only new runtime dependency.

---

## Install Footprint Comparison

| Extra | New deps added | Approximate size |
|-------|---------------|-----------------|
| `[realtime]` | `websockets` | ~175 KB wheel, zero transitive deps |
| `[azure]` | `azure-ai-inference`, `azure-core` | ~8–12 MB total |
| `[vertex]` | `google-genai` + transitive chain | ~30–50 MB (includes websockets, httpx, google-auth, tenacity, etc.) |
| `[server]` | `fastapi`, `uvicorn`, `sse-starlette` | ~5–8 MB |
| `[local]` | `sentence-transformers` | ~100–200 MB (torch) |

`[realtime]` is the **lightest extra in the entire library.** For users who already have
`[vertex]`, it adds zero bytes to disk (websockets is already present).

---

## Alternative Providers: Future-Proofing Assessment

| Provider | Status | WS Protocol | Path to library inclusion |
|----------|--------|-------------|--------------------------|
| xAI Grok Voice Agent | GA (2026) | OpenAI Realtime-compatible | Zero new deps — `OpenAIRealtimeClient` works as-is with a different `base_url`. Add `xai` provider entry in registry with `base_url="wss://api.x.ai/v1/realtime"`. Likely a 1.8.x minor. |
| ElevenLabs Conversational AI | GA | Proprietary WebSocket (`wss://api.elevenlabs.io/v1/convai/conversation`) | Requires new provider adapter (~200 LOC). No new deps — same websockets base class. Defer to 1.9.0. |
| Deepgram Voice Agent | GA | Proprietary WebSocket | Same as ElevenLabs pattern. New adapter, no new deps. Defer to 1.9.0. |
| Hume AI EVI | GA | Proprietary WebSocket | Hume Python SDK (`hume` on PyPI) could be used but is unnecessary — raw websockets is simpler and avoids a heavy SDK dep (Hume SDK pulls sounddevice, pyaudio). Use raw websockets. Defer to 1.9.0. |
| Mistral Voxtral Realtime | Transcription-focused, GA | WebSocket (STT-only, not full duplex voice agent) | Voxtral is a speech-to-text model, not a bidirectional voice agent in the OpenAI/Gemini sense. Out of scope for realtime voice provider abstraction. Do not include. |

**Key insight for xAI:** Because Grok Voice Agent is OpenAI Realtime API-compatible (same
WebSocket protocol, same event schema), it reuses `OpenAIRealtimeClient` with only a
`base_url` override. No new code needed — just a registry entry. The roadmapper may want
to include this as a "free" addition in 1.8.0 or as a low-effort 1.8.1 follow-up.

---

## Version Pinning Recommendation

```toml
realtime = [
    "websockets>=13.0,<17.0",
]
```

The upper bound `<17.0` mirrors google-genai's ceiling (which is already in `[vertex]`).
When websockets 17.0 is released (if it introduces breaking changes), both `[vertex]` and
`[realtime]` will need ceiling bumps together — keeping them in sync reduces maintenance
surface.

Do NOT pin to `<16` (openai SDK's constraint). UV's resolver handles the openai SDK's
tighter constraint automatically if the consumer also installs the openai SDK with its
realtime extra — which eq-chatbot-core does NOT do.

---

## Sources

- GlassAgents `backend/realtime/websocket_client.py` — production `BaseRealtimeWebsocketClient` using `import websockets`
- GlassAgents `pyproject.toml` — `websockets==15.0.1` confirmed as direct dep
- GlassAgents `backend/realtime/providers/nova.py` — zero boto3, pure asyncio
- PyPI METADATA for `openai==2.38.0`: `websockets<16,>=13; extra == "realtime"`
- PyPI METADATA for `google-genai==2.6.0`: `websockets<17.0,>=13.0.0` (core, not optional)
- PyPI: websockets 16.0 (latest as of 2026-01-10, requires Python ≥3.10, ~175 KB wheel, zero deps)
- [OpenAI Python SDK GitHub](https://github.com/openai/openai-python) — `client.realtime.connect()` confirmed in v2
- [google/genai live.py](https://github.com/googleapis/python-genai/blob/main/google/genai/live.py) — `from websockets.asyncio.client import connect as ws_connect` (MEDIUM confidence via WebSearch + PyPI dep confirmed)
- [xAI Voice Agent Docs](https://docs.x.ai/developers/model-capabilities/audio/voice-agent) — OpenAI Realtime API compatible
- [websockets changelog](https://websockets.readthedocs.io/en/stable/project/changelog.html) — version history and Python compatibility
- boto3/botocore GitHub issues — install size 25–65 MB for botocore confirmed

---

*Research completed: 2026-05-24*
