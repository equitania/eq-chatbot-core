# Test Report - 2026-08-19 09:43:51

**eq_chatbot_core v3.0.0** | 20.48s | Python 3.13.12 | macOS-26.6.2-arm64-arm-64bit-Mach-O

> **Result: FAILED - 6 failure(s), 0 error(s)**

Command: `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/.venv/lib/python3.13/site-packages/pytest/__main__.py tests/integration/test_melious_live.py tests/integration/test_vertex_live.py -q --no-header -m integration --tb=line`

## Summary

| Status | Count |
|--------|-------|
| Passed | 3 |
| Failed | 6 |
| **Total** | **9** |

## Configuration Status

**Action required** — missing API credentials cause tests to be skipped. Set the variables below in `tests/.env.test` to enable the affected tests:

| Provider | Missing variable(s) | Tests skipped | Action |
|----------|---------------------|---------------|--------|
| **Ionos** | `IONOS_API_KEY` | 0 | Add `IONOS_API_KEY=...` to `tests/.env.test` |

Credentials configured: `OpenAI`, `Anthropic`, `LangDock`, `OpenRouter`, `Mammouth`, `Azure`, `Vertex`, `LiteLLM`, `Melious`

## Models In Use

Resolved live from `tests/model_registry.py` against each provider's `list_models()`. By convention the `primary` in each chain is the cheapest available model; fallbacks rescue the run when the primary is deprecated.

| Provider | Model Used | Cost (per 1M tok) | Source | Status |
|----------|-----------|-------------------|--------|--------|
| OpenAI | — | $0.15 / $0.60 per 1M tok | — | SKIPPED — provider not exercised this run |
| Anthropic | — | $1.00 / $5.00 per 1M tok | — | SKIPPED — provider not exercised this run |
| LangDock (OpenAI backend) | — | LangDock gateway (see langdock.com pricing) | — | SKIPPED — provider not exercised this run |
| LangDock (Anthropic backend) | — | LangDock gateway (see langdock.com pricing) | — | SKIPPED — provider not exercised this run |
| OpenRouter | — | $0.02 / $0.03 per 1M tok | — | SKIPPED — provider not exercised this run |
| Mammouth AI | — | ~$0.05 / $0.40 per 1M tok (gateway, passthrough) | — | SKIPPED — provider not exercised this run |
| Azure AI | — | deployment-dependent | — | SKIPPED — provider not exercised this run |
| Google Vertex AI | `gemini-2.5-pro` | $0.15 / $0.60 per 1M tok | Env override | OK |
| LiteLLM Gateway | — | gateway (deployment-dependent) | — | SKIPPED — provider not exercised this run |
| IONOS AI Model Hub | — | ~$0.16 per 1M tok (EU-hosted, Berlin/de-txl) | — | SKIPPED — set `IONOS_API_KEY` in `tests/.env.test` |
| Melious.ai | `gpt-oss-20b` | ~EUR 0.4 in / 2.0 out per 1M tok (sovereign EU, MiniMax M3) | Env override | OK |
| Privatemode.ai | — | local proxy (confidential computing, EU) | — | SKIPPED — provider not exercised this run |
| Local (LM Studio / Ollama) | — | $0 (local) | — | SKIPPED — provider not exercised this run |

## Failed Tests

