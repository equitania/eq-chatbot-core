# Domain Pitfalls: Realtime Voice in eq-chatbot-core

**Domain:** Bidirectional realtime voice WebSocket clients ported into a multi-consumer PyPI library
**Researched:** 2026-05-24
**Sources:** GlassAgents reference implementation (battle-tested through Phase 3 Window 1), existing codebase analysis (CONCERNS.md, TESTING.md, mcp/client.py), handoff spec (eq-chatbot-core-realtime-handoff.md)

---

## Critical Pitfalls

Mistakes that cause session data loss, silent breakage, or production rewrites.

---

### PITFALL-01: WebSocket Closed Exception Not Mapped to Close Code

**What goes wrong:** `websockets.exceptions.ConnectionClosed` carries `.code` (1000, 1001, 1006, 4000–4999) and `.reason`. The existing `BaseRealtimeWebsocketClient.close()` catches bare `Exception` and wraps it as `RealtimeClientError`. Code 1006 (abnormal closure — no close frame received, e.g. network drop) is indistinguishable from 1000 (normal) at the `RealtimeClosedError` boundary. Consumers that want to reconnect on 1006 but not on 1000 cannot tell which happened.

**Why it happens:** The GlassAgents base (`websocket_client.py:144–153`) catches `Exception` in `close()` and re-raises as `RealtimeClientError`. `iter_events` silently returns on any `RealtimeClosedError` regardless of code. The close code is only available inside `ws_exceptions.ConnectionClosed`, which is swallowed at the boundary.

**Consequences:** Consumer reconnect logic cannot distinguish graceful shutdown from network death. Reconnect storms possible when provider drops with 1006 and consumer immediately retries in a tight loop. Silent data loss mid-stream (no way to distinguish "done" from "crash").

**Prevention:**
- In `BaseRealtimeWebsocketClient`, catch `ws_exceptions.ConnectionClosed` **before** the bare `except Exception` and surface the code: `RealtimeClosedError(code=exc.code, reason=exc.reason)`.
- Add `code: int | None` and `retriable: bool` to `RealtimeClosedError`.
- In `iter_events`, propagate the exception rather than silently `return` — let the caller decide whether to reconnect.
- Unit test: mock `ws.recv()` to raise `ConnectionClosed` with code=1006; assert caller receives `RealtimeClosedError(code=1006, retriable=True)`.

**WARNING SIGN:** Logs show reconnect attempts immediately after a session ends cleanly (code 1000). Or: provider drops mid-utterance and the client loop exits silently without any log.

**Phase:** contracts / foundation (must be in base class before any concrete provider is built)

---

### PITFALL-02: Reconnect Storm on Provider Rate-Limit or Regional Outage

**What goes wrong:** No reconnect/backoff is present in the current `BaseRealtimeWebsocketClient`. The handoff spec §4.4 notes "documented reconnect/backoff strategy" as a NICE-to-have. If consumers implement their own retry loop around `connect()` with no delay, a provider-side 429 or 503 triggers immediate reconnect → immediate 429 → reconnect → ... exhausting the rate limit faster.

**Why it happens:** The base class exposes a plain `async def connect()` with no retry semantics. A consumer calling `await client.connect()` inside `while True:` is the natural recovery pattern — and it's maximally destructive during an outage.

**Consequences:** API key banned or rate-limited further. Provider IP-blocks the origin. On regional outage, entire GlassAgents session fleet hammers the provider simultaneously (thundering herd).

**Prevention:**
- `BaseRealtimeWebsocketClient` should expose `async def connect_with_backoff(max_attempts: int = 5, base_delay_s: float = 1.0, max_delay_s: float = 30.0)` implementing truncated exponential backoff with jitter (`delay = min(base * 2**attempt + random.uniform(0, 1), max_delay)`).
- HTTP 429 responses from the WebSocket handshake (websockets raises `InvalidStatusCode` with `status_code=429`) should be caught and surfaced as `RealtimeRateLimitError` (subclasses `RealtimeClientError`) with `retry_after` extracted from `Retry-After` header when present.
- Document that callers MUST use `connect_with_backoff` rather than rolling their own loop.
- Unit test: mock `websockets.connect` to raise `InvalidStatusCode(429)` three times then succeed; assert backoff delays are applied and final connection succeeds.

**WARNING SIGN:** Log lines showing `"Failed to connect"` followed immediately (< 100ms later) by another `"Failed to connect"` in a tight loop.

**Phase:** foundation (base class)

---

### PITFALL-03: Double-Cancel Race During Backoff Reconnect

**What goes wrong:** When `cancel_response()` is called during an ongoing reconnect attempt, the cancellation event is lost (the connection is not yet live). When the connection is re-established and the response resumes, no cancel was sent — the audio output continues after the user has already triggered interruption. If the consumer then calls `cancel_response()` a second time on the resumed connection, the provider receives the cancel but the state machine is confused: the response ID may have changed between sessions.

**Why it happens:** `cancel_response()` calls `send_json()` which raises `RealtimeClosedError` if the socket is not connected. The caller (GlassAgents `bridge.py`, stays in app) may catch and suppress that error, resulting in zero cancels sent. The subsequent reconnect initializes a fresh session with a new response ID; the stale cancel has no target.

**Consequences:** Audio output continues after user interruption. Provider accumulates unbilled credits. Session state in the consumer (e.g. turn manager) diverges from provider state.

**Prevention:**
- During reconnect, queue pending `cancel_response` calls and replay them after session re-initialization only if the same `response_id` is still valid.
- Alternatively, document that `cancel_response` is "best-effort and session-scoped" — callers must not rely on it surviving a reconnect.
- Add a `_pending_cancel_response_id: str | None` field: if set when `_on_connected` fires, replay the cancel before yielding `SESSION_READY`.
- Unit test: simulate reconnect while cancel pending; assert cancel is replayed after reconnect or that `RESPONSE_DONE` is emitted to flush state.

