# Provider consolidation on `OpenAICompatibleProvider` — design

Date: 07.10.2026 · Target release: 3.4.0 · Status: approved in conversation, awaiting spec review

## Context

The library speaks the OpenAI Chat Completions wire protocol to most of its providers, yet only
four of them (IONOS, Melious, LiteLLM, Privatemode) inherit the shared `OpenAICompatibleProvider`.
OpenAI, Mammouth, OpenRouter and the local-server provider each carry their own copy of request
building, SSE parsing, tool-call assembly and error mapping; LangDock's `openai` backend carries a
fifth. Every fix has to be applied five times, and in practice is not.

Two of those copies decide request parameters from hand-maintained model-name lists:

- whether `temperature` is sent (`temperature_constraints.py`, ~45 entries; GPT-5 flips between
  generations — 5.1–5.4 accept it, 5.5/5.6 reject it), and
- whether the output limit is sent as `max_tokens` or `max_completion_tokens`
  (`NEW_API_MODELS`, duplicated in `openai_provider.py` and `langdock_provider.py`).

When a list is wrong the request fails with no fallback. Models change every few weeks, so the
lists are permanently behind.

This is **stage 1 of 3**. Stage 2 removes model IDs and name lists from library source; stage 3
reviews the test suite for real (non-mocked) coverage. Each stage gets its own spec.

## Goals

1. One implementation of the OpenAI wire protocol, in `OpenAICompatibleProvider`.
2. Request parameters that adapt to what the model accepts, learned at runtime, with no list to
   maintain.
3. Error mapping by HTTP status instead of substring search.
4. Zero change to the public API. A 3.3.x consumer (Odoo modules, CLI, server mode) runs unmodified
   on 3.4.0.

## Non-goals

- Removing model IDs, `DEFAULT_MODEL` values or the existing name lists (stage 2). In this stage
  the lists remain as the *initial guess* only.
- Restructuring the test suite beyond the tests this change makes obsolete (stage 3).
- `AnthropicProvider`, and LangDock's `anthropic`, `google`, `codestral` and `agent` backends,
  `LangDockAgentManager`, `LangDockKnowledgeManager`.
- Temperature *range* errors (e.g. 1.5 for a model accepting 0–1). Clamping stays as it is.

## Evidence (live probe, 07.10.2026)

| Endpoint | `temperature=0.7` | `max_tokens=200` |
|---|---|---|
| OpenAI, `gpt-5.6-luna` | HTTP 400, `param: "temperature"`, `code: "unsupported_value"` | HTTP 400, `param: "max_tokens"`, `code: "unsupported_parameter"` |
| Mammouth, `gpt-5.6-luna` | accepted | accepted |
| LangDock OpenAI, `gpt-6-luna` | accepted | accepted |
| LangDock OpenAI, `gpt-5.6-luna` | HTTP 400, model no longer offered | — |
| OpenRouter | HTTP 401 "User not found" — configured key rejected, not probed | — |

The LangDock row shows a built-in default model (`gpt-5.6-luna`) already broken today; stage 2
addresses that.

## Design

### 1. Adaptive request parameters (in `OpenAICompatibleProvider`)

**Initial guess.** Parameters are built as today: temperature through `clamp_temperature()`, the
output limit as `max_tokens` unless the name-based check says `max_completion_tokens`.

**Learning.** If `chat.completions.create()` raises an HTTP 400 that identifies one of exactly two
parameters as unsupported, the request is retried **once** with that parameter adjusted:

| Rejected parameter | Retry with |
|---|---|
| `temperature` | parameter omitted |
| `max_tokens` | same value as `max_completion_tokens` |

Recognition, in order:

1. Structured: `error.param` equals the parameter name (OpenAI sets `code` to
   `unsupported_parameter` or `unsupported_value`).
2. Fallback for gateways without `param`: the error message contains the parameter name in quotes
   (`'temperature'` or `"temperature"`) **and** `unsupported` or `not supported`.

Anything else propagates unchanged. At most one retry per parameter, so at most two per call: an
unknown model that rejects both still succeeds on its first call. A parameter that is rejected
again after its adjustment propagates as an error.

**Cache.** Learned facts are stored process-wide, keyed by `(effective base URL, model)`, guarded
by a lock. Per-instance storage would make consumers that build a provider per request (the Odoo
module) relearn on every request. The cache holds only two booleans per key and is never
persisted. A cached fact overrides the initial guess.

**Streaming.** The rejection arrives from `create()` before the first chunk is yielded, so the
retry — at most two, as above — happens before any output reaches the caller; partial output is never duplicated.

**Seeding (OpenRouter).** When OpenRouter's `/models` response carries `supported_parameters`,
`list_models()` writes the corresponding facts into the cache, so the first request is already
right.

