# No model IDs in library source — design (stage 2)

Date: 07.10.2026 · Target release: 4.0.0 · Status: approved in conversation, awaiting spec review
Builds on: `2026-10-07-provider-base-class-design.md` (stage 1, merged)

## Context

Model IDs change every few weeks. The library still names roughly 120 of them in `src/`:
default models per provider, name-prefix lists, context-length tables, a ~45-entry temperature
table, embedding dimension tables, image/TTS/STT defaults, a tokenizer map, and a bundled
capability snapshot with 20 models. Every list is permanently behind, and a stale entry breaks
real requests: on 07.10.2026 LangDock's built-in default `gpt-5.6-luna` was no longer offered,
and LangDock's `list_models()` hid every `gpt-6` model behind a prefix filter.

Stage 1 introduced runtime learning (`providers/param_learning.py`) for `temperature` and
`max_tokens`, with the name lists kept only as a first guess. Stage 2 removes the lists.

## Goals

1. No model ID, model family prefix or model-specific value anywhere under `src/` — code,
   docstrings, comments, packaged data. Enforced by a test.
2. The model always comes from the user: per call or per provider instance. Missing → a clear,
   typed error.
3. Decisions that lists used to make are made by the provider's API or learned at runtime.
4. `list_models()` reports what the provider says; unknown is `None`, never a guess.

## Non-goals

