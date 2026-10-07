# No model IDs in library source (stage 2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every model ID, model-family list and model-specific value from `src/eq_chatbot_core/`, make the model a required input (per call or per provider instance), and let the provider's API or runtime learning make the decisions the lists used to make.

**Architecture:** `BaseLLMProvider` gains a `model=` constructor argument and `resolve_model()`, which raises the new `ModelNotSpecifiedError` (a `ProviderError`). `param_learning` learns three parameters (`temperature`, `max_tokens`, `reasoning_effort`), understands Anthropic's error envelope and wording, and is wired into `AnthropicProvider` and LangDock's `anthropic` backend through a small shared module (`providers/anthropic_shared.py`). `list_models()` reports provider data and learned facts only; unknown is `None`. Embedders discover their vector size from the first response. A guard test scans every file under `src/` for model-ID patterns.

**Tech Stack:** Python ≥ 3.12, `openai` SDK 3.26 and `anthropic` SDK 1.11 on `httpx2`, pytest 9, stdlib `http.server` wire server (`tests/wire_server.py`), `qdrant-client` in-memory mode, Click 8.5, FastAPI `TestClient`, uv.

**Spec:** `docs/superpowers/specs/2026-10-07-no-model-ids-in-source-design.md` (builds on stage 1: `docs/superpowers/specs/2026-10-07-provider-base-class-design.md`)

## Global Constraints

- No model ID, model family prefix or model-specific value anywhere under `src/` — code, docstrings, comments, packaged data. Docstring examples use placeholders (`"your-model-id"`). Provider and backend names (`openai`, `anthropic`, `mistral` as URL path segment, `codestral` as LangDock backend name, `ollama`) are not model IDs and stay.
- The model always comes from the user: argument `model=` → the provider instance's `model` (constructor) → `ModelNotSpecifiedError`. `ModelNotSpecifiedError(ProviderError)` is exported from `eq_chatbot_core.providers`.
- Provider-level rules that hold for every model of a provider stay (Anthropic temperature 0–1, OpenAI `max_completion_tokens`, OpenAI-wire temperature 0–2). They are not model lists.
- Tests may name models (test data). Live tests take models from `tests/model_registry.py` or from a named probe constant in the test file.
- `tests/model_registry.py` carries uncommitted edits by the Captain: read it, never edit or stage it.
- Coverage gate `fail_under = 83` must hold after every task: `uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3`.
- `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/` and `uv run mypy src/` clean after every task.
- One commit per task, prefix `[ADD]`/`[CHG]`/`[FIX]`, German subject as in stage 1. The body lists every test the task xfailed (`file::test — reason`). Every commit message ends with exactly these two lines:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01GJzy9HGak7N5HG7StkSHWF`
  No push.
- Stage by explicit path only (`git add <file> <file>`); never `git add -A`, `git add .` or `git add tests/`. Never stage `tests/reports/`. Run `git checkout -- tests/reports/latest.md` before every commit (the test run rewrites it).
- Never delete a test. An obsolete test gets `@pytest.mark.xfail(reason="stage 2: <what was removed>", strict=False)`; an obsolete **live** test additionally `run=False` (it costs money). A test module that can no longer be imported gets a module-level `pytest.skip("stage 2: <why>", allow_module_level=True)` in an `except ImportError` around the failing import. All of them are listed in Task 10 for one batched "ja" from the Captain.
- Behaviour that still exists but is only covered by a mocked test that now breaks: port it to the wire server first (new test in the provider's `test_*_wire.py` or the task's new file), then xfail the mocked one with reason `stage 2: ported to <file>::<test>`.
- No mocking of library code in new tests. The only stand-ins: the wire server (replaces the remote provider), Qdrant `location=":memory:"` (replaces the vector database), temporary config files.
- `openai` / `anthropic` imports in `src/` stay inside functions and properties: old unit modules put MagicMocks into `sys.modules` at import time. New tests that need a real SDK use the `wire_server` fixture, which restores both real SDKs (`real_openai`, `real_anthropic` from Task 2).
- Deleting a file under `src/` (the two catalog JSON files, Task 6) needs the Captain's explicit "ja" first, and `git status --short <path>` must show the path clean.
- The repository mirrors to GitHub: no customer names, hostnames, internal URLs, IP addresses or keys in code, tests, docs or commit messages.
- Shell snippets the Captain types are Fish syntax; commands the agent runs may be POSIX.
- Version bump to 4.0.0 is not part of this plan (done later by `/afterwork`).
- Live tests run once, in Task 10. OpenRouter's configured key answers 401 (live there stays unverified). No local LM Studio/Ollama run. Privatemode only if its local proxy answers.

**Triage rule for existing tests** (every task has a step that applies it; its expected failures are listed there):

1. The test fails only because a call now needs a model (`ModelNotSpecifiedError`, or `NameError`/`ImportError` on a removed `DEFAULT_*` name) and it asserts behaviour that still exists → add the model to the call or constructor (`model="test-model"`; image `model="img-model"`; TTS `model="tts-model", voice="voice-1"`; STT `model="stt-model"`; CLI `"-m", "test-model"`). Never assert a library default.
2. The test asserts a removed default, name list, table value or name-derived metadata → xfail per the Global Constraints. Whole-module obsolescence: append `pytest.mark.xfail(reason="stage 2: …", strict=False)` to the module's `pytestmark`.
3. Mocked test of behaviour that still exists but changed shape → port to the wire server first, then xfail with `stage 2: ported to …`.
4. Anything else that fails is a regression: fix the code, not the test.

## Review Focus

1. **A model field that is set but empty** — Odoo hands an unset char field over as `False` and a cleared one as `""`. With a constructor model, the constructor model must be used; without one, `ModelNotSpecifiedError` — never a request carrying `"model": ""`. Pinned in Task 1 (`test_empty_model_from_a_form_field_falls_back_to_constructor`, `test_empty_model_without_constructor_model_never_sends_an_empty_id`).
2. **LangDock's `agent` backend called without a model** — the agent's model is configured in LangDock, so this must keep working, not raise `ModelNotSpecifiedError`. Pinned in Task 1 (`test_langdock_agent_backend_needs_no_model`).
3. **An Anthropic temperature range error** (`"temperature: range: 0..1"`) — must propagate as an error and must not be learned as "temperature unsupported" (that would silently drop the user's setting for that model for the rest of the process). Pinned in Task 3 (`test_range_error_is_not_learned`).
4. **Embedding vector size** — `dimensions` passed but the model returns another size must raise a clear `ValueError` instead of writing mismatched vectors; creating a Qdrant collection before the size is known must raise a clear `ValueError` instead of creating a collection of size `None`. Pinned in Task 6 (`test_configured_dimensions_mismatch_raises`, `test_collection_size_comes_from_the_embedder`).
5. **Server-mode streaming request without a model** — must answer HTTP 400 before the stream starts, not a 200 event stream whose only event is an error. Pinned in Task 7 (`test_stream_without_model_is_400_before_the_stream`).

---

## Task order and why it differs from the suggested shape

1. Model required (incl. image/TTS/STT; LangDock agent manager).
2. `param_learning` extensions (+ Anthropic error constants, `real_anthropic` fixture).
3. Anthropic + LangDock `anthropic` backend learning (+ Messages-API builders in the wire server).
4. **`list_models()` without filters / `None` metadata / learned `supports_temperature`.**
5. **Name lists removed** (temperature table, `NEW_API_MODELS`, reasoning prefixes, clamp signatures).
6. Embedders, retriever, rate limiter, context manager, capability catalog + package data, realtime config defaults.
7. CLI and server mode.
8. Guard test + remaining docstrings/comments.
9. Public-API snapshot regeneration.
10. Docs, live verification, deletion list, report.

Tasks 4 and 5 are swapped against the suggested shape: every `list_models()` implementation (OpenAI, Anthropic, LangDock, Mammouth) reads `get_temperature_constraints()` and the reasoning prefixes. Removing the tables first would break `list_models()` in the same commit; rewriting `list_models()` first leaves the tables without readers, so Task 5 is a pure deletion and the suite stays green after each task. Embedders move entirely into Task 6 because their `model` requirement and their dimension discovery replace the same `MODELS` table. Realtime configs and `ContextWindowManager` are not named in the spec but carry model IDs under `src/`, which the guard test (spec section 4) forbids; they go into Task 6.

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/eq_chatbot_core/providers/base.py` | `ModelNotSpecifiedError`; `BaseLLMProvider(model=)`, `default_model`, `resolve_model()` | 1 |
| `src/eq_chatbot_core/providers/__init__.py` | Export `ModelNotSpecifiedError`; placeholder docstring | 1, 8 |
| `src/eq_chatbot_core/providers/openai_compatible.py` | No `DEFAULT_MODEL`; resolve model; learning via shared helper; provider-level clamp | 1, 2, 5 |
| `src/eq_chatbot_core/providers/{openai,openrouter,mammouth,local,ionos,melious,litellm,privatemode}_provider.py` | Constructor `model=` (+ `image_model`, `tts_*`, `stt_model`); lists removed; `list_models()` reworked | 1, 4, 5, 8 |
| `src/eq_chatbot_core/providers/anthropic_provider.py` | `model=`; temperature learning; `list_models()` from the Models API | 1, 3, 4, 5, 8 |
| `src/eq_chatbot_core/providers/langdock_provider.py` | `model=`, agent backend without model, anthropic learning, unfiltered lists, no reasoning gating | 1, 3, 4, 5, 8 |
| `src/eq_chatbot_core/providers/param_learning.py` | Recognition (Anthropic envelope, "deprecated"), `reasoning_effort`, `learn_from_rejection`, `temperature_support`, `model_metadata` | 2 |
| `src/eq_chatbot_core/providers/anthropic_shared.py` (new) | `create_message`, `open_message_stream` (learning), `capability_supported` | 3, 4 |
| `src/eq_chatbot_core/providers/temperature_constraints.py` | Only `clamp_temperature(t, *, maximum)` and `apply_anthropic_temperature(params, t)` | 5 |
| `src/eq_chatbot_core/rag/embedder.py`, `rag/retriever.py`, `rag/context_manager.py` | Model required, dimension discovery, no limit table | 6 |
| `src/eq_chatbot_core/security/rate_limit.py` | `estimate_tokens` always `cl100k_base` | 6 |
| `src/eq_chatbot_core/services/capability_catalog.py`, `src/eq_chatbot_core/data/*.json`, `pyproject.toml` | Snapshot leaves the package; offline = empty catalog | 6 |
| `src/eq_chatbot_core/realtime/providers/{openai,gemini_live}.py` | No default realtime model | 6 |
| `src/eq_chatbot_core/cli.py`, `src/eq_chatbot_core/data/config.toml.example` | `--model` → config → explanatory exit | 7 |
| `src/eq_chatbot_core/server/app.py` | HTTP 400 for a missing model, eager for streams | 7 |
| `tests/wire_server.py`, `tests/conftest.py` | Anthropic constants and builders, embeddings builder, `real_anthropic` | 2, 3, 6 |
| `tests/unit/test_model_required_wire.py` (new) | Model resolution on every provider and call type | 1 |
| `tests/unit/test_anthropic_wire.py` (new) | Anthropic learning against the real SDK | 3 |
| `tests/unit/test_list_models_wire.py` (new) | Unfiltered lists, `None` metadata, learned facts | 4 |
| `tests/unit/test_no_name_lists_wire.py` (new) | Behaviour without name lists | 5 |
| `tests/unit/test_embedder_wire.py` (new) | Embedders and retriever (vector size) | 6 |
| `tests/unit/test_no_model_tables.py` (new) | Token estimator, context manager, capability catalog, packaging, realtime configs | 6 |
| `tests/unit/test_cli_model_required.py`, `tests/unit/server/test_model_required.py` (new) | CLI and server resolution | 7 |
| `tests/unit/test_no_model_ids_in_source.py` (new) | Guard test | 8 |
| `tests/unit/test_public_api_compat.py`, `tests/compat/snapshot.py`, `tests/compat/public_api.json` | Stage-2 allowance (Task 1), regenerated snapshot (Task 9) | 1, 3–5, 9 |
| `tests/integration/test_anthropic_live.py` (new), `tests/integration/test_openai_live.py` | Live learning proof; registry models instead of defaults | 10 |
| `CLAUDE.md`, `AGENTS.md`, `docs/providers.md`, `docs/cli.md`, `docs/reasoning.md`, `CHANGELOG.md` | Documentation | 10 |

---

### Task 1: Model is required — `ModelNotSpecifiedError`, `resolve_model()`, constructor `model=`

**Files:**
- Modify: `src/eq_chatbot_core/providers/base.py:143-190` (`BaseLLMProvider.__init__`, `default_model`), `:328-380` (new exception, `__all__`)
- Modify: `src/eq_chatbot_core/providers/__init__.py:183-226` (export)
- Modify: `src/eq_chatbot_core/providers/openai_compatible.py:14-19, 51-57, 72-74, 86-138, 261, 332`
- Modify: `src/eq_chatbot_core/providers/openai_provider.py:24-34, 53-62, 182-209`
- Modify: `src/eq_chatbot_core/providers/openrouter_provider.py:38-79, 125-154`
- Modify: `src/eq_chatbot_core/providers/mammouth_provider.py:34-58`
- Modify: `src/eq_chatbot_core/providers/local_provider.py:46-82`
- Modify: `src/eq_chatbot_core/providers/ionos_provider.py:8-12, 40-48`, `melious_provider.py:8-12, 43-53`, `privatemode_provider.py:88-90, 257-259`
- Modify: `src/eq_chatbot_core/providers/litellm_provider.py` (whole file body below the module docstring)
- Modify: `src/eq_chatbot_core/providers/anthropic_provider.py:50-96, 299, 390`
- Modify: `src/eq_chatbot_core/providers/langdock_provider.py:232-315, 426, 932, 1604-1614, 1856-1870`
- Modify: `tests/unit/test_public_api_compat.py`
- Modify: `tests/unit/test_openai_compatible_wire.py:258,266`, `tests/unit/test_openai_wire.py:37-47,117`, `tests/unit/test_openrouter_wire.py:54,62,89-95,205,209-219,227,305`
- Create: `tests/unit/test_model_required_wire.py`

**Interfaces:**
- Produces:
  - `eq_chatbot_core.providers.base.ModelNotSpecifiedError(provider: str, *, what: str = "model", argument: str = "model", constructor_argument: str = "model", hint: str | None = None)` — subclass of `ProviderError`; `.provider`, `.what`, `.status_code is None`; message `No <what> specified for provider "<provider>". <instruction>`, where the default instruction names `{argument}="..."` and `get_provider("<provider>", ..., {constructor_argument}="...")` and `hint` replaces it (used by the embedders in Task 6). Exported from `eq_chatbot_core.providers`.
  - `BaseLLMProvider.__init__(self, api_key: str, base_url: str | None = None, timeout: float = 60.0, max_retries: int = 2, model: str | None = None)`
  - `BaseLLMProvider.default_model -> str | None` (property, no longer abstract)
  - `BaseLLMProvider.resolve_model(self, model: str | None = None) -> str` (raises `ModelNotSpecifiedError`); `LangDockProvider.resolve_model` returns `model or ""` when `backend == "agent"`.
  - Constructors (new parameters appended at the end):
    `OpenAIProvider(api_key, base_url=None, timeout=60.0, max_retries=2, organization=None, model=None, image_model=None)`,
    `OpenRouterProvider(api_key, base_url=None, timeout=60.0, max_retries=2, site_url=None, site_name=None, model=None, image_model=None)`,
    `MammouthProvider(api_key, base_url=None, timeout=60.0, max_retries=2, model=None)`,
    `LocalLLMProvider(api_key="not-used", base_url=None, timeout=None, max_retries=2, model=None)`,
    `AnthropicProvider(api_key, base_url=None, timeout=60.0, max_retries=2, model=None)`,
    `LangDockProvider(api_key, base_url=None, timeout=60.0, max_retries=2, region="eu", backend="openai", reasoning_effort=None, agent_id=None, model=None)`,
    `LiteLLMProvider(api_key, base_url=None, timeout=60.0, max_retries=2, model=None, *, tts_model=None, tts_voice=None, stt_model=None)`.
  - Attributes `OpenAIProvider.image_model`, `OpenRouterProvider.image_model`, `LiteLLMProvider.tts_model`, `.tts_voice`, `.stt_model`.
  - `LiteLLMProvider.text_to_speech(text, *, model: str | None = None, voice: str | None = None, response_format="wav", **kwargs) -> bytes`; `transcribe(audio, *, model: str | None = None, **kwargs) -> str`.
  - `LangDockAgentManager.create_agent(self, name: str, instruction: str, model: str, knowledge_folder_ids=None, **kwargs)` — `model` has no default.
  - Test-side: `_STAGE2_CHANGES: dict[str, set[str]]` in `tests/unit/test_public_api_compat.py`; later tasks add names to it.
- Removed: `OpenAICompatibleProvider.DEFAULT_MODEL` (and therefore on IONOS, Melious, LiteLLM, Privatemode, Mammouth, OpenAI, OpenRouter, Local), `OpenAIProvider.DEFAULT_IMAGE_MODEL`, `OpenRouterProvider.DEFAULT_IMAGE_MODEL`, module-level `DEFAULT_MODEL` in `ionos_provider`, `melious_provider`, `litellm_provider`, `privatemode_provider`, module-level `DEFAULT_TTS_MODEL`, `DEFAULT_TTS_VOICE`, `DEFAULT_STT_MODEL` in `litellm_provider`, the `default_model` overrides of `OpenAICompatibleProvider`, `AnthropicProvider`, `LangDockProvider`.

- [ ] **Step 1: Write the failing tests — `tests/unit/test_model_required_wire.py`**

```python
"""Stage 2: the model always comes from the caller — per call or per provider instance.

Runs against the wire server; a missing model must fail before any request is sent.
"""

import inspect

import pytest

from eq_chatbot_core.providers import ModelNotSpecifiedError, ProviderError, get_provider
from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.ionos_provider import IonosProvider
from eq_chatbot_core.providers.langdock_provider import LangDockAgentManager, LangDockProvider
from eq_chatbot_core.providers.litellm_provider import LiteLLMProvider
from eq_chatbot_core.providers.local_provider import LocalLLMProvider
from eq_chatbot_core.providers.mammouth_provider import MammouthProvider
from eq_chatbot_core.providers.melious_provider import MeliousProvider
from eq_chatbot_core.providers.openai_provider import OpenAIProvider
from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider
from eq_chatbot_core.providers.privatemode_provider import PrivatemodeProvider
from tests.wire_server import Reply, chat_body, stream_events

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]
CHAT = ("POST", "/v1/chat/completions")
WIRE_NAMES = ["openai", "mammouth", "openrouter", "local", "ionos", "melious", "litellm", "privatemode"]


def _wire_provider(wire_server, name, **kw):
    url = wire_server.base_url
    makers = {
        "openai": lambda: OpenAIProvider(api_key="k", base_url=url, max_retries=0, **kw),
        "mammouth": lambda: MammouthProvider(api_key="k", base_url=url, max_retries=0, **kw),
        "openrouter": lambda: OpenRouterProvider(api_key="k", base_url=url, max_retries=0, **kw),
        "local": lambda: LocalLLMProvider(base_url=url, max_retries=0, **kw),
        "ionos": lambda: IonosProvider(api_key="k", base_url=url, max_retries=0, **kw),
        "melious": lambda: MeliousProvider(api_key="k", base_url=url, max_retries=0, **kw),
        "litellm": lambda: LiteLLMProvider(api_key="k", base_url=url, max_retries=0, **kw),
        "privatemode": lambda: PrivatemodeProvider(
            base_url=url, max_retries=0, allow_insecure_transport=True, **kw
        ),
    }
    return makers[name]()


@pytest.mark.parametrize("name", WIRE_NAMES)
def test_chat_without_any_model_raises_before_sending(wire_server, name):
    with pytest.raises(ModelNotSpecifiedError) as caught:
        _wire_provider(wire_server, name).chat_completion(MSG)
    assert caught.value.provider == name
    assert wire_server.requests == []


@pytest.mark.parametrize("name", WIRE_NAMES)
def test_stream_without_any_model_raises_before_sending(wire_server, name):
    with pytest.raises(ModelNotSpecifiedError):
        next(iter(_wire_provider(wire_server, name).stream_completion(MSG)))
    assert wire_server.requests == []


@pytest.mark.parametrize("name", WIRE_NAMES)
def test_constructor_model_is_used(wire_server, name):
    wire_server.expect(*CHAT, Reply(body=chat_body()))
    _wire_provider(wire_server, name, model="ctor-model").chat_completion(MSG)
    assert wire_server.requests[0].json["model"] == "ctor-model"


@pytest.mark.parametrize("name", WIRE_NAMES)
def test_call_model_beats_constructor_model(wire_server, name):
    wire_server.expect(*CHAT, Reply(sse=stream_events(["a"])))
    chunks = list(_wire_provider(wire_server, name, model="ctor-model").stream_completion(MSG, model="call-model"))
    assert chunks[-1].is_final
    assert wire_server.requests[0].json["model"] == "call-model"


@pytest.mark.parametrize("empty", ["", None, False])
def test_empty_model_from_a_form_field_falls_back_to_constructor(wire_server, empty):
    """Review focus 1: Odoo passes an unset char field as False and a cleared one as ""."""
    wire_server.expect(*CHAT, Reply(body=chat_body()))
    _wire_provider(wire_server, "openai", model="ctor-model").chat_completion(MSG, model=empty)
    assert wire_server.requests[0].json["model"] == "ctor-model"


@pytest.mark.parametrize("empty", ["", None, False])
def test_empty_model_without_constructor_model_never_sends_an_empty_id(wire_server, empty):
    with pytest.raises(ModelNotSpecifiedError):
        _wire_provider(wire_server, "mammouth").chat_completion(MSG, model=empty)
    assert wire_server.requests == []


def test_error_names_both_places_and_is_a_provider_error():
    error = ModelNotSpecifiedError("openai")
    assert isinstance(error, ProviderError)
    assert error.provider == "openai" and error.status_code is None and error.what == "model"
    assert 'model="..."' in str(error) and 'get_provider("openai"' in str(error)


@pytest.mark.parametrize("backend", ["openai", "anthropic", "google", "codestral"])
def test_langdock_backends_need_a_model(backend):
    provider = LangDockProvider(api_key="k", backend=backend)
    with pytest.raises(ModelNotSpecifiedError):
        provider.chat_completion(MSG)
    with pytest.raises(ModelNotSpecifiedError):
        next(iter(provider.stream_completion(MSG)))


def test_langdock_agent_backend_needs_no_model():
    """Review focus 2: the agent's model is configured in LangDock, not per request."""
    provider = LangDockProvider(api_key="k", backend="agent", agent_id="agent-1")
    assert provider.default_model is None
    assert provider.resolve_model(None) == ""


def test_langdock_constructor_model():
    assert LangDockProvider(api_key="k", backend="google", model="ctor-model").resolve_model() == "ctor-model"


def test_anthropic_needs_a_model_and_takes_one_in_the_constructor():
    with pytest.raises(ModelNotSpecifiedError):
        AnthropicProvider(api_key="k").chat_completion(MSG)
    with pytest.raises(ModelNotSpecifiedError):
        next(iter(AnthropicProvider(api_key="k").stream_completion(MSG)))
    assert AnthropicProvider(api_key="k", model="ctor-model").default_model == "ctor-model"


def test_get_provider_forwards_model():
    assert get_provider("mammouth", api_key="k", model="ctor-model").default_model == "ctor-model"
    assert get_provider("ollama", model="ctor-model").default_model == "ctor-model"


def _image_reply_body():
    body = chat_body("")
    body["choices"][0]["message"]["images"] = [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw=="}}
    ]
    return body


def test_openai_image_needs_a_model(wire_server):
    with pytest.raises(ModelNotSpecifiedError, match="image_model"):
        _wire_provider(wire_server, "openai").generate_image("a cat")
    assert wire_server.requests == []


def test_openai_image_model_from_constructor(wire_server):
    wire_server.expect(
        "POST", "/v1/images/generations", Reply(body={"created": 0, "data": [{"b64_json": "iVBORw=="}]})
    )
    provider = _wire_provider(wire_server, "openai", image_model="img-model")
    assert provider.generate_image("a cat").model == "img-model"
    assert wire_server.requests[0].json["model"] == "img-model"


def test_openrouter_image_needs_a_model(wire_server):
    with pytest.raises(ModelNotSpecifiedError, match="image_model"):
        _wire_provider(wire_server, "openrouter").generate_image("a cat")
    assert wire_server.requests == []


def test_openrouter_image_model_from_constructor(wire_server):
    wire_server.expect(*CHAT, Reply(body=_image_reply_body()))
    provider = _wire_provider(wire_server, "openrouter", image_model="img-model")
    assert provider.generate_image("a cat").model == "img-model"
    assert wire_server.requests[0].json["model"] == "img-model"


def test_tts_needs_model_and_voice(wire_server):
    with pytest.raises(ModelNotSpecifiedError, match="tts_model"):
        _wire_provider(wire_server, "litellm").text_to_speech("Hallo", voice="voice-1")
    with pytest.raises(ModelNotSpecifiedError, match="tts_voice"):
        _wire_provider(wire_server, "litellm").text_to_speech("Hallo", model="tts-model")
    assert wire_server.requests == []


def test_stt_needs_a_model(wire_server):
    with pytest.raises(ModelNotSpecifiedError, match="stt_model"):
        _wire_provider(wire_server, "litellm").transcribe(("a.wav", b"RIFF0000", "audio/wav"))
    assert wire_server.requests == []


def test_tts_and_stt_use_constructor_settings(wire_server):
    wire_server.expect("POST", "/v1/audio/speech", Reply(raw=b"RIFF", headers={"Content-Type": "audio/wav"}))
    wire_server.expect("POST", "/v1/audio/transcriptions", Reply(body={"text": "hallo"}))
    provider = _wire_provider(
        wire_server, "litellm", tts_model="tts-model", tts_voice="voice-1", stt_model="stt-model"
    )
    assert provider.text_to_speech("Hallo") == b"RIFF"
    assert (wire_server.requests[0].json["model"], wire_server.requests[0].json["voice"]) == ("tts-model", "voice-1")
    assert provider.transcribe(("a.wav", b"RIFF0000", "audio/wav")) == "hallo"


def test_agent_manager_create_agent_requires_a_model():
    parameter = inspect.signature(LangDockAgentManager.create_agent).parameters["model"]
    assert parameter.default is inspect.Parameter.empty
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/unit/test_model_required_wire.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: collection error — `ImportError: cannot import name 'ModelNotSpecifiedError' from 'eq_chatbot_core.providers'`.

- [ ] **Step 3: `base.py` — exception, constructor model, `default_model`, `resolve_model`**

Replace `BaseLLMProvider.__init__` (lines 150-169) with:

```python
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        model: str | None = None,
    ):
        """
        Initialize the provider.

        Args:
            api_key: API key for authentication
            base_url: Optional custom base URL
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures
            model: Model used when a call passes none. There is no built-in
                default: without it, every call must pass ``model=``.
        """
        self._api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._model = model or None
```

Replace the abstract `default_model` property (lines 186-190) with:

```python
    @property
    def default_model(self) -> str | None:
        """The model set on this instance (constructor ``model=``), or ``None``."""
        return getattr(self, "_model", None)

    def resolve_model(self, model: str | None = None) -> str:
        """Return the model for one call: ``model`` if given, else the instance's.

        Raises:
            ModelNotSpecifiedError: If neither names a model.
        """
        resolved = model or self.default_model
        if not resolved:
            raise ModelNotSpecifiedError(self.provider_name)
        return resolved
