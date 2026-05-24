# Feature Landscape: Realtime Voice Provider Integration (v1.8.0)

**Domain:** Realtime bidirectional voice streaming — provider-agnostic library layer
**Researched:** 2026-05-24
**Scope:** Provider landscape evaluation for eq-chatbot-core `[realtime]` extra
**Milestone:** v1.8.0 (production providers) + v1.9.0 (additional providers)

---

## Context: What the Contract Surface Requires

Every provider integrated into eq-chatbot-core must satisfy `RealtimeAdapterContract` — 11 async methods plus a `NormalizedRealtimeEvent` iterator. The `RealtimeProviderCapabilities` dataclass captures per-provider behavioral differences:

```
streaming_audio_input, streaming_audio_output, server_vad,
manual_turn_commit_required, tool_calling,
tool_result_submission_mode ("conversation_item" | "provider_call_id"),
voice_selection, interruption_cancel, startup_validation
```

The library is PCM16 mono-only in v1.8.0 (Captain decision). Any provider requiring Opus or μ-law as the only transport format cannot be integrated without an audio conversion layer (out of scope for v1.8.0).

---

## Table Stakes

Features every integrated provider must provide. Missing any = cannot implement the contract.

| Feature | Why Required | Notes |
|---------|--------------|-------|
| Bidirectional audio streaming | Core contract: `append_client_audio` + `response.audio.delta` events | Must be persistent connection, not request/response |
| PCM16 audio input (or transcoding-free path) | Library PCM16-only policy for v1.8.0 | Providers requiring Opus-only input are blocked until v1.9.0 |
| Normalized event emission | `iter_normalized_events()` must yield all 12 `NormalizedRealtimeEventTypes` | Provider-native events mapped to normalized schema |
| Session lifecycle | `connect()`, `initialize_session()`, `close()` must be implementable | Some providers call this "room" or "session" creation |
| Audio output streaming | `response.audio.delta` as raw PCM16 bytes | Providers that only return complete audio clips are incompatible |
| Graceful error propagation | `ERROR` event type in normalized stream | Auth failures, rate limits, overload must surface as normalized events |
| Official Python SDK or raw HTTP/WS reachable from Python | Library is pure Python | Providers with only browser SDKs are blocked |

## Differentiators

Features that meaningfully distinguish providers. Not required by the contract but influence provider selection.

| Feature | Provider(s) | Value for GlassAgents Use Case |
|---------|-------------|-------------------------------|
| Server-side VAD (Voice Activity Detection) | OpenAI, xAI Grok, AWS Nova Sonic | Eliminates client-side turn detection; less iOS audio processing |
| Emotion / prosody detection in output events | Hume EVI 3 | Unique — enables UI reactions to speaker emotional state |
| 200 K+ custom voices + zero-shot voice cloning | ElevenLabs, Hume EVI 3, xAI Grok | Brand differentiation; user voice personalization |
| Open-weight model available for self-hosting | Mistral Voxtral TTS (4B) | EU data sovereignty without cloud dependency |
| Multi-LLM backend (BYOLLM) | DeepGram Voice Agent, Hume EVI 3 | Swap underlying intelligence without changing voice layer |
| Tool calling including web/X search natively | xAI Grok Voice Agent | Reduces tool dispatcher complexity in GlassAgents |
| EU data residency (certified Sovereign Cloud) | AWS Bedrock (ESC, Jan 2026) | GDPR compliance without data-processing agreements |
| Sub-100 ms time-to-first-audio | Cartesia Sonic-3 (~40ms turbo) | Perceived latency reduction for turn transitions |
| Multilingual (70+ languages) | Gemini Live | Broadest language coverage in single provider |
| Native G.711 μ-law / A-law support | xAI Grok Voice Agent | Telephony integration without transcoding |

## Anti-Features

Features explicitly NOT included in eq-chatbot-core, for any provider.