**Logging.** Each retry is logged at INFO with provider, model and parameter.

### 2. Error mapping

`_handle_error` maps by SDK exception type / HTTP status first:

| Condition | Exception |
|---|---|
| 429 | `RateLimitError` (with `retry_after` when the response carries it) |
| 401, 403 | `AuthenticationError` |
| 503, 529 | `OverloadedError` (new for these providers) |
| 400 with `code: "context_length_exceeded"` | `ContextLengthError` |
| other | `ProviderError` with status code |

Substring matching remains only for errors without a status (connection-level). The bare word
`token` is no longer a criterion — today it turns "`max_tokens` is not supported" into a
`ContextLengthError`. Messages stay passed through `scrub_secrets`.

### 3. Base-class extension points

- `_default_headers() -> dict[str, str]` — extra HTTP headers for the SDK client (OpenRouter
  `HTTP-Referer` / `X-Title`).
- `_client_kwargs() -> dict[str, Any]` — extra `OpenAI(...)` arguments (OpenAI `organization`).
- Existing hooks stay: `_build_params`, `list_models`, `_handle_error`, `client`.

### 4. Provider migration

Each provider becomes a subclass (LangDock: a delegate) and keeps, unchanged: class name,
constructor signature and defaults, extra methods, class constants, and the keys returned by
`list_models()`. Removed: its own request building, SSE parsing, tool-call assembly, error
mapping and HTTP client construction.

| Provider | Stays provider-specific |
|---|---|
| Mammouth | `list_models()` from `/public/models` (incl. `max_input_tokens`) |
| Local (LM Studio, Ollama) | port selection, `is_server_available()`, friendly connect/timeout messages, 120 s timeout, `ALLOW_PRIVATE_RANGES = True`, `"not-used"` API key, model-list format |
| OpenAI | `generate_image()`, chat-model filter and metadata in `list_models()`; `NEW_API_MODELS` becomes the initial guess for the output-limit parameter |
| OpenRouter | `site_url`/`site_name` headers, `generate_image()`, model list with modalities and `supported_parameters` (seeds the cache), `provider/model` IDs |
| LangDock | only `backend="openai"`: `LangDockProvider` holds an internal `OpenAICompatibleProvider` for `/openai/{region}/v1` and forwards `reasoning_effort`; all other backends untouched |

**Behaviour change.** Mammouth, OpenRouter and Local move from hand-written `httpx2` calls to the
`openai` SDK. The SDK retries 429/5xx up to `max_retries` (default 2), and error message wording
changes; exception classes do not. OpenRouter's mid-stream error handling (fixed in commit `099468b`) must be
re-verified live; the SDK raises on `error` events in the stream.

**Order.** One provider per step, each a separate commit with a live test before the next:
Mammouth → Local → OpenAI → OpenRouter → LangDock. OpenRouter is late because its configured key is
currently rejected.

## Testing

**Live tests** (`integration` marker; models from `tests/model_registry.py`, never from library
source): per migrated provider, chat, streaming, one tool call and `list_models()`.
Learning, live: OpenAI `gpt-5.6-luna` with `temperature=0.7` and `max_tokens` succeeds; a second
identical call triggers no retry.

**Local OpenAI-wire test server** for CI, which has no keys. A stdlib `http.server` started on
`127.0.0.1` inside the test session, speaking the Chat Completions protocol (JSON and SSE). It
replays recorded provider behaviour — the exact 400 bodies above, a `param`-less variant, 429 with
`Retry-After`, 503, a stream that errors mid-way, tool-call deltas. The real SDK, the pinned
transport and the real error mapping run; only the remote provider is simulated. No mocking of
library code.

**Compatibility snapshot.** Before the first migration step, the public surface is recorded by
introspection: exported names, constructor signatures, public methods, class constants, and the
`list_models()` key set per provider. A test compares every later step against it.

**Obsolete mock tests.** Unit tests that only exercise the replaced hand-written HTTP code are
listed individually and deleted only after explicit approval. Tests of provider-specific logic
stay or move to the test server.

**Coverage.** The 83 % gate stays; coverage is measured after every step.

## Risks

| Risk | Mitigation |
|---|---|
| A gateway reports unsupported parameters in a form neither rule recognises | Error propagates as today (no regression); add the form to the test server once seen |
| SDK retry semantics differ from the old hand-written clients (extra latency on 5xx) | `max_retries` stays configurable; documented in the release notes |
| A consumer relies on exact error message text | Exception classes unchanged; wording change documented |
| OpenRouter mid-stream errors masked again | Test-server case plus live check once the key works |

## Release

Minor release 3.4.0 through `/afterwork`. Final proof of compatibility: a run of the Odoo chatbot
module against 3.4.0 (outside this repository, proposed as the last step).