**WARNING SIGN:** Log shows `cancel_response` called but `RealtimeClosedError` logged, followed by audio delta events after the session re-establishes.

**Phase:** OpenAI port (only OpenAI supports `interruption_cancel`)

---

### PITFALL-04: WebSocket Connection Not Closed on Exception Path

**What goes wrong:** The existing `BaseRealtimeWebsocketClient.connect()` sets `self._ws` before calling `_on_connected()`. If `_on_connected()` raises (or if `initialize_session()` raises immediately after connect), `self._ws` is set but `close()` is never called. The underlying TCP connection stays open indefinitely.

**Why it happens:** The current connect path in `websocket_client.py:53–82` has no `try/finally` around the post-connect setup. `close()` sets `self._ws = None` before calling `ws.close()` — so if the caller calls `close()` on a half-initialized instance, `ws.close()` is called correctly. But if the **caller** never calls `close()` (e.g. because the exception propagates up through a `with` block they didn't write), the connection leaks.

**Consequences:** Open TCP connections accumulate over the lifetime of the process. Provider-side session quota exhausted without corresponding active sessions on the client side.

**Prevention:**
- Implement `async def __aenter__ / __aexit__` on `BaseRealtimeWebsocketClient` that call `connect()` / `close()` and wrap post-connect setup in `try/except`.
- Document that the preferred usage is `async with client:`.
- In `connect()`, wrap `_on_connected()` in `try/except`; on failure, call `await self.close()` before re-raising.
- Unit test: mock `_on_connected` to raise; assert that `ws.close()` was called.

**WARNING SIGN:** Increasing TCP `CLOSE_WAIT` connections visible in `ss -tp` or `netstat`. Provider error "max concurrent sessions exceeded" despite apparent low client count.

**Phase:** foundation (base class)

---

### PITFALL-05: asyncio Task Leak — Receiver/Sender Tasks Not Cancelled on Close

**What goes wrong:** Consumers often spawn a background task to drain `iter_normalized_events()` (the natural async consumer pattern: `asyncio.create_task(bridge.run())`). If `close()` is called but the `iter_normalized_events` coroutine is still running in that task, the task blocks on `recv_json()` indefinitely. The task is never cancelled. On process exit `asyncio` logs "Task was destroyed but it is pending".

**Why it happens:** `iter_events()` is an `AsyncIterator` that loops until `RealtimeClosedError`. The `close()` method closes the socket, which causes the next `ws.recv()` to raise `ConnectionClosed`, which is caught and causes `iter_events()` to `return`. But if `close()` is called from another coroutine while `recv_json()` is awaiting, the task does cancel — however if the consumer holds the task reference and never cancels it, the task outlives the client.

**Consequences:** Memory leak. In long-lived processes (HTTP sidecar serving Avalonia), accumulated orphan tasks eventually exhaust the event loop.

**Prevention:**
- `BaseRealtimeWebsocketClient` should track a `_recv_task: asyncio.Task | None` if the library spawns any internal background tasks.
- If the library does NOT spawn internal tasks (current design), document explicitly in docstring: "Callers are responsible for cancelling any tasks awaiting `iter_normalized_events` before calling `close()`."
- Provide a helper `async def run_until_closed(callback)` that encapsulates the task lifecycle and cancels cleanly.
- Unit test: call `close()` while a task is pending on `iter_normalized_events`; assert the task completes within 100ms.

**WARNING SIGN:** `asyncio` debug mode logs "Task was destroyed but it is pending!" pointing at `iter_events`. Or: process memory grows with each session.

**Phase:** foundation (base class)

---

### PITFALL-06: PCM16 Sample-Rate Mismatch

**What goes wrong:** The library publishes `INPUT_AUDIO_SAMPLE_RATE = 24_000` (from `client.py:26`). OpenAI Realtime expects 24 kHz. The current Gemini Live adapter sends the rate in the MIME type: `audio/pcm;rate=24000`. If a consumer resamples or records at 16 kHz (common for telephony / iOS `AVAudioSession`) and sends those bytes to the library without resampling, the provider receives incorrectly-pitched audio and may fail VAD or produce garbled output silently (no error, just bad audio quality or missed speech detection).

**Why it happens:** The library cannot validate the sample rate of raw PCM bytes — it is just bytes. The constant `INPUT_AUDIO_SAMPLE_RATE` is an API contract, not an enforced invariant. GlassAgents' `audio_uplink.py` (stays in app) handles the resampling; the library does not.

**Consequences:** Silent audio quality degradation. Server VAD fails to trigger (OpenAI). Gemini ignores long utterances. Extremely hard to debug because the provider accepts the audio and proceeds.

**Prevention:**
- Export `INPUT_AUDIO_SAMPLE_RATE` as a first-class library constant with a clear docstring stating it is the **required** input sample rate.
- In `append_client_audio`, optionally validate `len(pcm16_audio) % 2 == 0` (PCM16 must be even-length) and raise `ValueError` if odd — this is a fast sanity check.
- Document in `docs/realtime.md`: "Callers are responsible for resampling to `INPUT_AUDIO_SAMPLE_RATE` (24 000 Hz). The library does not resample."
- In the mock provider, validate even-length PCM to surface consumer bugs during testing.

**WARNING SIGN:** Voice assistant transcribes speech at wrong pitch. Server VAD never fires (`INPUT_SPEECH_STARTED` never seen) despite audio being sent. Gemini returns empty audio responses.

**Phase:** contracts / foundation

---

### PITFALL-07: Send-Buffer Flooding — Uplink Faster Than Provider Consume

**What goes wrong:** `websockets` has an internal send buffer. If `append_client_audio` is called in a tight loop (iOS continuously sends 20ms PCM chunks at 24 kHz = ~960 bytes/chunk, 50 calls/second), and the provider's receive window is smaller than the send rate, `ws.send()` will block waiting for the provider to drain — or the buffer grows unbounded.

**Why it happens:** The current `send_json` has no flow-control. Audio calls `json.dumps(event)` including the base64-encoded audio body and sends immediately. There is no backpressure mechanism.

**Consequences:** Memory growth in the WebSocket send buffer. Connection eventually stalls. In extreme cases, the provider closes with 1009 (message too large — if chunks accumulate into one large frame somehow) or just drops the connection.

**Prevention:**
- Document that `append_client_audio` sends one chunk per call and callers should pace calls to match the provider's expected input rate.
- Consider adding an `asyncio.Queue`-based audio send queue with bounded size (`maxsize=50`) as an optional wrapper; when the queue is full, the oldest chunk is dropped (UDP-like loss is better than buffer bloat for voice).
- For the initial port, replicate GlassAgents' existing behavior (no queue) since it works in production, but add a comment: "Future: add bounded audio send queue for backpressure."
- Unit test: send 200 consecutive audio chunks against a mock WS that has artificial latency; assert no exception and that the final chunk was sent.

**WARNING SIGN:** `send_json` call times start growing (observable via `trace_events=True` timing). Process RSS grows during long sessions. Provider closes with 1009.

**Phase:** hardening (not blocking for initial port)

---

### PITFALL-08: Base64 Encoding Overhead on Audio Frames

**What goes wrong:** Both providers require base64-encoded audio in JSON frames. At 24 kHz PCM16 mono, a 20ms frame is 960 bytes raw → ~1280 bytes base64 → ~1350 bytes in JSON with envelope. This overhead is unavoidable for provider compliance, but `base64.b64encode(pcm16_audio).decode("ascii")` is called on every audio frame (50/second). Python's `base64.b64encode` is fast (~500MB/s), but it allocates a new bytes object and a new str on every call.

**Why it happens:** Per-frame allocation is the correct current approach (matches GlassAgents). The concern is not correctness but allocation pressure in long sessions. This is already present in GlassAgents (`client.py:177–182`, `gemini_live.py:254–266`) and has not caused production issues. Flag it for future profiling rather than premature optimization.

**Consequences:** Increased GC pressure in long sessions (30+ minutes). No functional breakage observed in GlassAgents Phase 3.

**Prevention:**
- Accept the current design for the initial port.
- Add a `# perf: per-frame allocation` comment so future profiling is guided.
- Do NOT pre-allocate or reuse buffers without profiling data — premature optimization risk.

**WARNING SIGN:** GC pause spikes visible in profiler after 20+ minutes of continuous streaming.

**Phase:** hardening (low priority; document only in v1.8.0)

---

### PITFALL-09: End-of-Turn Detection Race in Manual-VAD Providers (Gemini Live)

**What goes wrong:** Gemini Live has no server VAD (`server_vad=False`, `manual_turn_commit_required=True`). The consumer must call `commit_client_turn()` (which sends `realtimeInput.audioStreamEnd`) to signal end-of-speech. If the consumer calls `commit_client_turn()` before the last audio chunk is delivered (e.g. on a silence timer that fires slightly early), Gemini may process a truncated utterance. If the consumer calls it too late, Gemini has already been waiting for more audio.

**Why it happens:** GlassAgents' `turn_state.py` (stays in app) handles the turn detection timer. The library's `commit_client_turn()` just sends `audioStreamEnd`. The library cannot know whether the audio stream was complete.

**Consequences:** Truncated speech recognition. Gemini responds to partial utterance. Consumer's turn manager and provider diverge.

**Prevention:**
- Library responsibility is clear and minimal: `commit_client_turn()` sends the signal, nothing more. Document this explicitly.
- Export `GEMINI_LIVE_REALTIME_CAPABILITIES.manual_turn_commit_required = True` as a signal to consuming apps that they must implement their own VAD timing.
- Unit test: assert that `commit_client_turn()` sends `{"realtimeInput": {"audioStreamEnd": True}}` with no additional state.

**WARNING SIGN:** Gemini responds to half-sentences. Consumer logs show `commit_client_turn` called before all audio chunks were sent (observable via `trace_events=True` ordering).

**Phase:** Gemini port

---

## Moderate Pitfalls

---

### PITFALL-10: Tool Result Submission Schema Divergence

**What goes wrong:** OpenAI uses `conversation.item.create` with `{"type": "function_call_output", "call_id": ..., "output": ...}`. Gemini uses `toolResponse.functionResponses` with `{"id": ..., "name": ..., "response": {...}}`. The normalized event `TOOL_CALL_COMPLETED` puts `call_id` at `payload["call_id"]`. The consuming app reads `payload["call_id"]` and calls `client.submit_tool_result(call_id=..., output=...)`. This works because both providers accept the same `submit_tool_result(call_id, output)` signature — the schema divergence is hidden inside each provider's `submit_tool_result`.

**The actual breakage risk:** Gemini's `submit_tool_result` requires the tool **name** (which it looks up from `_tool_call_names_by_id`). If a Gemini `TOOL_CALL_COMPLETED` event is processed but the consumer delays `submit_tool_result` until after a reconnect, `_tool_call_names_by_id` is reset on reconnect (in `close()`) and the tool name is lost. The submit call silently uses `"tool"` as the name fallback (`gemini_live.py:308`).

**Prevention:**
- In the library's Gemini `submit_tool_result`: if `call_id not in self._tool_call_names_by_id`, log a `WARNING` (currently just `INFO` at line 301). Consider raising `RealtimeProtocolError` after logging so the consumer knows the state is stale.
- The `TOOL_CALL_COMPLETED` normalized payload must include `name` (it already does: `payload["item"]["name"]`). Consumers should pass name back as an optional argument to `submit_tool_result` as a safety override.
- Unit test: simulate tool call → reconnect → submit_tool_result; assert that `WARNING` is logged and the response uses the fallback name.

**WARNING SIGN:** Gemini tool responses arrive with `"name": "tool"` in the API log. Provider returns `UNHANDLED` event instead of proceeding after tool result.

**Phase:** Gemini port

---

### PITFALL-11: Tool Result Submission Race — Provider Emits Next Response Before Result Arrives

**What goes wrong:** OpenAI Realtime can emit `response.created` (normalizes to `RESPONSE_CREATED`) immediately after `response.function_call_arguments.done`. If the consumer is slow to process the tool and call `submit_tool_result`, OpenAI may have already started generating the next response turn. The tool result then arrives after the next response has begun, which the OpenAI API handles by queueing it — but the normalized `RESPONSE_CREATED` event already fired, causing the consumer to think a new turn started before the tool chain is complete.

**Why it happens:** OpenAI Realtime's server-side processing is pipelined. There is no explicit "waiting for tool results" state in the normalized event schema.

**Consequences:** Consumer turn state machine advances one turn ahead of the actual tool resolution. Double audio output if the consumer starts playing audio from the premature `RESPONSE_CREATED`.

**Prevention:**
- Document in `docs/realtime.md`: "For tool-calling sessions, consumers should track `TOOL_CALL_COMPLETED` events and suppress `RESPONSE_CREATED` playback until all pending tool calls have had results submitted."
- The normalized schema does not need a new event type for this; it is a consumer-side concern.
- Unit test (mock): fire `TOOL_CALL_COMPLETED`, then `RESPONSE_CREATED` before `submit_tool_result` is called; assert that the consumer (in a reference integration test) handles both events without duplicating audio.

**WARNING SIGN:** Consumer plays two consecutive audio responses for a single user turn. Logs show `RESPONSE_CREATED` before `submit_tool_result` completes.

**Phase:** OpenAI port (document); hardening (add note to mock provider replay)

---

### PITFALL-12: Tool Definition Schema — `additionalProperties` and `strict` Mode

**What goes wrong:** OpenAI Realtime's tool schema uses `"strict": true` when converting from `ToolDefinition` (via `to_openai_tool()`). Strict mode requires `additionalProperties: false` and all properties to be in `required`. Gemini's schema stripper (`_to_gemini_schema`) explicitly drops `additionalProperties` (line 668). If `ToolDefinition.parameters` contains `"$schema"`, `"$defs"`, or `"$ref"` keys (valid JSON Schema but unsupported by both providers), both providers will silently ignore those properties or raise an API error.

**The specific breakage:** A tool with `parameters: {"$defs": {...}, "properties": {"x": {"$ref": "#/$defs/..."}}}` will have its `$ref` property preserved in Gemini's schema (not explicitly stripped) but the referenced definition (`$defs`) is stripped — resulting in a broken schema sent to Gemini. Gemini returns an error like `INVALID_ARGUMENT: parameter schema invalid`.

**Prevention:**
- `ToolDefinition` should document: "Parameters must be a flat JSON Schema (no `$ref`, `$defs`, `allOf`, `anyOf`, `oneOf`). Both OpenAI and Gemini do not support JSON Schema references."
- In `_to_gemini_schema`, add `$ref`, `$defs`, `$schema`, `allOf`, `anyOf`, `oneOf` to the explicit drop-list.
- In the OpenAI tool normalizer, add a validation pass that warns if `$ref` is present.
- Unit test: pass a `ToolDefinition` with a `$ref` parameter; assert the schema sent to each provider has no `$ref` key.

**WARNING SIGN:** Provider returns `INVALID_ARGUMENT` error immediately after tool registration. Tools with complex parameter schemas work in unit tests (because tests use flat schemas) but fail in production.

**Phase:** contracts (ToolDefinition validation on port)

---

### PITFALL-13: `INPUT_SPEECH_STARTED` Without Prior `commit_client_turn()` (Server VAD vs Manual)

**What goes wrong:** On OpenAI (server VAD enabled), `input_audio_buffer.speech_started` fires automatically when the server detects speech — no client action required. This normalizes to `INPUT_SPEECH_STARTED`. On Gemini (manual VAD), `INPUT_SPEECH_STARTED` is never emitted by the provider; it would have to be synthesized by the adapter or the consuming app.

**The breakage:** A consumer that relies on `INPUT_SPEECH_STARTED` to trigger UI feedback (e.g. "listening indicator") will see it on OpenAI but never on Gemini, creating a provider-dependent consumer. The normalized event vocabulary claims to abstract providers; silently missing events break the abstraction.

**Prevention:**
- `RealtimeProviderCapabilities` already has `server_vad: bool`. Document in `docs/realtime.md`: "Consumers MUST check `capabilities.server_vad` before relying on `INPUT_SPEECH_STARTED`. For `server_vad=False` providers, synthesize this event locally when audio uplink begins."
- Do NOT synthesize `INPUT_SPEECH_STARTED` in the library adapter for Gemini — that would be opinionated behavior in the wrong layer. The app (GlassAgents `bridge.py`) handles this.
- Unit test for Gemini: assert that no `INPUT_SPEECH_STARTED` event is yielded from `iter_normalized_events` for a complete session with audio input.

**WARNING SIGN:** Consumer "listening" UI indicator works with OpenAI but never activates with Gemini.

**Phase:** Gemini port (document in capabilities; add to unit test suite)

---

### PITFALL-14: `sys.modules` Mock-Leak with Realtime SDKs (Repeat of Known Bug)

**What goes wrong:** This is a known issue in TESTING.md and CONCERNS.md. The `[realtime]` extra depends on `websockets`. Unlike `openai` / `anthropic`, `websockets` is not lazily imported inside the provider class — it is imported at module level in `websocket_client.py` (`import websockets`). This means injecting a mock at `sys.modules["websockets"]` before the import works, but if the module is already imported in a prior test (e.g. from a different test file that also uses `websockets` for something else), the mock is the real module and the real module is the mock.

**Why it happens:** The existing test pattern injects mocks before the first import. But `websockets` may be imported as a side-effect of other test file imports if tests run in the same pytest session. The current mitigation (separate unit/integration sessions) helps but does not fully prevent cross-file contamination within the unit session.

**Specific new risk for realtime:** `websockets.connect` is an async context manager. A `MagicMock()` does not automatically support `async with`. `AsyncMock` is needed. Using `MagicMock()` for `websockets` will cause `TypeError: object MagicMock can't be used in 'await' expression` — a confusing error that looks like an event loop issue.

**Prevention:**
- Use `unittest.mock.AsyncMock` for `websockets.connect` (not `MagicMock`).
- Mock pattern:
  ```python
  import sys
  from unittest.mock import AsyncMock, MagicMock, patch

  mock_ws_module = MagicMock()
  mock_ws_instance = AsyncMock()
  mock_ws_module.connect = AsyncMock(return_value=mock_ws_instance)
  mock_ws_module.exceptions.ConnectionClosed = ConnectionClosed  # use real exception class
  sys.modules["websockets"] = mock_ws_module
  sys.modules["websockets.exceptions"] = mock_ws_module.exceptions
  ```
- Keep realtime unit tests in a **separate file** (`tests/unit/test_realtime_openai.py`, `tests/unit/test_realtime_gemini.py`) loaded after all other unit tests — or in a dedicated `tests/unit/realtime/` sub-package with its own `conftest.py` that performs the mock injection in a session-scoped autouse fixture.
- The existing "separate pytest sessions for unit/integration" policy from PROJECT.md also applies here.

**WARNING SIGN:** `TypeError: object MagicMock can't be used in 'await' expression` in tests. Or: real WebSocket connections initiated during unit tests (network traffic visible).

**Phase:** foundation (establish test patterns before writing provider tests)

---

### PITFALL-15: Recording Real Provider Frames for Replay Tests — API Key Leakage

**What goes wrong:** The most valuable unit test technique for event normalization is to replay real provider wire frames. If frames are captured from a live session and committed to the repository, any API key that appears in those frames (e.g. Gemini's `key=` query parameter in the URL, which appears in some error event payloads) is permanently in git history.

**Why it happens:** Gemini Live error events can include the request URL in the error message. OpenAI Realtime error events sometimes include the model endpoint. Committing raw captured frames without scrubbing leaks these.

**Prevention:**
- All replay fixture files must be scrubbed before commit: run `grep -ri "sk-" tests/fixtures/` and `grep -ri "api_key\|api-key\|Bearer" tests/fixtures/`.
- Add a pre-commit hook or CI check: `grep -rE "(sk-|AIzaSy|key=[A-Za-z0-9_-]{20,})" tests/fixtures/` → fail if any match found.
- Store replay fixtures as sanitized minimal JSON, not raw captured streams. Create a `tests/fixtures/realtime/` directory with `openai_frames.json` and `gemini_frames.json` that are hand-crafted representative events.

**WARNING SIGN:** `grep -r "AIzaSy" tests/` returns hits. Pre-commit hook trips on fixture files.

**Phase:** foundation (establish fixture hygiene before any fixtures are created)

---

### PITFALL-16: pytest-asyncio Fixture Scope Confusion with async Context Managers

**What goes wrong:** `asyncio_mode = "auto"` is already configured (TESTING.md). The `BaseRealtimeWebsocketClient` is an async context manager (`__aenter__`/`__aexit__`). A `session`-scoped fixture that creates a provider instance will fail because `asyncio_mode = "auto"` with `scope="session"` requires an explicit `loop_scope="session"` on the fixture (pytest-asyncio 0.23+ behavior). If the fixture uses default scope, the event loop is torn down between tests while the session-scoped fixture still holds the connection.

**Why it happens:** pytest-asyncio's event loop lifecycle changed in 0.21+. Session-scoped async fixtures require `@pytest.fixture(scope="session", loop_scope="session")` to avoid "Event loop is closed" errors mid-suite.

**Prevention:**
- Realtime provider fixtures should be **function-scoped** by default (connect → test → close per test). This is the right default for connection-holding fixtures.
- Only use session-scoped fixtures for non-connection resources (config, API keys, recorded frame sets).
- In `tests/unit/realtime/conftest.py`, document why function scope is used: "Realtime clients hold WebSocket connections; session scope risks event loop teardown conflicts."
- Unit test: verify that a second test in the same file gets a fresh provider instance (assert `id(provider_a) != id(provider_b)`).

**WARNING SIGN:** `RuntimeError: Event loop is closed` after the first test in a class. Tests pass in isolation but fail when run together.

**Phase:** foundation (test infrastructure)

---

## Minor Pitfalls

---

### PITFALL-17: Gemini API Key in WebSocket URL Query — Proxy Log Leakage

**What goes wrong:** Gemini Live uses API key in the query string: `wss://...?key=AIzaSy...`. Any HTTP/HTTPS proxy or WAF that logs query parameters will capture the key. This is already mitigated in `gemini_live.py` via `redacted_websocket_url` / `_redact_sensitive_text`. The risk is in the **library port** not carrying that mitigation over.

**Prevention:**
- Port the `_redact_sensitive_url` and `_redact_sensitive_text` static methods verbatim into the library's Gemini provider.
- Override `_connection_error_endpoint()` to return `redacted_websocket_url` (not `websocket_url`).
- Override `_log_connect_failure()` to call `_redact_sensitive_text(str(exc))` before logging.
- Unit test: assert `_connection_error_endpoint()` does not contain the raw API key.

**WARNING SIGN:** Error logs showing the literal `key=AIzaSy...` value. Sentry/logging aggregator captures full WebSocket URL.

**Phase:** Gemini port

---

### PITFALL-18: TLS Certificate Validation Disabled in Tests Leaking to Production

**What goes wrong:** When writing integration tests against local WS test servers (using `pytest-server-fixtures` or `websockets.serve`), it is tempting to pass `ssl=None` or `ssl_context` with verification disabled to `websockets.connect`. If the provider client passes this via `_connection_kwargs()`, a test-only SSL override could be accidentally enabled in production builds.

**Prevention:**
- Never add `ssl=...` overrides to `_connection_kwargs()` in production provider code.
- Integration tests that need local TLS should use `pytest-ssl-certificates` or route through a localhost WS server without TLS (plain `ws://` on localhost is acceptable for tests).
- Add a `# test-only` comment wherever SSL override kwargs are used in test fixtures.
- Linting rule: `grep -r "ssl_context\|verify=False\|ssl=None" src/` should return empty.

**WARNING SIGN:** `ssl` parameter appears in production `_connection_kwargs()`. Integration tests pass against local server but production connections fail TLS validation errors.

**Phase:** foundation / hardening

---

### PITFALL-19: OpenAI Model Name Churn — `gpt-realtime` vs `gpt-4o-realtime-preview`

**What goes wrong:** The handoff spec (§4.1) uses default `model="gpt-realtime"` in `OpenAIRealtimeConfig`. The current GlassAgents `client.py:49` takes `model` as a required parameter. The actual OpenAI Realtime API uses model names like `gpt-4o-realtime-preview-2024-12-17`. A wrong default model causes the WebSocket handshake to fail with 404 or an API error immediately after connect.

**Why it happens:** OpenAI rotates preview model aliases. `gpt-realtime` appears in the handoff spec as a convenience alias but may not be a valid model ID on the OpenAI API.

**Prevention:**
- At library port time, verify the current valid model name against OpenAI's model list endpoint or docs.
- Set the default to the most recently validated model ID (e.g. `gpt-4o-realtime-preview-2024-12-17`) and document it with a "check OpenAI docs for latest" note.
- Add to `tests/model_registry.py` a `realtime` entry with a fallback chain (same pattern as chat models).
- Unit test: assert that the `websocket_url` property produces a URL with a non-empty `model=` query parameter.

**WARNING SIGN:** WebSocket connect returns HTTP 404 or 400. Log: `Failed to connect ... model=gpt-realtime`.

**Phase:** OpenAI port

---

### PITFALL-20: Gemini Live Model Name Rotation

**What goes wrong:** The current default model `gemini-2.5-flash-native-audio-preview-12-2025` is a dated preview alias. Google rotates these without notice. The library default in `GeminiLiveConfig.model` will become invalid, causing every connection attempt to fail with an API error.

**Prevention:**
- Same mitigation as PITFALL-19: add to `tests/model_registry.py` and document with rotation warning.
- `_build_setup_event` already prepends `models/` if missing — that part is correct.
- Add integration test that calls `list_models()` (or a minimal connect+close) against the live Gemini API using the registry model, so CI catches model name retirement.

**WARNING SIGN:** Integration test `test_gemini_live_live.py` fails with `INVALID_ARGUMENT: model not found`.

**Phase:** Gemini port

---

### PITFALL-21: `[realtime]` Extra Not Installed — Unhelpful ImportError

**What goes wrong:** `websockets` is a hard dependency of the realtime module. If a consumer installs `eq-chatbot-core` without `[realtime]`, importing `eq_chatbot_core.realtime` raises `ImportError: No module named 'websockets'` at the call site with no guidance.

**Prevention (matches existing lazy-import pattern in CONCERNS.md):**
- In `eq_chatbot_core/realtime/__init__.py`, wrap the `websockets` import in a `try/except ImportError`:
  ```python
  try:
      import websockets  # noqa: F401
  except ImportError as exc:
      raise ImportError(
          "eq-chatbot-core[realtime] is required for realtime voice support. "
          "Install with: pip install eq-chatbot-core[realtime]"
      ) from exc
  ```
- This matches the existing pattern used for `[azure]` and `[vertex]` extras.
- Unit test: remove `websockets` from `sys.modules` and assert the friendly error is raised.

**WARNING SIGN:** Consumer error reports `No module named 'websockets'` with no reference to the `[realtime]` extra.

**Phase:** foundation / contracts (must be in place before any realtime code ships)

---

### PITFALL-22: Sync vs Async Interface Confusion for Multi-Consumer Library

**What goes wrong:** All existing providers in `eq-chatbot-core` expose a synchronous interface (`chat_completion`, `stream_completion`). The new realtime providers are inherently async (WebSocket `await`). Consumers currently wrap sync providers in `asyncio.to_thread`. For realtime, they must use `asyncio` natively. If a consumer (e.g. `odoo-translator`) happens to discover the realtime module and tries to call `client.connect()` synchronously, they get a coroutine object, not a connection — a completely silent failure.

**Prevention:**
- Do NOT provide sync wrappers for realtime. The async interface is the correct one; forcing sync would require blocking event loops.
- Export realtime under `eq_chatbot_core.realtime` (not `eq_chatbot_core.providers`). This namespace separation signals that realtime is a different interface.
- Document clearly in `docs/realtime.md`: "Realtime providers are async-only. They are not compatible with the synchronous `get_provider()` factory."
- Do NOT register realtime providers in the existing `PROVIDER_NAMES` list or the `get_provider()` factory — this prevents them from appearing in the HTTP sidecar's `/v1/chat/completions` endpoint.

**WARNING SIGN:** Consumer raises `TypeError: object coroutine can't be used in 'await' expression` (they forgot `await`). Or: consumer registers a realtime provider via `get_provider("openai_realtime")` and the HTTP sidecar crashes.

**Phase:** contracts (design decision must be locked before implementation)

---

### PITFALL-23: Hardcoded Provider Name List Anti-Pattern (Known, Must Not Repeat)

**What goes wrong:** CONCERNS.md documents that provider names are hardcoded in three places: `providers/__init__.py`, `server/app.py`, `cli.py`. Adding realtime providers naively would add a fourth location if the realtime registry is a separate list.

**Prevention:**
- Realtime providers live in their own registry (`RealtimeProviderRegistry`), separate from the chat provider factory. They must NOT be added to the existing `PROVIDER_NAMES` constant.
- The `PROVIDER_NAMES` refactor (exporting to a constant) is a pre-existing debt; realtime must not make it worse.
- When adding `[realtime]` to the `eq-chatbot info` CLI output, pull from the realtime registry's `.registered_names()` method — do not hardcode a list.

**WARNING SIGN:** New realtime provider names appear in 3+ places in the codebase as string literals.

**Phase:** contracts / foundation

---

### PITFALL-24: Duplicate Provider-Name Lists Will Re-Emerge Without a Constant

**What goes wrong:** This is an extension of PITFALL-23. The `server/app.py` currently has `PROVIDER_NAMES` hardcoded for server validation. When realtime is added, the server's `/v1/realtime/connect` endpoint (if one is added in a future milestone) will need a list of valid realtime provider names. Without a single source of truth, this list will diverge.

**Prevention:**
- Define `REALTIME_PROVIDER_NAMES: frozenset[str]` as a module-level constant in `eq_chatbot_core/realtime/__init__.py`.
- Any server endpoint or CLI that validates provider names imports from there.

**Phase:** contracts

---

## Cross-Language Consumer Concerns

---

### PITFALL-25: Realtime Events Cannot Traverse the HTTP Sidecar (fr-designer / Avalonia)

**What goes wrong:** `fr-designer` consumes `eq-chatbot-core` via the HTTP sidecar (`[server]` extra). The sidecar exposes `/v1/chat/completions` (JSON) and `/v1/stream` (SSE). Realtime voice requires a bidirectional WebSocket — it cannot be proxied over the sidecar's current HTTP/SSE model without major sidecar extensions.

**The risk:** If the sidecar's `serve` command is documented as "supports all providers," a `fr-designer` developer might reasonably expect to access realtime via the sidecar. That is architecturally impossible without adding a WebSocket endpoint to the sidecar.

**Prevention:**
- Document in `docs/realtime.md`: "Realtime providers require a direct WebSocket connection from the consuming application. They are NOT accessible via the HTTP sidecar (`eq-chatbot serve`)."
- Add a note to the sidecar's OpenAPI spec or README: "Realtime voice is not available in sidecar mode. Use `eq_chatbot_core.realtime` directly in an async Python process."
- Do NOT add realtime provider names to the sidecar's provider validation list.

**Phase:** docs (final phase)

---

### PITFALL-26: sysReporter (Rust) CLI JSON I/O Cannot Support Realtime

**What goes wrong:** `sysReporter` uses `eq-chatbot chat` with JSON I/O over stdin/stdout. Realtime voice is inherently interactive and streaming — it cannot be represented as a single request/response exchange or even as line-delimited JSON without a persistent bidirectional channel.

**Prevention:**
- Document in `docs/realtime.md`: "Realtime providers are not accessible via the `eq-chatbot chat` CLI command. The CLI is designed for stateless chat completions."
- No code change needed; this is purely documentation.

**Phase:** docs

---

## Migration Risk for GlassAgents

---

### PITFALL-27: GlassAgents on `develop` Branch Mid-Flight — Library Bump Breaks CI

**What goes wrong:** GlassAgents currently has its own `backend/realtime/` in-tree. The migration plan (handoff §8) is to delete ~2300 LOC from GlassAgents after the library tag is cut. If `eq-chatbot-core==1.8.0` is published but the GlassAgents `develop` branch has not yet been updated, GlassAgents CI continues passing against its in-tree code. After the migration PR is merged into GlassAgents, any CI that pins `eq-chatbot-core==1.8.0` must work with the new library import paths.

**The specific breakage risk:** If `NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA` string value in the library differs from what GlassAgents hardcoded (e.g. `"response.audio.delta"` vs `"response.output_audio.delta"`), GlassAgents' `bridge.py` will receive events it doesn't recognize and silently drop all audio output.

**Prevention:**
- The library's event type string values must be byte-for-byte identical to the handoff spec §3.2 table. Do not change any string value during the port.
- Before the library tag is cut, run a cross-reference check: `grep -r "response\.audio\." /Users/picard/gitbase/GlassAgents/backend/` and verify every string matches the library's `NormalizedRealtimeEventTypes` constants.
- GlassAgents migration PR should include a test that imports `NormalizedRealtimeEventTypes` from the library and asserts each constant's string value against the previously hardcoded string.

**WARNING SIGN:** GlassAgents `bridge.py` receives `UNHANDLED` events where audio deltas are expected. Audio output is silent after migration.

**Phase:** hardening (pre-release validation gate)

---

### PITFALL-28: `server_vad: bool` Capability Flag Must Match Exact API Behavior

**What goes wrong:** The handoff spec §3.3 states `server_vad=True` for OpenAI. The `OpenAIRealtimeClient` has `include_turn_detection=False` as the default in GlassAgents (`client.py:48`), but the handoff spec and `OPENAI_REALTIME_CAPABILITIES` say `server_vad=True`. This is a documentation/code inconsistency: the capability flag says "server VAD is available" but the client config has turn detection off by default.

**The risk:** GlassAgents' `bridge.py` checks `capabilities.server_vad` to decide whether to fire `INPUT_SPEECH_STARTED` synthetically. If the library ships `server_vad=True` but the client default has turn detection off, the bridge will expect server-side VAD events that never arrive.

**Prevention:**
- Reconcile before port: `server_vad=True` should mean "the provider supports server VAD and it is enabled in the current config." If `include_turn_detection=False` (default), then effectively `server_vad=False` for this instance.
- Change `RealtimeProviderCapabilities` to be an instance attribute (set per-config) rather than a module-level constant.
- Or: change `OpenAIRealtimeConfig.include_turn_detection` default to `True` (matching the handoff spec intent) and document it.
- Validate against GlassAgents test: `test_openai_live.py` integration test should assert that `INPUT_SPEECH_STARTED` is received when server VAD is enabled.

**WARNING SIGN:** Integration test with server VAD enabled never receives `INPUT_SPEECH_STARTED`. GlassAgents bridge never fires the listening indicator.

**Phase:** OpenAI port (reconcile before writing the port)

---

### PITFALL-29: Event Type String Value Drift During Port

**What goes wrong:** The handoff spec §3.2 documents 12 event type string constants. The library implementation might introduce a typo or slight variation (e.g. `"response.audio_delta"` instead of `"response.audio.delta"`). GlassAgents' `bridge.py` has switch-case logic on these strings. A single character difference causes silent UNHANDLED events.

**Prevention:**
- Import the constants into a test that asserts their exact string values:
  ```python
  def test_event_type_string_values():
      assert NormalizedRealtimeEventTypes.SESSION_READY == "session.ready"
      assert NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA == "response.audio.delta"
      # ... all 12
  ```
- This test is zero-cost and catches any drift immediately.
- The test must be in `tests/unit/realtime/test_contracts.py` and run in CI.

**WARNING SIGN:** GlassAgents `bridge.py` logs show all events as `UNHANDLED` after migration.

**Phase:** contracts (first thing written)

---

## Phase-Specific Warning Summary

| Phase | Topic | Most Likely Pitfall | Mitigation |
|-------|-------|--------------------|-----------  |
| contracts | Event type string values | PITFALL-29: string drift breaks GlassAgents bridge | Write string-assertion tests first |
| contracts | ToolDefinition schema | PITFALL-12: $ref not stripped for Gemini | Add to Gemini schema stripper |
| contracts | Async interface | PITFALL-22: sync/async confusion | Namespace separation, no sync wrappers |
| contracts | Missing [realtime] extra | PITFALL-21: unhelpful ImportError | Friendly error with install hint |
| contracts | Provider name lists | PITFALL-23/24: list duplication anti-pattern | Separate realtime registry constant |
| foundation | WebSocket base class | PITFALL-01: close code not surfaced | Expose code in RealtimeClosedError |
| foundation | Reconnect | PITFALL-02: storm on 429/outage | connect_with_backoff with jitter |
| foundation | Connection leak | PITFALL-04: WS not closed on exception | async context manager + try/finally |
| foundation | Task leak | PITFALL-05: asyncio tasks not cancelled | Document caller responsibility |
| foundation | Test mock pattern | PITFALL-14: AsyncMock required for websockets | AsyncMock, fixture in realtime conftest |
| foundation | Fixture hygiene | PITFALL-15: API keys in replay fixtures | Pre-commit grep check on fixtures/ |
| foundation | pytest-asyncio scope | PITFALL-16: session-scope event loop teardown | Function-scoped provider fixtures |
| openai | Model name | PITFALL-19: model name churn | Registry pattern + validated default |
| openai | Double-cancel | PITFALL-03: cancel lost during reconnect | Pending cancel queue |
| openai | Tool race | PITFALL-11: RESPONSE_CREATED before tool result | Document consumer pattern |
| openai | server_vad flag | PITFALL-28: flag vs config mismatch | Reconcile before port |
| gemini | API key in URL | PITFALL-17: key in proxy logs | Port redaction helpers |
| gemini | Tool name after reconnect | PITFALL-10: stale _tool_call_names_by_id | Raise WARNING on missing name |
| gemini | Manual VAD | PITFALL-09: commit_client_turn timing | Document consumer responsibility |
| gemini | Model name rotation | PITFALL-20: preview model retired | Registry + integration test |
| hardening | Backpressure | PITFALL-07: send buffer flooding | Document pacing; bounded queue later |
| hardening | Pre-release validation | PITFALL-27: GlassAgents CI breaks on migration | String cross-reference check |
| docs | Sidecar consumers | PITFALL-25: fr-designer can't use realtime | Explicit docs + sidecar exclusion |
| docs | Rust CLI | PITFALL-26: sysReporter can't use realtime | Explicit docs |

---

## Sources

- GlassAgents `backend/realtime/websocket_client.py` (174 LOC) — base class error path analysis
- GlassAgents `backend/realtime/client.py` (391 LOC) — OpenAI client, cancel_response, tool result schema
- GlassAgents `backend/realtime/providers/gemini_live.py` (919 LOC) — Gemini tool result submission, redaction, schema stripping
- GlassAgents `docs/eq-chatbot-core-realtime-handoff.md` — authoritative migration spec, capabilities table, audio format
- `eq-chatbot-core/.planning/codebase/CONCERNS.md` — known anti-patterns not to repeat (provider name lists, sync I/O in async handlers, lazy import pattern)
- `eq-chatbot-core/.planning/codebase/TESTING.md` — sys.modules mock pattern, AsyncMock requirements, pytest-asyncio scope
- `eq-chatbot-core/src/eq_chatbot_core/mcp/client.py` — DNS pinning, URL validation, SSRF precedent

---

*Pitfalls analysis: 2026-05-24*