| Anti-Feature | Why Excluded | Correct Location |
|--------------|-------------|-----------------|
| Custom voice training / fine-tuning | Library is a transport layer, not a model-hosting platform | Consumer app or provider dashboard |
| Audio recording / buffering to disk | Consumers own audio pipeline; library yields bytes | GlassAgents `audio_uplink.py` |
| Turn management policy | App-level concern (barge-in strategy, silence detection thresholds) | GlassAgents `turn_state.py` |
| SIP / PSTN telephony bridging | Telecom-specific; out of scope for chatbot library | Separate integration layer |
| Browser-side WebRTC transport | Library targets server-side Python | Consumer web frontend |
| Conversation session persistence / storage | Library is stateless | Consumer app database |
| LLM routing / fallback logic across providers | Would make library opinionated about business logic | Consumer orchestration layer |
| Provider billing / subscription management | Not a library concern | Consumer app or provider dashboard |
| Agent persona configuration beyond `instructions` | App-level; `initialize_session(instructions=...)` is the boundary | Consumer session_modes.py |

---

## Provider Evaluations

### 1. OpenAI Realtime API

**Status in v1.8.0:** PRODUCTION — already ported from GlassAgents reference impl (391 LOC).

OpenAI's Realtime API (GA since October 2024) is the most mature bidirectional voice API available. It exposes both WebSocket (`wss://api.openai.com/v1/realtime?model=...`) and WebRTC transports; the library uses WebSocket for server-mediated compliance. The current production model is `gpt-realtime-2`, with native server-side VAD eliminating the need for explicit turn commits. Tool results are submitted as conversation items (the `"conversation_item"` mode in `RealtimeProviderCapabilities`). Response cancellation is native via `response.cancel`. Eight built-in voices are available. Pricing: ~$0.06/min audio input + ~$0.24/min audio output (uncached); prompt caching drops effective cost to ~$0.05–0.10/min. The official `openai` Python SDK (v2+) includes full realtime support. EU note: OpenAI has no EU-resident data processing by default; GDPR requires DPA. For GDPR-strict environments, Azure OpenAI Realtime is the path (EU regions available).

**RealtimeProviderCapabilities mapping:**
```
streaming_audio_input: true  | streaming_audio_output: true
server_vad: true             | manual_turn_commit_required: false
tool_calling: true           | tool_result_submission_mode: "conversation_item"
voice_selection: true        | interruption_cancel: true
```

**Fit to contract:** PERFECT — reference implementation. No extensions needed.

---

### 2. Google Gemini Live

**Status in v1.8.0:** PRODUCTION — already ported from GlassAgents reference impl (919 LOC).

Gemini Live API (GA on Vertex AI, Gemini API also available) is the second production provider. WebSocket endpoint: `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent`. The current recommended model is `gemini-2.5-flash-native-audio-preview-12-2025`. Unlike OpenAI, Gemini Live has no server VAD — clients must call `commit_client_turn()` explicitly, and the library surfaces this via `manual_turn_commit_required: true`. Tool results use `provider_call_id` submission mode. No native voice selection (fixed voice), no native interruption cancel. Multilingual: 70 languages. EU: Vertex AI offers EU (`europe-west*`) regions with data residency. The `google-cloud-aiplatform` and `google-generativeai` SDKs both provide access; raw WebSocket usage (as in the reference impl) avoids the SDK overhead.

**RealtimeProviderCapabilities mapping:**
```
streaming_audio_input: true  | streaming_audio_output: true
server_vad: false            | manual_turn_commit_required: true
tool_calling: true           | tool_result_submission_mode: "provider_call_id"
voice_selection: false       | interruption_cancel: false
```

**Fit to contract:** PERFECT — reference implementation. `cancel_response()` must be simulated (close + reconnect pattern from GlassAgents reference).

---

### 3. AWS Bedrock Nova Sonic (Nova 2 Sonic)

**Status in v1.8.0:** STUB only (Captain decision Q1 — promote to production in v1.9.0 if user lands).

