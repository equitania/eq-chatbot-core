# Test Report - 2026-07-07 18:10:47

**eq_chatbot_core v1.18.0** | 0.06s | Python 3.13.12 | macOS-26.5.2-arm64-arm-64bit-Mach-O

> **Result: ALL PASSED - 9 tests OK, 1 skipped**

Command: `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/.venv/bin/pytest tests/unit/test_document_extractor.py -q`

## Summary

| Status | Count |
|--------|-------|
| Passed | 9 |
| Failed | 0 |
| Skipped | 1 |
| **Total** | **10** |

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
| Google Vertex AI | — | $0.15 / $0.60 per 1M tok | — | SKIPPED — provider not exercised this run |
| LiteLLM Gateway | — | gateway (deployment-dependent) | — | SKIPPED — provider not exercised this run |
| IONOS AI Model Hub | — | ~$0.16 per 1M tok (EU-hosted, Berlin/de-txl) | — | SKIPPED — set `IONOS_API_KEY` in `tests/.env.test` |
| Melious.ai | — | ~EUR 0.4 in / 2.0 out per 1M tok (sovereign EU, MiniMax M3) | — | SKIPPED — provider not exercised this run |
| Local (LM Studio / Ollama) | — | $0 (local) | — | SKIPPED — provider not exercised this run |

## Skipped Tests

| Test | Reason / Action |
|------|-----------------|
| `unit/test_document_extractor.py::TestRichFormats::test_html_extraction` | Skipped: markitdown not installed (docs extra) |

## Results by Module

| Module | Test Model | Passed | Failed | Skipped | XFailed | Total | Duration |
|--------|------------|--------|--------|---------|---------|-------|----------|
| **Other** | - | 9 | 0 | 1 | 0 | 10 | <0.01s |

## Detailed Results

### Unit Tests (9 passed, 1 skipped)

#### Other (9 passed, 1 skipped) - <0.01s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `unit/test_document_extractor.py::TestPlainTextExtraction::test_markdown_passthrough` | PASSED | <0.01s |  |
| `unit/test_document_extractor.py::TestPlainTextExtraction::test_txt_passthrough` | PASSED | <0.01s |  |
| `unit/test_document_extractor.py::TestPlainTextExtraction::test_latin1_fallback_warns` | PASSED | <0.01s |  |
| `unit/test_document_extractor.py::TestGuards::test_too_large_rejected` | PASSED | <0.01s |  |
| `unit/test_document_extractor.py::TestGuards::test_default_limit_constant` | PASSED | <0.01s |  |
| `unit/test_document_extractor.py::TestGuards::test_unsupported_extension_rejected` | PASSED | <0.01s |  |
| `unit/test_document_extractor.py::TestGuards::test_non_bytes_rejected` | PASSED | <0.01s |  |
| `unit/test_document_extractor.py::TestGuards::test_supported_extensions_always_include_plain_text` | PASSED | <0.01s |  |
| `unit/test_document_extractor.py::TestRichFormats::test_missing_markitdown_yields_warning_not_crash` | PASSED | <0.01s |  |
| `unit/test_document_extractor.py::TestRichFormats::test_html_extraction` | SKIPPED | - | Skipped: markitdown not installed (docs extra) |