```

In the `chat_completion` and `stream_completion` docstrings replace `model: Model to use (defaults to provider's default)` with `model: Model to use; falls back to the constructor's ``model``.` In `generate_image` replace `model: Model to use (defaults to provider's image default)` with `model: Image model to use; falls back to the constructor's ``image_model``.`

After `class ProviderError` (after line 341) insert:

```python
class ModelNotSpecifiedError(ProviderError):
    """Raised when a call needs a model and neither the call nor the provider names one.

    The library ships no default model: model IDs change faster than releases.
    """

    def __init__(
        self,
        provider: str,
        *,
        what: str = "model",
        argument: str = "model",
        constructor_argument: str = "model",
        hint: str | None = None,
    ):
        instruction = hint or (
            f'Pass {argument}="..." to this call, or {constructor_argument}="..." when creating the provider: '
            f'get_provider("{provider}", ..., {constructor_argument}="...").'
        )
        super().__init__(f'No {what} specified for provider "{provider}". {instruction}', provider)
        self.what = what
```

Add `"ModelNotSpecifiedError",` to `__all__` after `"ProviderError",`.

- [ ] **Step 4: Export from `providers/__init__.py`**

In the import block at line 183 add `ModelNotSpecifiedError,` between `ModelInfo,` and `OverloadedError,`; in `__all__` add `"ModelNotSpecifiedError",` after `"ProviderError",`.

- [ ] **Step 5: `openai_compatible.py`**

- Module docstring example (lines 15-18): delete the line `        DEFAULT_MODEL = "some-model"`.
- Class docstring: delete the two lines starting `DEFAULT_MODEL: Soft default model id, overridable per call or via the` / `` ``model`` constructor argument.``.
- Delete line 74 `DEFAULT_MODEL: ClassVar[str] = ""`.
- In the `__init__` docstring replace the two `model:` lines with `model: Model used when a call passes none (there is no built-in default).`
- Replace `super().__init__(api_key, effective_base_url, timeout, max_retries)` with `super().__init__(api_key, effective_base_url, timeout, max_retries, model)` and delete the line `self._model = model`.
- Delete the `default_model` property (lines 136-138); the base class provides it.
- In `chat_completion` (line 261) and `stream_completion` (line 332) replace `model = model or self.default_model` with `model = self.resolve_model(model)`.

- [ ] **Step 6: `openai_provider.py`**

Delete lines 26-27 (comment and `DEFAULT_MODEL`) and lines 33-34 (comment and `DEFAULT_IMAGE_MODEL`). Replace `__init__` (lines 53-62) with:

```python
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        organization: str | None = None,
        model: str | None = None,
        image_model: str | None = None,
    ):
        self.organization = organization
        self.image_model = image_model or None
        super().__init__(api_key, base_url, timeout, max_retries, model)
```

In `generate_image`: docstring line `model: Model to use (defaults to 'gpt-image-1')` becomes `model: Image model; falls back to the constructor's ``image_model``.` Replace `model = model or self.DEFAULT_IMAGE_MODEL` with:

```python
        model = model or self.image_model
        if not model:
            raise ModelNotSpecifiedError(self.provider_name, what="image model", constructor_argument="image_model")
```

Import: `from eq_chatbot_core.providers.base import ImageResult, ModelNotSpecifiedError`.

- [ ] **Step 7: `openrouter_provider.py`**

Delete lines 40-41 (comment, `DEFAULT_MODEL`) and 47-48 (comment, `DEFAULT_IMAGE_MODEL`). Replace `__init__` (lines 57-79) with:

```python
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        site_url: str | None = None,
        site_name: str | None = None,
        model: str | None = None,
        image_model: str | None = None,
    ):
        """
        Initialize the OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            base_url: Optional custom base URL (defaults to OpenRouter API)
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures
            site_url: Optional site URL for HTTP-Referer header (for rankings)
            site_name: Optional site name for X-Title header (for display)
            model: Chat model used when a call passes none
            image_model: Image model used when ``generate_image`` gets none
        """
        self.site_url = site_url
        self.site_name = site_name
        self.image_model = image_model or None
        super().__init__(api_key, base_url, timeout, max_retries, model)
```

In `generate_image`: docstring `model: Model to use (defaults to 'google/gemini-2.5-flash-image')` becomes `model: Image model; falls back to the constructor's ``image_model``.`; replace `model = model or self.DEFAULT_IMAGE_MODEL` with the same three lines as in Step 6. Import `ModelNotSpecifiedError` from `eq_chatbot_core.providers.base` next to `ImageResult, ProviderError`.

- [ ] **Step 8: `mammouth_provider.py`, `local_provider.py`**

Mammouth: delete lines 34-35 (comment, `DEFAULT_MODEL`). Replace `__init__` with:

```python
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        model: str | None = None,
    ):
        """
        Initialize the Mammouth AI provider.

        Args:
            api_key: Mammouth AI API key
            base_url: Optional custom base URL (defaults to Mammouth API)
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures
            model: Model used when a call passes none
        """
        super().__init__(api_key, base_url, timeout, max_retries, model)
```

Local: delete line 47 `DEFAULT_MODEL = "local-model"`. Replace `__init__` with:

```python
    def __init__(
        self,
        api_key: str = "not-used",
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int = 2,
        model: str | None = None,
    ):
        """
        Initialize the local LLM provider.

        Args:
            api_key: API key (usually not required for local servers, defaults to "not-used")
            base_url: Server URL (defaults to LM Studio URL)
            timeout: Request timeout in seconds (defaults to 120s for model loading)
            max_retries: Number of retries on transient failures
            model: Model used when a call passes none (the id the server lists)
        """
        # Always validated (LAN mode): local servers are reachable without DNS
        # surprises, and the old provider validated the default too.
        super().__init__(
            api_key=api_key,
            base_url=base_url or self.LM_STUDIO_URL,
            timeout=timeout or self.DEFAULT_TIMEOUT,
            max_retries=max_retries,
            model=model,
        )
```

- [ ] **Step 9: `ionos_provider.py`, `melious_provider.py`, `privatemode_provider.py`**

IONOS module docstring lines 10-12 (`The default model is a soft default (overridable per call or via the ``model`` constructor argument).`) become `There is no default model: pass ``model=`` per call or to the constructor.` Delete lines 40-41 (comment, `DEFAULT_MODEL`) and line 48 `DEFAULT_MODEL = IonosProvider.DEFAULT_MODEL`.

Melious: same docstring replacement for lines 11-12; delete lines 43-46 (comment block and `DEFAULT_MODEL`) and line 53 `DEFAULT_MODEL = MeliousProvider.DEFAULT_MODEL`.

Privatemode: delete lines 88-90 (two comment lines and `DEFAULT_MODEL`) and the last line `DEFAULT_MODEL = PrivatemodeProvider.DEFAULT_MODEL`; in the `__init__` docstring the `model:` line becomes `model: Model used when a call passes none (there is no built-in default).`

- [ ] **Step 10: `litellm_provider.py`**

Module docstring lines 10-11 (`The default model is a soft default (overridable per call or via the ``model`` constructor argument).`) become `There is no default model, TTS model, voice or STT model: pass them per call or to the constructor.` Replace everything from line 24 (`from typing import Any`) to the end of the file with:

```python
from typing import Any

from eq_chatbot_core.providers.base import ModelNotSpecifiedError
from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider


class LiteLLMProvider(OpenAICompatibleProvider):
    """
    Provider for OpenAI-compatible gateways (LiteLLM proxy, vLLM, custom endpoints).

    Requires an explicit ``base_url`` (no default) and an ``api_key`` sent as a
    Bearer token. Supports chat completion, streaming, tool calls, model listing,
    and — via the OpenAI Audio API — text-to-speech and speech-to-text.
    """

    PROVIDER_NAME = "litellm"
    # Intentionally no default endpoint — a gateway address cannot be guessed.
    DEFAULT_BASE_URL = None
    # Gateways may be public or self-hosted on a LAN, so private ranges are
    # allowed here; cloud-metadata and link-local targets stay blocked.
    ALLOW_PRIVATE_RANGES = True
    MISSING_BASE_URL_MESSAGE = (
        "LiteLLMProvider requires an explicit base_url (e.g. 'https://litellm.example.com/v1'). There is no default endpoint."
    )

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        model: str | None = None,
        *,
        tts_model: str | None = None,
        tts_voice: str | None = None,
        stt_model: str | None = None,
    ):
        """
        Initialize the gateway provider.

        Args:
            api_key: Gateway key, sent as a Bearer token.
            base_url: OpenAI-compatible endpoint (required).
            timeout: Request timeout in seconds.
            max_retries: Number of retries on transient failures.
            model: Chat model used when a call passes none.
            tts_model: Text-to-speech model used when ``text_to_speech`` gets none.
            tts_voice: Voice used when ``text_to_speech`` gets none.
            stt_model: Speech-to-text model used when ``transcribe`` gets none.
        """
        super().__init__(api_key, base_url, timeout, max_retries, model)
        self.tts_model = tts_model or None
        self.tts_voice = tts_voice or None
        self.stt_model = stt_model or None

    def text_to_speech(
        self,
        text: str,
        *,
        model: str | None = None,
        voice: str | None = None,
        response_format: str = "wav",
        **kwargs: Any,
    ) -> bytes:
        """
        Synthesize speech from text via the gateway's TTS endpoint.

        Args:
            text: Input text to synthesize.
            model: TTS model id; falls back to the constructor's ``tts_model``.
            voice: Voice id; falls back to the constructor's ``tts_voice``.
            response_format: Audio container, e.g. ``wav`` or ``mp3``.
            **kwargs: Additional provider-specific parameters.

        Returns:
            Raw audio bytes.

        Raises:
            ModelNotSpecifiedError: If no model or no voice is given anywhere.
        """
        model = model or self.tts_model
        if not model:
            raise ModelNotSpecifiedError(
                self.provider_name, what="text-to-speech model", constructor_argument="tts_model"
            )
        voice = voice or self.tts_voice
        if not voice:
            raise ModelNotSpecifiedError(
                self.provider_name, what="text-to-speech voice", argument="voice", constructor_argument="tts_voice"
            )
        try:
            response = self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format=response_format,
                **kwargs,
            )
            # openai SDK returns a binary response wrapper; .read() yields bytes.
            value: bytes = response.read()
            return value
        except Exception as e:
            raise self._handle_error(e) from e

    def transcribe(
        self,
        audio: Any,
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Transcribe audio to text via the gateway's STT endpoint.

        Args:
            audio: Audio input accepted by the OpenAI SDK ``file`` parameter — a
                file-like object opened in binary mode, raw ``bytes``, or a
                ``(filename, bytes, content_type)`` tuple.
            model: STT model id; falls back to the constructor's ``stt_model``.
            **kwargs: Additional provider-specific parameters.

        Returns:
            The transcribed text.

        Raises:
            ModelNotSpecifiedError: If no model is given anywhere.
        """
        model = model or self.stt_model
        if not model:
            raise ModelNotSpecifiedError(
                self.provider_name, what="speech-to-text model", constructor_argument="stt_model"
            )
        try:
            response = self.client.audio.transcriptions.create(
                model=model,
                file=audio,
                **kwargs,
            )
            value: str = response.text
            return value
        except Exception as e:
            raise self._handle_error(e) from e
```

(`MISSING_BASE_URL_MESSAGE` is copied unchanged — it is a snapshot constant; changing it is out of scope.)

- [ ] **Step 11: `anthropic_provider.py`**

Replace `__init__` (lines 50-70) with the same body plus the new parameter:

```python
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        model: str | None = None,
    ):
        # Initialize the client attribute BEFORE validation so close()/__del__
        # stay safe if the SSRF guard below raises.
        self._client: Any = None

        # SSRF guard: only a caller-supplied base_url is validated — the fixed
        # public default needs no DNS round-trip. Private ranges are rejected
        # because Anthropic is a public cloud endpoint. Imported lazily to avoid
        # an import cycle.
        if base_url:
            from eq_chatbot_core.utils.url_validation import validate_url

            validate_url(base_url, allow_private_ranges=False)

        super().__init__(api_key, base_url, timeout, max_retries, model)
```

Delete the `default_model` property (lines 90-96). In `chat_completion` (line 299) and `stream_completion` (line 390) replace `model = model or self.default_model` with `model = self.resolve_model(model)`.

- [ ] **Step 12: `langdock_provider.py`**

- `__init__`: append parameter `model: str | None = None,` after `agent_id: str | None = None,`; in the docstring add `model: Model used when a call passes none (not used by the agent backend, whose model is configured in LangDock)`; replace `super().__init__(api_key, base_url or self.BASE_URL, timeout, max_retries)` with `super().__init__(api_key, base_url or self.BASE_URL, timeout, max_retries, model)`.
- Delete the whole `default_model` property (lines 289-315) and put in its place:

```python
    def resolve_model(self, model: str | None = None) -> str:
        """Model for one call; the agent backend needs none (its model lives in LangDock)."""
        if self.backend == "agent":
            return model or ""
        return super().resolve_model(model)
```

- `chat_completion` (line 426) and `stream_completion` (line 932): `model = model or self.default_model` → `model = self.resolve_model(model)`.
- `_list_codestral_models` docstring (lines 1605-1613) becomes:

```python
        """Deliberately empty: Codestral is FIM-only, not a chat model.

        LangDock does serve ``GET /mistral/eu/v1/models``, but surfacing that
        here would put a fill-in-the-middle model into a chat model picker, where
        it cannot answer. Callers address it explicitly with ``model=``.
        """
```

- `LangDockAgentManager.create_agent`: `model: str = "gpt-4o",` → `model: str,`; docstring `model: LLM model to use` → `model: Model the agent runs (required; there is no default)`.

- [ ] **Step 13: Stage-2 allowance in `tests/unit/test_public_api_compat.py`**

Replace the file with:

```python
"""The public provider surface must match the snapshot taken before the base-class migration.

A failure here means a consumer (Odoo module, CLI, server mode) may break. Fix the
code, not the snapshot — regenerating it is a reviewed API change.
"""

import json

import pytest

from tests.compat.snapshot import SNAPSHOT_PATH, public_surface

pytestmark = pytest.mark.unit

# `client` changes type (httpx2.Client -> openai.OpenAI) for providers moving off
# hand-written HTTP; it is an implementation detail, documented in the release notes.
_ALLOWED_DRIFT = {"client"}

# Stage 2 (no model IDs in source) changes these on purpose. Each stage-2 task
# adds what it changes; the snapshot task regenerates public_api.json and
# removes this mapping again.
_STAGE2_CHANGES: dict[str, set[str]] = {
    "providers.__all__": {"ModelNotSpecifiedError"},
    "OpenAIProvider": {"__init__", "DEFAULT_IMAGE_MODEL"},
    "OpenRouterProvider": {"__init__", "DEFAULT_IMAGE_MODEL"},
    "MammouthProvider": {"__init__"},
    "LocalLLMProvider": {"__init__"},
    "LangDockProvider": {"__init__"},
    "LangDockAgentManager": {"create_agent"},
    "IonosProvider": {"DEFAULT_MODEL"},
    "MeliousProvider": {"DEFAULT_MODEL"},
    "LiteLLMProvider": {"__init__", "DEFAULT_MODEL", "text_to_speech", "transcribe"},
    "PrivatemodeProvider": {"DEFAULT_MODEL"},
}


def _strip(surface: dict) -> dict:
    return {
        cls: {
            "members": {k: v for k, v in body["members"].items() if k not in _ALLOWED_DRIFT},
            "constants": body["constants"],
        }
        if isinstance(body, dict)
        else body
        for cls, body in surface.items()
    }


def test_public_surface_unchanged():
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    actual = public_surface()
    for cls, body in _strip(expected).items():
        allowed = _STAGE2_CHANGES.get(cls, set())
        if not isinstance(body, dict):
            assert (set(actual[cls]) ^ set(body)) <= allowed, cls
            continue
        live = _strip(actual)[cls]
        missing = set(body["members"]) - set(live["members"]) - allowed
        assert not missing, f"{cls} lost public members: {sorted(missing)}"
        changed = {
            k for k in body["members"] if k in live["members"] and live["members"][k] != body["members"][k]
        } - allowed
        assert not changed, f"{cls} changed signatures: {sorted(changed)}"
        lost_or_changed = {k for k, v in body["constants"].items() if live["constants"].get(k) != v} - allowed
        assert not lost_or_changed, f"{cls} constants lost or changed: {sorted(lost_or_changed)}"


def test_wire_server_serves_a_chat_completion(wire_server):
    from openai import OpenAI

    from tests.wire_server import Reply, chat_body

    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("hallo")))
    client = OpenAI(api_key="k", base_url=wire_server.base_url, max_retries=0)
    reply = client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
    assert reply.choices[0].message.content == "hallo"
    assert wire_server.requests[0].json["model"] == "m"
```

- [ ] **Step 14: Run the new tests and the compatibility test**

Run: `uv run pytest tests/unit/test_model_required_wire.py tests/unit/test_public_api_compat.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: all passed (55 + 2).

- [ ] **Step 15: Existing wire tests that change by design**

- `tests/unit/test_openai_compatible_wire.py:258`: `.text_to_speech("Hallo")` → `.text_to_speech("Hallo", model="tts-model", voice="voice-1")`; line 266: `.transcribe(("a.wav", b"RIFF0000", "audio/wav"))` → `.transcribe(("a.wav", b"RIFF0000", "audio/wav"), model="stt-model")`.
- `tests/unit/test_openai_wire.py::test_generate_image`: `generate_image("a cat")` → `generate_image("a cat", model="img-model")`; `== "gpt-image-1"` → `== "img-model"`. Line 117 (`test_generate_image_errors_by_status`): add `model="img-model"`.
- `tests/unit/test_openrouter_wire.py`: add `model="img-model"` to the `generate_image("a cat")` calls on lines 54, 62, 205, 227 and 305.
- `tests/unit/test_openrouter_wire.py::test_generate_image_defaults_and_custom_model` → xfail `stage 2: OpenRouter has no default image model; ported to test_model_required_wire.py::test_openrouter_image_model_from_constructor`.
- `tests/unit/test_openrouter_wire.py::test_defaults_and_site_info` → first add the port directly above it:

```python
def test_base_url_and_site_info():
    provider = OpenRouterProvider(api_key="sk-or-test", site_url="https://e.example", site_name="n")
    assert provider.provider_name == "openrouter"
    assert provider.default_model is None
    assert provider.base_url == OpenRouterProvider.DEFAULT_BASE_URL
    assert (provider.site_url, provider.site_name) == ("https://e.example", "n")
    assert provider.supports_image_generation is True
```

  then xfail the old one: `stage 2: no default model; ported to test_openrouter_wire.py::test_base_url_and_site_info`.

- [ ] **Step 16: Existing mocked tests — apply the triage rule**

Run: `uv run pytest tests/unit/ -q -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|passed|failed"`
Expected failures and their treatment:
- `tests/unit/test_ionos.py`, `test_melious.py`, `test_privatemode.py`: collection error on `DEFAULT_MODEL` in the module import block → remove `DEFAULT_MODEL,` from that import (rule 1); then xfail `test_default_model_fallback` and `test_uses_default_model` / `test_default_model_is_used` with `stage 2: no built-in default model`. Chat tests that call without a model get `model="test-model"`.
- `tests/unit/test_litellm.py`: remove `DEFAULT_MODEL, DEFAULT_STT_MODEL, DEFAULT_TTS_MODEL, DEFAULT_TTS_VOICE,` from the import block; xfail `test_default_model_fallback`, `test_uses_default_model`, `test_text_to_speech_returns_bytes`, `test_transcribe_returns_text` with `stage 2: no default chat/TTS/STT model or voice; ported to test_model_required_wire.py::test_tts_and_stt_use_constructor_settings`.
- `tests/unit/test_anthropic.py`, `test_openai.py`, `test_openai_image.py`, `test_openrouter_image.py`, `test_mammouth.py`, `test_local.py`, `test_factory.py`, `test_langdock*.py`: rule 1 for calls that only lack a model; rule 2 for assertions on `default_model`, `DEFAULT_MODEL` or `DEFAULT_IMAGE_MODEL` values.
Re-run until the line shows `0 failed`.

- [ ] **Step 17: Coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git checkout -- tests/reports/latest.md
git add src/eq_chatbot_core/providers/base.py src/eq_chatbot_core/providers/__init__.py \
  src/eq_chatbot_core/providers/openai_compatible.py src/eq_chatbot_core/providers/openai_provider.py \
  src/eq_chatbot_core/providers/openrouter_provider.py src/eq_chatbot_core/providers/mammouth_provider.py \
  src/eq_chatbot_core/providers/local_provider.py src/eq_chatbot_core/providers/ionos_provider.py \
  src/eq_chatbot_core/providers/melious_provider.py src/eq_chatbot_core/providers/privatemode_provider.py \
  src/eq_chatbot_core/providers/litellm_provider.py src/eq_chatbot_core/providers/anthropic_provider.py \
  src/eq_chatbot_core/providers/langdock_provider.py tests/unit/test_model_required_wire.py \
  tests/unit/test_public_api_compat.py tests/unit/test_openai_compatible_wire.py tests/unit/test_openai_wire.py \
  tests/unit/test_openrouter_wire.py
git add <every mocked test file edited in Step 16, by name>
git commit -m "[CHG] Modell ist Pflicht: ModelNotSpecifiedError statt eingebauter Standardmodelle

xfailed:
<file::test — reason, one per line>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GJzy9HGak7N5HG7StkSHWF"
```

Expected: coverage ≥ 83 %; ruff and mypy report no issues. (The two angle-bracket lines are filled from Step 16's actual edits — they are the record, not a placeholder for code.)

---
### Task 2: `param_learning` — Anthropic recognition, `reasoning_effort`, shared retry helper

**Files:**
- Modify: `src/eq_chatbot_core/providers/param_learning.py` (whole file)
- Modify: `src/eq_chatbot_core/providers/openai_compatible.py:223-249` (`_create`)
- Modify: `tests/wire_server.py` (three constants after `GATEWAY_TEMPERATURE_REJECTION_NO_PARAM`)
- Modify: `tests/conftest.py:26-29` (capture the real anthropic SDK), `:1675-1696` (`real_anthropic` fixture, `wire_server` depends on it)
- Modify: `tests/unit/test_param_learning.py` (append), `tests/unit/test_openai_compatible_wire.py` (append)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces (module `eq_chatbot_core.providers.param_learning`):
  - `LEARNABLE: tuple[str, ...] = ("temperature", "max_tokens", "reasoning_effort")`
  - `METADATA_KEYS: tuple[str, ...]` = `("supports_temperature", "default_temperature", "min_temperature", "max_temperature", "supports_reasoning", "supports_vision", "max_output_tokens", "default_max_tokens", "context_length")`
  - `rejected_parameter(error: BaseException) -> str | None` (unchanged signature; also reads Anthropic's envelope and "deprecated")
  - `adjust(params: dict[str, Any], parameter: str) -> bool` (also `extra_body["temperature"]`, `reasoning_effort`)
  - `apply(base_url: str, model: str, params: dict[str, Any], *, only: tuple[str, ...] = LEARNABLE) -> None`
  - `mark_unsupported(base_url: str, model: str, parameter: str) -> None`
  - `learn_from_rejection(error: BaseException, base_url: str, model: str, params: dict[str, Any], adjusted: set[str], *, provider: str, logger: logging.Logger, only: tuple[str, ...] = LEARNABLE) -> bool`
  - `seed_temperature_support(base_url: str, model: str, supported: bool) -> None` (unchanged)
  - `temperature_support(base_url: str, model: str) -> bool | None`
  - `model_metadata(base_url: str, model: str, **reported: Any) -> dict[str, Any]`
  - `clear() -> None`
- Produces (tests): `tests.wire_server.OPENAI_REASONING_EFFORT_REJECTION`, `ANTHROPIC_TEMPERATURE_DEPRECATED`, `ANTHROPIC_TEMPERATURE_RANGE`; fixture `real_anthropic`; `wire_server` now restores both real SDKs.

- [ ] **Step 1: Wire-server constants (append after `GATEWAY_TEMPERATURE_REJECTION_NO_PARAM` in `tests/wire_server.py`)**

```python
# Same envelope as OPENAI_MAX_TOKENS_REJECTION; modelled on it, not recorded.
OPENAI_REASONING_EFFORT_REJECTION: dict[str, Any] = {
    "error": {
        "message": "Unsupported parameter: 'reasoning_effort' is not supported with this model.",
        "type": "invalid_request_error",
        "param": "reasoning_effort",
        "code": "unsupported_parameter",
    }
}
# Anthropic Messages API, 07.10.2026: message text recorded live (temperature=0.7
# via extra_body on a Claude 5 model); envelope as Anthropic documents its errors.
ANTHROPIC_TEMPERATURE_DEPRECATED: dict[str, Any] = {
    "type": "error",
    "error": {"type": "invalid_request_error", "message": "`temperature` is deprecated for this model."},
}
# Anthropic, 07.10.2026 (temperature=1.5): out of range — must not be learned as unsupported.
ANTHROPIC_TEMPERATURE_RANGE: dict[str, Any] = {
    "type": "error",
    "error": {"type": "invalid_request_error", "message": "temperature: range: 0..1"},
}
```

- [ ] **Step 2: `real_anthropic` fixture in `tests/conftest.py`**

Directly above `import openai as _REAL_OPENAI` (line 29) — isort order, the comment block stays above both — add:

```python
import anthropic as _REAL_ANTHROPIC  # tests/unit/test_anthropic.py replaces it at import time
```

After the `real_openai` fixture add:

```python
@pytest.fixture
def real_anthropic(monkeypatch):
    """Make ``sys.modules["anthropic"]`` the real SDK for the duration of a test (see ``real_openai``)."""
    monkeypatch.setitem(sys.modules, "anthropic", _REAL_ANTHROPIC)
```

Change `def wire_server(real_openai):` to `def wire_server(real_openai, real_anthropic):` and its docstring's last line to `Depends on ``real_openai`` and ``real_anthropic``: wire tests always run the real SDKs.`

- [ ] **Step 3: Write the failing tests (append to `tests/unit/test_param_learning.py`)**

Extend the `from tests.wire_server import (...)` block with `ANTHROPIC_TEMPERATURE_DEPRECATED`, `ANTHROPIC_TEMPERATURE_RANGE`, `OPENAI_REASONING_EFFORT_REJECTION`, then append:

```python
def _anthropic_error_for(wire_server, body):
    from anthropic import Anthropic

    wire_server.expect("POST", "/v1/messages", Reply(400, body))
    client = Anthropic(api_key="k", base_url=wire_server.root_url, max_retries=0)
    with pytest.raises(Exception) as caught:
        client.messages.create(model="m", max_tokens=5, messages=[{"role": "user", "content": "x"}])
    return caught.value


def test_recognises_reasoning_effort_rejection(wire_server):
    error = _error_for(wire_server, 400, OPENAI_REASONING_EFFORT_REJECTION)
    assert param_learning.rejected_parameter(error) == "reasoning_effort"


def test_recognises_anthropic_deprecation_inside_its_envelope(wire_server):
    error = _anthropic_error_for(wire_server, ANTHROPIC_TEMPERATURE_DEPRECATED)
    assert param_learning.rejected_parameter(error) == "temperature"


def test_anthropic_range_error_is_not_a_rejection(wire_server):
    assert param_learning.rejected_parameter(_anthropic_error_for(wire_server, ANTHROPIC_TEMPERATURE_RANGE)) is None


def test_adjust_temperature_in_extra_body_without_touching_the_callers_dict():
    caller_extra = {"temperature": 0.7, "metadata": {"a": 1}}
    params = {"model": "m", "extra_body": caller_extra}
    assert param_learning.adjust(params, "temperature")
    assert params["extra_body"] == {"metadata": {"a": 1}}
    assert caller_extra == {"temperature": 0.7, "metadata": {"a": 1}}

    only_temperature = {"model": "m", "extra_body": {"temperature": 0.7}}
    assert param_learning.adjust(only_temperature, "temperature")
    assert only_temperature == {"model": "m"}


def test_reasoning_effort_dropped_and_remembered():
    params = {"model": "m", "reasoning_effort": "high"}
    assert param_learning.adjust(params, "reasoning_effort") and params == {"model": "m"}
    param_learning.mark_unsupported("http://a/v1", "m", "reasoning_effort")
    later = {"reasoning_effort": "low", "temperature": 0.5}
    param_learning.apply("http://a/v1", "m", later)
    assert later == {"temperature": 0.5}


def test_apply_only_touches_the_named_parameters():
    param_learning.mark_unsupported("http://a/v1", "m", "max_tokens")
    params = {"max_tokens": 10}
    param_learning.apply("http://a/v1", "m", params, only=("temperature",))
    assert params == {"max_tokens": 10}


def test_learn_from_rejection_retries_each_parameter_once(wire_server, caplog):
    import logging

    logger = logging.getLogger("tests.learning")
    error = _error_for(wire_server, 400, OPENAI_TEMPERATURE_REJECTION)
    params = {"model": "m", "temperature": 0.7}
    adjusted: set[str] = set()
    with caplog.at_level("INFO", logger="tests.learning"):
        assert param_learning.learn_from_rejection(error, "http://a/v1", "m", params, adjusted, provider="p", logger=logger)
    assert params == {"model": "m"} and adjusted == {"temperature"}
    assert "p: model m rejected 'temperature'" in caplog.text
    assert param_learning.temperature_support("http://a/v1", "m") is False
    # Same rejection again in this call: no second retry.
    assert not param_learning.learn_from_rejection(error, "http://a/v1", "m", params, adjusted, provider="p", logger=logger)


def test_learn_from_rejection_respects_only(wire_server):
    import logging

    error = _error_for(wire_server, 400, OPENAI_MAX_TOKENS_REJECTION)
    params = {"model": "m", "max_tokens": 10}
    learned = param_learning.learn_from_rejection(
        error, "http://a/v1", "m", params, set(), provider="p", logger=logging.getLogger("t"), only=("temperature",)
    )
    assert not learned and params == {"model": "m", "max_tokens": 10}


def test_temperature_support_and_model_metadata():
    assert param_learning.temperature_support("http://a/v1", "m") is None
    meta = param_learning.model_metadata("http://a/v1", "m", context_length=1000)
    assert meta == {**dict.fromkeys(param_learning.METADATA_KEYS), "context_length": 1000}
    param_learning.mark_unsupported("http://a/v1/", "m", "temperature")
    assert param_learning.temperature_support("http://a/v1", "m") is False
    reported_true = param_learning.model_metadata("http://a/v1", "m", supports_temperature=True)
    assert reported_true["supports_temperature"] is False  # learned beats reported
```

Append to `tests/unit/test_openai_compatible_wire.py` (add `OPENAI_REASONING_EFFORT_REJECTION` to its `tests.wire_server` import):

```python
def test_reasoning_effort_rejection_learned(wire_server):
    wire_server.expect(*CHAT, Reply(400, OPENAI_REASONING_EFFORT_REJECTION), Reply(body=chat_body()))
    provider = _provider(wire_server)
    provider.chat_completion(MSG, model="m", reasoning_effort="high")
    provider.chat_completion(MSG, model="m", reasoning_effort="high")
    first, second, third = _sent(wire_server)
    assert first["reasoning_effort"] == "high"
    assert "reasoning_effort" not in second and "reasoning_effort" not in third


def test_learning_is_logged_on_the_provider_module_logger(wire_server, caplog):
    """The live learning test listens on this logger name."""
    wire_server.expect(*CHAT, Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body()))
    with caplog.at_level("INFO", logger="eq_chatbot_core.providers.openai_compatible"):
        _provider(wire_server).chat_completion(MSG, model="m", temperature=0.7)
    assert "rejected 'temperature'" in caplog.text