AWS Nova 2 Sonic (`amazon.nova-2-sonic-v1:0`) is a production GA speech-to-speech model on Amazon Bedrock. The transport is **not WebSocket** — it uses Bedrock's `InvokeModelWithBidirectionalStream` over **HTTP/2** (bidi streaming), accessed via `boto3` / `botocore`. This means the base `BaseRealtimeWebsocketClient` class does not apply; a separate `BaseRealtimeBedrocktClient` (HTTP/2 bidi) would be needed. Latency under 500ms. Server-side VAD available. Tool calling (function calling) supported. Seven languages. Audio: PCM16. Pricing: $0.0034/1K speech input tokens + $0.0136/1K speech output tokens (~$0.017/min estimated). EU: available in `eu-north-1`, with AWS European Sovereign Cloud (Germany-based, Jan 2026) for strict GDPR compliance. The GlassAgents existing stub (91 LOC) is ABC-conformant only — a production impl requires non-trivial HTTP/2 bidi work with boto3 event streams. **Key blocker for v1.8.0 production:** divergent transport (HTTP/2 not WS) means significant new infrastructure; not worth the v1.8.0 scope.

**RealtimeProviderCapabilities mapping (for stub):**
```
streaming_audio_input: true  | streaming_audio_output: true
server_vad: true             | manual_turn_commit_required: false
tool_calling: true           | tool_result_submission_mode: "conversation_item"
voice_selection: true        | interruption_cancel: true
startup_validation: false    (stub — no real connection)
```

**Fit to contract:** NEEDS EXTENSION — transport layer is HTTP/2, not WebSocket; `BaseRealtimeWebsocketClient` cannot be reused. Production impl deferred to v1.9.0.

---

### 4. DeepGram Voice Agent

**Status evaluated for:** v1.8.0 or v1.9.0 inclusion decision.

DeepGram's Voice Agent API is an orchestrated pipeline (STT → LLM → TTS) exposed as a single WebSocket session, GA and actively deployed in production. The architecture differs fundamentally from OpenAI/Gemini: DeepGram acts as a full orchestration layer — it manages turn detection, LLM calls (bring-your-own or DeepGram-hosted), and TTS synthesis. Audio in/out is `linear16` at configurable sample rates (24 000 Hz supported — PCM16 compatible). WebSocket-based. Official Python SDK on PyPI (`deepgram-sdk`), actively maintained with async support. Tool/function calling is supported (mid-conversation function calls). Server-side VAD and barge-in detection are built in. Voice selection: multiple Aura TTS voices. Pricing: flat $4.50/hr (includes STT + LLM + TTS) or unbundled per-component billing. BYOLLM allows pointing at any OpenAI-compatible endpoint. EU: Standard cloud; GDPR compliance via DPA available; no EU-sovereign inference node.

**Architecture consideration for the contract:** Because DeepGram orchestrates the LLM internally, `initialize_session(tools=...)` maps to configuring the LLM function schema at session setup, not a separate message round-trip. The normalized event model maps cleanly (DeepGram emits transcript events that map to `INPUT_SPEECH_STARTED/STOPPED`, audio delta for output, and tool call events).

**RealtimeProviderCapabilities mapping (proposed):**
```
streaming_audio_input: true  | streaming_audio_output: true
server_vad: true             | manual_turn_commit_required: false
tool_calling: true           | tool_result_submission_mode: "provider_call_id"
voice_selection: true        | interruption_cancel: true
```

**Fit to contract:** GOOD — WebSocket transport maps to `BaseRealtimeWebsocketClient`. The orchestrated nature means the provider adapter is simpler than Gemini Live (no manual turn commit, no tool result conversation item threading). SDK quality is HIGH.

---

### 5. ElevenLabs Conversational AI (ElevenAgents)

**Status evaluated for:** v1.9.0 inclusion decision.