- Restructuring the remaining mocked tests (stage 3).
- Changing which providers exist, or the transport/security layer.
- Provider-level rules that hold for every model of a provider (Anthropic's temperature range
  0–1, OpenAI's `max_completion_tokens`) — these stay; they are not model lists.

## Evidence (live probes, 07.10.2026)

| Endpoint, model | Request | Response |
|---|---|---|
| OpenAI, `gpt-5.6-luna` | `temperature=0.7` | 400, `param: "temperature"`, `code: "unsupported_value"` |
| OpenAI, `gpt-5.6-luna` | `max_tokens` | 400, `param: "max_tokens"`, `code: "unsupported_parameter"` |
| Anthropic, `claude-sonnet-5` | `temperature=0.7` (via `extra_body`) | 400, `message: "`temperature` is deprecated for this model."`, no `param` |
| Anthropic, `claude-haiku-4-5` | `temperature=0.7` | accepted |
| Anthropic, `claude-haiku-4-5` | `temperature=1.5` | 400, `message: "temperature: range: 0..1"` |
| LangDock OpenAI, `gpt-5.6-luna` | any | 400, model no longer offered |

## Design

### 1. Model is required

- Resolution order for every call that needs a model (chat, stream, image, TTS, STT, embed):
  argument `model=` → the provider instance's `model` (constructor) → `ModelNotSpecifiedError`.
- `ModelNotSpecifiedError(ProviderError)` is new, exported from `eq_chatbot_core.providers`. Its
  message names both places to set the model. Subclassing `ProviderError` keeps existing
  `except ProviderError` handlers (Odoo module, server mode) working.
- Every provider constructor accepts an optional `model: str | None = None` (additive where
  missing: OpenAI, Mammouth, OpenRouter, Local, Anthropic, LangDock). LiteLLM additionally takes
  `tts_model`, `tts_voice`, `stt_model`; OpenAI and OpenRouter take `image_model`.
- `default_model` stays as a non-abstract property returning the instance's model or `None`.
- Removed: `DEFAULT_MODEL`, `DEFAULT_IMAGE_MODEL`, `DEFAULT_TTS_MODEL`, `DEFAULT_TTS_VOICE`,
  `DEFAULT_STT_MODEL` class constants and the module-level `DEFAULT_MODEL` aliases.
- CLI: model from `--model`, else the provider's `model` key in
  `~/.config/eq-chatbot/config.toml`, else an explanatory message (exit code ≠ 0, no traceback).
  Server mode: the request's `model` field, else HTTP 400 with the same explanation.

### 2. Name lists removed

**Temperature.** `MODEL_TEMPERATURE_CONSTRAINTS`, `get_temperature_constraints()` and
`strip_provider_prefix()` (if unused afterwards) are removed. What remains:
- `clamp_temperature(temperature, *, maximum=2.0) -> float` — provider-level range only.
- `apply_anthropic_temperature(params, temperature)` — clamps to 0–1 and routes into
  `extra_body`; no model argument.
Whether a model accepts temperature at all is decided only by learning.

**Learning extended** (`param_learning`):
- Recognition also accepts "deprecated" alongside "unsupported"/"not supported" in the
  text fallback (Anthropic's wording). The range message "temperature: range: 0..1" carries no
  quoted name and no such word, so it is still not a rejection.
- `reasoning_effort` becomes learnable: on rejection it is dropped and remembered.
- `AnthropicProvider` and LangDock's `anthropic` backend use `apply` / `rejected_parameter` /
  `adjust` / `mark_unsupported` for `temperature` (one retry, same rules as stage 1). `max_tokens`
  is mandatory in the Anthropic API and is not learned there.

**Output limit.** `NEW_API_MODELS` and both `_uses_new_token_api` copies are removed.
`OpenAIProvider` always sends `max_completion_tokens` (accepted by the OpenAI API for all current
models). Every other OpenAI-wire provider sends `max_tokens`; learning corrects it.

**Reasoning effort.** `REASONING_MODEL_PREFIXES` (Mammouth, OpenRouter) and LangDock's
`REASONING_MODELS` are removed. `reasoning_effort` is sent whenever the caller sets it (argument
or LangDock's constructor default) and is learned away if a model rejects it.

**Model listing.** Prefix filters are removed (`CHAT_MODEL_PREFIXES`, LangDock's
`supported_prefixes`), as are `MODEL_CONTEXT_LENGTHS` tables, name-based vision detection and
LangDock's static Anthropic fallback list (`_get_known_anthropic_models`). `list_models()` returns
every model the provider lists. The existing keys stay; values:

| Source | Fields |
|---|---|
| Provider API | Mammouth `context_length`/`max_output_tokens`; OpenRouter context, modalities, `supports_tools`, `supports_reasoning` (from `supported_parameters` containing `reasoning`), temperature support |
| Learning memory | `supports_temperature = False` when a rejection was learned for that endpoint+model |
| Otherwise | `None` (unknown) — including `min_temperature`, `max_temperature`, `default_temperature`, `supports_vision`, `context_length` |

### 3. Embeddings, rate limiter, catalog

- **Embedders**: `OpenAIEmbedder.MODELS` is removed; `model` is required; `dimensions` may be
  passed, else it is read from the first embedding response and cached (`None` before that).
  `LangDockEmbedder` and `MeliousEmbedder` follow the same rule.
- **Rate limiter**: `estimate_tokens(text, model=None)` always uses `cl100k_base`; the encoding
  map and the `"gpt-4"` default are removed. `model` stays in the signature, unused.
- **Capability catalog**: `data/capability_catalog.json` and `data/capability_overrides.json`
  leave the package. Remote fetch from `data.ownerp.io` stays; on failure the catalog is empty
  (`lookup()` → `None`) and the failure is logged at WARNING.

### 4. Guard test

`tests/unit/test_no_model_ids_in_source.py` scans every file under `src/eq_chatbot_core/`
(code, docstrings, comments, JSON/TOML data) with case-insensitive patterns for model IDs and
families — at least: `gpt-\d`, `gpt-image`, `chatgpt`, `\bo[1-9](-mini|-pro|-preview)?\b`,
`claude-`, `gemini-`, `mistral-`, `\bllama-`, `text-embedding`, `whisper`, `dall-e`, `kokoro`,
`nemotron`, `qwen`, `kimi`, `minimax`, `deepseek`, `grok`, `sonar`. It reports
file and line for every hit. Provider and backend names (`openai`, `anthropic`, `mistral` as a URL
path segment, `codestral` as a LangDock backend name, `ollama`) are not model IDs and must not
match. Docstring examples use placeholders (`"your-model-id"`).

## Testing

- New behaviour is tested against the stage-1 wire server: `ModelNotSpecifiedError` on every
  call type and provider; constructor `model=`; unfiltered `list_models()` with `None` fields;
  `reasoning_effort` learning; embedder dimension discovery.
- Anthropic learning is tested against the real Anthropic SDK pointed at the wire server
  (Messages API shape: `POST /v1/messages`, error body `{"type":"error","error":{...}}`), and
  live: `claude-sonnet-5` with `temperature=0.7` succeeds and the second call does not retry.
- Live tests keep taking models from `tests/model_registry.py`. Tests that checked built-in
  defaults (`test_backend_defaults_are_actually_available`, `test_default_model_is_still_served`,
  `test_default_model_actually_answers`) are replaced by "the registry model appears in
  `list_models()` and answers".
- Mocked tests asserting defaults or name lists are xfailed with a reason and collected into one
  deletion list for the Captain at the end, as in stage 1.
- The public-API snapshot is regenerated in its own reviewed step; the commit lists every
  removed or changed member.
- Coverage gate 83 % stays.

## Migration (CHANGELOG "Upgrading from 3.x")

- Pass `model=` per call or to the provider constructor; without it calls raise
  `ModelNotSpecifiedError`. Same for `generate_image`, `text_to_speech`, `transcribe`, embedders.
- `list_models()` returns all provider models; `None` means unknown. Treat
  `supports_temperature is None` as "allowed — the library adapts".
- Removed constants and functions (full list in the entry).
- Embedders: pass `dimensions` when creating a vector collection before the first embed call.
- The bundled capability snapshot is gone; offline the catalog is empty.

## Risks

| Risk | Mitigation |
|---|---|
| A consumer (Odoo module) relies on default models | Typed `ModelNotSpecifiedError` with an actionable message; check the Odoo module before releasing 4.0 (outside this repo) |
| UIs hide controls when metadata is `None` | Documented in the migration section |
| A provider rejects a parameter in a form not recognised | Error propagates as today; add the form to recognition and the wire server |
| OpenAI's full model list includes non-chat models | Documented; filtering by name would reintroduce the list |
| Guard test false positives on legitimate words | Patterns target model families; provider/backend names are excluded and tested as non-matches |

## Release

4.0.0 through `/afterwork`, after the Odoo chatbot module has been checked for calls without a
model.