| Test | Error |
|------|-------|
| `integration/test_melious_live.py::TestMeliousLive::test_simple_completion` | E   eq_chatbot_core.providers.base.ProviderError: Error code: 503 - {'error': {'message': 'The model provider encountered an error. Please try again.', 'type': 'server_error', 'param': None, 'code': ' |
| `integration/test_melious_live.py::TestMeliousLive::test_streaming_completion` | E   eq_chatbot_core.providers.base.ProviderError: The model provider encountered a streaming error. Please try again. |
| `integration/test_melious_live.py::TestMeliousLive::test_context_manager` | E   eq_chatbot_core.providers.base.ProviderError: Error code: 503 - {'error': {'message': 'The model provider encountered an error. Please try again.', 'type': 'server_error', 'param': None, 'code': ' |
| `integration/test_vertex_live.py::TestVertexLive::test_simple_completion` | E   eq_chatbot_core.providers.base.ProviderError: Your default credentials were not found. To set up Application Default Credentials, see https://cloud.google.com/docs/authentication/external/set-up-a |
| `integration/test_vertex_live.py::TestVertexLive::test_streaming_completion` | E   eq_chatbot_core.providers.base.ProviderError: Your default credentials were not found. To set up Application Default Credentials, see https://cloud.google.com/docs/authentication/external/set-up-a |
| `integration/test_vertex_live.py::TestVertexLive::test_system_message` | E   eq_chatbot_core.providers.base.ProviderError: Your default credentials were not found. To set up Application Default Credentials, see https://cloud.google.com/docs/authentication/external/set-up-a |

## Results by Module

| Module | Test Model | Passed | Failed | Skipped | XFailed | Total | Duration |
|--------|------------|--------|--------|---------|---------|-------|----------|
| **Provider: Google Vertex AI** **!!** | `gemini-2.5-pro` | 2 | 3 | 0 | 0 | 5 | 14.84s |
| **Provider: Melious.ai (sovereign EU)** **!!** | `gpt-oss-20b` | 1 | 3 | 0 | 0 | 4 | 4.31s |

## Detailed Results

### Integration Tests (3 passed, 6 failed)

#### Provider: Google Vertex AI (2 passed, 3 failed) - 14.84s | Model: `gemini-2.5-pro`

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_vertex_live.py::TestVertexLive::test_simple_completion` | FAILED | 8.78s | E   eq_chatbot_core.providers.base.ProviderError: Your default credentials were not found. To set up Application Default Credentials, see https://cloud.google.com/docs/authentication/external/set-up-adc for more information. |
| `integration/test_vertex_live.py::TestVertexLive::test_streaming_completion` | FAILED | 3.16s | E   eq_chatbot_core.providers.base.ProviderError: Your default credentials were not found. To set up Application Default Credentials, see https://cloud.google.com/docs/authentication/external/set-up-adc for more information. |
| `integration/test_vertex_live.py::TestVertexLive::test_system_message` | FAILED | 2.90s | E   eq_chatbot_core.providers.base.ProviderError: Your default credentials were not found. To set up Application Default Credentials, see https://cloud.google.com/docs/authentication/external/set-up-adc for more information. |
| `integration/test_vertex_live.py::TestVertexLive::test_list_models` | PASSED | <0.01s |  |
| `integration/test_vertex_live.py::TestVertexLive::test_context_manager` | PASSED | <0.01s |  |

#### Provider: Melious.ai (sovereign EU) (1 passed, 3 failed) - 4.31s | Model: `gpt-oss-20b`

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_melious_live.py::TestMeliousLive::test_simple_completion` | FAILED | 1.97s | E   eq_chatbot_core.providers.base.ProviderError: Error code: 503 - {'error': {'message': 'The model provider encountered an error. Please try again.', 'type': 'server_error', 'param': None, 'code': 'provider_error'}} |
| `integration/test_melious_live.py::TestMeliousLive::test_streaming_completion` | FAILED | 0.33s | E   eq_chatbot_core.providers.base.ProviderError: The model provider encountered a streaming error. Please try again. |
| `integration/test_melious_live.py::TestMeliousLive::test_list_models` | PASSED | 0.16s |  |
| `integration/test_melious_live.py::TestMeliousLive::test_context_manager` | FAILED | 1.85s | E   eq_chatbot_core.providers.base.ProviderError: Error code: 503 - {'error': {'message': 'The model provider encountered an error. Please try again.', 'type': 'server_error', 'param': None, 'code': 'provider_error'}} |