ElevenLabs Conversational AI (branded as ElevenAgents in 2026) exposes a WebSocket API (`wss://api.elevenlabs.io/v1/convai/conversation?agent_id={agent_id}`) for bidirectional voice sessions. Audio format: PCM16 at 16 000 Hz — **note the 16 kHz vs 24 kHz for OpenAI**; the library's `INPUT_AUDIO_SAMPLE_RATE` constant would need provider-specific override. Official Python SDK (`elevenlabs`) on PyPI, maintained. Tool calling: supported natively (MCP tool use in Conversational 2.0), client-side tool execution. Voice selection: 3 000+ voices including 200K+ via cloning — strongest voice library in the ecosystem. Pricing: $0.08–$0.12/min depending on LLM tier (per-minute, not per-token). Silence discount (95% reduction for pauses >10s). EU: Standard SaaS; GDPR DPA available. The primary differentiator is voice quality and the enormous voice library — the Conversational AI wraps ElevenLabs Flash v2.5 TTS which is industry-leading in naturalness.

**Architecture consideration:** ElevenLabs operates an agent-centric model (you pre-configure an agent_id with system prompts, voice, LLM). This constrains `initialize_session(instructions=...)` to be a pre-session configuration step rather than a per-connection parameter — the adapter must manage agent config via REST before opening the WebSocket. This is a meaningful adapter complexity.

**RealtimeProviderCapabilities mapping (proposed):**
```
streaming_audio_input: true  | streaming_audio_output: true
server_vad: true             | manual_turn_commit_required: false
tool_calling: true           | tool_result_submission_mode: "provider_call_id"
voice_selection: true        | interruption_cancel: true
```

**Fit to contract:** MEDIUM EFFORT — WebSocket transport compatible, SDK available, but agent-centric config model requires pre-session REST calls to map `initialize_session(instructions=...)`. Sample rate mismatch (16 kHz) requires adapter-layer resampling or a `session_sample_rate` capability field extension. Defer to v1.9.0.

---

### 6. Hume AI EVI 3

**Status evaluated for:** v1.9.0 or "do not add" decision.

Hume EVI 3 is the third generation of Hume's Empathic Voice Interface — a speech-language model that processes and generates audio with emotional expression baked in (not post-processed). WebSocket-based (`client.empathic_voice.chat.connect(...)`). Official `hume` Python SDK on PyPI (supports Python 3.9–3.11; **3.12+ compatibility needs verification**). Audio: PCM16 supported, plus WAV and MP3. Tool calling: yes, but **only when the supplemental LLM is Claude, GPT, Gemini, or Moonshot AI** — the tool calls route through the backing LLM and EVI handles the voice layer. Voice selection: 200K+ custom voices, zero-shot cloning from 30s of audio; EVI 3 can capture rhythm, tone, and personality (not just timbre). Pricing: $0.04–$0.07/min depending on plan. EU: standard cloud, GDPR DPA available; no EU-sovereign inference. The unique differentiator is **prosody/emotion output events** — EVI emits emotion scores alongside audio deltas, which is not representable in the current `NormalizedRealtimeEvent` schema.

**Architecture consideration:** The emotion output events would require an extension to `NormalizedRealtimeEvent` (e.g., an `EMOTION_SCORES` type not in the current 12-constant set). Adding provider-specific event types would widen the normalized schema and add consumer complexity. Python 3.12/3.13 SDK compatibility is unclear.

**RealtimeProviderCapabilities mapping (proposed):**
```
streaming_audio_input: true   | streaming_audio_output: true
server_vad: true              | manual_turn_commit_required: false
tool_calling: true            (conditional on LLM choice)
tool_result_submission_mode: "provider_call_id"
voice_selection: true         | interruption_cancel: true
```

**Fit to contract:** REQUIRES SCHEMA EXTENSION for emotion events — the `NormalizedRealtimeEventTypes` set would need `EMOTION_SCORES` or a metadata extension on the existing payload. Conditional tool calling (LLM-dependent) complicates capability declaration. Recommend deferring to v1.9.0 with a schema extension RFC first.

---

### 7. xAI Grok Voice Agent API

**Status evaluated for:** v1.9.0 inclusion decision.

