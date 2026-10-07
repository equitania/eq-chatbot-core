# Final re-review of c2e8618 (scoped)

Tests: test_param_learning.py + test_cli_model_required.py: 30 passed.

## I-1: resolved
- param_learning.py:74-75: reasoning_effort with code != unsupported_parameter returns None -> not learned, 400 reaches the caller, next call still sends the parameter (pinned by test_reasoning_effort_value_rejection_reaches_caller_and_is_not_remembered).
- reasoning_effort unsupported_parameter still learned (existing test line 105); temperature unsupported_value (OPENAI_TEMPERATURE_REJECTION) still learned (parametrized test line 32).

## I-2: resolved
- cli.py:789 (image) and :1019 (listing-assets) use config_image_model; precedence --model > recipe defaults.model > config image_model > error. Error names image_model (cli.py:799, :1054, helper with key/what). chat/test-provider untouched (config_model still line 80).
- docs/cli.md (EN+DE), usage/AGENT.md, config.toml.example, CHANGELOG consistent with the code.

## Tests
Pin: value rejection not learned (unit + wire), image ignores chat model, image_model used on the wire, listing-assets error names image_model.

## New issues
- Minor, src/eq_chatbot_core/providers/param_learning.py:77-84: text fallback (body without `param`) still learns a reasoning_effort value rejection, e.g. "Unsupported value: 'reasoning_effort' does not support 'none'", because only the structured branch has the new guard. Gateways only; arguably acceptable but inconsistent. Not tested.
- Minor, tests/unit/test_cli_model_required.py: precedence recipe defaults.model > config image_model for listing-assets is not pinned by a test (code is correct).
