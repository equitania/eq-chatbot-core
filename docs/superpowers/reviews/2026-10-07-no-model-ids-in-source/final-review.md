# Final whole-branch review — stage 2 "no model IDs in source"

Range: `ad70862..20634fb` (branch `feature/no-model-ids`), reviewed read-only on 07.10.2026.
Unit suite at review time: `uv run pytest tests/unit -q -p no:cacheprovider -x` → 1981 passed, 188 xfailed, 0 failed.

## Verdict: Ready with fixes

The core goal holds: no model ID under `src/` (guard test green), every chat / stream / image /
TTS / STT / embedder path resolves the model as call argument → constructor → typed
`ModelNotSpecifiedError`, the server answers 400 before a stream starts, the CLI exits 1 with a
message. The retry-and-learn loop exists once (`param_learning.call_with_learning`), is bounded
(at most one retry per parameter, so at most four requests per call), keyed by
`base_url.rstrip("/") + model` consistently between request path and `list_models()`, and its
shared memory is lock-protected. Range errors (OpenAI `invalid_value`/`decimal_above_max_value`,
Anthropic "temperature: range: 0..1") are not learned. Two behaviour problems would hit a real
consumer and should be fixed before 4.0.0; the rest is minor.

Counts: Critical 0 · Important 2 · Minor 10

---

## Important

### I-1 A rejected *value* of `reasoning_effort` disables the parameter for that model for the whole process

`src/eq_chatbot_core/providers/param_learning.py:41` (`_REJECTION_CODES` contains
`unsupported_value`) and `:72` (structured branch returns the param for either code).

`unsupported_value` is the right signal for `temperature` (the model only takes its default),
but for `reasoning_effort` OpenAI uses the same code when one *value* is not offered, e.g.
`"Unsupported value: 'reasoning_effort' does not support 'none' with this model. Supported values
are: 'minimal', 'low', 'medium', and 'high'."` (`param: "reasoning_effort"`,
`code: "unsupported_value"`).

Failure scenario: the Odoo module sets `reasoning_effort="none"` (required for tools on one model
family, see CHANGELOG "Known") and a user switches the bot to a model that does not offer `none`.
The library drops the parameter, the retry succeeds, and `mark_unsupported` records
`reasoning_effort` as unsupported for that endpoint+model. From then on every request for that
model in the worker process silently loses its effort setting — including valid values like
`"high"` — until the process restarts. The only trace is an INFO log. `test_param_learning.py:131-135`
locks this in (`later = {"reasoning_effort": "low"}` is stripped).

Fix: learn `reasoning_effort` only from `unsupported_parameter` (and from the text fallback);
for `unsupported_value` either propagate the 400 (the caller chose an invalid value) or retry
once *without remembering*. Add a wire-server reply for the value form and a test that a later
call with a different value still sends it.

### I-2 CLI `image` / `listing-assets` take the provider's *chat* model from the config file, and the error message tells users to put the image model there

`src/eq_chatbot_core/cli.py:787` (`image`: `model = resolve_model(provider, model)` →
`config_model(provider)`), `cli.py:1013` (`listing-assets`), `cli.py:82-89`
(`model_required_message`), mirrored in `docs/cli.md:111/373` and `usage/AGENT.md:42,87`.

The config file has one `model` key per provider, which the same docs describe as the chat model.
Before 4.0 an empty key fell back to the built-in image default; now the user is pushed to fill it.