xAI launched the Grok Voice Agent API on December 17, 2025 (GA). WebSocket endpoint: `wss://api.x.ai/v1/realtime`. Architecture mirrors OpenAI Realtime closely (same overall session model, server VAD). Pricing: flat $0.05/min (100 concurrent sessions per team, 30-min max session). Audio: PCM16 and native G.711 μ-law/A-law support. Tool calling: supports `web_search`, `x_search`, `file_search`, remote MCP tools, and custom function tools. Voice selection: yes, plus voice cloning from short audio clips. EU: data processing agreements and EU data residency options available (confirmed). The API also supports SIP and LiveKit transports in addition to WebSocket. As of May 2026 there is **no official Python SDK** — integration is via raw WebSocket or through LiveKit's Python SDK as a transport wrapper. The $0.05/min flat rate is the most competitive among full-stack providers.

**RealtimeProviderCapabilities mapping (proposed):**
```
streaming_audio_input: true  | streaming_audio_output: true
server_vad: true             | manual_turn_commit_required: false
tool_calling: true           | tool_result_submission_mode: "conversation_item"
voice_selection: true        | interruption_cancel: true
```

**Fit to contract:** GOOD CONCEPTUALLY — transport and session model are very close to OpenAI Realtime, so the adapter would be a near-fork of the OpenAI provider. Blocker: no official Python SDK; raw WS implementation adds maintenance burden. Defer to v1.9.0 pending SDK availability or clear community library.

---

### 8. Mistral Voxtral

**Status evaluated for:** "do not add" in library context.

Mistral's Voxtral product line in 2026 consists of three distinct components: Voxtral Transcribe 2 (speech-to-text, sub-200ms, $0.006/min), Voxtral TTS (4B open-weight model, streaming, $0.016/1K chars), and Voxtral Mini 4B Realtime (self-hosted ASR, Hugging Face model). **Mistral does NOT currently offer a bidirectional speech-to-speech conversational API** equivalent to OpenAI Realtime or Gemini Live. The "realtime" in "Voxtral Realtime" refers to low-latency STT inference, not a conversational loop. Building a voice agent with Voxtral requires assembling STT + LLM + TTS components separately — that is a pipeline architecture, not a provider-native session. The open-weight TTS is a compelling building block for self-hosted voice (EU sovereignty, no per-minute cloud cost) but it is not a `RealtimeAdapterContract` target. Recommended action: note Voxtral TTS as a future building block for a self-hosted pipeline provider; do not add to realtime provider registry in v1.8.0 or v1.9.0.

**Fit to contract:** DOES NOT FIT — no bidirectional speech-to-speech session API. STT + TTS components exist but no orchestrated conversational loop. Do not add as a realtime provider.

---

### 9. Cartesia Sonic

**Status evaluated for:** "do not add" in library context.

Cartesia Sonic-3 is a TTS model with a WebSocket API for low-latency streaming synthesis (sub-100ms TTFA, ~40ms turbo variant). It is NOT a bidirectional voice agent — there is no speech input processing. Cartesia is building toward a full pipeline with "Ink" (STT) and "Line" (agent platform), but as of May 2026 these are in early availability and not a unified session-based conversational API. The Cartesia Python SDK (`cartesia`, v3.x on PyPI) is mature for TTS use. The existing pipecat and LiveKit integrations use Cartesia as a TTS component within a larger pipeline (not a standalone voice agent provider). **Recommended action:** same as Voxtral — valuable TTS component for a future pipeline-assembled provider; not a `RealtimeAdapterContract` target today.

**Fit to contract:** DOES NOT FIT — TTS-only; no STT or bidirectional session. Do not add as a realtime provider.

---

### 10. LiveKit Agents

