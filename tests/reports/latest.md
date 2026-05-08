# Test Report - 2026-05-08 11:54:57

**eq_chatbot_core v1.7.0** | 2.35s | Python 3.13.12 | macOS-26.4.1-arm64-arm-64bit-Mach-O

> **Result: ALL PASSED - 1 tests OK**

Command: `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/.venv/lib/python3.13/site-packages/pytest/__main__.py tests/integration/test_openai_live.py::TestAnthropicLive::test_simple_completion -v --no-cov`

## Summary

| Status | Count |
|--------|-------|
| Passed | 1 |
| Failed | 0 |
| **Total** | **1** |

## Configuration Status

Credentials configured: `OpenAI`, `Anthropic`, `LangDock`, `OpenRouter`, `Mammouth`, `Azure`, `Vertex`

## Models In Use

Resolved live from `tests/model_registry.py` against each provider's `list_models()`. By convention the `primary` in each chain is the cheapest available model; fallbacks rescue the run when the primary is deprecated.

| Provider | Model Used | Cost (per 1M tok) | Source | Status |
|----------|-----------|-------------------|--------|--------|
| OpenAI | — | $0.15 / $0.60 per 1M tok | — | SKIPPED — provider not exercised this run |
| Anthropic | `claude-haiku-4-5-20251001` | $1.00 / $5.00 per 1M tok | Registry primary | OK |
| LangDock (OpenAI backend) | — | LangDock gateway (see langdock.com pricing) | — | SKIPPED — provider not exercised this run |
| LangDock (Anthropic backend) | — | LangDock gateway (see langdock.com pricing) | — | SKIPPED — provider not exercised this run |
| OpenRouter | — | $0.02 / $0.03 per 1M tok | — | SKIPPED — provider not exercised this run |
| Mammouth AI | — | $0.10 / $0.40 per 1M tok | — | SKIPPED — provider not exercised this run |
| Azure AI | — | deployment-dependent | — | SKIPPED — provider not exercised this run |
| Google Vertex AI | — | $0.15 / $0.60 per 1M tok | — | SKIPPED — provider not exercised this run |
| Local (LM Studio / Ollama) | — | $0 (local) | — | SKIPPED — provider not exercised this run |

## Results by Module

| Module | Test Model | Passed | Failed | Skipped | XFailed | Total | Duration |
|--------|------------|--------|--------|---------|---------|-------|----------|
| **Provider: OpenAI** | - | 1 | 0 | 0 | 0 | 1 | 1.71s |

## Detailed Results

### Integration Tests (1 passed)

#### Provider: OpenAI (1 passed) - 1.71s

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_openai_live.py::TestAnthropicLive::test_simple_completion` | PASSED | 1.71s |