```

- [ ] **Step 4: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_param_learning.py tests/unit/test_openai_compatible_wire.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: FAILED for every new test except `test_learning_is_logged_on_the_provider_module_logger` (already true) — e.g. `AttributeError: module ... has no attribute 'learn_from_rejection'`, `assert None == 'temperature'` for the Anthropic envelope.

- [ ] **Step 5: Rewrite `src/eq_chatbot_core/providers/param_learning.py`**

```python
"""Runtime-learned request-parameter support, per (endpoint, model).

Models differ in whether they accept ``temperature``, whether they want the
output limit as ``max_tokens`` or ``max_completion_tokens``, and whether they
take ``reasoning_effort`` — and the answer changes between model generations
faster than any list could follow. Providers send what the caller asked for,
recognise the provider's "unsupported parameter" rejection, retry once with the
parameter adjusted, and record the fact here so later requests are right the
first time.

The memory is process-wide (consumers such as the Odoo module build a provider
per request), thread-safe, holds three flags per key, and is never persisted.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

LEARNABLE: tuple[str, ...] = ("temperature", "max_tokens", "reasoning_effort")

# Keys of the capability/constraint part of a list_models() entry. A value the
# provider does not report is None (unknown) — never a guess from the name.
METADATA_KEYS: tuple[str, ...] = (
    "supports_temperature",
    "default_temperature",
    "min_temperature",
    "max_temperature",
    "supports_reasoning",
    "supports_vision",
    "max_output_tokens",
    "default_max_tokens",
    "context_length",
)

# Codes that mean "this model does not take this parameter" — as opposed to
# "invalid_value" (out of range), which must reach the caller unchanged.
_REJECTION_CODES = frozenset({"unsupported_parameter", "unsupported_value"})
# "deprecated" is Anthropic's wording ("`temperature` is deprecated for this model.").
_REJECTION_WORDS = ("unsupported", "not supported", "deprecated")
_QUOTED_PARAM = re.compile(r"""['"`](temperature|max_tokens|reasoning_effort)['"`]""")

_lock = threading.Lock()
_MEMORY: dict[str, set[tuple[str, str]]] = {parameter: set() for parameter in LEARNABLE}


def _key(base_url: str, model: str) -> tuple[str, str]:
    return base_url.rstrip("/"), model


def rejected_parameter(error: BaseException) -> str | None:
    """Return the learnable parameter a 400 response rejected, or ``None``.

    Structured form first: ``error.param`` names the parameter and ``code`` is an
    unsupported-* code (OpenAI). Fallback for bodies without ``param`` (gateways,
    Anthropic): the message quotes the parameter name and says "unsupported",
    "not supported" or "deprecated". Anthropic wraps its error in an envelope
    (``{"type": "error", "error": {...}}``), which is unwrapped first.
    """
    if getattr(error, "status_code", None) != 400:
        return None
    body = getattr(error, "body", None)
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        body = body["error"]
    if isinstance(body, dict):
        param = body.get("param")
        code = body.get("code")
        if param:
            return param if param in LEARNABLE and code in _REJECTION_CODES else None
        message = str(body.get("message") or "")
    else:
        message = str(error)
    lowered = message.lower()
    if not any(word in lowered for word in _REJECTION_WORDS):
        return None
    match = _QUOTED_PARAM.search(message)
    return match.group(1) if match else None


def adjust(params: dict[str, Any], parameter: str) -> bool:
    """Rewrite ``params`` to avoid ``parameter``. Returns False if nothing changed.

    ``temperature`` is removed wherever it is — top level (OpenAI wire) or inside
    ``extra_body`` (Anthropic SDK; the caller's dict is copied, not mutated).
    ``max_tokens`` becomes ``max_completion_tokens``. ``reasoning_effort`` is removed.
    """
    if parameter == "temperature":
        if "temperature" in params:
            del params["temperature"]
            return True
        extra_body = params.get("extra_body")
        if isinstance(extra_body, dict) and "temperature" in extra_body:
            remaining = {k: v for k, v in extra_body.items() if k != "temperature"}
            if remaining:
                params["extra_body"] = remaining
            else:
                del params["extra_body"]
            return True
        return False
    if parameter == "max_tokens" and "max_tokens" in params:
        params["max_completion_tokens"] = params.pop("max_tokens")
        return True
    if parameter == "reasoning_effort" and "reasoning_effort" in params:
        del params["reasoning_effort"]
        return True
    return False


def apply(base_url: str, model: str, params: dict[str, Any], *, only: tuple[str, ...] = LEARNABLE) -> None:
    """Apply what was learned for (base_url, model) to ``params`` in place, limited to ``only``."""
    key = _key(base_url, model)
    with _lock:
        learned = [parameter for parameter in only if key in _MEMORY.get(parameter, set())]
    for parameter in learned:
        adjust(params, parameter)


def mark_unsupported(base_url: str, model: str, parameter: str) -> None:
    memory = _MEMORY.get(parameter)
    if memory is None:
        return
    with _lock:
        memory.add(_key(base_url, model))


def learn_from_rejection(
    error: BaseException,
    base_url: str,
    model: str,
    params: dict[str, Any],
    adjusted: set[str],
    *,
    provider: str,
    logger: logging.Logger,
    only: tuple[str, ...] = LEARNABLE,
) -> bool:
    """Handle one failed request. True means ``params`` was adjusted: send it again.

    At most one retry per parameter and call (``adjusted`` collects them); a
    parameter rejected again after its adjustment propagates. Logged at INFO on
    the caller's logger so each provider module reports its own retries.
    """
    parameter = rejected_parameter(error)
    if parameter is None or parameter not in only or parameter in adjusted or not adjust(params, parameter):
        return False
    adjusted.add(parameter)
    mark_unsupported(base_url, model, parameter)
    logger.info(
        "%s: model %s rejected '%s'; retrying adjusted and remembering it for this endpoint",
        provider,
        model,
        parameter,
    )
    return True


def seed_temperature_support(base_url: str, model: str, supported: bool) -> None:
    """Record temperature support reported by the provider's own model list."""
    key = _key(base_url, model)
    with _lock:
        if supported:
            _MEMORY["temperature"].discard(key)
        else:
            _MEMORY["temperature"].add(key)


def temperature_support(base_url: str, model: str) -> bool | None:
    """``False`` once a temperature rejection was learned or seeded; otherwise ``None`` (unknown)."""
    with _lock:
        return False if _key(base_url, model) in _MEMORY["temperature"] else None


def model_metadata(base_url: str, model: str, **reported: Any) -> dict[str, Any]:
    """The ``METADATA_KEYS`` part of a ``list_models()`` entry.

    ``reported`` holds what the provider's API said; every other key is ``None``.
    A learned temperature rejection makes ``supports_temperature`` ``False``
    whatever the API reported.
    """
    meta: dict[str, Any] = dict.fromkeys(METADATA_KEYS)
    meta.update(reported)
    if temperature_support(base_url, model) is False:
        meta["supports_temperature"] = False
    return meta


def clear() -> None:
    with _lock:
        for memory in _MEMORY.values():
            memory.clear()
```

- [ ] **Step 6: `OpenAICompatibleProvider._create` uses the helper**

Replace the body of `_create` (lines 232-249, after its docstring) with:

```python
        model = params["model"]
        param_learning.apply(self._effective_base_url, model, params)
        adjusted: set[str] = set()
        while True:
            try:
                return self.client.chat.completions.create(**params)
            except Exception as error:
                if not param_learning.learn_from_rejection(
                    error,
                    self._effective_base_url,
                    model,
                    params,
                    adjusted,
                    provider=self.provider_name,
                    logger=_logger,
                ):
                    raise
```

In its docstring replace `A 400 naming ``temperature`` or ``max_tokens`` as unsupported` with `A 400 naming ``temperature``, ``max_tokens`` or ``reasoning_effort`` as unsupported`.

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/unit/test_param_learning.py tests/unit/test_openai_compatible_wire.py tests/unit/test_mammouth_wire.py tests/unit/test_openrouter_wire.py tests/unit/test_langdock_openai_wire.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: all passed (the xfails from Task 1 report as xfailed).

- [ ] **Step 8: Full suite, coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git checkout -- tests/reports/latest.md
git add src/eq_chatbot_core/providers/param_learning.py src/eq_chatbot_core/providers/openai_compatible.py \
  tests/wire_server.py tests/conftest.py tests/unit/test_param_learning.py tests/unit/test_openai_compatible_wire.py
git commit -m "[ADD] Parameter-Lernen: reasoning_effort, Anthropic-Fehlerform, gemeinsamer Retry-Helfer

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GJzy9HGak7N5HG7StkSHWF"
```

Expected: unit suite green (0 failed), coverage ≥ 83 %.

---

### Task 3: Anthropic and LangDock's `anthropic` backend learn `temperature`

**Files:**
- Create: `src/eq_chatbot_core/providers/anthropic_shared.py`
- Modify: `src/eq_chatbot_core/providers/anthropic_provider.py` (imports; `chat_completion` line 330; `stream_completion` line 430)
- Modify: `src/eq_chatbot_core/providers/langdock_provider.py` (imports; `_anthropic_chat_completion` line 711; `_anthropic_stream_completion` line 1116)
- Modify: `tests/wire_server.py` (append three builders)
- Create: `tests/unit/test_anthropic_wire.py`

**Interfaces:**
- Consumes: `param_learning.apply(..., only=)`, `param_learning.learn_from_rejection(...)`, `param_learning.temperature_support(...)` (Task 2); `real_anthropic` via `wire_server` (Task 2); `BaseLLMProvider.resolve_model` (Task 1).
- Produces (module `eq_chatbot_core.providers.anthropic_shared`):
  - `ANTHROPIC_LEARNABLE: tuple[str, ...] = ("temperature",)`
  - `create_message(client: Any, params: dict[str, Any], *, base_url: str, provider: str, logger: logging.Logger) -> Any`
  - `open_message_stream(stack: ExitStack, client: Any, params: dict[str, Any], *, base_url: str, provider: str, logger: logging.Logger) -> Any`
- Produces: `AnthropicProvider._endpoint() -> str` (learning key: `self.base_url or self.DEFAULT_BASE_URL`); LangDock's anthropic backend uses `self._get_backend_url()` as key.
- Produces (tests): `tests.wire_server.anthropic_message_body(text="ok", *, model="test-model", input_tokens=5, output_tokens=2) -> dict`, `anthropic_stream_events(pieces: list[str], *, model="test-model", input_tokens=5, output_tokens=2) -> list[str]`, `anthropic_models_body(models: list[dict[str, Any]]) -> dict`.

- [ ] **Step 1: Messages-API builders (append to `tests/wire_server.py`)**

```python
def anthropic_message_body(
    text: str = "ok", *, model: str = "test-model", input_tokens: int = 5, output_tokens: int = 2
) -> dict[str, Any]:
    """A Messages API response (POST /v1/messages)."""
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


def anthropic_stream_events(
    pieces: list[str], *, model: str = "test-model", input_tokens: int = 5, output_tokens: int = 2
) -> list[str]:
    """Messages API SSE frames (``event:`` + ``data:`` lines) for a text answer.

    The server appends ``data: [DONE]``; the anthropic SDK ignores that unnamed event.
    """

    def frame(kind: str, data: dict[str, Any]) -> str:
        return f"event: {kind}\ndata: {json.dumps({'type': kind, **data})}"

    message = {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": {"input_tokens": input_tokens, "output_tokens": 0},
    }
    events = [
        frame("message_start", {"message": message}),
        frame("content_block_start", {"index": 0, "content_block": {"type": "text", "text": ""}}),
    ]
    events += [frame("content_block_delta", {"index": 0, "delta": {"type": "text_delta", "text": p}}) for p in pieces]
    events += [
        frame("content_block_stop", {"index": 0}),
        frame(
            "message_delta",
            {"delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": output_tokens}},
        ),
        frame("message_stop", {}),
    ]
    return events


def anthropic_models_body(models: list[dict[str, Any]]) -> dict[str, Any]:
    """A Models API page (GET /v1/models); each entry needs at least ``id``."""
    data = [
        {"type": "model", "display_name": m["id"], "created_at": "2026-01-01T00:00:00Z", **m} for m in models
    ]
    return {
        "data": data,
        "has_more": False,
        "first_id": data[0]["id"] if data else None,
        "last_id": data[-1]["id"] if data else None,
    }
```

- [ ] **Step 2: Write the failing tests — `tests/unit/test_anthropic_wire.py`**

```python
"""AnthropicProvider and LangDock's anthropic backend against the wire server.

The real anthropic SDK talks the Messages API shape (POST /v1/messages, error body
{"type": "error", "error": {...}}) to the local server; only the remote is simulated.
"""

import pytest

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.langdock_provider import LangDockProvider
from tests.wire_server import (
    ANTHROPIC_TEMPERATURE_DEPRECATED,
    ANTHROPIC_TEMPERATURE_RANGE,
    Reply,
    anthropic_message_body,
    anthropic_stream_events,
)

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]


def _anthropic(wire_server):
    provider = AnthropicProvider(api_key="sk-ant-test", base_url=wire_server.root_url, max_retries=0)
    return provider, "/v1/messages", wire_server.root_url


def _langdock(wire_server):
    provider = LangDockProvider(api_key="ld-test", base_url=wire_server.root_url, max_retries=0, backend="anthropic")
    return provider, "/anthropic/eu/v1/messages", provider._get_backend_url()


BOTH = [_anthropic, _langdock]
IDS = ["anthropic", "langdock-anthropic"]


def _sent(wire_server, path):
    return [r.json for r in wire_server.requests if r.path == path]


@pytest.mark.parametrize("make", BOTH, ids=IDS)
def test_deprecated_temperature_is_dropped_and_learned(wire_server, make):
    provider, path, _ = make(wire_server)
    wire_server.expect(
        "POST", path, Reply(400, ANTHROPIC_TEMPERATURE_DEPRECATED), Reply(body=anthropic_message_body("hallo"))
    )
    assert provider.chat_completion(MSG, model="m", temperature=0.7).content == "hallo"
    assert provider.chat_completion(MSG, model="m", temperature=0.7).content == "hallo"
    first, second, third = _sent(wire_server, path)
    assert first["temperature"] == 0.7
    assert "temperature" not in second
    assert "temperature" not in third  # learned: the second call sends no retry


@pytest.mark.parametrize("make", BOTH, ids=IDS)
def test_stream_learns_before_the_first_chunk(wire_server, make):
    provider, path, _ = make(wire_server)
    wire_server.expect(
        "POST",
        path,
        Reply(400, ANTHROPIC_TEMPERATURE_DEPRECATED),
        Reply(sse=anthropic_stream_events(["hal", "lo"])),
    )
    chunks = list(provider.stream_completion(MSG, model="m", temperature=0.7))
    assert "".join(c.content for c in chunks) == "hallo"  # nothing duplicated
    assert chunks[-1].is_final and (chunks[-1].input_tokens, chunks[-1].output_tokens) == (5, 2)
    assert "temperature" not in _sent(wire_server, path)[1]


@pytest.mark.parametrize("make", BOTH, ids=IDS)
def test_range_error_is_not_learned(wire_server, make):
    """Review focus 3: '0..1' means the value is wrong, not that the model takes none."""
    provider, path, key = make(wire_server)
    wire_server.expect("POST", path, Reply(400, ANTHROPIC_TEMPERATURE_RANGE))
    with pytest.raises(ProviderError):
        provider.chat_completion(MSG, model="m", temperature=0.9)
    assert len(_sent(wire_server, path)) == 1
    assert param_learning.temperature_support(key, "m") is None


@pytest.mark.parametrize("make", BOTH, ids=IDS)
def test_learning_shared_across_instances(wire_server, make):
    provider, path, _ = make(wire_server)
    wire_server.expect("POST", path, Reply(400, ANTHROPIC_TEMPERATURE_DEPRECATED), Reply(body=anthropic_message_body()))
    provider.chat_completion(MSG, model="m", temperature=0.7)
    again, _, _ = make(wire_server)
    again.chat_completion(MSG, model="m", temperature=0.7)
    sent = _sent(wire_server, path)
    assert len(sent) == 3 and "temperature" not in sent[-1]


@pytest.mark.parametrize("make", BOTH, ids=IDS)
def test_temperature_travels_in_the_body_and_max_tokens_is_kept(wire_server, make):
    provider, path, _ = make(wire_server)
    wire_server.expect("POST", path, Reply(body=anthropic_message_body()))
    provider.chat_completion(MSG, model="m", temperature=0.4, max_tokens=50)
    sent = _sent(wire_server, path)[0]
    assert sent["temperature"] == 0.4 and sent["max_tokens"] == 50
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_anthropic_wire.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: `test_deprecated_temperature_is_dropped_and_learned`, `test_stream_learns_before_the_first_chunk` and `test_learning_shared_across_instances` FAIL (a `ProviderError` from the 400); the range and transport tests pass.

- [ ] **Step 4: Create `src/eq_chatbot_core/providers/anthropic_shared.py`**

```python
"""Helpers shared by AnthropicProvider and LangDock's ``anthropic`` backend.

Whether a model takes ``temperature`` is learned from the Messages API's own
rejection (newer models answer "`temperature` is deprecated for this model.")
and remembered per endpoint and model in ``param_learning``. ``max_tokens`` is
mandatory in this API and is never learned here.
"""

from __future__ import annotations

import logging
from contextlib import ExitStack
from typing import Any

from eq_chatbot_core.providers import param_learning

ANTHROPIC_LEARNABLE: tuple[str, ...] = ("temperature",)


def create_message(
    client: Any, params: dict[str, Any], *, base_url: str, provider: str, logger: logging.Logger
) -> Any:
    """``client.messages.create(**params)``, retried once without a rejected temperature."""
    model = params["model"]
    param_learning.apply(base_url, model, params, only=ANTHROPIC_LEARNABLE)
    adjusted: set[str] = set()
    while True:
        try:
            return client.messages.create(**params)
        except Exception as error:
            if not param_learning.learn_from_rejection(
                error, base_url, model, params, adjusted, provider=provider, logger=logger, only=ANTHROPIC_LEARNABLE
            ):
                raise


def open_message_stream(
    stack: ExitStack,
    client: Any,
    params: dict[str, Any],
    *,
    base_url: str,
    provider: str,
    logger: logging.Logger,
) -> Any:
    """Enter ``client.messages.stream(**params)`` on ``stack``, with the same retry rule.

    The SDK sends the request when the stream manager is entered, before any
    event is read — so a retry never duplicates output already yielded.
    """
    model = params["model"]
    param_learning.apply(base_url, model, params, only=ANTHROPIC_LEARNABLE)
    adjusted: set[str] = set()
    while True:
        try:
            return stack.enter_context(client.messages.stream(**params))
        except Exception as error:
            if not param_learning.learn_from_rejection(
                error, base_url, model, params, adjusted, provider=provider, logger=logger, only=ANTHROPIC_LEARNABLE
            ):
                raise
```

- [ ] **Step 5: Wire `AnthropicProvider`**

Imports: add `from contextlib import ExitStack` and `from eq_chatbot_core.providers.anthropic_shared import create_message, open_message_stream`.
Add after `_get_retry_delay`:

```python
    def _endpoint(self) -> str:
        """Endpoint key for parameter learning."""
        return self.base_url or self.DEFAULT_BASE_URL
```

In `chat_completion` replace `response = self.client.messages.create(**params)` with:

```python
                response = create_message(
                    self.client, params, base_url=self._endpoint(), provider=self.provider_name, logger=logger
                )
```

In `stream_completion` replace the line `with self.client.messages.stream(**params) as stream:` with the two lines

```python
                with ExitStack() as stack:
                    stream = open_message_stream(
                        stack, self.client, params, base_url=self._endpoint(), provider=self.provider_name, logger=logger
                    )
```

and keep the `for event in stream:` block one level inside this `with` (its indentation does not change). The overload retry loop around both calls stays as is: a learned retry happens inside the helper and does not use up an overload attempt.

- [ ] **Step 6: Wire LangDock's anthropic backend**

Imports in `langdock_provider.py`: add `from contextlib import ExitStack` and `from eq_chatbot_core.providers.anthropic_shared import create_message, open_message_stream`.
In `_anthropic_chat_completion` replace `response = self.anthropic_client.messages.create(**params)` with:

```python
            response = create_message(
                self.anthropic_client, params, base_url=self._get_backend_url(), provider="langdock", logger=_logger
            )
```

In `_anthropic_stream_completion` replace `with self.anthropic_client.messages.stream(**params) as stream:` with:

```python
            with ExitStack() as stack:
                stream = open_message_stream(
                    stack, self.anthropic_client, params, base_url=self._get_backend_url(), provider="langdock",
                    logger=_logger,
                )
```

keeping the `for event in stream:` block inside it at unchanged indentation.

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/unit/test_anthropic_wire.py tests/unit/test_anthropic.py tests/unit/test_langdock.py tests/unit/test_langdock_backends.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: `test_anthropic_wire.py` all passed (10); the mocked Anthropic/LangDock modules show no new failures (their mocked `messages.create` / `messages.stream` are still called with the same kwargs; `ExitStack.enter_context` accepts a MagicMock context manager like `with` does). If one does fail, apply the triage rule.

- [ ] **Step 8: Full suite, coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git checkout -- tests/reports/latest.md
git add src/eq_chatbot_core/providers/anthropic_shared.py src/eq_chatbot_core/providers/anthropic_provider.py \
  src/eq_chatbot_core/providers/langdock_provider.py tests/wire_server.py tests/unit/test_anthropic_wire.py
git commit -m "[ADD] Anthropic und LangDock-Anthropic lernen, ob ein Modell temperature annimmt

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GJzy9HGak7N5HG7StkSHWF"
```

---
### Task 4: `list_models()` — every listed model, provider data or learned facts, else `None`

**Files:**
- Modify: `src/eq_chatbot_core/providers/anthropic_shared.py` (append `capability_supported`)
- Modify: `src/eq_chatbot_core/providers/openai_provider.py:75-180` (`CHAT_MODEL_PREFIXES`, `MODEL_CONTEXT_LENGTHS`, `_get_model_constraints`, `list_models`; import of `get_temperature_constraints`)
- Modify: `src/eq_chatbot_core/providers/anthropic_provider.py:535-605` (`_get_model_constraints`, `list_models`; import of `get_temperature_constraints`)
- Modify: `src/eq_chatbot_core/providers/langdock_provider.py:205-230` (`MODEL_CONTEXT_LENGTHS`), `:1382-1448` (`_get_model_constraints`), `:1482-1602` (`_list_openai_models`, `_list_anthropic_models`, `_get_known_anthropic_models`, `_list_google_models`), `:1616-1639` (`_list_agent_models`); import of `get_temperature_constraints`
- Modify: `src/eq_chatbot_core/providers/mammouth_provider.py:73-110` (`list_models`)
- Modify: `src/eq_chatbot_core/providers/openrouter_provider.py:94-123, 202-262` (`list_models`, `_get_model_constraints`)
- Modify: `src/eq_chatbot_core/providers/local_provider.py:137-160` (`list_models`)
- Modify: `tests/unit/test_public_api_compat.py` (`_STAGE2_CHANGES`)
- Create: `tests/unit/test_list_models_wire.py`

**Interfaces:**
- Consumes: `param_learning.model_metadata`, `param_learning.temperature_support`, `param_learning.seed_temperature_support`, `param_learning.METADATA_KEYS` (Task 2); `tests.wire_server.anthropic_models_body` (Task 3).
- Produces: `anthropic_shared.capability_supported(capabilities: Any, name: str) -> bool | None`.
- Key sets per provider stay exactly as before (OpenAI/Anthropic/LangDock: base keys + `METADATA_KEYS`; Mammouth, OpenRouter, Local: their own sets); only values change.
- Removed: `OpenAIProvider.CHAT_MODEL_PREFIXES`, `OpenAIProvider.MODEL_CONTEXT_LENGTHS`, `OpenAIProvider._get_model_constraints`, `AnthropicProvider._get_model_constraints`, `LangDockProvider.MODEL_CONTEXT_LENGTHS`, `LangDockProvider._get_model_constraints`, `LangDockProvider._get_known_anthropic_models`.

- [ ] **Step 1: Write the failing tests — `tests/unit/test_list_models_wire.py`**

```python
"""list_models(): every model the provider lists; provider data or learned facts, else None."""

import pytest

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.langdock_provider import LangDockProvider
from eq_chatbot_core.providers.local_provider import LocalLLMProvider
from eq_chatbot_core.providers.mammouth_provider import MammouthProvider
from eq_chatbot_core.providers.openai_provider import OpenAIProvider
from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider
from tests.wire_server import (
    OPENAI_TEMPERATURE_REJECTION,
    Reply,
    anthropic_models_body,
    chat_body,
    models_body,
)

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]
UNKNOWN = dict.fromkeys(param_learning.METADATA_KEYS)


def _unknown_part(entry):
    return {k: entry[k] for k in UNKNOWN}


def test_openai_lists_everything_unfiltered_with_unknown_metadata(wire_server):
    wire_server.expect("GET", "/v1/models", Reply(body=models_body(["chat-a", "embed-b", "brand-new-family-1"])))
    models = OpenAIProvider(api_key="k", base_url=wire_server.base_url, max_retries=0).list_models()
    assert [m["id"] for m in models] == ["brand-new-family-1", "chat-a", "embed-b"]
    for m in models:
        assert _unknown_part(m) == UNKNOWN
        assert (m["name"], m["provider"], m["owned_by"], m["created"]) == (m["id"], "openai", "test", 0)


def test_openai_learned_rejection_shows_in_the_list(wire_server):
    provider = OpenAIProvider(api_key="k", base_url=wire_server.base_url, max_retries=0)
    wire_server.expect(
        "POST", "/v1/chat/completions", Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body())
    )
    provider.chat_completion(MSG, model="picky", temperature=0.7)
    wire_server.expect("GET", "/v1/models", Reply(body=models_body(["picky", "other"])))
    by_id = {m["id"]: m for m in provider.list_models()}
    assert by_id["picky"]["supports_temperature"] is False
    assert by_id["other"]["supports_temperature"] is None


def test_langdock_openai_lists_everything(wire_server):
    wire_server.expect("GET", "/openai/eu/v1/models", Reply(body=models_body(["chat-like", "embedding-like"])))
    models = LangDockProvider(api_key="k", base_url=wire_server.root_url, max_retries=0).list_models()
    assert [m["id"] for m in models] == ["chat-like", "embedding-like"]
    for m in models:
        assert (m["backend"], m["region"], m["provider"]) == ("openai", "eu", "langdock")
        assert _unknown_part(m) == UNKNOWN


@pytest.mark.parametrize(
    ("make", "path"),
    [
        (lambda ws: AnthropicProvider(api_key="k", base_url=ws.root_url, max_retries=0), "/v1/models"),
        (
            lambda ws: LangDockProvider(api_key="k", base_url=ws.root_url, max_retries=0, backend="anthropic"),
            "/anthropic/eu/v1/models",
        ),
    ],
    ids=["anthropic", "langdock-anthropic"],
)
def test_anthropic_metadata_comes_from_the_models_api(wire_server, make, path):
    body = anthropic_models_body(
        [
            {
                "id": "reported",
                "display_name": "Reported",
                "max_input_tokens": 1000,
                "max_tokens": 200,
                "capabilities": {"image_input": {"supported": True}, "thinking": {"supported": False, "types": {}}},
            },
            {"id": "silent"},
        ]
    )
    wire_server.expect("GET", path, Reply(body=body))
    by_id = {m["id"]: m for m in make(wire_server).list_models()}
    reported = by_id["reported"]
    assert reported["name"] == "Reported"
    assert (reported["context_length"], reported["max_output_tokens"]) == (1000, 200)
    assert reported["supports_vision"] is True and reported["supports_reasoning"] is False
    assert reported["min_temperature"] is None and reported["supports_temperature"] is None
    assert _unknown_part(by_id["silent"]) == UNKNOWN


def test_langdock_google_reports_what_gemini_reports(wire_server):
    body = {
        "models": [
            {
                "name": "models/g-1",
                "inputTokenLimit": 1000,
                "outputTokenLimit": 100,
                "temperature": 1.0,
                "maxTemperature": 2.0,
                "thinking": True,
            },
            {"name": "models/g-2"},
        ]
    }
    wire_server.expect("GET", "/google/eu/v1beta/models", Reply(body=body))
    provider = LangDockProvider(api_key="k", base_url=wire_server.root_url, max_retries=0, backend="google")
    by_id = {m["id"]: m for m in provider.list_models()}
    g1 = by_id["g-1"]
    assert (g1["context_length"], g1["max_output_tokens"]) == (1000, 100)
    assert (g1["default_temperature"], g1["max_temperature"], g1["supports_reasoning"]) == (1.0, 2.0, True)
    assert g1["min_temperature"] is None and g1["supports_vision"] is None
    assert _unknown_part(by_id["g-2"]) == UNKNOWN


def _mammouth(wire_server):
    provider = MammouthProvider(api_key="k", base_url=wire_server.base_url, max_retries=0)
    provider.MODELS_URL = f"{wire_server.root_url}/public/models"
    return provider


def test_mammouth_reports_its_limits_and_nothing_else(wire_server):
    data = [{"id": "b-model", "max_input_tokens": 1000, "max_output_tokens": 100}, {"id": "a-model"}]
    wire_server.expect("GET", "/public/models", Reply(body={"data": data}))
    models = _mammouth(wire_server).list_models()
    assert [m["id"] for m in models] == ["a-model", "b-model"]
    assert models[1] == {
        "id": "b-model",
        "name": "b-model",
        "provider": "mammouth",
        "context_length": 1000,
        "max_output_tokens": 100,
        "supports_temperature": None,
        "min_temperature": None,
        "max_temperature": None,
        "supports_reasoning": None,
        "supports_streaming": True,
    }


def test_openrouter_metadata_from_the_api(wire_server):
    body = {
        "data": [
            {
                "id": "v/full",
                "name": "Full",
                "description": "d",
                "context_length": 1000,
                "created": 5,
                "supported_parameters": ["temperature", "tools", "reasoning"],
                "default_parameters": {"temperature": 0.6},
                "input_modalities": ["text", "image"],
                "output_modalities": ["text"],
                "top_provider": {"max_completion_tokens": 300},
            },
            {"id": "v/bare", "supported_parameters": None, "input_modalities": None},
        ]
    }
    wire_server.expect("GET", "/v1/models", Reply(body=body))
    provider = OpenRouterProvider(api_key="k", base_url=wire_server.base_url, max_retries=0)
    by_id = {m["id"]: m for m in provider.list_models()}
    full, bare = by_id["v/full"], by_id["v/bare"]
    assert (full["name"], full["description"], full["provider"], full["created"]) == ("Full", "d", "openrouter", 5)
    flags = (full["supports_temperature"], full["supports_tools"], full["supports_reasoning"], full["supports_vision"])
    assert flags == (True, True, True, True)
    assert (full["default_temperature"], full["min_temperature"], full["max_temperature"]) == (0.6, None, None)
    assert (full["max_output_tokens"], full["default_max_tokens"], full["context_length"]) == (300, None, 1000)
    for key in (
        "supports_temperature",
        "supports_tools",
        "supports_reasoning",
        "supports_vision",
        "max_output_tokens",
        "input_modalities",
        "default_temperature",
    ):
        assert bare[key] is None, key


def test_openrouter_learned_rejection_beats_the_list(wire_server):
    provider = OpenRouterProvider(api_key="k", base_url=wire_server.base_url, max_retries=0)
    wire_server.expect(
        "POST", "/v1/chat/completions", Reply(400, OPENAI_TEMPERATURE_REJECTION), Reply(body=chat_body())
    )
    provider.chat_completion(MSG, model="v/picky", temperature=0.5)
    wire_server.expect(
        "GET", "/v1/models", Reply(body={"data": [{"id": "v/picky", "supported_parameters": ["temperature"]}]})
    )
    (model,) = provider.list_models()
    assert model["supports_temperature"] is False
    provider.chat_completion(MSG, model="v/picky", temperature=0.5)
    assert "temperature" not in wire_server.requests[-1].json  # the list did not undo it


def test_local_does_not_guess_tools_or_vision(wire_server):
    wire_server.expect("GET", "/v1/models", Reply(body=models_body(["m"])))
    (model,) = LocalLLMProvider(base_url=wire_server.base_url, max_retries=0).list_models()
    assert model == {
        "id": "m",
        "name": "m",
        "provider": "local",
        "context_length": None,
        "supports_streaming": True,
        "supports_tools": None,
        "supports_vision": None,
        "owned_by": "test",
        "created": 0,
    }
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_list_models_wire.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: FAILED for every test (filtered ids, guessed ranges, `False` instead of `None`), e.g. `assert ['chat-a'] == ['brand-new-family-1', 'chat-a', 'embed-b']`.

- [ ] **Step 3: `anthropic_shared.capability_supported` (append to `src/eq_chatbot_core/providers/anthropic_shared.py`)**

```python
def capability_supported(capabilities: Any, name: str) -> bool | None:
    """``capabilities.<name>.supported`` from the Models API, or ``None`` if not reported."""
    value = getattr(getattr(capabilities, name, None), "supported", None)
    return value if isinstance(value, bool) else None
