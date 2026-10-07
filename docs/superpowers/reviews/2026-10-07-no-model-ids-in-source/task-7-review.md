# Task 7 review (30cb889..c23292e)

Spec compliance: ✅
Quality: Approved

New tests re-run: 64 passed (tests/unit/test_cli_model_required.py + tests/unit/server).

## Checks
- Brief steps 4-7 and "Produces" implemented as written (model_required_message, four commands exit 1, _model_missing_to_http with status 400 and detail.type, mapping in _provider_error_to_http, eager resolve in /chat/stream).
- No CLI path reaches a provider call without a model: test-provider, chat, image, listing-assets are guarded. list-models and serve need no model (list-models calls list_models only). listing-assets --dry-run returns before the guard on purpose (no provider call). Local providers are guarded too (a lm_studio call without a model now exits 1; that is the intended stage-2 behaviour).
- Server /chat: ModelNotSpecifiedError is a ProviderError, so the existing except maps it to 400 via _provider_error_to_http. /chat/stream: provider_extra model is passed to get_provider(model=...), so resolve_model finds the instance model. The LangDock agent backend overrides resolve_model (langdock_provider.py:262) and returns without a model, so the eager call does not reject it. No false rejection.
- Error messages: only provider name and config path (no key, no base_url). The path contains the home directory, which is local information, not a secret.
- Triage: only "-m test-model" added or model in config text; no asserted default; no xfails. Rule 1 only.
- Test isolation: autouse fixture in tests/conftest.py resets the config cache, so _use_config does not leak.

## Findings
Critical: 0
Important: 0
Minor: 4

1. Minor, tests/unit/server/test_model_required.py: no test that /chat/stream with a LangDock agent backend (provider_extra backend=agent, agent_id) is not rejected, nor that a provider_extra model passes the eager check on /chat/stream (only /chat is covered). Fix: add a wire-server test for each.
2. Minor, tests/unit/test_cli_model_required.py:45-50: parametrize covers only provider openai; the local path (lm_studio / ollama without model) and image with openrouter are untested, and listing-assets --dry-run without a model (must succeed) is not pinned. Fix: add a lm_studio case and a dry-run assertion.
3. Minor, tests/unit/test_cli_model_required.py:80-85: "flag beats config" and "config used" cover test-provider only; chat and image config resolution are unpinned. Fix: add one wire test for chat with a config model.
4. Minor, tests/unit/test_cli_chat.py (custom-model test, `or` assertion, pre-existing): the model-forwarding assertion is vacuous because `call_kwargs.kwargs.get("model") or ...` is truthy for any model. Fix: `assert call_kwargs.kwargs["model"] == "gpt-4o"`.

Note (not a finding): docs/cli.md still describes default models; the report assigns it to Task 10.