**Note: Framework, not provider.** LiveKit Agents is an open-source framework for building voice agents that integrates with multiple STT/TTS/LLM providers (including Deepgram, Cartesia, OpenAI, ElevenLabs). It manages WebRTC rooms, media handling, and agent lifecycle. It is not a provider in the `RealtimeAdapterContract` sense — it sits at the application layer, above the transport layer. eq-chatbot-core is a library used by applications; adding LiveKit as a "provider" would invert the abstraction. **Correct relationship:** consumers (like GlassAgents) can use LiveKit Agents as their application framework and consume eq-chatbot-core providers within that framework. No action needed in the library.

---

## Feature Dependencies

```
PCM16 audio pipeline (library constant) → All provider audio adapters
BaseRealtimeWebsocketClient → OpenAI, Gemini Live, DeepGram, ElevenLabs, xAI adapters
BaseRealtimeBedrocktClient (new, HTTP/2) → Nova Sonic production impl
ToolDefinition dataclass (library-owned) → tool_calling on all providers
NormalizedRealtimeEvent schema (12 constants) → all providers map to this
EMOTION_SCORES event type (RFC needed) → Hume EVI 3 (blocks EVI 3 integration)
Sample-rate negotiation extension → ElevenLabs (16kHz vs 24kHz library default)
```

---

## MVP Recommendation for v1.8.0

Prioritize:
1. OpenAI Realtime — already reference-implemented; PCM16/24kHz; server VAD; tool calling; GA
2. Gemini Live — already reference-implemented; PCM16/24kHz; explicit turn commit; tool calling; GA
3. AWS Nova Sonic — stub only (ABC conformance); explicitly deferred per Captain Q1 decision
4. Mock provider — queue-backed, no network; essential for consumer test suites

Defer to v1.9.0: DeepGram Voice Agent, xAI Grok Voice Agent
Defer with RFC first: ElevenLabs (sample rate mismatch), Hume EVI 3 (schema extension needed)
Do not add: Mistral Voxtral (no conversational API), Cartesia Sonic (TTS only)

---

## Recommendation Table

| Provider | Version | Rationale |
|----------|---------|-----------|
| OpenAI Realtime | **v1.8.0 — PRODUCTION** | Reference impl exists; GA; server VAD; tool calling; PCM16/24kHz exact match |
| Gemini Live | **v1.8.0 — PRODUCTION** | Reference impl exists; GA; Vertex EU; 70 languages; PCM16/24kHz exact match |
| AWS Nova Sonic | **v1.8.0 — STUB** | Captain Q1 decision; HTTP/2 transport needs new base class; promote in v1.9.0 if user lands |
| Mock provider | **v1.8.0 — PRODUCTION** | Zero-network test harness required by GlassAgents migration |
| DeepGram Voice Agent | **v1.9.0** | GA; Python SDK mature; WebSocket compatible; PCM16/24kHz; BYOLLM; but no current user driving it and flat $4.50/hr pricing model needs evaluation |
| xAI Grok Voice Agent | **v1.9.0** | Compelling ($0.05/min flat, server VAD, tool+search); OpenAI-compatible session model; blocked by no official Python SDK today |
| ElevenLabs Conversational AI | **v1.9.0 (after RFC)** | Best voice library (3K+ voices); GA; but 16kHz sample rate requires contract extension + agent-centric config pre-session REST |
| Hume AI EVI 3 | **v1.9.0 (after RFC)** | Unique emotion output events; Python SDK 3.12+ compatibility unclear; requires `EMOTION_SCORES` schema extension; conditional tool calling |
| AWS Nova Sonic production | **v1.9.0** | Promote stub to production; needs `BaseRealtimeBedrocktClient` (HTTP/2 bidi, not WS); EU sovereign cloud available |
| Mistral Voxtral | **Do not add** | No bidirectional speech-to-speech session API; STT+TTS pipeline only; open-weight TTS may be a future pipeline building block but is not a RealtimeAdapterContract provider |
| Cartesia Sonic | **Do not add** | TTS only, no STT; "Line" agent platform too early; not a session-based realtime provider |
| LiveKit Agents | **Do not add** | Application framework, not a provider; correct relationship is consumer uses LiveKit + eq-chatbot-core providers together |