```

- [ ] **Step 4: OpenAI**

Delete `CHAT_MODEL_PREFIXES` (with its comment), `MODEL_CONTEXT_LENGTHS` (with its comment) and `_get_model_constraints`. Replace `list_models` with:

```python
    def list_models(self) -> list[dict[str, Any]]:
        """
        List every model the OpenAI API reports.

        Nothing is filtered by name, so embedding, audio and image models appear
        too. Metadata the API does not report is ``None`` (unknown);
        ``supports_temperature`` is ``False`` once a rejection was learned.
        """
        try:
            models = self.client.models.list()
            result = [
                {
                    "id": model.id,
                    "name": model.id,
                    "created": getattr(model, "created", None),
                    "owned_by": getattr(model, "owned_by", None),
                    "provider": self.provider_name,
                    **param_learning.model_metadata(self._effective_base_url, model.id),
                }
                for model in models.data
            ]
            result.sort(key=lambda m: m["id"])
            return result

        except Exception as e:
            raise self._handle_error(e) from e
```

Imports: drop `from eq_chatbot_core.providers.temperature_constraints import get_temperature_constraints`; add `from eq_chatbot_core.providers import param_learning`.

- [ ] **Step 5: Anthropic**

Delete `_get_model_constraints` and the `get_temperature_constraints` import (keep `apply_anthropic_temperature`). Add `from eq_chatbot_core.providers import param_learning` and extend the `anthropic_shared` import with `capability_supported`. Replace `list_models` with:

```python
    def list_models(self) -> list[dict[str, Any]]:
        """
        List the models the Anthropic Models API reports, with the limits and
        capabilities it reports; everything else is ``None`` (unknown).

        ``supports_temperature`` is ``False`` once a rejection was learned.
        """
        try:
            models_response = self.client.models.list(limit=100)

            chat_models = []
            for model in models_response.data:
                capabilities = getattr(model, "capabilities", None)
                chat_models.append(
                    {
                        "id": model.id,
                        "name": getattr(model, "display_name", None) or model.id,
                        "created": getattr(model, "created_at", None),
                        "provider": self.provider_name,
                        **param_learning.model_metadata(
                            self._endpoint(),
                            model.id,
                            context_length=getattr(model, "max_input_tokens", None),
                            max_output_tokens=getattr(model, "max_tokens", None),
                            supports_vision=capability_supported(capabilities, "image_input"),
                            supports_reasoning=capability_supported(capabilities, "thinking"),
                        ),
                    }
                )

            # Newest first
            chat_models.sort(key=lambda m: m.get("created") or "", reverse=True)
            return chat_models

        except Exception as e:
            raise self._handle_error(e) from e
```

- [ ] **Step 6: LangDock**

Delete `MODEL_CONTEXT_LENGTHS` (lines 205-230), `_get_model_constraints` (lines 1382-1448) and `_get_known_anthropic_models` (lines 1546-1567). Imports: drop `get_temperature_constraints` from the `temperature_constraints` import (keep `apply_anthropic_temperature`, `clamp_temperature`); add `from eq_chatbot_core.providers import param_learning`; extend the `anthropic_shared` import with `capability_supported`. Replace the four listing helpers:

```python
    def _list_openai_models(self) -> list[dict[str, Any]]:
        """Every model LangDock's OpenAI endpoint lists for this workspace."""
        models = self.openai_client.models.list()
        base = self._get_backend_url()
        result = [
            {
                "id": model.id,
                "name": model.id,
                "created": getattr(model, "created", None),
                "owned_by": getattr(model, "owned_by", "langdock"),
                "provider": self.provider_name,
                "backend": self.backend,
                "region": self.region,
                **param_learning.model_metadata(base, model.id),
            }
            for model in models.data
        ]
        result.sort(key=lambda m: m["id"])
        return result

    def _list_anthropic_models(self) -> list[dict[str, Any]]:
        """Anthropic models LangDock lists, with what the Models API reports."""
        base = self._get_backend_url()
        try:
            models_response = self.anthropic_client.models.list(limit=100)
            result = []
            for model in models_response.data:
                capabilities = getattr(model, "capabilities", None)
                result.append(
                    {
                        "id": model.id,
                        "name": getattr(model, "display_name", None) or model.id,
                        "created": getattr(model, "created_at", None),
                        "provider": self.provider_name,
                        "backend": self.backend,
                        "region": self.region,
                        **param_learning.model_metadata(
                            base,
                            model.id,
                            context_length=getattr(model, "max_input_tokens", None),
                            max_output_tokens=getattr(model, "max_tokens", None),
                            supports_vision=capability_supported(capabilities, "image_input"),
                            supports_reasoning=capability_supported(capabilities, "thinking"),
                        ),
                    }
                )
            result.sort(key=lambda m: m.get("created") or "", reverse=True)
            return result
        except (AttributeError, KeyError, TypeError) as e:
            # No static fallback list: an unknown model list is an empty one.
            _logger.warning("Anthropic model listing not supported by this endpoint: %s", e)
            return []
```

`_list_google_models` keeps its docstring, its request and the `model_id` / `if not model_id: continue` lines; replace the line `constraints = self._get_model_constraints(model_id)` and the `result.append({...})` call after it with:

```python
            thinking = model.get("thinking")
            result.append(
                {
                    "id": model_id,
                    "name": model_id.replace("-", " ").title(),
                    "provider": self.provider_name,
                    "backend": self.backend,
                    "region": self.region,
                    **param_learning.model_metadata(
                        self._get_backend_url(),
                        model_id,
                        context_length=model.get("inputTokenLimit"),
                        max_output_tokens=model.get("outputTokenLimit"),
                        default_temperature=model.get("temperature"),
                        max_temperature=model.get("maxTemperature"),
                        supports_reasoning=thinking if isinstance(thinking, bool) else None,
                    ),
                }
            )
```

`_list_agent_models`: replace `constraints = self._get_model_constraints(model_id)` and `**constraints,` with `**param_learning.model_metadata(self._get_backend_url(), model_id),`.

- [ ] **Step 7: Mammouth, OpenRouter, Local**

Mammouth `list_models` loop body becomes (add `from eq_chatbot_core.providers import param_learning`):

```python
        models = []
        for model_data in model_list:
            model_id = model_data.get("id", model_data.get("model", ""))
            if not model_id:
                continue
            models.append(
                {
                    "id": model_id,
                    "name": model_data.get("name", model_id),
                    "provider": self.provider_name,
                    "context_length": model_data.get("max_input_tokens"),
                    "max_output_tokens": model_data.get("max_output_tokens"),
                    # Mammouth's list says nothing about temperature or reasoning.
                    "supports_temperature": param_learning.temperature_support(self._effective_base_url, model_id),
                    "min_temperature": None,
                    "max_temperature": None,
                    "supports_reasoning": None,
                    "supports_streaming": True,
                }
            )

        models.sort(key=lambda m: m["id"])
        return models
```

OpenRouter: replace `list_models` and `_get_model_constraints`:

```python
    def list_models(self) -> list[dict[str, Any]]:
        """List models with the metadata OpenRouter reports; seeds parameter learning.

        A model whose ``supported_parameters`` omit ``temperature`` is seeded as
        "temperature unsupported". A learned rejection always wins over the list:
        ``supports_temperature`` is then ``False`` whatever the list claims.
        Values OpenRouter does not report are ``None``.
        """
        try:
            data = self.client.get("/models", cast_to=object)
        except Exception as e:
            raise self._handle_error(e) from e

        models = []
        for model_data in data.get("data", []) if isinstance(data, dict) else []:
            model_id = model_data.get("id", "")
            constraints = self._get_model_constraints(model_data)
            if constraints["supports_temperature"] is False:
                param_learning.seed_temperature_support(self._effective_base_url, model_id, False)
            if param_learning.temperature_support(self._effective_base_url, model_id) is False:
                constraints["supports_temperature"] = False
            models.append(
                {
                    "id": model_id,
                    "name": model_data.get("name", model_id),
                    "description": model_data.get("description", ""),
                    "context_length": model_data.get("context_length"),
                    "provider": self.provider_name,
                    "created": model_data.get("created"),
                    **constraints,
                }
            )
        models.sort(key=lambda m: m["id"])
        return models
```

```python
    def _get_model_constraints(self, model_data: dict[str, Any]) -> dict[str, Any]:
        """Metadata from OpenRouter's model entry; ``None`` where it says nothing.

        OpenRouter may send these fields as JSON null rather than omitting them,
        so ``or`` treats null and absent alike.
        """
        supported = model_data.get("supported_parameters") or None
        defaults = model_data.get("default_parameters") or {}
        input_modalities = model_data.get("input_modalities") or None
        output_modalities = model_data.get("output_modalities") or None
        max_output = (model_data.get("top_provider") or {}).get("max_completion_tokens") or model_data.get(
            "max_tokens"
        )
        return {
            "supports_temperature": ("temperature" in supported) if supported else None,
            "default_temperature": defaults.get("temperature"),
            "min_temperature": defaults.get("min_temperature"),
            "max_temperature": defaults.get("max_temperature"),
            "supports_reasoning": ("reasoning" in supported) if supported else None,
            "supports_vision": ("image" in input_modalities) if input_modalities else None,
            "supports_tools": ("tools" in supported or "tool_choice" in supported) if supported else None,
            "supports_streaming": True,  # OpenRouter streams every model (provider-level)
            "max_output_tokens": max_output or None,
            "default_max_tokens": None,
            "input_modalities": input_modalities,
            "output_modalities": output_modalities,
        }
```

Local `list_models`: `"supports_tools": False,  # Most local models ...` → `"supports_tools": None,` and `"supports_vision": False,  # ...` → `"supports_vision": None,` (comments removed; the server does not report either).

- [ ] **Step 8: Stage-2 allowance**

In `tests/unit/test_public_api_compat.py` extend `_STAGE2_CHANGES`: `"OpenAIProvider"` gets `"CHAT_MODEL_PREFIXES"`, `"MODEL_CONTEXT_LENGTHS"`; `"LangDockProvider"` gets `"MODEL_CONTEXT_LENGTHS"`.

- [ ] **Step 9: Run the new tests**

Run: `uv run pytest tests/unit/test_list_models_wire.py tests/unit/test_public_api_compat.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: all passed (10 + 2).

- [ ] **Step 10: Existing tests that change by design**

xfail (reason given after the dash):
- `tests/unit/test_openai_wire.py::test_list_models_filters_and_annotates` — `stage 2: list_models() no longer filters by model name; ported to test_list_models_wire.py::test_openai_lists_everything_unfiltered_with_unknown_metadata`
- `tests/unit/test_langdock_openai_wire.py::test_list_models_filters_to_supported_prefixes` — `stage 2: no prefix filter; ported to test_list_models_wire.py::test_langdock_openai_lists_everything`
- `tests/unit/test_mammouth_wire.py::test_list_models_from_public_endpoint` and `::test_list_models_constraints_and_sorting` — `stage 2: temperature range and reasoning are no longer derived from the model name; ported to test_list_models_wire.py::test_mammouth_reports_its_limits_and_nothing_else`
- `tests/unit/test_openrouter_wire.py::test_list_models_metadata_and_constraints` and `::test_model_constraints_regular_reasoning_and_null_parameters` — `stage 2: no name-based reasoning detection or default temperature range; ported to test_list_models_wire.py::test_openrouter_metadata_from_the_api`
- `tests/unit/test_openrouter_wire.py::test_runtime_rejection_survives_optimistic_model_list` — `stage 2: a learned rejection now shows as supports_temperature=False; ported to test_list_models_wire.py::test_openrouter_learned_rejection_beats_the_list`
- `tests/unit/test_local_wire.py::test_list_models_format` — `stage 2: supports_tools/supports_vision are no longer guessed; ported to test_list_models_wire.py::test_local_does_not_guess_tools_or_vision`

Then run `uv run pytest tests/unit/ -q -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|passed|failed"` and apply the triage rule to the mocked modules that assert name-derived list metadata: `test_openai.py`, `test_anthropic.py`, `test_langdock.py`, `test_langdock_backends.py`, `test_langdock_google_models.py`, `test_list_models_schema.py`, `test_mammouth.py`, `test_local.py`. Expected treatment: rule 2 (`stage 2: list metadata is reported by the provider or None, not derived from the model name`). Re-run until `0 failed`.

- [ ] **Step 11: Coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git checkout -- tests/reports/latest.md
git add src/eq_chatbot_core/providers/anthropic_shared.py src/eq_chatbot_core/providers/openai_provider.py \
  src/eq_chatbot_core/providers/anthropic_provider.py src/eq_chatbot_core/providers/langdock_provider.py \
  src/eq_chatbot_core/providers/mammouth_provider.py src/eq_chatbot_core/providers/openrouter_provider.py \
  src/eq_chatbot_core/providers/local_provider.py tests/unit/test_list_models_wire.py \
  tests/unit/test_public_api_compat.py tests/unit/test_openai_wire.py tests/unit/test_langdock_openai_wire.py \
  tests/unit/test_mammouth_wire.py tests/unit/test_openrouter_wire.py tests/unit/test_local_wire.py
git add <every mocked test file edited in Step 10, by name>
git commit -m "[CHG] list_models(): alle Modelle, Metadaten nur vom Provider oder gelernt, sonst None

xfailed:
<file::test — reason, one per line>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GJzy9HGak7N5HG7StkSHWF"
```

---

### Task 5: Name lists removed — temperature table, output-limit list, reasoning prefixes

**Files:**
- Modify: `src/eq_chatbot_core/providers/temperature_constraints.py` (whole file)
- Modify: `src/eq_chatbot_core/providers/openai_compatible.py:39, 209-212` (clamp call)
- Modify: `src/eq_chatbot_core/providers/openai_provider.py:36-73` (`NEW_API_MODELS`, `_token_param`, `_uses_new_token_api`), `:182-243` (`generate_image`)
- Modify: `src/eq_chatbot_core/providers/anthropic_provider.py` (two `apply_anthropic_temperature` calls)
- Modify: `src/eq_chatbot_core/providers/langdock_provider.py` (`_LangDockOpenAIBackend._token_param` and `_build_params`; `REASONING_MODELS`; `_is_reasoning_model`; `_uses_new_token_api`; two `apply_anthropic_temperature` and two `clamp_temperature` calls; `__init__` docstring line 253; class docstring line 186)
- Modify: `src/eq_chatbot_core/providers/mammouth_provider.py:13-19, 39-71`
- Modify: `src/eq_chatbot_core/providers/openrouter_provider.py:50-55, 89-92`
- Modify: `src/eq_chatbot_core/services/capability_catalog.py:26, 89, 92, 137` (private `_strip_provider_prefix`)
- Modify: `tests/unit/test_public_api_compat.py` (`_STAGE2_CHANGES`)
- Create: `tests/unit/test_no_name_lists_wire.py`

**Interfaces:**
- Consumes: `param_learning` learning (Tasks 2–3), `anthropic_message_body` (Task 3).
- Produces (module `eq_chatbot_core.providers.temperature_constraints`): `ANTHROPIC_MAX_TEMPERATURE: float = 1.0`; `clamp_temperature(temperature: float, *, maximum: float = 2.0) -> float`; `apply_anthropic_temperature(params: dict[str, Any], temperature: float) -> None`.
- Produces: `OpenAIProvider._token_param(model) -> "max_completion_tokens"` always; LangDock's openai delegate inherits `"max_tokens"`; `reasoning_effort` (argument or LangDock constructor default) is sent for every model.
- Produces: `eq_chatbot_core.services.capability_catalog._strip_provider_prefix(model_id: str) -> str`.
- Removed: `MODEL_TEMPERATURE_CONSTRAINTS`, `DEFAULT_TEMP_CONSTRAINTS`, `get_temperature_constraints`, `strip_provider_prefix` (from `temperature_constraints`), `OpenAIProvider.NEW_API_MODELS`, `OpenAIProvider._uses_new_token_api`, `LangDockProvider._uses_new_token_api`, `LangDockProvider.REASONING_MODELS`, `LangDockProvider._is_reasoning_model`, `_LangDockOpenAIBackend._token_param`, `MammouthProvider.REASONING_MODEL_PREFIXES`, `._is_reasoning_model`, `._get_temperature_constraints`, `._clamp_temperature`, `OpenRouterProvider.REASONING_MODEL_PREFIXES`, `._is_reasoning_model`, the `dall-e` branch in `OpenAIProvider.generate_image`.

- [ ] **Step 1: Write the failing tests — `tests/unit/test_no_name_lists_wire.py`**

```python
"""Stage 2: what name lists used to decide is now decided by the API or learned.

Real-looking model names below are test data: they show that a name no longer
changes what is sent.
"""

import pytest

from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.langdock_provider import LangDockProvider
from eq_chatbot_core.providers.mammouth_provider import MammouthProvider
from eq_chatbot_core.providers.openai_provider import OpenAIProvider
from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider
from eq_chatbot_core.providers.temperature_constraints import apply_anthropic_temperature, clamp_temperature
from tests.wire_server import OPENAI_REASONING_EFFORT_REJECTION, Reply, anthropic_message_body, chat_body

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_param_memory")]
MSG = [{"role": "user", "content": "x"}]
CHAT = ("POST", "/v1/chat/completions")
LANGDOCK_CHAT = ("POST", "/openai/eu/v1/chat/completions")


def test_clamp_is_provider_level_only():
    assert clamp_temperature(0.7) == 0.7
    assert clamp_temperature(3.0) == 2.0
    assert clamp_temperature(-1.0) == 0.0
    assert clamp_temperature(1.5, maximum=1.0) == 1.0


def test_anthropic_temperature_clamped_into_extra_body():
    params = {"model": "m"}
    apply_anthropic_temperature(params, 1.5)
    assert params == {"model": "m", "extra_body": {"temperature": 1.0}}


@pytest.mark.parametrize("model", ["o3", "gpt-5", "deepseek-reasoner", "anything-new"])
def test_temperature_is_sent_whatever_the_model_name(wire_server, model):
    wire_server.expect(*CHAT, Reply(body=chat_body()))
    MammouthProvider(api_key="k", base_url=wire_server.base_url, max_retries=0).chat_completion(
        MSG, model=model, temperature=0.3
    )
    assert wire_server.requests[0].json["temperature"] == 0.3


def test_anthropic_sends_temperature_for_any_model_name(wire_server):
    wire_server.expect("POST", "/v1/messages", Reply(body=anthropic_message_body()))
    AnthropicProvider(api_key="k", base_url=wire_server.root_url, max_retries=0).chat_completion(
        MSG, model="claude-sonnet-5", temperature=1.4
    )
    assert wire_server.requests[0].json["temperature"] == 1.0  # Anthropic's provider-level 0..1


def test_openai_always_sends_max_completion_tokens(wire_server):
    wire_server.expect(*CHAT, Reply(body=chat_body()))
    OpenAIProvider(api_key="k", base_url=wire_server.base_url, max_retries=0).chat_completion(
        MSG, model="any-model", max_tokens=20
    )
    sent = wire_server.requests[0].json
    assert sent["max_completion_tokens"] == 20 and "max_tokens" not in sent


def test_langdock_openai_sends_max_tokens_whatever_the_model(wire_server):
    wire_server.expect(*LANGDOCK_CHAT, Reply(body=chat_body()))
    LangDockProvider(api_key="k", base_url=wire_server.root_url, max_retries=0).chat_completion(
        MSG, model="gpt-5", max_tokens=20
    )
    sent = wire_server.requests[0].json
    assert sent["max_tokens"] == 20 and "max_completion_tokens" not in sent


def test_langdock_constructor_reasoning_effort_sent_for_any_model_and_learned_away(wire_server):
    """Set once in the constructor, never per call: still dropped once a model rejects it."""
    wire_server.expect(*LANGDOCK_CHAT, Reply(400, OPENAI_REASONING_EFFORT_REJECTION), Reply(body=chat_body()))
    provider = LangDockProvider(api_key="k", base_url=wire_server.root_url, max_retries=0, reasoning_effort="high")
    provider.chat_completion(MSG, model="plain-model")
    provider.chat_completion(MSG, model="plain-model")
    first, second, third = [r.json for r in wire_server.requests]
    assert first["reasoning_effort"] == "high"
    assert "reasoning_effort" not in second and "reasoning_effort" not in third


def test_openrouter_reasoning_effort_passes_through(wire_server):
    wire_server.expect(*CHAT, Reply(body=chat_body()))
    OpenRouterProvider(api_key="k", base_url=wire_server.base_url, max_retries=0).chat_completion(
        MSG, model="vendor/plain", reasoning_effort="low"
    )
    assert wire_server.requests[0].json["reasoning_effort"] == "low"


def test_openai_image_without_b64_is_a_clear_error(wire_server):
    wire_server.expect(
        "POST", "/v1/images/generations", Reply(body={"created": 0, "data": [{"url": "https://example.invalid/i.png"}]})
    )
    provider = OpenAIProvider(api_key="k", base_url=wire_server.base_url, max_retries=0, image_model="dall-e-3")
    with pytest.raises(ProviderError, match="response_format"):
        provider.generate_image("a cat")
    assert "response_format" not in wire_server.requests[0].json  # no name-based guess any more
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_no_name_lists_wire.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: FAILED — `TypeError: clamp_temperature() missing 1 required positional argument`, `KeyError: 'temperature'` for `o3`, `max_tokens` present for OpenAI `any-model`, etc.

- [ ] **Step 3: Replace `src/eq_chatbot_core/providers/temperature_constraints.py`**

```python
"""Provider-level temperature rules.

Only rules that hold for every model of a provider live here: the 0–2 range of
the OpenAI wire protocol and Anthropic's 0–1 range. Whether a particular model
accepts ``temperature`` at all is learned at runtime (``param_learning``),
never looked up by name.
"""

import logging
from typing import Any

_logger = logging.getLogger(__name__)

ANTHROPIC_MAX_TEMPERATURE = 1.0


def clamp_temperature(temperature: float, *, maximum: float = 2.0) -> float:
    """Clamp ``temperature`` into ``0.0 … maximum``; logs a warning when it clamps."""
    if temperature < 0.0:
        _logger.warning("Temperature %.2f below 0.00, clamping to 0.00", temperature)
        return 0.0
    if temperature > maximum:
        _logger.warning("Temperature %.2f above maximum %.2f, clamping to %.2f", temperature, maximum, maximum)
        return maximum
    return temperature


def apply_anthropic_temperature(params: dict[str, Any], temperature: float) -> None:
    """Put a temperature clamped to 0–1 where the Anthropic SDK still accepts it.

    anthropic 1.0.0 removed ``temperature``, ``top_p`` and ``top_k`` from
    ``messages.create()`` / ``messages.stream()``: passing one raises
    ``TypeError``. The value travels in ``extra_body`` instead, as the SDK's
    migration guide prescribes. A model that no longer takes a temperature
    rejects it; ``anthropic_shared`` learns that and drops it.

    Args:
        params: Request kwargs, mutated in place. An existing ``extra_body`` is
            merged into, never replaced.
        temperature: Requested temperature.
    """
    extra_body = params.setdefault("extra_body", {})
    extra_body["temperature"] = clamp_temperature(temperature, maximum=ANTHROPIC_MAX_TEMPERATURE)
```

- [ ] **Step 4: Callers of the clamp functions**

- `openai_compatible._build_params`: replace

```python
        # Clamp temperature per model constraints (skip for reasoning models)
        clamped = clamp_temperature(model, temperature)
        if clamped is not None:
            params["temperature"] = clamped
```

  with

```python
        # Provider-level range only. A model that takes no temperature rejects
        # it once and is remembered (see _create / param_learning).
        params["temperature"] = clamp_temperature(temperature)
```

- `anthropic_provider.py` (two places) and `langdock_provider.py` (two places): `apply_anthropic_temperature(params, model, temperature)` → `apply_anthropic_temperature(params, temperature)`; delete the comment line above each (`# Clamp temperature per model constraints`).
- `langdock_provider.py` Google chat and stream (two places): replace

```python
            # Clamp temperature per model constraints
            clamped = clamp_temperature(model, temperature)
```

  with nothing, and inside `generationConfig` replace `"temperature": clamped if clamped is not None else temperature,` with `"temperature": clamp_temperature(temperature),`.

- [ ] **Step 5: OpenAI — output limit and image response format**

Delete `NEW_API_MODELS` with its comment and `_uses_new_token_api`. Replace `_token_param` with:

```python
    def _token_param(self, model: str) -> str:
        """The OpenAI API takes ``max_completion_tokens`` for every current model."""
        return "max_completion_tokens"
```

In `generate_image`, docstring `size:` entry becomes `size: Image dimensions, passed through to the API (valid sizes depend on the model).`; replace the block from `params: dict[str, Any] = {` to `image_bytes = base64.b64decode(resp.data[0].b64_json)` with:

```python
            params: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "n": 1,
                "size": size,
            }
            params.update(kwargs)

            resp = self.client.images.generate(**params)
            b64 = resp.data[0].b64_json
            if not b64:
                raise ProviderError(
                    f"Image model {model} returned no base64 image data. "
                    'Pass response_format="b64_json" for models that answer with a URL.',
                    provider=self.provider_name,
                )
            image_bytes = base64.b64decode(b64)
```

Import `ProviderError` from `eq_chatbot_core.providers.base` (next to `ImageResult, ModelNotSpecifiedError`). `_handle_error` passes a `ProviderError` through unchanged.

- [ ] **Step 6: LangDock — no output-limit guess, no reasoning gating**

- Delete `_LangDockOpenAIBackend._token_param` (the base class sends `max_tokens`; learning corrects it).
- In `_LangDockOpenAIBackend._build_params` replace `if effort and self._owner._is_reasoning_model(model):` with `if effort:`.
- Delete `REASONING_MODELS` (with its comment), `_is_reasoning_model` and `_uses_new_token_api`.
- Class docstring line `- Reasoning effort control for O1/O3/O4 models` → `- Reasoning effort, sent with every openai-backend request when set`.
- `__init__` docstring `reasoning_effort: For O1/O3/O4 models - 'low', 'medium', 'high'` → `reasoning_effort: 'low', 'medium' or 'high'; sent with every openai-backend request when set. A model that rejects it is learned and the parameter dropped.`

- [ ] **Step 7: Mammouth and OpenRouter**

Mammouth: delete the two `temperature_constraints` imports (lines 14-19), `REASONING_MODEL_PREFIXES` with its comment, `_is_reasoning_model`, `_get_temperature_constraints`, `_clamp_temperature`. Delete `import logging` / `_logger` only if ruff reports them unused.
OpenRouter: delete `REASONING_MODEL_PREFIXES` with its comment and `_is_reasoning_model`.

- [ ] **Step 8: `capability_catalog` keeps its own prefix helper**

In `src/eq_chatbot_core/services/capability_catalog.py` delete `from eq_chatbot_core.providers.temperature_constraints import strip_provider_prefix` and add after `_logger`:

```python
def _strip_provider_prefix(model_id: str) -> str:
    """``vendor/model`` -> ``model``; an id without a vendor part is returned unchanged."""
    return model_id.split("/", 1)[1] if "/" in model_id else model_id
```

Replace the three calls `strip_provider_prefix(` with `_strip_provider_prefix(`.

- [ ] **Step 9: Stage-2 allowance**

Extend `_STAGE2_CHANGES`: `"OpenAIProvider"` += `"NEW_API_MODELS"`; `"LangDockProvider"` += `"REASONING_MODELS"`; `"MammouthProvider"` += `"REASONING_MODEL_PREFIXES"`; `"OpenRouterProvider"` += `"REASONING_MODEL_PREFIXES"`.

- [ ] **Step 10: Run the new tests**

Run: `uv run pytest tests/unit/test_no_name_lists_wire.py tests/unit/test_anthropic_wire.py tests/unit/test_public_api_compat.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: all passed (12 + 10 + 2).

- [ ] **Step 11: Existing tests that change by design**

- `tests/unit/test_temperature_constraints.py`: wrap its `from eq_chatbot_core.providers.temperature_constraints import (...)` block (lines 10-15) as

```python
try:
    from eq_chatbot_core.providers.temperature_constraints import (
        DEFAULT_TEMP_CONSTRAINTS,
        clamp_temperature,
        get_temperature_constraints,
        strip_provider_prefix,
    )
except ImportError:
    pytest.skip(
        "stage 2: the per-model temperature table was removed; provider-level clamp tested in "
        "test_no_name_lists_wire.py",
        allow_module_level=True,
    )
```

  (keep exactly the names the original block imports).
- `tests/unit/test_gpt5_temperature.py`, `tests/unit/test_anthropic_temperature_transport.py`: whole module obsolete (both call the clamp functions with a model argument) → append to `pytestmark` `pytest.mark.xfail(reason="stage 2: temperature support is learned, not looked up by model name; ported to test_no_name_lists_wire.py and test_anthropic_wire.py", strict=False)`.
- `tests/unit/test_mammouth_wire.py::test_reasoning_model_gets_no_temperature` — `stage 2: temperature is no longer withheld by model name; ported to test_no_name_lists_wire.py::test_temperature_is_sent_whatever_the_model_name`
- `tests/unit/test_openrouter_wire.py::test_reasoning_model_detection` and `::test_reasoning_model_gets_no_temperature` — `stage 2: no reasoning-model prefix list; ported to test_no_name_lists_wire.py`
- `tests/unit/test_langdock_openai_wire.py::test_reasoning_effort_only_for_reasoning_models` — `stage 2: reasoning_effort is sent for every model and learned away; ported to test_no_name_lists_wire.py::test_langdock_constructor_reasoning_effort_sent_for_any_model_and_learned_away`

Then run the unit suite and apply the triage rule to mocked modules asserting name-based temperature, token-parameter or reasoning behaviour: `test_mammouth.py`, `test_openai.py`, `test_anthropic.py`, `test_langdock*.py`, `test_openrouter*.py`, `test_capability_catalog.py` (only if it imported `strip_provider_prefix`). Expected treatment: rule 2. Re-run until `0 failed`.

- [ ] **Step 12: Coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git checkout -- tests/reports/latest.md
git add src/eq_chatbot_core/providers/temperature_constraints.py src/eq_chatbot_core/providers/openai_compatible.py \
  src/eq_chatbot_core/providers/openai_provider.py src/eq_chatbot_core/providers/anthropic_provider.py \
  src/eq_chatbot_core/providers/langdock_provider.py src/eq_chatbot_core/providers/mammouth_provider.py \
  src/eq_chatbot_core/providers/openrouter_provider.py src/eq_chatbot_core/services/capability_catalog.py \
  tests/unit/test_no_name_lists_wire.py tests/unit/test_public_api_compat.py tests/unit/test_temperature_constraints.py \
  tests/unit/test_gpt5_temperature.py tests/unit/test_anthropic_temperature_transport.py \
  tests/unit/test_mammouth_wire.py tests/unit/test_openrouter_wire.py tests/unit/test_langdock_openai_wire.py
git add <every mocked test file edited in Step 11, by name>
git commit -m "[CHG] Namenslisten entfernt: Temperatur-Tabelle, NEW_API_MODELS, Reasoning-Präfixe

xfailed:
<file::test — reason, one per line>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GJzy9HGak7N5HG7StkSHWF"
```

---
### Task 6: Embedders, retriever, token estimate, context window, capability catalog, realtime configs

**Files:**
- Modify: `src/eq_chatbot_core/rag/embedder.py` (whole file)
- Modify: `src/eq_chatbot_core/rag/retriever.py:167-199` (`ensure_collection`)
- Modify: `src/eq_chatbot_core/rag/context_manager.py:41-93` (`MODEL_LIMITS`, `__init__`, `_get_model_limit`)
- Modify: `src/eq_chatbot_core/security/rate_limit.py:229-261` (`estimate_tokens`)
- Modify: `src/eq_chatbot_core/services/capability_catalog.py:1-34, 98-122, 145`
- Delete (after the Captain's "ja"): `src/eq_chatbot_core/data/capability_catalog.json`, `src/eq_chatbot_core/data/capability_overrides.json`
- Modify: `pyproject.toml:148-164` (wheel packaging)
- Modify: `src/eq_chatbot_core/realtime/providers/openai.py:57-62, 97-100`, `src/eq_chatbot_core/realtime/providers/gemini_live.py:62-66, 100-103`
- Modify: `tests/wire_server.py` (append `embeddings_body`)
- Create: `tests/unit/test_embedder_wire.py`, `tests/unit/test_no_model_tables.py`

**Interfaces:**
- Consumes: `ModelNotSpecifiedError(..., hint=...)` (Task 1); `wire_server` (Task 2).
- Produces:
  - `BaseEmbedder.dimensions -> int | None` (abstract property)
  - `OpenAIEmbedder(api_key: str, model: str | None = None, base_url: str | None = None, dimensions: int | None = None)`; `PROVIDER_NAME = "openai"`; raises `ModelNotSpecifiedError` at construction without a model; `embed()` sets `dimensions` from the first response and raises `ValueError` on a mismatch.
  - `LangDockEmbedder(api_key: str, model: str | None = None, region: str = "eu", dimensions: int | None = None)`; `PROVIDER_NAME = "langdock"`.
  - `MeliousEmbedder(api_key: str, model: str | None = None, base_url: str | None = None, dimensions: int | None = None)`; `PROVIDER_NAME = "melious"`.
  - `HybridRetriever.ensure_collection(vector_size: int | None = None) -> str` raises `ValueError` when neither `vector_size` nor `embedder.dimensions` is known.
  - `ContextWindowManager(model: str, max_response_tokens: int = 4096, history_ratio: float = 0.3, rag_ratio: float = 0.4, context_length: int | None = None)`; `DEFAULT_CONTEXT_LENGTH = 128000`.
  - `estimate_tokens(text: str, model: str | None = None) -> int` (model unused).
  - `CapabilityCatalog.from_remote(url=None, timeout=10.0)` returns `CapabilityCatalog({})` on failure and logs WARNING `Capability catalog remote fetch failed; catalog is empty: …`.
  - `OpenAIRealtimeConfig.model: str = ""`, `GeminiLiveConfig.model: str = ""` (clients raise `ValueError` mentioning `model`).
  - Test-side: `tests.wire_server.embeddings_body(vectors: list[list[float]], *, model: str = "test-model") -> dict`.
- Removed: `OpenAIEmbedder.MODELS`, `ContextWindowManager.MODEL_LIMITS`, `ContextWindowManager._get_model_limit`, `CapabilityCatalog.from_snapshot`, `capability_catalog._SNAPSHOT_PATH`, the bundled JSON files.

- [ ] **Step 1: Builder (append to `tests/wire_server.py`)**

```python
def embeddings_body(vectors: list[list[float]], *, model: str = "test-model") -> dict[str, Any]:
    """An embeddings response (POST /v1/embeddings) with float vectors."""
    return {
        "object": "list",
        "model": model,
        "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vectors)],
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }
```

- [ ] **Step 2: Write the failing tests — `tests/unit/test_embedder_wire.py`**

```python
"""Embedders: the model is the caller's; the vector size is passed or read from the first response."""

import pytest

from eq_chatbot_core.providers import ModelNotSpecifiedError
from eq_chatbot_core.rag.embedder import LangDockEmbedder, MeliousEmbedder, OpenAIEmbedder
from tests.wire_server import Reply, embeddings_body

pytestmark = pytest.mark.unit
EMBED = ("POST", "/v1/embeddings")


@pytest.mark.parametrize("cls", [OpenAIEmbedder, LangDockEmbedder, MeliousEmbedder])
def test_model_is_required(cls):
    with pytest.raises(ModelNotSpecifiedError, match="embedding model") as caught:
        cls(api_key="k")
    assert f"{cls.__name__}(" in str(caught.value)


def test_dimensions_unknown_until_the_first_embedding(wire_server):
    embedder = OpenAIEmbedder(api_key="k", model="emb-test", base_url=wire_server.base_url)
    assert embedder.dimensions is None
    wire_server.expect(*EMBED, Reply(body=embeddings_body([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])))
    vectors = embedder.embed(["a", "b"])
    assert vectors.shape == (2, 3)
    assert embedder.dimensions == 3
    assert wire_server.requests[0].json["model"] == "emb-test"


def test_passed_dimensions_are_known_up_front():
    assert MeliousEmbedder(api_key="k", model="emb-test", dimensions=1024).dimensions == 1024
    assert LangDockEmbedder(api_key="k", model="emb-test", dimensions=256).dimensions == 256


def test_configured_dimensions_mismatch_raises(wire_server):
    """Review focus 4: a wrong size must not reach a vector collection silently."""
    embedder = OpenAIEmbedder(api_key="k", model="emb-test", base_url=wire_server.base_url, dimensions=4)
    wire_server.expect(*EMBED, Reply(body=embeddings_body([[0.1, 0.2, 0.3]])))
    with pytest.raises(ValueError, match="dimensions=4"):
        embedder.embed("a")


def test_collection_size_comes_from_the_embedder(wire_server):
    """Review focus 4: no collection of unknown size; the discovered size is used."""
    from qdrant_client import QdrantClient

    from eq_chatbot_core.rag.retriever import HybridRetriever

    embedder = OpenAIEmbedder(api_key="k", model="emb-test", base_url=wire_server.base_url)
    retriever = HybridRetriever(QdrantClient(location=":memory:"), "docs", embedder)
    with pytest.raises(ValueError, match="(?i)vector size"):
        retriever.ensure_collection()

    wire_server.expect(*EMBED, Reply(body=embeddings_body([[0.1, 0.2, 0.3]])))
    embedder.embed("a")
    retriever.ensure_collection()
    assert retriever.client.get_collection("docs").config.params.vectors.size == 3
```

- [ ] **Step 3: Write the failing tests — `tests/unit/test_no_model_tables.py`**

```python
"""Token estimate, context window, capability catalog and realtime configs carry no model tables."""

import tomllib
from importlib import resources
from pathlib import Path

import pytest

from tests.wire_server import Reply

pytestmark = pytest.mark.unit


def test_estimate_tokens_is_the_same_for_every_model():
    from eq_chatbot_core.security.rate_limit import estimate_tokens

    text = "Hallo Welt, dies ist ein Test."
    assert estimate_tokens(text) == estimate_tokens(text, model="anything") == estimate_tokens(text, "other") > 0


def test_context_length_is_passed_not_looked_up():
    from eq_chatbot_core.rag.context_manager import ContextWindowManager

    assert ContextWindowManager(model="any").max_tokens == ContextWindowManager.DEFAULT_CONTEXT_LENGTH
    assert ContextWindowManager(model="any", context_length=32000).max_tokens == 32000
    assert not hasattr(ContextWindowManager, "MODEL_LIMITS")


def test_catalog_is_empty_when_the_remote_fetch_fails(wire_server, caplog):
    from eq_chatbot_core.services.capability_catalog import CapabilityCatalog

    wire_server.expect("GET", "/catalog.json", Reply(500, {"error": "down"}))
    with caplog.at_level("WARNING", logger="eq_chatbot_core.services.capability_catalog"):
        catalog = CapabilityCatalog.from_remote(f"{wire_server.root_url}/catalog.json")
    assert catalog.lookup("any-model") is None
    assert "catalog is empty" in caplog.text


def test_no_catalog_snapshot_ships_with_the_package():
    from eq_chatbot_core.services.capability_catalog import CapabilityCatalog

    data = resources.files("eq_chatbot_core") / "data"
    assert not (data / "capability_catalog.json").is_file()
    assert not (data / "capability_overrides.json").is_file()
    assert not hasattr(CapabilityCatalog, "from_snapshot")

    pyproject = tomllib.loads((Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    packaged = [*wheel.get("artifacts", []), *wheel.get("exclude", []), *wheel.get("force-include", {})]
    assert not [p for p in packaged if "capability_" in p]


def test_realtime_configs_have_no_default_model():
    from eq_chatbot_core.realtime.providers.gemini_live import GeminiLiveClient, GeminiLiveConfig
    from eq_chatbot_core.realtime.providers.openai import OpenAIRealtimeClient, OpenAIRealtimeConfig

    assert OpenAIRealtimeConfig(api_key="k").model == ""
    assert GeminiLiveConfig(api_key="k").model == ""
    with pytest.raises(ValueError, match="model"):
        OpenAIRealtimeClient(OpenAIRealtimeConfig(api_key="k"))
    with pytest.raises(ValueError, match="model"):
        GeminiLiveClient(GeminiLiveConfig(api_key="k"))
```

- [ ] **Step 4: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_embedder_wire.py tests/unit/test_no_model_tables.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: FAILED — `DID NOT RAISE ModelNotSpecifiedError`, `ValueError: Unknown model: emb-test`, `assert 'gpt-realtime' == ''`, `AttributeError: ... DEFAULT_CONTEXT_LENGTH`; `test_estimate_tokens_is_the_same_for_every_model` may already pass.

- [ ] **Step 5: Replace `src/eq_chatbot_core/rag/embedder.py`**

```python
"""
Embedding adapters for RAG pipeline.

The embedding model is always the caller's choice — there is no default — and the
vector size is either passed as ``dimensions`` or read from the first embedding
response. Nothing is looked up from a model table.
"""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from eq_chatbot_core.providers.base import ModelNotSpecifiedError


class BaseEmbedder(ABC):
    """Abstract base class for embedding models."""

    @property
    @abstractmethod
    def dimensions(self) -> int | None:
        """Embedding vector size; ``None`` until it is known."""
        ...

    @abstractmethod
    def embed(self, texts: str | list[str]) -> np.ndarray:
        """
        Generate embeddings for text(s).

        Args:
            texts: Single text or list of texts

        Returns:
            numpy array of shape (n_texts, dimensions)
        """
        ...


class OpenAIEmbedder(BaseEmbedder):
    """Embeddings through the OpenAI API or any OpenAI-compatible ``/embeddings`` endpoint."""

    PROVIDER_NAME = "openai"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        base_url: str | None = None,
        dimensions: int | None = None,
    ):
        """
        Initialize the embedder.

        Args:
            api_key: API key
            model: Embedding model id (required; there is no default)
            base_url: Optional custom base URL
            dimensions: Vector size the model produces. Pass it when a vector
                collection must be created before the first ``embed()`` call;
                otherwise it is read from the first response.

        Raises:
            ModelNotSpecifiedError: If ``model`` is missing.
            ValueError: If ``base_url`` fails URL validation.
        """
        if not model:
            raise ModelNotSpecifiedError(
                self.PROVIDER_NAME,
                what="embedding model",
                hint=f'Pass model="..." to {type(self).__name__}(...).',
            )
        self.api_key = api_key
        self.model = model
        self._client: Any = None
        self._dimensions = dimensions

        # SSRF guard: only a caller-supplied base_url is validated — fixed public
        # defaults set by subclasses are trusted and need no DNS round-trip.
        # Imported lazily to avoid an import cycle.
        if base_url:
            from eq_chatbot_core.utils.url_validation import validate_url

            validate_url(base_url, allow_private_ranges=False)

        self.base_url = base_url

    @property
    def dimensions(self) -> int | None:
        return self._dimensions

    @property
    def client(self) -> Any:
        """Lazy initialization of OpenAI client.

        Built on the same pinned httpx2 client as the chat providers: the SDK's
        default client follows redirects and re-resolves DNS on every connect,
        so a URL that passed validation could still be steered to an internal
        address.
        """
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError("OpenAI package not installed. Install with: pip install openai") from e

            import httpx2

            from eq_chatbot_core.utils.url_validation import build_pinned_transport_for_url

            effective_url = self.base_url or self.DEFAULT_BASE_URL
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=effective_url,
                http_client=httpx2.Client(transport=build_pinned_transport_for_url(effective_url)),
            )
        return self._client

    def embed(self, texts: str | list[str]) -> np.ndarray:
        """Generate embeddings; the first response fixes ``dimensions`` if it was not passed."""
        if isinstance(texts, str):
            texts = [texts]

        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
        )

        vectors = np.array([d.embedding for d in response.data])
        self._check_dimensions(vectors)
        return vectors

    def _check_dimensions(self, vectors: np.ndarray) -> None:
        if vectors.ndim != 2 or vectors.shape[0] == 0:
            return
        size = int(vectors.shape[1])
        if self._dimensions is None:
            self._dimensions = size
        elif size != self._dimensions:
            raise ValueError(
                f"Embedding model {self.model!r} returned {size}-dimensional vectors, "
                f"but dimensions={self._dimensions} was configured."
            )


class LangDockEmbedder(OpenAIEmbedder):
    """LangDock embedding API (OpenAI-compatible)."""

    PROVIDER_NAME = "langdock"
    BASE_URLS = {
        "eu": "https://api.langdock.com/openai/eu/v1",
        "us": "https://api.langdock.com/openai/us/v1",
    }

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        region: str = "eu",
        dimensions: int | None = None,
    ):
        """
        Initialize LangDock embedder.

        Args:
            api_key: LangDock API key
            model: Embedding model id (required; there is no default)
            region: API region ('eu' or 'us')
            dimensions: Vector size the model produces (else read from the first response)
        """
        # The region endpoints are fixed, built-in public URLs — assign after the
        # super() call so the SSRF guard's DNS round-trip is not paid for a URL
        # the caller cannot influence.
        super().__init__(api_key, model, None, dimensions)
        self.base_url = self.BASE_URLS.get(region, self.BASE_URLS["eu"])
        self.region = region


class MeliousEmbedder(OpenAIEmbedder):
    """Melious.ai embedding API (OpenAI-compatible, sovereign EU-hosted).

    The embedding model ids are advertised by Melious ``/v1/models``; pass one as
    ``model``. ``dimensions`` may be passed, else it is read from the first response.
    """

    PROVIDER_NAME = "melious"
    DEFAULT_BASE_URL = "https://api.melious.ai/v1"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        base_url: str | None = None,
        dimensions: int | None = None,
    ):
        """
        Initialize the Melious embedder.

        Args:
            api_key: Melious API key (sent as a Bearer token).
            model: Embedding model id as advertised by Melious ``/v1/models`` (required).
            base_url: OpenAI-compatible endpoint. Defaults to the official
                Melious URL; override only to route through a proxy.
            dimensions: Vector size the model produces (else read from the first response).

        Raises:
            ModelNotSpecifiedError: If ``model`` is missing.
            ValueError: If ``base_url`` fails URL validation.
        """
        super().__init__(api_key, model, base_url, dimensions)
        self.base_url = base_url or self.DEFAULT_BASE_URL
```

- [ ] **Step 6: `HybridRetriever.ensure_collection`**

Docstring `vector_size: Vector dimensions (required for creation)` → `vector_size: Vector dimensions (defaults to the embedder's ``dimensions``)`. Replace

```python
        if not exists:
            if vector_size is None:
                vector_size = self.embedder.dimensions
```

with

```python
        if not exists:
            if vector_size is None:
                vector_size = self.embedder.dimensions
            if vector_size is None:
                raise ValueError(
                    f"Vector size unknown for collection '{self.collection}': pass vector_size=..., "
                    "create the embedder with dimensions=..., or embed one text first."
                )
```

- [ ] **Step 7: `ContextWindowManager`, `estimate_tokens`**

`context_manager.py`: replace the `MODEL_LIMITS = {...}` block with

```python
    # Used when the caller does not pass the model's context window. The library
    # keeps no per-model table; list_models() reports context_length where the
    # provider does.
    DEFAULT_CONTEXT_LENGTH = 128000
```

Append `context_length: int | None = None,` to the `__init__` parameters (after `rag_ratio`); docstring: `model: Model name (stored for callers; no limit is looked up from it)` and add `context_length: The model's context window in tokens (e.g. from list_models()); defaults to DEFAULT_CONTEXT_LENGTH`. Replace `self.max_tokens = self._get_model_limit(model)` with `self.max_tokens = context_length or self.DEFAULT_CONTEXT_LENGTH` and delete `_get_model_limit`.

`rate_limit.py`: replace `estimate_tokens` with

```python
def estimate_tokens(text: str, model: str | None = None) -> int:
    """
    Estimate the token count of ``text`` with the ``cl100k_base`` encoding.

    The estimate is the same for every model; ``model`` is accepted for
    backwards compatibility and ignored.

    Args:
        text: Text to estimate
        model: Ignored

    Returns:
        Estimated token count
    """
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(text))

    except ImportError:
        # Fallback: rough estimate (4 chars per token)
        return len(text) // 4
```

- [ ] **Step 8: Capability catalog — no bundled snapshot**

Replace the module docstring (lines 1-17) with:

```python
"""Model capability catalog.

Resolves per-model *capabilities* (vision, audio, files, tools, reasoning) and
context/output *limits* across all supported providers from the curated,
Equitania-hosted ``capability_catalog.json`` (Single Source of Truth, maintained
centrally by the ``eq-model-catalog`` sync tool). The package ships no copy:
:meth:`CapabilityCatalog.from_remote` fetches the live file, and when that fails
the catalog is empty (``lookup()`` returns ``None``) and a WARNING is logged.

Each model entry lists ``aliases`` — the per-provider technical model ids — so a
configured ``model_id`` maps back to the canonical entry regardless of provider.
"""
```

Delete `import json`, `import os`, the `_SNAPSHOT_PATH = ...` line and the whole `from_snapshot` classmethod. Replace `from_remote` with:

```python
    @classmethod
    def from_remote(cls, url: str | None = None, timeout: float = 10.0) -> CapabilityCatalog:
        """Fetch the hosted Equitania catalog; on any failure return an empty catalog."""
        try:
            import httpx2

            from eq_chatbot_core.utils.url_validation import build_validating_transport

            # `url` is caller-supplied, so the request is SSRF-checked instead of
            # being trusted to point at the Equitania catalog.
            with httpx2.Client(transport=build_validating_transport(), timeout=timeout) as client:
                resp = client.get(url or DEFAULT_CATALOG_URL)
            resp.raise_for_status()
            return cls(resp.json())
        except Exception as e:  # network/parse failure -> empty catalog
            _logger.warning("Capability catalog remote fetch failed; catalog is empty: %s", e)
            return cls({})
```

Line 145 comment → `# Longest-prefix fallback (e.g. a dated snapshot id -> its undated alias).`

- [ ] **Step 9: Ask before deleting the two JSON files**

Run: `git status --short src/eq_chatbot_core/data/`
Expected: no output (both files committed, unchanged).
Ask the Captain verbatim: „Soll ich `src/eq_chatbot_core/data/capability_catalog.json` und `src/eq_chatbot_core/data/capability_overrides.json` wirklich löschen? `capability_overrides.json` ist Eingabe für das Sync-Tool eq-model-catalog — soll sie vorher dorthin umziehen? (ja/nein)“ — and wait. On "ja":

```bash
git rm src/eq_chatbot_core/data/capability_catalog.json src/eq_chatbot_core/data/capability_overrides.json
```

On "nein": stop this task and report; the guard test in Task 8 cannot pass while the files are under `src/`.

- [ ] **Step 10: `pyproject.toml` packaging**

Replace lines 148-164 (`[tool.hatch.build.targets.wheel]` through the `config.toml.example` force-include line) with:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/eq_chatbot_core"]
# Ship the CLI config template (used by `eq-chatbot config init`). The capability
# catalog is not bundled: CapabilityCatalog.from_remote() fetches it.
artifacts = ["src/eq_chatbot_core/data/*.example"]

[tool.hatch.build.targets.wheel.force-include]
# PEP 561 marker: without it type checkers ignore the inline annotations of this
# package entirely, so every downstream consumer sees `Any` despite mypy strict.
"src/eq_chatbot_core/py.typed" = "eq_chatbot_core/py.typed"
"src/eq_chatbot_core/data/config.toml.example" = "eq_chatbot_core/data/config.toml.example"
```

- [ ] **Step 11: Realtime configs**

`realtime/providers/openai.py`: replace the four comment lines and `model: str = "gpt-realtime"` (lines 58-62) with

```python
    # Realtime model id, chosen by the caller. No default: realtime model ids
    # change like any other model id.
    model: str = ""
```

and the error text on line 99 with `"OpenAIRealtimeConfig.model must be non-empty. Pass the realtime model id; there is no default."`.

`realtime/providers/gemini_live.py`: replace lines 63-66 (the three comment lines and `model: str = "gemini-3.1-flash-live-preview"`) with

```python
    # Live API model id, chosen by the caller. No default: model ids change.
    model: str = ""
```

and the error text on line 102 with `"GeminiLiveConfig.model must be non-empty. Pass the Live API model id; there is no default."`.

- [ ] **Step 12: Run the new tests**

Run: `uv run pytest tests/unit/test_embedder_wire.py tests/unit/test_no_model_tables.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: all passed (7 + 5).

- [ ] **Step 13: Existing tests — apply the triage rule**

Run: `uv run pytest tests/unit/ -q -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|passed|failed"`
Expected failures and treatment:
- `tests/unit/test_embedder.py`: rule 1 where a test constructs an embedder without `model` but tests something else; rule 2 (`stage 2: no embedding model table`) for assertions on `MODELS`, the default model or the 1536 default.
- `tests/unit/test_rate_limit.py`: rule 2 only for assertions on the encoding map; others pass unchanged.
- `tests/unit/test_context_manager.py`: `ContextWindowManager(model="gpt-4")` expecting 8192 and similar table lookups → rule 2 (`stage 2: no context-length table; pass context_length`).
- `tests/unit/test_capability_catalog.py`: the two `from_snapshot` users → rule 2 (`stage 2: the snapshot left the package`); if a fixture loads the snapshot file, give the module a module-level skip in the `except` of that load.
- `tests/unit/realtime/test_realtime_gemini.py::test_default_model_contains_gemini`, `::test_default_model_is_verified_alias` and any default-model test in `test_realtime_openai.py` → rule 2 (`stage 2: no default realtime model`); every other `OpenAIRealtimeConfig(` / `GeminiLiveConfig(` call in those two files (28 calls, most without `model=`) gets `model="test-model"` when it lacks one (rule 1). `tests/unit/realtime/test_factory.py` is unaffected (it fails on the missing `api_key` before the model check).
Re-run until `0 failed`.

- [ ] **Step 14: Coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git checkout -- tests/reports/latest.md
git add src/eq_chatbot_core/rag/embedder.py src/eq_chatbot_core/rag/retriever.py \
  src/eq_chatbot_core/rag/context_manager.py src/eq_chatbot_core/security/rate_limit.py \
  src/eq_chatbot_core/services/capability_catalog.py pyproject.toml \
  src/eq_chatbot_core/realtime/providers/openai.py src/eq_chatbot_core/realtime/providers/gemini_live.py \
  tests/wire_server.py tests/unit/test_embedder_wire.py tests/unit/test_no_model_tables.py
git add <every existing test file edited in Step 13, by name>
git commit -m "[CHG] Embedder, Katalog, Tokenschätzung, Kontextfenster, Realtime ohne Modelltabellen

xfailed:
<file::test — reason, one per line>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GJzy9HGak7N5HG7StkSHWF"
```

(`git rm` in Step 9 already staged the two deletions.)

---

### Task 7: CLI and server mode resolve the model or explain why they cannot

**Files:**
- Modify: `src/eq_chatbot_core/cli.py:1-8, 75-79, 149-230, 419-536, 737-800, 940-1060, 1100-1112`
- Modify: `src/eq_chatbot_core/data/config.toml.example:30-94`
- Modify: `src/eq_chatbot_core/server/app.py:28-48, 117-135, 180-205`
- Create: `tests/unit/test_cli_model_required.py`, `tests/unit/server/test_model_required.py`

**Interfaces:**
- Consumes: `BaseLLMProvider.resolve_model`, `ModelNotSpecifiedError` (Task 1); `config_model(provider)`, `config_path()`, `reset_cache()` from `eq_chatbot_core.utils.config` (existing).
- Produces: `eq_chatbot_core.cli.model_required_message(provider: str) -> str` (names `--model`, `[providers.<provider>]` and the config path); `test-provider`, `chat`, `image`, `listing-assets` exit 1 without a model (chat: JSON `{"error": ...}` on stderr; listing-assets: `click.ClickException`); `eq_chatbot_core.server.app._model_missing_to_http(exc: ModelNotSpecifiedError) -> HTTPException` (status 400, `detail.type == "ModelNotSpecifiedError"`).

- [ ] **Step 1: Write the failing CLI tests — `tests/unit/test_cli_model_required.py`**

```python
"""CLI: the model comes from --model or the config file; otherwise a clear message, no traceback."""

import json

import pytest
from click.testing import CliRunner

from eq_chatbot_core.cli import main
from eq_chatbot_core.utils import config as _config
from tests.wire_server import Reply, chat_body

pytestmark = pytest.mark.unit


def _use_config(tmp_path, monkeypatch, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setenv("EQ_CHATBOT_CONFIG", str(path))
    _config.reset_cache()


@pytest.mark.parametrize(
    "args",
    [
        ["test-provider", "-p", "openai", "-k", "sk-test"],
        ["image", "-p", "openai", "-k", "sk-test", "--prompt", "a cat"],
    ],
    ids=["test-provider", "image"],
)
def test_missing_model_is_explained_without_traceback(args):
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 1
    assert "--model" in result.output and "[providers.openai]" in result.output
    assert "Traceback" not in result.output and isinstance(result.exception, SystemExit)


def test_chat_missing_model_is_a_json_error():
    payload = json.dumps({"messages": [{"role": "user", "content": "x"}]})
    result = CliRunner().invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input=payload)
    assert result.exit_code == 1
    error_line = next(line for line in result.output.splitlines() if line.startswith("{"))
    assert "--model" in json.loads(error_line)["error"]


def test_listing_assets_missing_model(tmp_path):
    recipe = tmp_path / "recipe.json"
    recipe.write_text(
        json.dumps({"schema": "eq-listing-assets/1", "defaults": {"provider": "openai"},
                    "assets": [{"id": "a", "out": "a.png", "prompt": "p"}]}),
        encoding="utf-8",
    )
    result = CliRunner().invoke(main, ["listing-assets", "--recipe", str(recipe), "--api-key", "sk-test"])
    assert result.exit_code == 1
    assert "--model" in result.output and "Traceback" not in result.output


def test_model_from_config_file_is_used(wire_server, tmp_path, monkeypatch):
    _use_config(tmp_path, monkeypatch, f'[providers.mammouth]\nmodel = "cfg-model"\nbase_url = "{wire_server.base_url}"\n')
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("hallo")))
    result = CliRunner().invoke(main, ["test-provider", "-p", "mammouth", "-k", "mm-test"])
    assert result.exit_code == 0, result.output
    assert wire_server.requests[0].json["model"] == "cfg-model"


