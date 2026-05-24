# Test Report - 2026-05-24 21:30:20

**eq_chatbot_core v1.7.2** | 0.04s | Python 3.13.12 | macOS-26.5-arm64-arm-64bit-Mach-O

> **Result: ALL PASSED - 12 tests OK**

Command: `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/.venv/bin/pytest tests/unit/realtime/test_mock.py tests/unit/realtime/test_factory.py -v -m unit`

## Summary

| Status | Count |
|--------|-------|
| Passed | 12 |
| Failed | 0 |
| **Total** | **12** |

## Configuration Status

**Action required** — missing API credentials cause tests to be skipped. Set the variables below in `tests/.env.test` to enable the affected tests:

| Provider | Missing variable(s) | Tests skipped | Action |
|----------|---------------------|---------------|--------|
| **OpenAI** | `OPENAI_API_KEY` | 0 | Add `OPENAI_API_KEY=...` to `tests/.env.test` |
| **Anthropic** | `ANTHROPIC_API_KEY` | 0 | Add `ANTHROPIC_API_KEY=...` to `tests/.env.test` |
| **LangDock** | `LANGDOCK_API_KEY` | 0 | Add `LANGDOCK_API_KEY=...` to `tests/.env.test` |
| **OpenRouter** | `OPENROUTER_API_KEY` | 0 | Add `OPENROUTER_API_KEY=...` to `tests/.env.test` |
| **Mammouth** | `MAMMOUTH_API_KEY` | 0 | Add `MAMMOUTH_API_KEY=...` to `tests/.env.test` |
| **Azure** | `AZURE_API_KEY`, `AZURE_ENDPOINT` | 0 | Add `AZURE_API_KEY=...` to `tests/.env.test` |
| **Vertex** | `VERTEX_PROJECT` | 0 | Add `VERTEX_PROJECT=...` to `tests/.env.test` |

## Models In Use

Resolved live from `tests/model_registry.py` against each provider's `list_models()`. By convention the `primary` in each chain is the cheapest available model; fallbacks rescue the run when the primary is deprecated.

| Provider | Model Used | Cost (per 1M tok) | Source | Status |
|----------|-----------|-------------------|--------|--------|
| OpenAI | — | $0.15 / $0.60 per 1M tok | — | SKIPPED — set `OPENAI_API_KEY` in `tests/.env.test` |
| Anthropic | — | $1.00 / $5.00 per 1M tok | — | SKIPPED — set `ANTHROPIC_API_KEY` in `tests/.env.test` |
| LangDock (OpenAI backend) | — | LangDock gateway (see langdock.com pricing) | — | SKIPPED — set `LANGDOCK_API_KEY` in `tests/.env.test` |
| LangDock (Anthropic backend) | — | LangDock gateway (see langdock.com pricing) | — | SKIPPED — set `LANGDOCK_API_KEY` in `tests/.env.test` |
| OpenRouter | — | $0.02 / $0.03 per 1M tok | — | SKIPPED — set `OPENROUTER_API_KEY` in `tests/.env.test` |
| Mammouth AI | — | ~$0.05 / $0.40 per 1M tok (gateway, passthrough) | — | SKIPPED — set `MAMMOUTH_API_KEY` in `tests/.env.test` |
| Azure AI | — | deployment-dependent | — | SKIPPED — set `AZURE_API_KEY` in `tests/.env.test` |
| Google Vertex AI | — | $0.15 / $0.60 per 1M tok | — | SKIPPED — set `VERTEX_PROJECT` in `tests/.env.test` |
| Local (LM Studio / Ollama) | — | $0 (local) | — | SKIPPED — `SKIP_LOCAL_TESTS=true` |

## Results by Module

| Module | Test Model | Passed | Failed | Skipped | XFailed | Total | Duration |
|--------|------------|--------|--------|---------|---------|-------|----------|
| **Services & Core** | - | 5 | 0 | 0 | 0 | 5 | <0.01s |
| **Other** | - | 7 | 0 | 0 | 0 | 7 | <0.01s |

## Detailed Results

### Unit Tests (12 passed)

#### Services & Core (5 passed) - <0.01s

| Test | Status | Duration |
|------|--------|----------|
| `unit/realtime/test_factory.py::test_registry_contains_mock` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_get_realtime_provider_mock` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_get_realtime_provider_case_insensitive` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_get_realtime_provider_unknown_raises` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_registry_registered_names_sorted` | PASSED | <0.01s |

#### Other (7 passed) - <0.01s

| Test | Status | Duration |
|------|--------|----------|
| `unit/realtime/test_mock.py::test_isinstance_check` | PASSED | <0.01s |
| `unit/realtime/test_mock.py::test_connect_sets_connected` | PASSED | <0.01s |
| `unit/realtime/test_mock.py::test_close_sets_disconnected` | PASSED | <0.01s |
| `unit/realtime/test_mock.py::test_context_manager` | PASSED | <0.01s |
| `unit/realtime/test_mock.py::test_enqueue_and_iter` | PASSED | <0.01s |
| `unit/realtime/test_mock.py::test_append_client_audio_even_ok` | PASSED | <0.01s |
| `unit/realtime/test_mock.py::test_append_client_audio_odd_raises` | PASSED | <0.01s |
