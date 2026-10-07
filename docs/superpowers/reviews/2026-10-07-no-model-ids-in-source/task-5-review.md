# Task 5 review (809f2e2..ffb8175)

Spec compliance: ✅ (one process miss, see Important 1)
Quality: Needs fixes (minor-level only, plus one Important test-port gap)

Checked: every name in the brief's "Removed" list is gone from src/ (grep clean); `strip_provider_prefix` and its 6 tests stay active; new test file matches the brief; the 14 tests of test_no_name_lists_wire.py + test_public_api_compat.py pass; all xfail reasons start with "stage 2:".

## Findings

### Important
1. tests/unit/test_anthropic_temperature_transport.py (module-level pytestmark xfail): `TestApplyAnthropicTemperature::test_existing_extra_body_is_preserved` is whole-module xfailed without a port. Ruling 9 requires porting it first, and triage rule 3 applies (behaviour still exists: `setdefault("extra_body", {})` merge). The new `test_anthropic_temperature_clamped_into_extra_body` only uses a fresh dict. Fix: add to test_no_name_lists_wire.py
   `params = {"extra_body": {"foo": "bar"}}; apply_anthropic_temperature(params, 0.3); assert params["extra_body"] == {"foo": "bar", "temperature": 0.3}`
   and name it in the module's xfail reason. Also the `is True/False` return test is obsolete by design (returns None), fine.

### Minor
1. tests/unit/test_temperature_constraints.py:10 blanket `# ruff: noqa: F821` also hides real undefined names in the active TestStripProviderPrefix tests. Fix: acceptable as is; or restrict by wrapping the xfailed classes' bodies' references via `# noqa: F821` per line, or `globals()`-free helper. Low value.
2. Class/module docstrings under src/ still name models (openai_provider.py:17-21, mammouth_provider.py:24-25, openrouter_provider.py:23-34, langdock_provider.py:5-7,176-178). Not in this brief (reported by implementer, Task 8 guard sweep); make sure Task 8 covers langdock lines 5-7/176-178 and openrouter, not only OpenAI and Mammouth.
2b. openai_provider.py generate_image: dall-e models now return a URL and raise ProviderError unless the caller passes response_format. Intended; make sure it lands in the Task 10 CHANGELOG (ruling 9).
3. Reasons of the xfails in test_mammouth.py / test_openai.py / test_langdock.py say "provider-level clamp and learning tested in ..." for tests such as test_gpt41_temperature_passthrough; no real behaviour is lost (passthrough is covered by test_clamp_is_provider_level_only and the wire test), so no action beyond accuracy.
4. test_no_name_lists_wire.py::test_temperature_is_sent_whatever_the_model_name covers Mammouth only; OpenAI and OpenRouter share the base but are not exercised. Optional: parametrize over provider.