def test_flag_beats_config_file(wire_server, tmp_path, monkeypatch):
    _use_config(tmp_path, monkeypatch, f'[providers.mammouth]\nmodel = "cfg-model"\nbase_url = "{wire_server.base_url}"\n')
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("hallo")))
    result = CliRunner().invoke(main, ["test-provider", "-p", "mammouth", "-k", "mm-test", "-m", "flag-model"])
    assert result.exit_code == 0, result.output
    assert wire_server.requests[0].json["model"] == "flag-model"
```

- [ ] **Step 2: Write the failing server tests — `tests/unit/server/test_model_required.py`**

```python
"""Server mode: the request's model field (or provider_extra model), else HTTP 400 before any stream."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from eq_chatbot_core.server.app import create_app  # noqa: E402
from tests.wire_server import Reply, chat_body  # noqa: E402

TOKEN = "test-token-with-enough-entropy-aaaaaaaa"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
BODY = {"provider": "openai", "api_key": "sk-test", "messages": [{"role": "user", "content": "x"}]}


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    """Same reason as in test_app.py: sse-starlette binds a singleton event to the first loop."""
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None  # type: ignore[assignment]
    yield
    AppStatus.should_exit_event = None  # type: ignore[assignment]


@pytest.fixture
def client():
    return TestClient(create_app(auth_token=TOKEN))


@pytest.mark.unit
def test_chat_without_model_is_400(client):
    resp = client.post("/chat", json=BODY, headers=AUTH)
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["type"] == "ModelNotSpecifiedError" and detail["provider"] == "openai"
    assert '"model"' in detail["error"]


@pytest.mark.unit
def test_stream_without_model_is_400_before_the_stream(client):
    """Review focus 5: not a 200 event stream that carries an error event."""
    resp = client.post("/chat/stream", json=BODY, headers=AUTH)
    assert resp.status_code == 400
    assert resp.json()["detail"]["type"] == "ModelNotSpecifiedError"


@pytest.mark.unit
def test_model_in_provider_extra_counts(client, wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("hallo")))
    body = {**BODY, "provider": "mammouth", "base_url": wire_server.base_url, "provider_extra": {"model": "extra-model"}}
    resp = client.post("/chat", json=body, headers=AUTH)
    assert resp.status_code == 200 and resp.json()["content"] == "hallo"
    assert wire_server.requests[0].json["model"] == "extra-model"
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_cli_model_required.py tests/unit/server/test_model_required.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: FAILED for the missing-model CLI tests (message has no `--model`), `test_chat_without_model_is_400` (502), `test_stream_without_model_is_400_before_the_stream` (200); the config/flag/provider_extra tests pass already.

- [ ] **Step 4: CLI helper and `resolve_model` docstring**

After `resolve_model` in `cli.py` add:

```python
def model_required_message(provider: str) -> str:
    """Explain where a model comes from; there is no built-in default."""
    from eq_chatbot_core.utils.config import config_path

    return (
        f"No model given for provider '{provider}'. Pass --model/-m, or set "
        f'model = "..." under [providers.{provider}] in {config_path()}.'
    )
```

`resolve_model` docstring → `"""Resolve the model: --model flag > config file > None (the command then stops with model_required_message())."""`.

- [ ] **Step 5: Commands**

`test_provider`: after the API-key check (`sys.exit(1)` at line 189) insert

```python
    if not model:
        click.echo(click.style("Error: ", fg="red") + model_required_message(provider), err=True)
        sys.exit(1)
```

and replace the `if model: ... else: ...` call block with

```python
        response = provider_instance.chat_completion(
            messages=[{"role": "user", "content": message}],
            model=model,
        )
```

`chat`: after the API-key check insert

```python
    if not model:
        click.echo(json.dumps({"error": model_required_message(provider)}), err=True)
        sys.exit(1)
```

put `"model": model,` into the initial `kwargs` dict and delete `if model: kwargs["model"] = model`.

`image`: after the API-key check insert the same three lines as in `test_provider`.

`listing-assets`: comment above the resolution → `# Resolve provider and model: CLI > recipe defaults > config file. The provider falls back to openai; the model has no default.`; after the API-key `ClickException` insert

```python
    if not resolved_model:
        raise click.ClickException(model_required_message(resolved_provider))
```

Docstring examples: in `test_provider` replace `-m claude-3-5-sonnet-20241022` with `-m your-model-id`, `eq-chatbot test-provider -p openai -k sk-...` and `LLM_API_KEY=sk-... eq-chatbot test-provider -p openai` get ` -m your-model-id`, `-m llama3.2:latest` → `-m your-local-model`, `eq-chatbot test-provider -p lm_studio` / `-p local -u ...` get ` -m your-local-model`. In `chat`: `-m claude-3-5-sonnet-20241022` → `-m your-model-id`, `-m gpt-4o-mini` → `-m your-model-id`, the first example gets ` -m your-model-id`. In `image`: the line `Supported providers: openai (gpt-image-1), openrouter (gemini-2.5-flash-image).` → `Supported providers: openai, openrouter. The image model comes from --model or the config file.`; each example gets ` -m your-image-model`. In `listing-assets`: `"defaults": {"provider": "openai", "model": "gpt-image-1"},` → `"defaults": {"provider": "openai", "model": "your-image-model"},`.
`info`: `"    • openai     - GPT-4, GPT-4o, GPT-4.1, o1, o3, o4 series"` → `"    • openai     - OpenAI API (chat, images)"`; `"    • anthropic  - Claude 3, Claude 3.5, Claude 4"` → `"    • anthropic  - Anthropic Messages API"`.

- [ ] **Step 6: `config.toml.example`**

In the header comment replace `optional model (default model).` with `model (used when --model is not given — there is no built-in default).` Replace every commented `# model    = "..."` line (9 cloud lines and the two local `"local-model"` lines) with `# model    = "your-model-id"`.

- [ ] **Step 7: Server mode**

`server/app.py`: import `ModelNotSpecifiedError` in the `eq_chatbot_core.providers` import block. Add before `_provider_error_to_http`:

```python
def _model_missing_to_http(exc: ModelNotSpecifiedError) -> HTTPException:
    """A request without a model is the caller's error: 400, with where to put it."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": f'No model given for provider "{exc.provider}". Set the request\'s "model" field, '
            'or "model" in "provider_extra".',
            "type": "ModelNotSpecifiedError",
            "provider": exc.provider,
            "retry_after": None,
        },
    )
```

First lines of `_provider_error_to_http`:

```python
    if isinstance(exc, ModelNotSpecifiedError):
        return _model_missing_to_http(exc)
```

In `chat_stream`, after the `try/except` that builds `provider_inst`, add:

```python
        # Resolve now: a generator would only raise after the 200 stream started.
        try:
            provider_inst.resolve_model(req.model)
        except ModelNotSpecifiedError as exc:
            raise _model_missing_to_http(exc) from exc
```

- [ ] **Step 8: Run the new tests**

Run: `uv run pytest tests/unit/test_cli_model_required.py tests/unit/server/test_model_required.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: all passed (6 + 3).

- [ ] **Step 9: Existing tests — apply the triage rule**