Failure scenario: `eq-chatbot image -p openai --prompt …` without `-m` prints "set
`model = "..."` under [providers.openai]". The user sets the image model there; now `eq-chatbot
chat -p openai` sends the image model to chat completions and fails. Conversely, a user who has a
chat model configured runs `image` without `-m` and sends the chat model to `/images/generations`
(400 from the API instead of the clear local message). The library itself already separates the
two (`image_model=`), only the CLI conflates them.

Fix: read an `image_model` key from `[providers.<name>]` for `image` and `listing-assets` (or drop
the config fallback for images and require `-m`/recipe), and give these commands their own
message ("Pass --model/-m or set image_model = ..."). Add CLI tests for both directions.

---

## Minor

M-1 **Realtime clients raise `ValueError`, not `ModelNotSpecifiedError`.**
`realtime/providers/openai.py:95-98`, `realtime/providers/gemini_live.py:98-101`. A consumer that
catches `ProviderError`/`ModelNotSpecifiedError` for "no model" will not catch this. Acceptable
(fail-fast before network, spec lists only chat/stream/image/TTS/STT/embed), but the CHANGELOG
"Upgrading" line should name the exception type.

M-2 **`OpenAIProvider` with a custom `base_url` cannot recover from a gateway that rejects
`max_completion_tokens`.** `openai_provider.py:44-46`, `param_learning.adjust` only maps
`max_tokens → max_completion_tokens`, and `rejected_parameter` ignores a `param` outside
`LEARNABLE`. Before stage 2 unknown model names got `max_tokens`. Someone using
`get_provider("openai", base_url=<vLLM/Ollama/Azure-style gateway>)` now gets a hard 400 (or a
silently ignored limit). Document "use `local`/`litellm` for non-OpenAI endpoints" in the CHANGELOG,
or make the learning symmetric.

M-3 **`list_models()` key shape and learned temperature are inconsistent across providers.**
`openai_compatible.py:388-413` (IONOS, Melious, LiteLLM, Privatemode) returns no metadata keys at
all and never reports a learned rejection; `local_provider.py:150-163` has no
`supports_temperature`; `mammouth_provider.py` builds a subset by hand. Only OpenAI, LangDock and
Anthropic use `param_learning.model_metadata`. The spec's "learning memory → `supports_temperature
= False`" therefore holds for some providers only. Use `model_metadata()` everywhere.

M-4 **Stream: "before anything is sent" is true, "the call raises" is not.**
`docs/providers.md:76-78` says the call raises `ModelNotSpecifiedError`; for
`stream_completion` (generator) it surfaces on the first `next()`. Server mode handles this
(`server/app.py:135-139`), a library consumer does not see it at call time. Deferred from Task 1,
still open — one sentence in the docs, or resolve eagerly via a non-generator wrapper.

M-5 **`ContextWindowManager` logs a WARNING on every construction without `context_length`.**
`rag/context_manager.py`. Consumers that build one per request (the Odoo module builds providers
per request) get one WARNING per chat turn. Ruling 6 asked for the WARNING; consider logging once
per model (module-level set) to avoid log flooding.

M-6 **Anthropic listing reads only the first page.** `anthropic_shared.py:71`
`client.models.list(limit=100).data` ignores pagination; iterating the page object would
auto-paginate. Harmless today, contradicts "returns every model the provider lists".

M-7 **`LangDockAgentManager.create_agent(name, instruction, model)` without a model raises
`TypeError`**, not `ModelNotSpecifiedError`. Clear enough for a required positional; mention in the
upgrade notes for consistency.

M-8 **Docs / CHANGELOG nits.** CHANGELOG "Removed" lists `MODEL_CONTEXT_LENGTHS` twice (OpenAI
and LangDock — qualify them). `docs/providers.md:137,150,437,450` still use a real model id as the
example while every other example uses `your-model-id`. `docs/providers.md:71,379` call
`m.id`/`m.supports_vision` on what are dicts (pre-existing, but this branch rewrote the section
around it). `.planning/codebase/CONCERNS.md:32` and `CONVENTIONS.md:26` still describe
`MODEL_TEMPERATURE_CONSTRAINTS` as current (planning notes, low priority).

M-9 **Test coverage gaps after the xfail sweep (deletion list).** Every "ported to …" reference in
the xfail reasons resolves to an existing test (checked mechanically). Behaviour that is still in
the code but only asserted inside xfailed tests: default `timeout`/`max_retries` of
`OpenAIProvider`/`AnthropicProvider` and `organization is None` (`test_openai.py::TestOpenAIProviderInit::test_basic_init`,
`test_anthropic.py::...::test_basic_init`), Local default `api_key`/`timeout` partly
(`test_local.py::test_default_initialization`; `test_local_wire.py:19` covers most of it). Split
the still-valid assertions out before deleting (already a deferred Task 1 minor).

M-10 **Embedder `dimensions=` name collides with OpenAI's request parameter `dimensions`.**
`rag/embedder.py:46-71`. It is only a size check, never sent; a caller passing `dimensions=256`
to get shortened vectors gets a `ValueError` on the first embed instead. Say "expected vector
size, not sent to the API" in the docstring and CHANGELOG.

---

## Checked and fine

- Model resolution: all OpenAI-wire providers via `OpenAICompatibleProvider.chat_completion` /
  `stream_completion`; Anthropic; LangDock resolves once before dispatch, so the `google` and
  `codestral` backends get `ModelNotSpecifiedError` too (agent backend exempt, tested);
  OpenAI/OpenRouter image, LiteLLM TTS (model and voice) and STT, all three embedders raise the
  typed error before any request. Empty strings from form fields fall back to the constructor
  model and never send an empty id.
- Learning: bounded (`adjusted` set per call), never re-enabled by a list, Anthropic path limited
  to `temperature` (`max_tokens` is mandatory there), Anthropic error envelope unwrapped, range
  messages not learned, learned state applied before the first send. Overload retries in
  `AnthropicProvider` reuse already-adjusted params correctly. Thread safety: all reads/writes of
  `_MEMORY` under `_lock`; `adjust` only touches the per-call dict (copies `extra_body`).
- Server mode: 400 with `detail.type == "ModelNotSpecifiedError"` for `/chat` and before
  `/chat/stream` opens; `/models` maps the new listing `ProviderError` to HTTP.
- Secrets/hostnames: added lines contain only public provider endpoints, `litellm.example.com`
  placeholders and test dummies (`sk-or-from-config`); the former gateway domain is gone from the
  tracked tree. No personal paths or customer data in the diff.
- Dead code: no references left to the removed constants/functions in `src/`;
  `strip_provider_prefix` is still used by `capability_catalog` (ruling 2).

## Note on the working tree

At review time the worktree had 29 uncommitted changes not made by this review (two staged
deletions of fully-xfailed test modules, 26 modified test files, `tests/reports/latest.md`), i.e.
the deletion-list work appears to be in progress in another session. The test run above ran
against that tree; `tests/reports/latest.md` and two new `tests/reports/test-report-*.md` files
were also written by this review's test runs — restore/ignore them before the next commit as
the constraints prescribe. This review assessed the committed range only.