---

## Contract Extension Needs by Provider

| Provider | Extension Required | Blocking v1.8.0? |
|----------|-------------------|------------------|
| OpenAI | None | No |
| Gemini Live | None | No |
| Nova Sonic (stub) | None | No |
| Nova Sonic (production) | `BaseRealtimeBedrocktClient` (HTTP/2 bidi) | Deferred to v1.9.0 |
| DeepGram | None — maps cleanly | Not in v1.8.0 scope |
| xAI Grok | None — session model mirrors OpenAI | Not in v1.8.0 scope |
| ElevenLabs | `session_sample_rate` capability field in `RealtimeProviderCapabilities` | RFC needed before v1.9.0 |
| Hume EVI 3 | `EMOTION_SCORES` event type + `tool_calling_conditional` capability flag | RFC needed before v1.9.0 |

---

## Sources

- [OpenAI Realtime API — Advancing voice intelligence](https://openai.com/index/advancing-voice-intelligence-with-new-models-in-the-api/)
- [OpenAI Realtime costs guide](https://developers.openai.com/api/docs/guides/realtime-costs)
- [OpenAI Pricing (realtime audio tokens)](https://openai.com/api/pricing/)
- [Gemini Live API overview](https://ai.google.dev/gemini-api/docs/live-api)
- [Gemini Live WebSocket quickstart](https://ai.google.dev/gemini-api/docs/live-api/get-started-websocket)
- [Gemini Live on Vertex AI blog](https://cloud.google.com/blog/topics/developers-practitioners/how-to-use-gemini-live-api-native-audio-in-vertex-ai)
- [AWS Introducing Nova Sonic](https://aws.amazon.com/blogs/aws/introducing-amazon-nova-sonic-human-like-voice-conversations-for-generative-ai-applications/)
- [AWS Nova Sonic bidirectional streaming API docs](https://docs.aws.amazon.com/nova/latest/userguide/speech-bidirection.html)
- [AWS Nova pricing](https://aws.amazon.com/nova/pricing/)
- [AWS Bedrock regional availability](https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html)
- [DeepGram Voice Agent API](https://deepgram.com/product/voice-agent-api)
- [DeepGram configure voice agent](https://developers.deepgram.com/docs/configure-voice-agent)
- [DeepGram voice agent audio docs](https://developers.deepgram.com/docs/voice-agent-audio-playback)
- [DeepGram pricing](https://deepgram.com/pricing)
- [ElevenLabs Agent WebSocket API](https://elevenlabs.io/docs/eleven-agents/api-reference/eleven-agents/websocket)
- [ElevenLabs Conversational AI cost](https://help.elevenlabs.io/hc/en-us/articles/29298065878929-How-much-does-ElevenLabs-Agents-formerly-Conversational-AI-cost)
- [Hume AI EVI 3 announcement](https://www.hume.ai/blog/announcing-evi-3-api)
- [Hume AI EVI tool use docs](https://dev.hume.ai/docs/speech-to-speech-evi/features/tool-use)
- [Hume AI audio docs](https://dev.hume.ai/docs/speech-to-speech-evi/guides/audio)
- [Hume AI pricing](https://www.hume.ai/pricing)
- [xAI Grok Voice Agent API launch](https://x.ai/news/grok-voice-agent-api)
- [xAI Voice overview docs](https://docs.x.ai/docs/guides/voice)
- [xAI Voice Agent API docs](https://docs.x.ai/developers/model-capabilities/audio/voice-agent)
- [Mistral Voxtral TTS release](https://mistral.ai/news/voxtral-tts)
- [Mistral Voxtral Mini 4B Realtime — Hugging Face](https://huggingface.co/mistralai/Voxtral-Mini-4B-Realtime-2602)
- [Cartesia Sonic-3 product](https://cartesia.ai/sonic)
- [Cartesia Python SDK](https://pypi.org/project/cartesia/)
- [Cartesia 2026 changelog](https://docs.cartesia.ai/changelog/2026)