Run: `uv run pytest tests/unit/ -q -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|passed|failed"`
Expected: failures in `tests/unit/test_cli_chat.py`, `test_cli_image.py`, `test_cli_listing_assets.py` (≈45 invocations without `-m`) where the command now stops before reaching the patched provider → rule 1: add `"-m", "test-model"` to the argument list (listing-assets: `"--model", "test-model"`, or a `"model"` in the recipe's `defaults` when the test is about recipe defaults). Tests that assert "provider default model is used" → rule 2 (`stage 2: no default model; the CLI stops with model_required_message()`). `tests/unit/server/test_app.py` should pass unchanged (its providers are MagicMocks, so `resolve_model` returns a mock). Re-run until `0 failed`.

- [ ] **Step 10: Coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git checkout -- tests/reports/latest.md
git add src/eq_chatbot_core/cli.py src/eq_chatbot_core/data/config.toml.example src/eq_chatbot_core/server/app.py \
  tests/unit/test_cli_model_required.py tests/unit/server/test_model_required.py
git add <every CLI test file edited in Step 9, by name>
git commit -m "[CHG] CLI und Server-Modus: Modell aus --model, Konfiguration oder Anfrage, sonst klare Meldung

xfailed:
<file::test — reason, one per line>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GJzy9HGak7N5HG7StkSHWF"
```

---
### Task 8: Guard test and the remaining docstrings and comments

**Files:**
- Create: `tests/unit/test_no_model_ids_in_source.py`
- Modify: `src/eq_chatbot_core/providers/__init__.py:1-46` (module docstring)
- Modify: `src/eq_chatbot_core/providers/anthropic_provider.py:1-3, 32-41` (docstrings)
- Modify: `src/eq_chatbot_core/providers/langdock_provider.py:4-9, 176-181` and the `_list_google_models` docstring
- Modify: `src/eq_chatbot_core/providers/mammouth_provider.py:4-7, 25-30`, `openai_provider.py:13-22`, `openrouter_provider.py:19-36`, `privatemode_provider.py:44-56` and the `_build_params` docstring

**Interfaces:**
- Consumes: Tasks 1–7 removed every code-level inventory entry (Appendix A).
- Produces: `tests.unit.test_no_model_ids_in_source.MODEL_ID: re.Pattern[str]`, `SPEC_PATTERNS`, `ADDED_PATTERNS`, `_hits(root: Path) -> list[str]`.

- [ ] **Step 1: Write the guard test — `tests/unit/test_no_model_ids_in_source.py`**

```python
"""No model ID, model family or model-specific value anywhere under src/ (stage 2).

Model IDs change every few weeks, so any list in the library is permanently
behind. Models come from the caller — per call or per provider instance. This
test scans every file of the package (code, docstrings, comments, packaged data)
and reports file and line for each hit. Docstring examples use placeholders such
as "your-model-id". Provider and backend names (openai, anthropic, mistral as a
URL segment, codestral as a LangDock backend, ollama) are not model IDs.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src" / "eq_chatbot_core"

# Spec, section "Guard test".
SPEC_PATTERNS = (
    r"gpt-\d",
    r"gpt-image",
    r"chatgpt",
    r"\bo[1-9](-mini|-pro|-preview)?\b",
    r"claude-",
    r"gemini-",
    r"mistral-",
    r"\bllama-",
    r"text-embedding",
    r"whisper",
    r"dall-e",
    r"kokoro",
    r"nemotron",
    r"qwen",
    r"kimi",
    r"minimax",
    r"deepseek",
    r"grok",
    r"sonar",
)
# Found by the stage-2 inventory (plan, Appendix A): IDs and family keys the
# spec patterns miss.
ADDED_PATTERNS = (
    r"\bgpt-oss",
    r"\bgpt-realtime",
    r"voxtral",
    r"codestral-\d",
    r"\bllama\d",
    r"\bmai-ds",
    r"\bcodex-mini",
    r"\baf_bella\b",
    r"""["'](claude|gemini|llama|mistral|cohere)["']""",
)
MODEL_ID = re.compile("|".join(SPEC_PATTERNS + ADDED_PATTERNS), re.IGNORECASE)


def _hits(root: Path) -> list[str]:
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            match = MODEL_ID.search(line)
            if match:
                hits.append(f"{path.relative_to(root.parent)}:{number}: {match.group(0)!r} in {line.strip()[:100]}")
    return hits


def test_no_model_ids_in_source():
    hits = _hits(SRC)
    assert not hits, "Model IDs in src/ — take them from the caller instead:\n" + "\n".join(hits)


@pytest.mark.parametrize(
    "text",
    [
        "openai",
        "OpenAIProvider",
        "anthropic",
        "AnthropicProvider",
        "/mistral/{region}/v1",
        '"codestral": "/mistral/{region}/v1",',
        'backend="codestral"',
        "ollama",
        "OLLAMA_URL",
        "your-model-id",
        "cl100k_base",
        "Gemini Live API",
    ],
)
def test_provider_and_backend_names_are_not_model_ids(text):
    assert not MODEL_ID.search(text)


@pytest.mark.parametrize(
    "text",
    [
        "gpt-5.6-luna",
        "o3",
        "o4-mini",
        "claude-sonnet-5",
        "gemini-3.7-flash",
        "text-embedding-3-small",
        "whisper-large-v3",
        "kokoro-tts-1",
        "nemotron-3-nano-30b-a3b",
        "qwen3.6-35b-a3b",
        "kimi-latest",
        "minimax-428b-m3",
        "deepseek-v3",
        "gpt-image-1",
        "dall-e-3",
        "gpt-oss-120b",
        "gpt-realtime",
        "codestral-2501",
        "llama3.2:latest",
        '"claude": {',
    ],
)
def test_model_ids_are_detected(text):
    assert MODEL_ID.search(text)


def test_hits_are_reported_with_file_and_line(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "m.py").write_text('x = 1\nDEFAULT = "gpt-5.6-luna"\n', encoding="utf-8")
    assert _hits(package) == ["pkg/m.py:2: 'gpt-5.6-luna' in DEFAULT = \"gpt-5.6-luna\""]
```

- [ ] **Step 2: Run it to see what is left**

Run: `uv run pytest tests/unit/test_no_model_ids_in_source.py -q -p no:cacheprovider 2>&1 | tail -40`
Expected: only `test_no_model_ids_in_source` FAILS, listing the docstring/comment lines that Appendix A assigns to Task 8 (providers `__init__`, anthropic, langdock, mammouth, openai, openrouter, privatemode docstrings). Any hit assigned to Tasks 1–7 means that task is incomplete: fix it there, not here.

- [ ] **Step 3: Replace the docstrings**

`providers/__init__.py`, lines 1-46:

```python
"""
LLM Provider adapters for OpenAI, Anthropic, LangDock, OpenRouter, Mammouth, Privatemode, and local servers.

Supports cloud providers (OpenAI, Anthropic, LangDock, OpenRouter, Mammouth, IONOS, Melious, Privatemode, LiteLLM)
and local LLM servers (LM Studio, Ollama) that expose OpenAI-compatible APIs.

There is no default model. Pass ``model=`` per call or to ``get_provider``;
otherwise calls raise ``ModelNotSpecifiedError``. ``list_models()`` shows the ids
a provider offers.

Usage:
    from eq_chatbot_core.providers import get_provider

    # Model per call
    provider = get_provider("openai", api_key="sk-...")
    response = provider.chat_completion(messages=[...], model="your-model-id")

    # Model per provider instance
    provider = get_provider("mammouth", api_key="mm-...", model="your-model-id")
    response = provider.chat_completion(messages=[...])

    # OpenRouter ids carry a vendor prefix
    provider = get_provider("openrouter", api_key="sk-or-...")
    response = provider.chat_completion(messages=[...], model="vendor/your-model-id")

    # Local providers (LM Studio or Ollama): the id the server lists
    provider = get_provider("local", base_url="http://localhost:1234/v1", model="your-local-model")

    # LiteLLM / any OpenAI-compatible gateway (base_url is REQUIRED, no default)
    provider = get_provider("litellm", api_key="...", base_url="https://your-gateway.example/v1")

    # IONOS AI Model Hub and Melious.ai (EU-hosted; base_url has a default)
    provider = get_provider("ionos", api_key="...", model="your-model-id")
    provider = get_provider("melious", api_key="sk-mel-...", model="your-model-id")

    # Privatemode (end-to-end encrypted, via the locally-run attesting proxy).
    # The proxy usually holds the API key, so none is passed here.
    provider = get_provider("privatemode", model="your-model-id")  # http://localhost:8080/v1
"""
```

`anthropic_provider.py`: module docstring `Anthropic Claude provider implementation.` → `Anthropic provider implementation.`; class docstring →

```python
    """
    Anthropic Messages API provider.

    Pass the model per call or as ``model=`` to the constructor; ``list_models()``
    returns the ids the account can use.
    """
```

`langdock_provider.py` module docstring lines 4-9 →

```
LangDock is a unified API gateway with several backends:
- openai: OpenAI-compatible chat completions
- anthropic: Anthropic Messages API
- google: Google Generative Language API (via Vertex AI)
- codestral: fill-in-the-middle code completion
- agent: LangDock custom agents with knowledge
```

class docstring `Backends:` block (lines 176-181) →

```
    Backends:
    - openai: OpenAI-compatible chat completions
    - anthropic: Anthropic Messages API
    - google: Google Generative Language API (via Vertex AI)
    - codestral: fill-in-the-middle code completion (FIM)
    - agent: LangDock custom agents with knowledge folders
```

`_list_google_models` docstring →

```python
        """List the Google models LangDock offers this workspace, live.

        The endpoint is the one LangDock's "Invalid model, available models are: …"
        error is generated from, so the list cannot go stale. Ids come back as
        ``models/<id>``; the prefix is stripped because sending it back is a 400.
        """
```

`mammouth_provider.py` module docstring lines 4-7 →

```
Mammouth AI (https://mammouth.ai) provides access to models from many vendors
through one OpenAI-compatible API. The wire protocol is handled by
OpenAICompatibleProvider; only the model listing is Mammouth-specific.
```

class docstring →

```python
    """
    Mammouth AI API provider.

    Model ids carry no vendor prefix (unlike OpenRouter's ``vendor/model``);
    ``list_models()`` returns them.
    """
```

`openai_provider.py` class docstring →

```python
    """
    OpenAI API provider: chat completions and image generation.

    Pass the chat model per call or as ``model=``, the image model per call or as
    ``image_model=``; ``list_models()`` returns every id the account can use.
    """
```

`openrouter_provider.py` class docstring →

```python
    """
    OpenRouter API provider for 400+ models from many vendors.

    Model ids follow the format ``vendor/model-name``; ``list_models()`` returns
    them with the metadata OpenRouter reports.
    """
```

`privatemode_provider.py` module docstring, the `Models` section and the endpoint list (lines 44-56) →

```
Models (see https://docs.privatemode.ai/models/overview/)
---------------------------------------------------------
Model ids change over time and are discovered live via ``GET /v1/models``; no
static catalog is bundled on purpose, and there is no default model.

Reference endpoints (OpenAI-compatible, served by the proxy):
- POST /v1/chat/completions   (chat + streaming)
- GET  /v1/models
- POST /v1/embeddings
- POST /v1/audio/transcriptions
```

`_build_params` docstring: `` ``{"thinking": false}`` to skip Kimi's reasoning pass`` → `` ``{"thinking": false}`` to skip a model's reasoning pass``.

- [ ] **Step 4: Run the guard test**

Run: `uv run pytest tests/unit/test_no_model_ids_in_source.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected: `34 passed` (1 scan + 12 non-matches + 20 matches + 1 report format).

- [ ] **Step 5: Prove the inventory is empty**

Every Appendix A entry names the text that matched. The guard pattern must match each of them (otherwise the guard could miss a re-introduction), and the guard passing in Step 4 shows none is left.

```bash
uv run python - <<'EOF'
import re
import pathlib
from tests.unit.test_no_model_ids_in_source import MODEL_ID
plan = pathlib.Path("docs/superpowers/plans/2026-10-07-no-model-ids-in-source.md").read_text(encoding="utf-8")
appendix = plan.split("\n## Appendix A")[1]
tokens = re.findall(r" — `([^`]+)` \|", appendix)
print(len(tokens), "inventory tokens; not matched by the guard:", [t for t in tokens if not MODEL_ID.search(t)])
EOF
```

Expected: `255 inventory tokens; not matched by the guard: []` (the two JSON rows carry no token; their files are gone).

- [ ] **Step 6: Full suite, coverage, lint, commit**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
git checkout -- tests/reports/latest.md
git add tests/unit/test_no_model_ids_in_source.py src/eq_chatbot_core/providers/__init__.py \
  src/eq_chatbot_core/providers/anthropic_provider.py src/eq_chatbot_core/providers/langdock_provider.py \
  src/eq_chatbot_core/providers/mammouth_provider.py src/eq_chatbot_core/providers/openai_provider.py \
  src/eq_chatbot_core/providers/openrouter_provider.py src/eq_chatbot_core/providers/privatemode_provider.py
git commit -m "[ADD] Wächtertest: keine Modell-IDs unter src/, Docstrings mit Platzhaltern

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GJzy9HGak7N5HG7StkSHWF"
```

---

### Task 9: Regenerate the public-API snapshot (own reviewed step)

**Files:**
- Modify: `tests/compat/snapshot.py:17-29` (`CLASSES` gains `AnthropicProvider`)
- Modify: `tests/compat/public_api.json` (regenerated)
- Modify: `tests/unit/test_public_api_compat.py` (stage-2 allowance removed)

**Interfaces:**
- Consumes: the final provider surface of Tasks 1–8.
- Produces: a snapshot of the 4.0 surface; `test_public_surface_unchanged` strict again (no `_STAGE2_CHANGES`).

- [ ] **Step 1: List every removed or changed member against the old snapshot**

```bash
uv run python - <<'EOF'
import json
from tests.compat.snapshot import SNAPSHOT_PATH, public_surface
old = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
new = public_surface()
for cls, body in old.items():
    if not isinstance(body, dict):
        print(f"{cls}: added {sorted(set(new[cls]) - set(body))}, removed {sorted(set(body) - set(new[cls]))}")
        continue
    live = new[cls]
    for kind in ("members", "constants"):
        for name in sorted(body[kind]):
            if name not in live[kind]:
                print(f"{cls}.{name}: removed")
            elif live[kind][name] != body[kind][name]:
                print(f"{cls}.{name}: {body[kind][name]}  ->  {live[kind][name]}")
EOF
```

Expected — exactly these items (one printed line per member), nothing else:
- `providers.__all__: added ['ModelNotSpecifiedError'], removed []`
- `OpenAIProvider.__init__` changed (adds `model`, `image_model`); `CHAT_MODEL_PREFIXES`, `DEFAULT_IMAGE_MODEL`, `MODEL_CONTEXT_LENGTHS`, `NEW_API_MODELS` removed
- `MammouthProvider.__init__` changed (adds `model`); `REASONING_MODEL_PREFIXES` removed
- `OpenRouterProvider.__init__` changed (adds `model`, `image_model`); `DEFAULT_IMAGE_MODEL`, `REASONING_MODEL_PREFIXES` removed
- `LocalLLMProvider.__init__` changed (adds `model`)
- `LangDockProvider.__init__` changed (adds `model`); `MODEL_CONTEXT_LENGTHS`, `REASONING_MODELS` removed
- `LangDockAgentManager.create_agent` changed (`model: str`, no default)
- `IonosProvider.DEFAULT_MODEL`, `MeliousProvider.DEFAULT_MODEL`, `PrivatemodeProvider.DEFAULT_MODEL` removed
- `LiteLLMProvider.__init__` changed (adds keyword-only `tts_model`, `tts_voice`, `stt_model`); `text_to_speech`, `transcribe` changed (`model`/`voice` default `None`); `DEFAULT_MODEL` removed
A line not in this list is an unintended API change: fix the code, do not continue.

- [ ] **Step 2: Add Anthropic to the snapshot**

In `tests/compat/snapshot.py` add to `CLASSES` after the OpenAI entry:

```python
    ("eq_chatbot_core.providers.anthropic_provider", "AnthropicProvider"),
```

- [ ] **Step 3: Regenerate and review**

Run: `uv run python -m tests.compat.snapshot && git diff --stat tests/compat/public_api.json`
Expected: `wrote .../tests/compat/public_api.json`; one changed file. Then `git diff tests/compat/public_api.json | grep -E '^[-+]  ' | head -120` — the removed lines are exactly Step 1's items, the added lines are the new signatures, `resolve_model` (every provider), and the new `AnthropicProvider` block.

- [ ] **Step 4: Remove the stage-2 allowance**

Restore `tests/unit/test_public_api_compat.py` to its strict form:

```python
"""The public provider surface must match the reviewed snapshot (tests/compat/public_api.json).

A failure here means a consumer (Odoo module, CLI, server mode) may break. Fix the
code, not the snapshot — regenerating it is a reviewed API change.
"""

import json

import pytest

from tests.compat.snapshot import SNAPSHOT_PATH, public_surface

pytestmark = pytest.mark.unit

# `client` changes type (httpx2.Client -> openai.OpenAI) for providers moving off
# hand-written HTTP; it is an implementation detail, documented in the release notes.
_ALLOWED_DRIFT = {"client"}


def _strip(surface: dict) -> dict:
    return {
        cls: {
            "members": {k: v for k, v in body["members"].items() if k not in _ALLOWED_DRIFT},
            "constants": body["constants"],
        }
        if isinstance(body, dict)
        else body
        for cls, body in surface.items()
    }


def test_public_surface_unchanged():
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    actual = public_surface()
    for cls, body in _strip(expected).items():
        if not isinstance(body, dict):
            assert actual[cls] == body, cls
            continue
        live = _strip(actual)[cls]
        missing = set(body["members"]) - set(live["members"])
        assert not missing, f"{cls} lost public members: {sorted(missing)}"
        changed = {k for k in body["members"] if live["members"][k] != body["members"][k]}
        assert not changed, f"{cls} changed signatures: {sorted(changed)}"
        lost_or_changed = {k for k, v in body["constants"].items() if live["constants"].get(k) != v}
        assert not lost_or_changed, f"{cls} constants lost or changed: {sorted(lost_or_changed)}"


def test_wire_server_serves_a_chat_completion(wire_server):
    from openai import OpenAI

    from tests.wire_server import Reply, chat_body

    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("hallo")))
    client = OpenAI(api_key="k", base_url=wire_server.base_url, max_retries=0)
    reply = client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
    assert reply.choices[0].message.content == "hallo"
    assert wire_server.requests[0].json["model"] == "m"
```

Run: `uv run pytest tests/unit/test_public_api_compat.py -q -p no:cacheprovider 2>&1 | tail -2`
Expected: `2 passed`.

- [ ] **Step 5: Commit (body = Step 1's list)**

```bash
git checkout -- tests/reports/latest.md
git add tests/compat/snapshot.py tests/compat/public_api.json tests/unit/test_public_api_compat.py
git commit -m "[CHG] API-Momentaufnahme 4.0 neu erzeugt (geprüfte Änderung)

Entfernt oder geändert gegenüber der Momentaufnahme vor Stufe 2:
<the lines printed by Step 1, verbatim>

Neu: ModelNotSpecifiedError in providers.__all__, resolve_model() auf allen Providern,
AnthropicProvider in der Momentaufnahme.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GJzy9HGak7N5HG7StkSHWF"
```

---

### Task 10: Documentation, live verification, deletion list, report

**Files:**
- Modify: `CLAUDE.md`, `AGENTS.md` (identical apart from lines 1 and 3)
- Modify: `docs/providers.md` (EN and DE), `docs/cli.md` (EN and DE), `docs/reasoning.md` (EN and DE)
- Modify: `CHANGELOG.md` (`## [Unreleased]`)
- Create: `tests/integration/test_anthropic_live.py`
- Modify: `tests/integration/test_openai_live.py:470-570` (default-model classes)

**Interfaces:**
- Consumes: everything above; live fixtures `*_api_key`, `*_resolved_model`, `clean_param_memory` from `tests/conftest.py`.
- Produces: documentation of the 4.0 behaviour; the live proof; the deletion list for the Captain.

- [ ] **Step 1: `CLAUDE.md`**

- After the Provider Factory code block (after line 83) insert:

```markdown
There is no default model. Pass `model=` per call or to `get_provider(..., model=...)`
(images: `image_model=`; LiteLLM audio: `tts_model=`, `tts_voice=`, `stt_model=`); otherwise
calls raise `ModelNotSpecifiedError` (a `ProviderError`). Never add a model ID, family prefix
or model-specific value to `src/` — `tests/unit/test_no_model_ids_in_source.py` fails on it.
Tests take models from `tests/model_registry.py`.
```

- In the Provider Base Class code block replace `    default_model: str              # Property: Default model ID` with
  `    default_model: str | None       # Property: the constructor's model, or None` and add the line `    def resolve_model(model) -> str          # call model > constructor model > ModelNotSpecifiedError` after `list_models()`.
- In the paragraph below it replace the last sentence with: `Whether a model accepts `temperature`, wants `max_completion_tokens` or takes `reasoning_effort` is learned at runtime (`providers/param_learning.py`, for Anthropic via `providers/anthropic_shared.py`); never add a model to a list to fix it. `list_models()` reports what the provider says — unknown is `None`.`
- Exception hierarchy: insert `├── ModelNotSpecifiedError # no model per call or per instance` below `ProviderError (base)`.
- Module structure: `param_learning.py` comment → `# Learns per endpoint/model whether temperature / max_tokens / reasoning_effort are accepted`; add `│   ├── anthropic_shared.py # Temperature learning + capability helper for Anthropic and LangDock-anthropic` below it; `temperature_constraints.py` comment → `# Provider-level clamp, apply_anthropic_temperature()`; `embedder.py` comment → `# Embedding generation (OpenAI, LangDock, Melious); model required, size discovered`; `data/` comment → `# config.toml.example (no bundled capability catalog)`.
- Dependencies paragraph: `use `apply_anthropic_temperature()` from `providers/temperature_constraints.py`, which clamps and routes the value into `extra_body`.` → `use `apply_anthropic_temperature(params, temperature)` from `providers/temperature_constraints.py`, which clamps to 0–1 and routes the value into `extra_body`; whether a model takes it at all is learned (`providers/anthropic_shared.py`).`

- [ ] **Step 2: `AGENTS.md` — the same edits**

Apply Step 1's edits to `AGENTS.md`.
Run: `diff <(sed '1d;3d' CLAUDE.md) <(sed '1d;3d' AGENTS.md) && echo identical`
Expected: `identical`.

- [ ] **Step 3: `docs/providers.md` — English**

- Quick start code block: `get_provider(...)` lines unchanged; the two `model="gpt-4o",` → `model="your-model-id",`; after the code block add:

```markdown
### Choosing a model

There is no default model. Pass `model=` per call, or once to `get_provider(..., model=...)`;
without either, the call raises `ModelNotSpecifiedError` (a `ProviderError`) before anything
is sent. Image generation takes `image_model=` (OpenAI, OpenRouter), LiteLLM's audio takes
`tts_model=`, `tts_voice=` and `stt_model=`. LangDock's `agent` backend needs no model — the
agent's model is configured in LangDock.

`list_models()` returns every model the provider lists — nothing is filtered by name, so
OpenAI's list includes embedding and audio models. Metadata the provider does not report is
`None` (unknown), never a guess. Treat `supports_temperature is None` as "allowed — the
library adapts"; it becomes `False` once a model rejected `temperature`.
```

- Replace the body of `### Parameter learning` (up to, not including, the paragraph starting `Errors are mapped by HTTP status`) with:

```markdown
Whether a model accepts `temperature`, wants `max_completion_tokens` instead of `max_tokens`, or takes `reasoning_effort` is not kept in a model list: the library learns it at runtime. This applies to every OpenAI-wire provider (OpenAI, Mammouth, OpenRouter, Local, IONOS, Melious, LiteLLM, Privatemode, LangDock's `openai` backend) and, for `temperature`, to Anthropic and LangDock's `anthropic` backend.

- If the endpoint rejects `temperature` as unsupported (Anthropic says "deprecated"), the request is repeated once without it.
- If it rejects `max_tokens`, the request is repeated once with `max_completion_tokens`. OpenAI itself always gets `max_completion_tokens`.
- If it rejects `reasoning_effort` (passed per call, or LangDock's constructor setting), the request is repeated once without it.
- Each parameter is retried at most once. The answer is remembered per endpoint and model for the rest of the process, so the cost is one extra request the first time a model is used.
- A range error ("temperature: range: 0..1") is not a rejection: it reaches the caller.
- On OpenRouter, `list_models()` pre-seeds "temperature unsupported" for models whose metadata does not offer `temperature`; a learned rejection always wins over the list.
```

- Replace the body of `### Temperature clamping` (heading stays) with:

```markdown
Only provider-level ranges are applied; there is no per-model table.

| Provider | Range | Behavior |
|----------|-------|----------|
| OpenAI-wire providers, LangDock `google` | 0–2 | Clamped to `[0, 2]` |
| Anthropic, LangDock `anthropic` | 0–1 | Clamped to `[0, 1]`, sent in `extra_body` |

A model that takes no temperature at all rejects it once; the library drops it and remembers that (see Parameter learning).
```

- In `### Capability matrix` rename the column `Temperature clamping` to `Temperature range` (values unchanged).

- [ ] **Step 4: `docs/providers.md` — Deutsch**

Same changes in the German half, with German typography („…“):
- Quick start: `model="gpt-4o",` → `model="your-model-id",` (twice); then:

```markdown
### Modell wählen

Es gibt kein Standardmodell. `model=` wird pro Aufruf übergeben oder einmal an `get_provider(..., model=...)`; fehlt beides, wirft der Aufruf `ModelNotSpecifiedError` (ein `ProviderError`), bevor etwas gesendet wird. Bildgenerierung nimmt `image_model=` (OpenAI, OpenRouter), die Audio-Funktionen von LiteLLM nehmen `tts_model=`, `tts_voice=` und `stt_model=`. Das `agent`-Backend von LangDock braucht kein Modell — das Modell des Agenten ist in LangDock eingestellt.

`list_models()` liefert jedes Modell, das der Provider auflistet — nichts wird nach Namen gefiltert, die Liste von OpenAI enthält also auch Embedding- und Audio-Modelle. Metadaten, die der Provider nicht meldet, sind `None` (unbekannt), nie geraten. `supports_temperature is None` heißt „erlaubt — die Bibliothek passt sich an“; nach einer Ablehnung wird daraus `False`.
```

- `### Parameter-Lernen` body (up to the error-mapping paragraph):

```markdown
Ob ein Modell `temperature` annimmt, statt `max_tokens` lieber `max_completion_tokens` will oder `reasoning_effort` versteht, steht in keiner Modellliste: Die Bibliothek lernt es zur Laufzeit. Das gilt für jeden Provider mit OpenAI-Protokoll (OpenAI, Mammouth, OpenRouter, Local, IONOS, Melious, LiteLLM, Privatemode, LangDocks `openai`-Backend) und für `temperature` auch für Anthropic und LangDocks `anthropic`-Backend.

- Lehnt der Endpunkt `temperature` als nicht unterstützt ab (Anthropic schreibt „deprecated“), wird die Anfrage einmal ohne wiederholt.
- Lehnt er `max_tokens` ab, wird sie einmal mit `max_completion_tokens` wiederholt. OpenAI selbst bekommt immer `max_completion_tokens`.
- Lehnt er `reasoning_effort` ab (pro Aufruf oder als LangDock-Konstruktorwert), wird sie einmal ohne wiederholt.
- Jeder Parameter wird höchstens einmal wiederholt. Das Ergebnis gilt je Endpunkt und Modell für den Rest des Prozesses — es kostet also eine zusätzliche Anfrage beim ersten Einsatz eines Modells.
- Ein Bereichsfehler („temperature: range: 0..1“) ist keine Ablehnung: Er erreicht den Aufrufer.
- Bei OpenRouter setzt `list_models()` „temperature nicht unterstützt“ vorab für Modelle, deren Metadaten `temperature` nicht anbieten; eine gelernte Ablehnung hat immer Vorrang vor der Liste.
```

- `### Temperature-Clamping` body:

```markdown
Es gelten nur Bereiche auf Provider-Ebene; eine Tabelle je Modell gibt es nicht.

| Provider | Bereich | Verhalten |
|----------|---------|-----------|
| Provider mit OpenAI-Protokoll, LangDock `google` | 0–2 | Auf `[0, 2]` begrenzt |
| Anthropic, LangDock `anthropic` | 0–1 | Auf `[0, 1]` begrenzt, in `extra_body` gesendet |

Ein Modell, das gar keine Temperatur annimmt, lehnt sie einmal ab; die Bibliothek lässt sie dann weg und merkt sich das (siehe Parameter-Lernen).
```

- `### Capability-Matrix`: column `Temperature-Clamping` → `Temperaturbereich`.

- [ ] **Step 5: `docs/cli.md` and `docs/reasoning.md`**

`docs/cli.md`:
- `| `-m`, `--model` | Model id (defaults to provider's `default_model`) |` and `| `-m`, `--model` | Model id (provider default if omitted) |` → `| `-m`, `--model` | Model id (required unless `model` is set in the config file) |`
- `| model | `--model` > config > provider default |` → `| model | `--model` > config > error (no default) |`
- `| `-m`, `--model` | Modell-ID (Default: `default_model` des Providers) |` and `| `-m`, `--model` | Modell-ID (Provider-Default wenn weggelassen) |` → `| `-m`, `--model` | Modell-ID (Pflicht, sofern `model` nicht in der Konfigurationsdatei steht) |`
- `| model | `--model` > Config > Provider-Default |` → `| model | `--model` > Config > Fehler (kein Default) |`
- The examples `-m claude-3-5-sonnet-20241022` (EN line 33, DE line 295) → `-m your-model-id`; the `test-provider -p openai` and `image` examples get ` -m your-model-id` / ` -m your-image-model`; `# Prompt inline, default model, write to output.png` → `# Prompt inline, write to output.png`; `# Prompt inline, Default-Modell, Ausgabe nach output.png` → `# Prompt inline, Ausgabe nach output.png`. The `test-provider` example blocks (EN and DE) get ` -m your-model-id` on the `-p openai` line and ` -m your-local-model` on the `-p local` line.

`docs/reasoning.md`: in the English and the German code example replace `catalog = CapabilityCatalog.from_snapshot()   # or .from_remote() for the live catalog` / `catalog = CapabilityCatalog.from_snapshot()   # oder .from_remote() für den Live-Katalog` with `catalog = CapabilityCatalog.from_remote()   # empty catalog (lookup() -> None) when offline` / `catalog = CapabilityCatalog.from_remote()   # leerer Katalog (lookup() -> None), wenn offline`; in the sentences before them replace `ships a curated catalog (`data/capability_catalog.json`)` with `reads a curated catalog hosted by Equitania` and `liefert einen kuratierten Katalog (`data/capability_catalog.json`)` with `liest einen von Equitania gehosteten, kuratierten Katalog`.

- [ ] **Step 6: `CHANGELOG.md`**

Under `## [Unreleased]`, before `### Changed`, insert:

```markdown
### Removed (breaking)

- Built-in default models: `DEFAULT_MODEL` on every provider and the module-level `DEFAULT_MODEL` aliases (`ionos_provider`, `melious_provider`, `litellm_provider`, `privatemode_provider`), `OpenAIProvider.DEFAULT_IMAGE_MODEL`, `OpenRouterProvider.DEFAULT_IMAGE_MODEL`, `litellm_provider.DEFAULT_TTS_MODEL`, `DEFAULT_TTS_VOICE`, `DEFAULT_STT_MODEL`, the per-backend defaults of `LangDockProvider`, the default of `LangDockAgentManager.create_agent(model=...)`, the default models of `OpenAIRealtimeConfig` and `GeminiLiveConfig`.
- Name lists: `MODEL_TEMPERATURE_CONSTRAINTS`, `DEFAULT_TEMP_CONSTRAINTS`, `get_temperature_constraints()`, `strip_provider_prefix()` (`providers/temperature_constraints.py`), `OpenAIProvider.NEW_API_MODELS`, `CHAT_MODEL_PREFIXES`, `MODEL_CONTEXT_LENGTHS`, `LangDockProvider.REASONING_MODELS`, `MODEL_CONTEXT_LENGTHS`, `MammouthProvider.REASONING_MODEL_PREFIXES`, `OpenRouterProvider.REASONING_MODEL_PREFIXES`, `OpenAIEmbedder.MODELS`, `ContextWindowManager.MODEL_LIMITS`, the encoding map in `estimate_tokens()`.
- The bundled capability snapshot (`data/capability_catalog.json`, `data/capability_overrides.json`) and `CapabilityCatalog.from_snapshot()`.

### Changed (stage 2: no model IDs in source)

- `ModelNotSpecifiedError(ProviderError)` is raised when neither the call nor the provider instance names a model (chat, stream, image, TTS, STT, embedders). Every provider constructor takes `model=`; OpenAI and OpenRouter take `image_model=`; LiteLLM takes `tts_model=`, `tts_voice=`, `stt_model=`. New `resolve_model()` on every provider.
- `clamp_temperature(temperature, *, maximum=2.0)` and `apply_anthropic_temperature(params, temperature)` lost their model argument and apply provider-level ranges only.
- Parameter learning also covers `reasoning_effort` and, for `temperature`, Anthropic and LangDock's anthropic backend (Anthropic's "deprecated" wording and error envelope are recognised).
- `OpenAIProvider` always sends `max_completion_tokens`; every other OpenAI-wire provider sends `max_tokens` and learns otherwise. `reasoning_effort` is sent whenever set.
- `list_models()` returns every model the provider lists; values the provider does not report are `None`.
- Embedders: `dimensions` may be passed, else it is read from the first response; `HybridRetriever.ensure_collection()` raises when the size is unknown.
- CLI: model from `--model`, else the config file, else a message and exit code 1. Server mode: the request's `model`, else HTTP 400 (streams too).
- `tests/unit/test_no_model_ids_in_source.py` fails on any model ID under `src/`.

### Upgrading from 3.x

- Pass `model=` per call or to the provider constructor; without it calls raise `ModelNotSpecifiedError`. Same for `generate_image` (`image_model=`), `text_to_speech` (`tts_model=`, `tts_voice=`), `transcribe` (`stt_model=`) and the embedders.
- `list_models()` returns all provider models; `None` means unknown. Treat `supports_temperature is None` as "allowed — the library adapts".
- Removed constants and functions: see "Removed" above.
- Embedders: pass `dimensions` when creating a vector collection before the first embed call.
- The bundled capability snapshot is gone; offline the catalog is empty.
- `ContextWindowManager`: pass `context_length=` (for example from `list_models()`), else 128000 is assumed.
- Realtime: pass `model=` to `OpenAIRealtimeConfig` / `GeminiLiveConfig`.
```

- [ ] **Step 7: Live tests — replace the default-model checks with registry checks**

In `tests/integration/test_openai_live.py`:
- Mark `TestLangDockDefaultsAreLive.test_backend_defaults_are_actually_available`, `TestProviderDefaultsAreLive.test_default_model_is_still_served` and `TestProviderDefaultsAreLive.test_default_model_actually_answers` with `@pytest.mark.xfail(reason="stage 2: providers have no built-in default model; replaced by TestRegistryModelsAreLive", run=False)`.
- Append:

```python
@pytest.mark.integration
class TestRegistryModelsAreLive:
    """The registry model appears in list_models() and answers — set via the constructor, as callers now must."""

    @pytest.mark.parametrize(
        ("provider_name", "key_fixture", "model_fixture", "extra"),
        [
            ("openai", "openai_api_key", "openai_resolved_model", {}),
            ("anthropic", "anthropic_api_key", "anthropic_resolved_model", {}),
            ("openrouter", "openrouter_api_key", "openrouter_resolved_model", {}),
            ("mammouth", "mammouth_api_key", "mammouth_resolved_model", {}),
            ("melious", "melious_api_key", "melious_resolved_model", {}),
            ("ionos", "ionos_api_key", "ionos_resolved_model", {}),
            ("langdock", "langdock_api_key", "langdock_resolved_model", {"backend": "openai"}),
            ("langdock", "langdock_api_key", "langdock_anthropic_resolved_model", {"backend": "anthropic"}),
            ("langdock", "langdock_api_key", "langdock_google_resolved_model", {"backend": "google"}),
        ],
        ids=["openai", "anthropic", "openrouter", "mammouth", "melious", "ionos", "ld-openai", "ld-anthropic", "ld-google"],
    )
    def test_registry_model_is_listed_and_answers(self, request, provider_name, key_fixture, model_fixture, extra):
        api_key = request.getfixturevalue(key_fixture)
        if not api_key:
            pytest.skip(f"{key_fixture.upper()} not set")
        model = request.getfixturevalue(model_fixture)
        provider = get_provider(provider_name, api_key=api_key, model=model, **extra)

        assert model in {m["id"] for m in provider.list_models()}
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say OK"}], temperature=0.7, max_tokens=512
        )
        assert response.content.strip()
```

Create `tests/integration/test_anthropic_live.py`:

```python
"""Anthropic live: temperature learning without a name list (stage 2)."""

import logging

import pytest

from eq_chatbot_core.providers import get_provider

# Probed 07.10.2026: answers "`temperature` is deprecated for this model." Test data.
TEMPERATURE_DEPRECATED_MODEL = "claude-sonnet-5"
_LOGGER = "eq_chatbot_core.providers.anthropic_provider"


@pytest.mark.integration
def test_deprecated_temperature_is_learned_once(anthropic_api_key, clean_param_memory, caplog):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    provider = get_provider("anthropic", api_key=anthropic_api_key)
    messages = [{"role": "user", "content": "Say OK"}]

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        first = provider.chat_completion(messages, model=TEMPERATURE_DEPRECATED_MODEL, temperature=0.7, max_tokens=64)
    assert first.content.strip()
    assert "rejected 'temperature'" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        second = provider.chat_completion(
            messages, model=TEMPERATURE_DEPRECATED_MODEL, temperature=0.7, max_tokens=64
        )
    assert second.content.strip()
    assert "rejected" not in caplog.text  # the second call sends no retry


@pytest.mark.integration
def test_chat_and_stream_with_the_registry_model(anthropic_api_key, anthropic_resolved_model):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    from tests.integration.live_checks import check_chat, check_stream

    provider = get_provider("anthropic", api_key=anthropic_api_key)
    check_chat(provider, anthropic_resolved_model)
    check_stream(provider, anthropic_resolved_model)
```

- [ ] **Step 8: Run the live suite once (costs money)**

Run: `uv run pytest tests/integration/ -q -p no:cacheprovider -m integration 2>&1 | grep -E "^(FAILED|ERROR)|passed|failed|skipped"`
Expected:
- `test_anthropic_live.py` both passed (the learning proof: first call logs one `rejected 'temperature'`, second call none).
- `TestRegistryModelsAreLive`: passed for openai, anthropic, mammouth, melious, ionos and the three LangDock backends with configured keys; `openrouter` fails or errors with HTTP 401 "User not found" in its resolver — expected (configured key rejected), recorded as unverified.
- The three old default-model tests: xfailed (not run).
- LM Studio/Ollama tests: skipped (`SKIP_LOCAL_TESTS` default true). Privatemode: skipped unless the local proxy answers.
- Any other failure whose message is `No model specified for provider …`: a live test that relied on a default — pass its provider's `*_resolved_model` fixture as `model=` (triage rule 1), then re-run only that test: `uv run pytest <file>::<test> -q -p no:cacheprovider -m integration`. Anything else is a regression: stop and investigate.

- [ ] **Step 9: Collect the deletion list and ask once**

```bash
grep -rn 'reason="stage 2:' tests/ | sed -E 's/:[0-9]+:.*reason="/ — /; s/".*//' | sort
grep -rln '"stage 2:' tests/ | xargs grep -ln "allow_module_level=True"
```

Present the combined list (`file::test — reason`, modules marked as whole modules) to the Captain together with the stage-1 note that none of them was deleted, and ask: „Darf ich diese als xfail/skip markierten Tests löschen? (ja/nein)“ — wait. On "ja": delete exactly those functions/modules, run the unit suite (`0 failed`, coverage ≥ 83 %), and commit as `[CHG] Tests: durch Stufe 2 überholte Tests entfernt` with the list in the body and the two trailer lines. On "nein": leave them and note it in the report.

- [ ] **Step 10: Final verification**

```bash
uv run pytest tests/unit/ -q -p no:cacheprovider --cov=eq_chatbot_core 2>&1 | tail -3
uv run pytest tests/unit/test_no_model_ids_in_source.py tests/unit/test_public_api_compat.py -q -p no:cacheprovider 2>&1 | tail -1
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/
git status --short
```

Expected: unit suite `0 failed`, coverage ≥ 83 %; guard and compatibility tests passed; ruff/mypy clean; `git status` shows only the Captain's `tests/model_registry.py` and possibly `tests/reports/latest.md` (restore it with `git checkout -- tests/reports/latest.md`).

- [ ] **Step 11: Commit docs and live tests**

```bash
git checkout -- tests/reports/latest.md
git add CLAUDE.md AGENTS.md docs/providers.md docs/cli.md docs/reasoning.md CHANGELOG.md \
  tests/integration/test_anthropic_live.py tests/integration/test_openai_live.py
git add <every other integration test file edited in Step 8, by name>
git commit -m "[CHG] Doku und Live-Tests: kein Standardmodell, Modelle aus der Registry

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GJzy9HGak7N5HG7StkSHWF"
```

- [ ] **Step 12: Report to the Captain (German, plain sentences)**

Cover: what was verified live and with which models (from the resolver output), that the Anthropic learning was proven live, that OpenRouter stayed unverified (key answers 401), that LM Studio/Ollama and — unless its proxy ran — Privatemode were not run, that `reasoning_effort` learning is proven on the wire server only, the deletion list and the Captain's decision, the size of the change (`git diff --stat 8ae3887 -- src/eq_chatbot_core/ | tail -1`), and the proposal from the spec: before releasing 4.0.0 via `/afterwork`, check the Odoo chatbot module for calls without a model (outside this repository).

---

## Self-review

1. **Spec coverage.** Model required for chat/stream/image/TTS/STT/embed → Tasks 1, 6. `ModelNotSpecifiedError(ProviderError)` exported, message names both places → Task 1. Constructor `model=` incl. OpenAI, Mammouth, OpenRouter, Local, Anthropic, LangDock; LiteLLM `tts_model`/`tts_voice`/`stt_model`; OpenAI/OpenRouter `image_model` → Task 1. `default_model` non-abstract → Task 1. Constants and module aliases removed → Task 1. CLI and server mode → Task 7. Temperature table, `get_temperature_constraints`, `strip_provider_prefix` (moved, still used by the catalog), clamp signatures → Task 5. "deprecated" recognition → Task 2 (plus the envelope unwrap the spec does not mention but the real SDK needs). `reasoning_effort` learnable → Task 2; sent whenever set, prefixes/`REASONING_MODELS` removed → Task 5. Anthropic + LangDock anthropic learning, `max_tokens` not learned there → Task 3. `NEW_API_MODELS`, both `_uses_new_token_api`, OpenAI always `max_completion_tokens` → Task 5. Prefix filters, context tables, name-based vision, `_get_known_anthropic_models`, `None` metadata, learned `supports_temperature`, OpenRouter fields from the API → Task 4. Embedders, rate limiter, catalog + package data → Task 6. Guard test with file and line, provider names as non-matches → Task 8. Wire-server tests for every new behaviour; Anthropic against the real SDK on the wire server; live `claude-sonnet-5` at 0.7 without a second retry; registry tests replacing the three default tests; xfail + batched deletion list; snapshot in its own reviewed step; coverage 83 % → Tasks 1–10. CHANGELOG "Upgrading from 3.x" → Task 10.
2. **Placeholder scan.** The only angle-bracket text is in commit bodies and `git add` lines that record which existing test files a triage step touched; those lists depend on the run and are records, not code. No "TBD", no "similar to Task N", every code step has code.
3. **Type consistency.** `resolve_model(model: str | None = None) -> str` (Tasks 1, 7); `ModelNotSpecifiedError(provider, *, what, argument, constructor_argument, hint)` (Tasks 1, 6); `learn_from_rejection(error, base_url, model, params, adjusted, *, provider, logger, only)` (Tasks 2, 3); `apply(..., *, only)` (Tasks 2, 3); `temperature_support`, `model_metadata`, `METADATA_KEYS` (Tasks 2, 4); `create_message` / `open_message_stream` / `capability_supported` in `anthropic_shared` (Tasks 3, 4); `clamp_temperature(t, *, maximum)` / `apply_anthropic_temperature(params, t)` (Task 5 and docs); `embeddings_body`, `anthropic_message_body`, `anthropic_stream_events`, `anthropic_models_body` (Tasks 3, 4, 6); `_STAGE2_CHANGES` (Tasks 1, 4, 5, removed in 9).
4. **Review Focus.** Each of the five lines has its test in the owning task (Tasks 1, 1, 3, 6, 7).

---

## Appendix A — Inventory of model IDs and model-specific values under `src/`

Generated on 07.10.2026 at HEAD 8ae3887 by scanning every file under `src/eq_chatbot_core/` (except `__pycache__`) with the guard pattern of Task 8 (spec patterns plus the nine added ones). 376 matching lines: 255 rows below with one line each, plus the two JSON files (121 lines) as one row each. "Pattern" says whether a spec pattern matched (`spec`) or only an added one (`added`, 23 lines — the reason the guard extends the spec's list). Verified with `uv run python`: the combined pattern matches every entry below and none of `openai`, `anthropic`, `/mistral/{region}/v1`, `codestral` (backend name), `ollama`.

Not detectable by any pattern and removed anyway: `LocalLLMProvider.DEFAULT_MODEL = "local-model"` (`providers/local_provider.py:47`, a placeholder, Task 1), the commented `"local-model"` examples in `data/config.toml.example:90,94` (Task 7), and prose model-family names without an ID (`providers/openrouter_provider.py:24-27`, `providers/langdock_provider.py:6-7,178-179`, `cli.py:1111`; Tasks 7–8). The realtime voice default `"ash"` (`realtime/providers/openai.py:63`) is a provider voice name, not a model ID, and stays.

| # | File (under `src/eq_chatbot_core/`) : line | What — matched text | Pattern | Removed in |
|---|---|---|---|---|
| 1 | `cli.py:161` | `test-provider` docstring examples — `claude-` | spec | Task 7 |
| 2 | `cli.py:168` | `test-provider` docstring examples — `llama3` | added | Task 7 |
| 3 | `cli.py:444` | `chat` docstring examples — `claude-` | spec | Task 7 |
| 4 | `cli.py:446` | `chat` docstring examples — `gpt-4` | spec | Task 7 |
| 5 | `cli.py:751` | `image` docstring: default image models — `gpt-image` | spec | Task 7 |
| 6 | `cli.py:966` | `listing-assets` recipe example — `gpt-image` | spec | Task 7 |
| 7 | `cli.py:1110` | `info` output: model families — `GPT-4` | spec | Task 7 |
| 8 | `data/capability_catalog.json:138–679 (118 lines)` | bundled catalog data (model IDs, aliases) | spec | Task 6 |
| 9 | `data/capability_overrides.json:9–12 (3 lines)` | bundled catalog data (model IDs, aliases) | spec | Task 6 |
| 10 | `data/config.toml.example:39` | commented `model = ...` examples — `gpt-4` | spec | Task 7 |
| 11 | `data/config.toml.example:44` | commented `model = ...` examples — `claude-` | spec | Task 7 |
| 12 | `data/config.toml.example:49` | commented `model = ...` examples — `gpt-4` | spec | Task 7 |
| 13 | `data/config.toml.example:54` | commented `model = ...` examples — `gpt-4` | spec | Task 7 |
| 14 | `data/config.toml.example:59` | commented `model = ...` examples — `gpt-4` | spec | Task 7 |
| 15 | `data/config.toml.example:64` | commented `model = ...` examples — `qwen` | spec | Task 7 |
| 16 | `data/config.toml.example:70` | commented `model = ...` examples — `Llama-` | spec | Task 7 |
| 17 | `data/config.toml.example:76` | commented `model = ...` examples — `minimax` | spec | Task 7 |
| 18 | `data/config.toml.example:85` | commented `model = ...` examples — `kimi` | spec | Task 7 |
| 19 | `providers/__init__.py:16` | module docstring usage examples — `gpt-4` | spec | Task 8 |
| 20 | `providers/__init__.py:20` | module docstring usage examples — `gpt-4` | spec | Task 8 |
| 21 | `providers/__init__.py:22` | module docstring usage examples — `gpt-4` | spec | Task 8 |
| 22 | `providers/__init__.py:24` | module docstring usage examples — `gemini-` | spec | Task 8 |
| 23 | `providers/__init__.py:32` | module docstring usage examples — `qwen` | spec | Task 8 |
| 24 | `providers/__init__.py:36` | module docstring usage examples — `Llama-` | spec | Task 8 |
| 25 | `providers/__init__.py:40` | module docstring usage examples — `minimax` | spec | Task 8 |
| 26 | `providers/__init__.py:45` | module docstring usage examples — `kimi` | spec | Task 8 |
| 27 | `providers/anthropic_provider.py:36` | class docstring: model list — `claude-` | spec | Task 8 |
| 28 | `providers/anthropic_provider.py:37` | class docstring: model list — `claude-` | spec | Task 8 |
| 29 | `providers/anthropic_provider.py:38` | class docstring: model list — `claude-` | spec | Task 8 |
| 30 | `providers/anthropic_provider.py:39` | class docstring: model list — `claude-` | spec | Task 8 |
| 31 | `providers/anthropic_provider.py:40` | class docstring: model list — `claude-` | spec | Task 8 |
| 32 | `providers/anthropic_provider.py:96` | `default_model` returns a model ID — `claude-` | spec | Task 1 |
| 33 | `providers/anthropic_provider.py:544` | `_get_model_constraints`: name-based vision/output detection — `claude-` | spec | Task 4 |
| 34 | `providers/anthropic_provider.py:546` | `_get_model_constraints`: name-based vision/output detection — `claude-` | spec | Task 4 |
| 35 | `providers/anthropic_provider.py:547` | `_get_model_constraints`: name-based vision/output detection — `claude-` | spec | Task 4 |
| 36 | `providers/ionos_provider.py:41` | `DEFAULT_MODEL` — `Llama-` | spec | Task 1 |
| 37 | `providers/langdock_provider.py:5` | module docstring: model families — `GPT-4` | spec | Task 8 |
| 38 | `providers/langdock_provider.py:177` | class docstring: model families — `GPT-4` | spec | Task 8 |
| 39 | `providers/langdock_provider.py:186` | class docstring: model families — `O1` | spec | Task 8 |
| 40 | `providers/langdock_provider.py:203` | `REASONING_MODELS` — `o1` | spec | Task 5 |
| 41 | `providers/langdock_provider.py:208` | `MODEL_CONTEXT_LENGTHS` — `gpt-4` | spec | Task 4 |
| 42 | `providers/langdock_provider.py:209` | `MODEL_CONTEXT_LENGTHS` — `gpt-4` | spec | Task 4 |
| 43 | `providers/langdock_provider.py:210` | `MODEL_CONTEXT_LENGTHS` — `gpt-4` | spec | Task 4 |
| 44 | `providers/langdock_provider.py:211` | `MODEL_CONTEXT_LENGTHS` — `gpt-5` | spec | Task 4 |
| 45 | `providers/langdock_provider.py:212` | `MODEL_CONTEXT_LENGTHS` — `o1` | spec | Task 4 |
| 46 | `providers/langdock_provider.py:213` | `MODEL_CONTEXT_LENGTHS` — `o1-mini` | spec | Task 4 |
| 47 | `providers/langdock_provider.py:214` | `MODEL_CONTEXT_LENGTHS` — `o1-preview` | spec | Task 4 |
| 48 | `providers/langdock_provider.py:215` | `MODEL_CONTEXT_LENGTHS` — `o3` | spec | Task 4 |
| 49 | `providers/langdock_provider.py:216` | `MODEL_CONTEXT_LENGTHS` — `o3-mini` | spec | Task 4 |
| 50 | `providers/langdock_provider.py:217` | `MODEL_CONTEXT_LENGTHS` — `o4-mini` | spec | Task 4 |
| 51 | `providers/langdock_provider.py:219` | `MODEL_CONTEXT_LENGTHS` — `claude-` | spec | Task 4 |
| 52 | `providers/langdock_provider.py:220` | `MODEL_CONTEXT_LENGTHS` — `claude-` | spec | Task 4 |
| 53 | `providers/langdock_provider.py:221` | `MODEL_CONTEXT_LENGTHS` — `claude-` | spec | Task 4 |
| 54 | `providers/langdock_provider.py:222` | `MODEL_CONTEXT_LENGTHS` — `claude-` | spec | Task 4 |
| 55 | `providers/langdock_provider.py:225` | `MODEL_CONTEXT_LENGTHS` — `gemini-` | spec | Task 4 |
| 56 | `providers/langdock_provider.py:226` | `MODEL_CONTEXT_LENGTHS` — `gemini-` | spec | Task 4 |
| 57 | `providers/langdock_provider.py:227` | `MODEL_CONTEXT_LENGTHS` — `gemini-` | spec | Task 4 |
| 58 | `providers/langdock_provider.py:253` | `__init__` docstring: reasoning_effort only for named families — `O1` | spec | Task 5 |
| 59 | `providers/langdock_provider.py:293` | `default_model` per-backend IDs + comment — `gpt-5` | spec | Task 1 |
| 60 | `providers/langdock_provider.py:294` | `default_model` per-backend IDs + comment — `claude-` | spec | Task 1 |
| 61 | `providers/langdock_provider.py:303` | `default_model` per-backend IDs + comment — `gpt-4` | spec | Task 1 |
| 62 | `providers/langdock_provider.py:304` | `default_model` per-backend IDs + comment — `claude-` | spec | Task 1 |
| 63 | `providers/langdock_provider.py:308` | `default_model` per-backend IDs + comment — `gemini-` | spec | Task 1 |
| 64 | `providers/langdock_provider.py:309` | `default_model` per-backend IDs + comment — `codestral-2` | added | Task 1 |
| 65 | `providers/langdock_provider.py:315` | `default_model` per-backend IDs + comment — `gpt-4` | spec | Task 1 |
| 66 | `providers/langdock_provider.py:468` | `_uses_new_token_api` prefixes — `gpt-4` | spec | Task 5 |
| 67 | `providers/langdock_provider.py:469` | `_uses_new_token_api` prefixes — `gpt-5` | spec | Task 5 |
| 68 | `providers/langdock_provider.py:470` | `_uses_new_token_api` prefixes — `o1` | spec | Task 5 |
| 69 | `providers/langdock_provider.py:471` | `_uses_new_token_api` prefixes — `o3` | spec | Task 5 |
| 70 | `providers/langdock_provider.py:472` | `_uses_new_token_api` prefixes — `o4` | spec | Task 5 |
| 71 | `providers/langdock_provider.py:1391` | `_get_model_constraints`: name-based vision/limits — `GPT-4` | spec | Task 4 |
| 72 | `providers/langdock_provider.py:1395` | `_get_model_constraints`: name-based vision/limits — `gpt-4` | spec | Task 4 |
| 73 | `providers/langdock_provider.py:1398` | `_get_model_constraints`: name-based vision/limits — `o1` | spec | Task 4 |
| 74 | `providers/langdock_provider.py:1401` | `_get_model_constraints`: name-based vision/limits — `"gemini"` | added | Task 4 |
| 75 | `providers/langdock_provider.py:1404` | `_get_model_constraints`: name-based vision/limits — `"claude"` | added | Task 4 |
| 76 | `providers/langdock_provider.py:1423` | `_get_model_constraints`: name-based vision/limits — `o1` | spec | Task 4 |
| 77 | `providers/langdock_provider.py:1429` | `_get_model_constraints`: name-based vision/limits — `"claude"` | added | Task 4 |
| 78 | `providers/langdock_provider.py:1431` | `_get_model_constraints`: name-based vision/limits — `"gemini"` | added | Task 4 |
| 79 | `providers/langdock_provider.py:1488` | `_list_openai_models` `supported_prefixes` — `gpt-4` | spec | Task 4 |
| 80 | `providers/langdock_provider.py:1489` | `_list_openai_models` `supported_prefixes` — `gpt-4` | spec | Task 4 |
| 81 | `providers/langdock_provider.py:1490` | `_list_openai_models` `supported_prefixes` — `gpt-5` | spec | Task 4 |
| 82 | `providers/langdock_provider.py:1491` | `_list_openai_models` `supported_prefixes` — `o1` | spec | Task 4 |
| 83 | `providers/langdock_provider.py:1492` | `_list_openai_models` `supported_prefixes` — `o3` | spec | Task 4 |
| 84 | `providers/langdock_provider.py:1493` | `_list_openai_models` `supported_prefixes` — `o4` | spec | Task 4 |
| 85 | `providers/langdock_provider.py:1549` | `_get_known_anthropic_models` static list — `claude-` | spec | Task 4 |
| 86 | `providers/langdock_provider.py:1550` | `_get_known_anthropic_models` static list — `claude-` | spec | Task 4 |
| 87 | `providers/langdock_provider.py:1551` | `_get_known_anthropic_models` static list — `claude-` | spec | Task 4 |
| 88 | `providers/langdock_provider.py:1552` | `_get_known_anthropic_models` static list — `claude-` | spec | Task 4 |
| 89 | `providers/langdock_provider.py:1572` | `_list_google_models` docstring history — `gemini-` | spec | Task 8 |
| 90 | `providers/langdock_provider.py:1608` | `_list_codestral_models` docstring — `codestral-2` | added | Task 1 |
| 91 | `providers/langdock_provider.py:1860` | `LangDockAgentManager.create_agent` default model — `gpt-4` | spec | Task 1 |
| 92 | `providers/litellm_provider.py:31` | `DEFAULT_TTS_MODEL` / `DEFAULT_TTS_VOICE` / `DEFAULT_STT_MODEL` — `kokoro` | spec | Task 1 |
| 93 | `providers/litellm_provider.py:32` | `DEFAULT_TTS_MODEL` / `DEFAULT_TTS_VOICE` / `DEFAULT_STT_MODEL` — `af_bella` | added | Task 1 |
| 94 | `providers/litellm_provider.py:33` | `DEFAULT_TTS_MODEL` / `DEFAULT_TTS_VOICE` / `DEFAULT_STT_MODEL` — `whisper` | spec | Task 1 |
| 95 | `providers/litellm_provider.py:49` | `DEFAULT_MODEL` — `qwen` | spec | Task 1 |
| 96 | `providers/litellm_provider.py:71` | `text_to_speech` docstring defaults — `kokoro` | spec | Task 1 |
| 97 | `providers/litellm_provider.py:72` | `text_to_speech` docstring defaults — `af_bella` | added | Task 1 |
| 98 | `providers/litellm_provider.py:107` | `transcribe` docstring default — `whisper` | spec | Task 1 |
| 99 | `providers/mammouth_provider.py:6` | module docstring: vendor list naming a model family — `DeepSeek` | spec | Task 8 |
| 100 | `providers/mammouth_provider.py:28` | class docstring examples — `gpt-4` | spec | Task 8 |
| 101 | `providers/mammouth_provider.py:29` | class docstring examples — `claude-` | spec | Task 8 |
| 102 | `providers/mammouth_provider.py:35` | `DEFAULT_MODEL` — `gpt-5` | spec | Task 1 |
| 103 | `providers/mammouth_provider.py:40` | `REASONING_MODEL_PREFIXES` — `o1` | spec | Task 5 |
| 104 | `providers/mammouth_provider.py:61` | `_is_reasoning_model` docstring — `O1` | spec | Task 5 |
| 105 | `providers/melious_provider.py:44` | `DEFAULT_MODEL` + history comment — `minimax` | spec | Task 1 |
| 106 | `providers/melious_provider.py:45` | `DEFAULT_MODEL` + history comment — `nemotron` | spec | Task 1 |
| 107 | `providers/melious_provider.py:46` | `DEFAULT_MODEL` + history comment — `nemotron` | spec | Task 1 |
| 108 | `providers/openai_provider.py:17` | class docstring: model list — `GPT-4` | spec | Task 8 |
| 109 | `providers/openai_provider.py:18` | class docstring: model list — `GPT-4` | spec | Task 8 |
| 110 | `providers/openai_provider.py:19` | class docstring: model list — `GPT-5` | spec | Task 8 |
| 111 | `providers/openai_provider.py:20` | class docstring: model list — `O1` | spec | Task 8 |
| 112 | `providers/openai_provider.py:21` | class docstring: model list — `gpt-image` | spec | Task 8 |
| 113 | `providers/openai_provider.py:27` | `DEFAULT_MODEL` — `gpt-5` | spec | Task 1 |
| 114 | `providers/openai_provider.py:34` | `DEFAULT_IMAGE_MODEL` — `gpt-image` | spec | Task 1 |
| 115 | `providers/openai_provider.py:37` | `NEW_API_MODELS` — `GPT-4` | spec | Task 5 |
| 116 | `providers/openai_provider.py:39` | `NEW_API_MODELS` — `gpt-4` | spec | Task 5 |
| 117 | `providers/openai_provider.py:40` | `NEW_API_MODELS` — `gpt-4` | spec | Task 5 |
| 118 | `providers/openai_provider.py:41` | `NEW_API_MODELS` — `gpt-5` | spec | Task 5 |
| 119 | `providers/openai_provider.py:42` | `NEW_API_MODELS` — `gpt-5` | spec | Task 5 |
| 120 | `providers/openai_provider.py:43` | `NEW_API_MODELS` — `gpt-5` | spec | Task 5 |
| 121 | `providers/openai_provider.py:44` | `NEW_API_MODELS` — `o1` | spec | Task 5 |
| 122 | `providers/openai_provider.py:45` | `NEW_API_MODELS` — `o1-mini` | spec | Task 5 |
| 123 | `providers/openai_provider.py:46` | `NEW_API_MODELS` — `o1-preview` | spec | Task 5 |
| 124 | `providers/openai_provider.py:47` | `NEW_API_MODELS` — `o3` | spec | Task 5 |
| 125 | `providers/openai_provider.py:48` | `NEW_API_MODELS` — `o3-mini` | spec | Task 5 |
| 126 | `providers/openai_provider.py:49` | `NEW_API_MODELS` — `o4` | spec | Task 5 |
| 127 | `providers/openai_provider.py:50` | `NEW_API_MODELS` — `o4-mini` | spec | Task 5 |
| 128 | `providers/openai_provider.py:77` | `CHAT_MODEL_PREFIXES` — `gpt-3` | spec | Task 4 |
| 129 | `providers/openai_provider.py:78` | `CHAT_MODEL_PREFIXES` — `gpt-4` | spec | Task 4 |
| 130 | `providers/openai_provider.py:79` | `CHAT_MODEL_PREFIXES` — `gpt-5` | spec | Task 4 |
| 131 | `providers/openai_provider.py:80` | `CHAT_MODEL_PREFIXES` — `o1` | spec | Task 4 |
| 132 | `providers/openai_provider.py:81` | `CHAT_MODEL_PREFIXES` — `o3` | spec | Task 4 |
| 133 | `providers/openai_provider.py:82` | `CHAT_MODEL_PREFIXES` — `o4` | spec | Task 4 |
| 134 | `providers/openai_provider.py:83` | `CHAT_MODEL_PREFIXES` — `chatgpt` | spec | Task 4 |
| 135 | `providers/openai_provider.py:88` | `MODEL_CONTEXT_LENGTHS` — `gpt-4` | spec | Task 4 |
| 136 | `providers/openai_provider.py:89` | `MODEL_CONTEXT_LENGTHS` — `gpt-4` | spec | Task 4 |
| 137 | `providers/openai_provider.py:90` | `MODEL_CONTEXT_LENGTHS` — `gpt-4` | spec | Task 4 |
| 138 | `providers/openai_provider.py:91` | `MODEL_CONTEXT_LENGTHS` — `gpt-4` | spec | Task 4 |
| 139 | `providers/openai_provider.py:92` | `MODEL_CONTEXT_LENGTHS` — `gpt-3` | spec | Task 4 |
| 140 | `providers/openai_provider.py:93` | `MODEL_CONTEXT_LENGTHS` — `o1` | spec | Task 4 |
| 141 | `providers/openai_provider.py:94` | `MODEL_CONTEXT_LENGTHS` — `o1-mini` | spec | Task 4 |
| 142 | `providers/openai_provider.py:95` | `MODEL_CONTEXT_LENGTHS` — `o1-preview` | spec | Task 4 |
| 143 | `providers/openai_provider.py:96` | `MODEL_CONTEXT_LENGTHS` — `o3` | spec | Task 4 |
| 144 | `providers/openai_provider.py:97` | `MODEL_CONTEXT_LENGTHS` — `o3-mini` | spec | Task 4 |
| 145 | `providers/openai_provider.py:98` | `MODEL_CONTEXT_LENGTHS` — `o4-mini` | spec | Task 4 |
| 146 | `providers/openai_provider.py:99` | `MODEL_CONTEXT_LENGTHS` — `gpt-5` | spec | Task 4 |
| 147 | `providers/openai_provider.py:110` | `_get_model_constraints`: name-based vision/limits — `GPT-4` | spec | Task 4 |
| 148 | `providers/openai_provider.py:111` | `_get_model_constraints`: name-based vision/limits — `gpt-4` | spec | Task 4 |
| 149 | `providers/openai_provider.py:129` | `_get_model_constraints`: name-based vision/limits — `o1` | spec | Task 4 |
| 150 | `providers/openai_provider.py:141` | `_get_model_constraints`: name-based vision/limits — `gpt-4` | spec | Task 4 |
| 151 | `providers/openai_provider.py:195` | `generate_image` docstring default — `gpt-image` | spec | Task 1 |
| 152 | `providers/openai_provider.py:196` | `generate_image` docstring: per-model sizes — `gpt-image` | spec | Task 5 |
| 153 | `providers/openai_provider.py:197` | `generate_image` docstring: per-model sizes — `DALL-E` | spec | Task 5 |
| 154 | `providers/openai_provider.py:218` | `generate_image`: name-based `response_format` branch — `gpt-image` | spec | Task 5 |
| 155 | `providers/openai_provider.py:219` | `generate_image`: name-based `response_format` branch — `dall-e` | spec | Task 5 |
| 156 | `providers/openai_provider.py:221` | `generate_image`: name-based `response_format` branch — `dall-e` | spec | Task 5 |
| 157 | `providers/openrouter_provider.py:23` | class docstring: model families/examples — `GPT-4` | spec | Task 8 |
| 158 | `providers/openrouter_provider.py:32` | class docstring: model families/examples — `gpt-4` | spec | Task 8 |
| 159 | `providers/openrouter_provider.py:33` | class docstring: model families/examples — `claude-` | spec | Task 8 |
| 160 | `providers/openrouter_provider.py:34` | class docstring: model families/examples — `gemini-` | spec | Task 8 |
| 161 | `providers/openrouter_provider.py:35` | class docstring: model families/examples — `llama-` | spec | Task 8 |
| 162 | `providers/openrouter_provider.py:41` | `DEFAULT_MODEL` — `gpt-5` | spec | Task 1 |
| 163 | `providers/openrouter_provider.py:48` | `DEFAULT_IMAGE_MODEL` — `gemini-` | spec | Task 1 |
| 164 | `providers/openrouter_provider.py:52` | `REASONING_MODEL_PREFIXES` — `o1` | spec | Task 5 |
| 165 | `providers/openrouter_provider.py:53` | `REASONING_MODEL_PREFIXES` — `o3` | spec | Task 5 |
| 166 | `providers/openrouter_provider.py:54` | `REASONING_MODEL_PREFIXES` — `o4` | spec | Task 5 |
| 167 | `providers/openrouter_provider.py:90` | `_is_reasoning_model` docstring — `O1` | spec | Task 5 |
| 168 | `providers/openrouter_provider.py:142` | `generate_image` docstring default — `gemini-` | spec | Task 1 |
| 169 | `providers/privatemode_provider.py:48` | module docstring: model IDs — `kimi` | spec | Task 8 |
| 170 | `providers/privatemode_provider.py:55` | module docstring: model IDs — `qwen` | spec | Task 8 |
| 171 | `providers/privatemode_provider.py:56` | module docstring: model IDs — `whisper` | spec | Task 8 |
| 172 | `providers/privatemode_provider.py:88` | `DEFAULT_MODEL` + comment — `Kimi` | spec | Task 1 |
| 173 | `providers/privatemode_provider.py:90` | `DEFAULT_MODEL` + comment — `kimi` | spec | Task 1 |
| 174 | `providers/privatemode_provider.py:243` | `_build_params` docstring: model family — `Kimi` | spec | Task 8 |
| 175 | `providers/temperature_constraints.py:4` | module docstring — `GPT-4` | spec | Task 5 |
| 176 | `providers/temperature_constraints.py:18` | `MODEL_TEMPERATURE_CONSTRAINTS` — `DeepSeek` | spec | Task 5 |
| 177 | `providers/temperature_constraints.py:19` | `MODEL_TEMPERATURE_CONSTRAINTS` — `deepseek` | spec | Task 5 |
| 178 | `providers/temperature_constraints.py:22` | `MODEL_TEMPERATURE_CONSTRAINTS` — `o1` | spec | Task 5 |
| 179 | `providers/temperature_constraints.py:23` | `MODEL_TEMPERATURE_CONSTRAINTS` — `o1-mini` | spec | Task 5 |
| 180 | `providers/temperature_constraints.py:24` | `MODEL_TEMPERATURE_CONSTRAINTS` — `o1-preview` | spec | Task 5 |
| 181 | `providers/temperature_constraints.py:25` | `MODEL_TEMPERATURE_CONSTRAINTS` — `o3` | spec | Task 5 |
| 182 | `providers/temperature_constraints.py:26` | `MODEL_TEMPERATURE_CONSTRAINTS` — `o3-mini` | spec | Task 5 |
| 183 | `providers/temperature_constraints.py:27` | `MODEL_TEMPERATURE_CONSTRAINTS` — `o3-pro` | spec | Task 5 |
| 184 | `providers/temperature_constraints.py:28` | `MODEL_TEMPERATURE_CONSTRAINTS` — `o4-mini` | spec | Task 5 |
| 185 | `providers/temperature_constraints.py:29` | `MODEL_TEMPERATURE_CONSTRAINTS` — `codex-mini` | added | Task 5 |
| 186 | `providers/temperature_constraints.py:30` | `MODEL_TEMPERATURE_CONSTRAINTS` — `GPT-4` | spec | Task 5 |
| 187 | `providers/temperature_constraints.py:31` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-4` | spec | Task 5 |
| 188 | `providers/temperature_constraints.py:32` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-4` | spec | Task 5 |
| 189 | `providers/temperature_constraints.py:33` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-4` | spec | Task 5 |
| 190 | `providers/temperature_constraints.py:34` | `MODEL_TEMPERATURE_CONSTRAINTS` — `GPT-5` | spec | Task 5 |
| 191 | `providers/temperature_constraints.py:36` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-5` | spec | Task 5 |
| 192 | `providers/temperature_constraints.py:39` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-5` | spec | Task 5 |
| 193 | `providers/temperature_constraints.py:44` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-5` | spec | Task 5 |
| 194 | `providers/temperature_constraints.py:45` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-5` | spec | Task 5 |
| 195 | `providers/temperature_constraints.py:46` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-5` | spec | Task 5 |
| 196 | `providers/temperature_constraints.py:47` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-5` | spec | Task 5 |
| 197 | `providers/temperature_constraints.py:48` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-5` | spec | Task 5 |
| 198 | `providers/temperature_constraints.py:50` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-4` | spec | Task 5 |
| 199 | `providers/temperature_constraints.py:51` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-4` | spec | Task 5 |
| 200 | `providers/temperature_constraints.py:52` | `MODEL_TEMPERATURE_CONSTRAINTS` — `gpt-4` | spec | Task 5 |
| 201 | `providers/temperature_constraints.py:56` | `MODEL_TEMPERATURE_CONSTRAINTS` — `"claude"` | added | Task 5 |
| 202 | `providers/temperature_constraints.py:58` | `MODEL_TEMPERATURE_CONSTRAINTS` — `claude-` | spec | Task 5 |
| 203 | `providers/temperature_constraints.py:59` | `MODEL_TEMPERATURE_CONSTRAINTS` — `claude-` | spec | Task 5 |
| 204 | `providers/temperature_constraints.py:60` | `MODEL_TEMPERATURE_CONSTRAINTS` — `claude-` | spec | Task 5 |
| 205 | `providers/temperature_constraints.py:61` | `MODEL_TEMPERATURE_CONSTRAINTS` — `claude-` | spec | Task 5 |
| 206 | `providers/temperature_constraints.py:62` | `MODEL_TEMPERATURE_CONSTRAINTS` — `claude-` | spec | Task 5 |
| 207 | `providers/temperature_constraints.py:63` | `MODEL_TEMPERATURE_CONSTRAINTS` — `claude-` | spec | Task 5 |
| 208 | `providers/temperature_constraints.py:64` | `MODEL_TEMPERATURE_CONSTRAINTS` — `claude-` | spec | Task 5 |
| 209 | `providers/temperature_constraints.py:67` | `MODEL_TEMPERATURE_CONSTRAINTS` — `"claude"` | added | Task 5 |
| 210 | `providers/temperature_constraints.py:69` | `MODEL_TEMPERATURE_CONSTRAINTS` — `"gemini"` | added | Task 5 |
| 211 | `providers/temperature_constraints.py:70` | `MODEL_TEMPERATURE_CONSTRAINTS` — `Mistral-` | spec | Task 5 |
| 212 | `providers/temperature_constraints.py:71` | `MODEL_TEMPERATURE_CONSTRAINTS` — `"mistral"` | added | Task 5 |
| 213 | `providers/temperature_constraints.py:72` | `MODEL_TEMPERATURE_CONSTRAINTS` — `DeepSeek` | spec | Task 5 |
| 214 | `providers/temperature_constraints.py:73` | `MODEL_TEMPERATURE_CONSTRAINTS` — `deepseek` | spec | Task 5 |
| 215 | `providers/temperature_constraints.py:74` | `MODEL_TEMPERATURE_CONSTRAINTS` — `deepseek` | spec | Task 5 |
| 216 | `providers/temperature_constraints.py:75` | `MODEL_TEMPERATURE_CONSTRAINTS` — `deepseek` | spec | Task 5 |
| 217 | `providers/temperature_constraints.py:76` | `MODEL_TEMPERATURE_CONSTRAINTS` — `deepseek` | spec | Task 5 |
| 218 | `providers/temperature_constraints.py:78` | `MODEL_TEMPERATURE_CONSTRAINTS` — `mai-ds` | added | Task 5 |
| 219 | `providers/temperature_constraints.py:80` | `MODEL_TEMPERATURE_CONSTRAINTS` — `"llama"` | added | Task 5 |
| 220 | `providers/temperature_constraints.py:81` | `MODEL_TEMPERATURE_CONSTRAINTS` — `Grok` | spec | Task 5 |
| 221 | `providers/temperature_constraints.py:82` | `MODEL_TEMPERATURE_CONSTRAINTS` — `grok` | spec | Task 5 |
| 222 | `providers/temperature_constraints.py:84` | `MODEL_TEMPERATURE_CONSTRAINTS` — `"cohere"` | added | Task 5 |
| 223 | `providers/temperature_constraints.py:85` | `MODEL_TEMPERATURE_CONSTRAINTS` — `Kimi` | spec | Task 5 |
| 224 | `providers/temperature_constraints.py:86` | `MODEL_TEMPERATURE_CONSTRAINTS` — `kimi` | spec | Task 5 |
| 225 | `providers/temperature_constraints.py:101` | `strip_provider_prefix` docstring examples — `gpt-4` | spec | Task 5 |
| 226 | `providers/temperature_constraints.py:102` | `strip_provider_prefix` docstring examples — `claude-` | spec | Task 5 |
| 227 | `providers/temperature_constraints.py:103` | `strip_provider_prefix` docstring examples — `gpt-4` | spec | Task 5 |
| 228 | `providers/temperature_constraints.py:125` | `get_temperature_constraints` comment — `gpt-5` | spec | Task 5 |
| 229 | `providers/temperature_constraints.py:150` | `clamp_temperature` docstring — `o1` | spec | Task 5 |
| 230 | `rag/context_manager.py:42` | `ContextWindowManager.MODEL_LIMITS` — `gpt-4` | spec | Task 6 |
| 231 | `rag/context_manager.py:43` | `ContextWindowManager.MODEL_LIMITS` — `gpt-4` | spec | Task 6 |
| 232 | `rag/context_manager.py:44` | `ContextWindowManager.MODEL_LIMITS` — `gpt-4` | spec | Task 6 |
| 233 | `rag/context_manager.py:45` | `ContextWindowManager.MODEL_LIMITS` — `gpt-4` | spec | Task 6 |
| 234 | `rag/context_manager.py:46` | `ContextWindowManager.MODEL_LIMITS` — `claude-` | spec | Task 6 |
| 235 | `rag/context_manager.py:47` | `ContextWindowManager.MODEL_LIMITS` — `claude-` | spec | Task 6 |
| 236 | `rag/context_manager.py:48` | `ContextWindowManager.MODEL_LIMITS` — `claude-` | spec | Task 6 |
| 237 | `rag/embedder.py:35` | `OpenAIEmbedder` docstring — `text-embedding` | spec | Task 6 |
| 238 | `rag/embedder.py:42` | `OpenAIEmbedder.MODELS` — `text-embedding` | spec | Task 6 |
| 239 | `rag/embedder.py:43` | `OpenAIEmbedder.MODELS` — `text-embedding` | spec | Task 6 |
| 240 | `rag/embedder.py:44` | `OpenAIEmbedder.MODELS` — `text-embedding` | spec | Task 6 |
| 241 | `rag/embedder.py:50` | `OpenAIEmbedder` default model — `text-embedding` | spec | Task 6 |
| 242 | `rag/embedder.py:137` | `LangDockEmbedder` default model — `text-embedding` | spec | Task 6 |
| 243 | `realtime/providers/gemini_live.py:64` | `GeminiLiveConfig.model` default + comment — `gemini-` | spec | Task 6 |
| 244 | `realtime/providers/gemini_live.py:65` | `GeminiLiveConfig.model` default + comment — `gemini-` | spec | Task 6 |
| 245 | `realtime/providers/gemini_live.py:66` | `GeminiLiveConfig.model` default + comment — `gemini-` | spec | Task 6 |
| 246 | `realtime/providers/gemini_live.py:102` | validation message naming a model — `gemini-` | spec | Task 6 |
| 247 | `realtime/providers/openai.py:58` | `OpenAIRealtimeConfig.model` default + comment — `gpt-realtime` | added | Task 6 |
| 248 | `realtime/providers/openai.py:60` | `OpenAIRealtimeConfig.model` default + comment — `gpt-realtime` | added | Task 6 |
| 249 | `realtime/providers/openai.py:61` | `OpenAIRealtimeConfig.model` default + comment — `gpt-realtime` | added | Task 6 |
| 250 | `realtime/providers/openai.py:62` | `OpenAIRealtimeConfig.model` default + comment — `gpt-realtime` | added | Task 6 |
| 251 | `realtime/providers/openai.py:99` | validation message naming models — `gpt-realtime` | added | Task 6 |
| 252 | `security/rate_limit.py:229` | `estimate_tokens` default `model` — `gpt-4` | spec | Task 6 |
| 253 | `security/rate_limit.py:247` | `estimate_tokens` encoding map — `gpt-4` | spec | Task 6 |
| 254 | `security/rate_limit.py:248` | `estimate_tokens` encoding map — `gpt-4` | spec | Task 6 |
| 255 | `security/rate_limit.py:249` | `estimate_tokens` encoding map — `gpt-4` | spec | Task 6 |
| 256 | `security/rate_limit.py:250` | `estimate_tokens` encoding map — `"claude"` | added | Task 6 |
| 257 | `services/capability_catalog.py:145` | comment example — `claude-` | spec | Task 6 |
