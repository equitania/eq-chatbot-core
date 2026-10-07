# Task 6 review (686e972..d9483ad)

Spec compliance: ✅
Quality: Approved

Checked: `uv run pytest tests/unit/test_embedder_wire.py tests/unit/test_no_model_tables.py tests/unit/test_embedder.py` gives 27 passed, 3 xfailed.
`git grep` over src/ and pyproject.toml finds no remaining `from_snapshot`, `MODEL_LIMITS`, `_get_model_limit`, `_SNAPSHOT_PATH`, `OpenAIEmbedder.MODELS` or snapshot reference, and no positional-model caller of `estimate_tokens`. Nothing else in src/ constructs `ContextWindowManager` or an embedder. The only reader of `embedder.dimensions` is `retriever.ensure_collection`, which handles `None`.

## Spec compliance
- Everything in the brief's "Removed" list is gone from src/: `OpenAIEmbedder.MODELS`, `ContextWindowManager.MODEL_LIMITS` and `_get_model_limit`, `CapabilityCatalog.from_snapshot`, `_SNAPSHOT_PATH`, both JSON files, and the wheel entries.
- "Produces" signatures match the brief (embedders, `ensure_collection`, `ContextWindowManager`, `estimate_tokens`, `from_remote`, the realtime configs).
- Ruling 6 is met: the 128000 fallback logs a WARNING that names the value and `context_length=`, and a test covers it.
- Triage:
  - Rule 1 was applied correctly in `test_embedder.py` (model added to 4 constructions) and in the realtime tests.
  - Every xfail reason starts with "stage 2:".
  - The xfailed behaviours (model table, default dimensions, snapshot, limit table, default realtime model) are all removed behaviours.
  - The one still-existing behaviour, the remote-fetch failure, is ported to `test_no_model_tables.py` and the xfail says so.
- The wire server allows `127.0.0.1` as a localhost name, so the catalog and embedder wire tests do reach the stub server and are not passing because of an SSRF block.

## Findings
Critical: 0
Important: 0
Minor: 5

1. Minor: tests/unit/test_context_manager.py, `test_unknown_model_falls_back_to_128000` (around line 71) still asserts the library default as the literal 128000.
   Fix: assert `mgr.max_tokens == ContextWindowManager.DEFAULT_CONTEXT_LENGTH` and rename the test to say "no context_length -> fallback".
2. Minor: src/eq_chatbot_core/rag/context_manager.py, `__init__`, the lines `if context_length is None: warn` and `self.max_tokens = context_length or DEFAULT`. A caller passing `context_length=0` or a negative value gets the 128000 default silently, with no WARNING.
   Fix: warn on `not context_length`, or raise `ValueError` for `context_length <= 0`.
3. Minor: src/eq_chatbot_core/rag/retriever.py, `ensure_collection` docstring (around line 168) does not list the new `ValueError` under Raises.
   Fix: add `Raises: ValueError: neither vector_size nor embedder.dimensions is known`.
4. Minor: stale wording in tests/unit/test_embedder.py. The `TestOpenAIEmbedder` docstring says "validates against its static catalog", and the `test_skips_static_model_validation` docstring says a "dynamic (non-catalog) model id must be accepted". `TestSnapshotAndRemote` in tests/unit/test_capability_catalog.py is misnamed after the snapshot left.
   Fix: reword to "accepts any caller-supplied model id" and rename the class.
5. Minor: weak coverage in the new tests.
   - tests/unit/test_embedder_wire.py never calls `ensure_collection` with an up-front `dimensions=` or an explicit `vector_size=`.
   - It has no wire test that LangDock or Melious discover and check dimensions, or that Melious sends the model in the request.
   Fix: add `ensure_collection(vector_size=5)` and `OpenAIEmbedder(..., dimensions=3)` cases against `:memory:` Qdrant. Add one Melious wire test with `base_url=wire_server.base_url` that asserts the `model` in the request body and `dimensions` after `embed()`.
