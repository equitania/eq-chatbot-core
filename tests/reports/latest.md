# Test Report - 2026-08-18 17:18:17

**eq_chatbot_core v2.1.0** | 10.11s | Python 3.12.13 | macOS-26.6.1-arm64-arm-64bit

> **Result: ALL PASSED - 1934 tests OK, 5 expected failures, 1 skipped**

Command: `/private/tmp/claude-501/-Users-picard-gitbase-PyPi-Projects-eq-chatbot-core/43f71caf-d5f3-4a97-a7df-21e33c8819d7/scratchpad/ci-env/bin/pytest tests/unit/ -q --no-header`

## Summary

| Status | Count |
|--------|-------|
| Passed | 1934 |
| Failed | 0 |
| Skipped | 1 |
| XFailed (expected) | 5 |
| **Total** | **1940** |

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
| Local (LM Studio / Ollama) | — | $0 (local) | — | SKIPPED — `SKIP_LOCAL_TESTS=true` |

## Skipped Tests

| Test | Reason / Action |
|------|-----------------|
| `unit/test_document_extractor.py::TestRichFormats::test_html_extraction` | Skipped: markitdown not installed (docs extra) |

## Results by Module

| Module | Test Model | Passed | Failed | Skipped | XFailed | Total | Duration |
|--------|------------|--------|--------|---------|---------|-------|----------|
| **Provider: OpenAI** | - | 46 | 0 | 0 | 0 | 46 | 0.04s |
| **Provider: Anthropic** | - | 50 | 0 | 0 | 0 | 50 | 0.13s |
| **Provider: LangDock** | - | 60 | 0 | 0 | 0 | 60 | 0.06s |
| **Provider: OpenRouter** | - | 41 | 0 | 0 | 0 | 41 | 0.01s |
| **Provider: Mammouth AI** | - | 42 | 0 | 0 | 0 | 42 | 0.01s |
| **Provider: Azure AI** | - | 50 | 0 | 0 | 0 | 50 | 0.04s |
| **Provider: Google Vertex AI** | - | 45 | 0 | 0 | 0 | 45 | 0.02s |
| **Provider: LiteLLM Gateway** | - | 30 | 0 | 0 | 0 | 30 | 0.02s |
| **Provider: IONOS AI Model Hub** | - | 27 | 0 | 0 | 0 | 27 | 0.04s |
| **Provider: Melious.ai (sovereign EU)** | - | 28 | 0 | 0 | 0 | 28 | 0.05s |
| **Provider: Local (LM Studio / Ollama)** | - | 35 | 0 | 0 | 0 | 35 | 0.03s |
| **Security** | - | 423 | 0 | 0 | 5 | 428 | 0.05s |
| **RAG Pipeline** | - | 117 | 0 | 0 | 0 | 117 | 0.36s |
| **Services & Core** | - | 203 | 0 | 0 | 0 | 203 | 0.03s |
| **MCP Client** | - | 99 | 0 | 0 | 0 | 99 | 1.56s |
| **Other** | - | 638 | 0 | 1 | 0 | 639 | 4.53s |

## Detailed Results

### Unit Tests (1933 passed, 1 skipped, 5 xfailed)

#### Provider: OpenAI (46 passed) - 0.04s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_openai.py::TestOpenAIProviderInit::test_basic_init` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderInit::test_init_with_custom_params` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderInit::test_ssrf_metadata_blocked` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderInit::test_private_range_blocked` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderInit::test_non_http_scheme_blocked` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderInit::test_rejected_base_url_leaves_instance_closable` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderInit::test_lazy_client_initialization` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderInit::test_client_property_creates_client` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderInit::test_client_reuses_instance` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIChatCompletion::test_simple_completion` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIChatCompletion::test_completion_with_model` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIChatCompletion::test_completion_with_temperature` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIChatCompletion::test_completion_with_max_tokens_legacy` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIChatCompletion::test_completion_with_max_tokens_new_api` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIChatCompletion::test_completion_with_tools` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIChatCompletion::test_completion_extra_kwargs` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIChatCompletion::test_completion_reasoning_model_no_temperature` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIChatCompletion::test_completion_gpt41_temperature_clamped` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIStreamCompletion::test_stream_completion` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIStreamCompletion::test_stream_includes_usage` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIStreamCompletion::test_stream_with_max_tokens` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIStreamCompletion::test_stream_tool_calls` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIListModels::test_list_models_filters_chat_models` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIListModels::test_list_models_includes_constraints` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIListModels::test_list_models_sorted` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIModelAPIDetection::test_new_api_models_detected` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIModelAPIDetection::test_legacy_api_models_detected` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIModelAPIDetection::test_case_insensitive_detection` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIModelConstraints::test_reasoning_model_constraints` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIModelConstraints::test_gpt_model_constraints` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIModelConstraints::test_vision_support_detection` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIModelConstraints::test_context_length_detection` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIErrorHandling::test_error_scrubs_secret` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIErrorHandling::test_rate_limit_error` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIErrorHandling::test_authentication_error` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIErrorHandling::test_context_length_error` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIErrorHandling::test_generic_error` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIErrorHandling::test_stream_error_handling` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIErrorHandling::test_list_models_error_handling` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderProperties::test_provider_name` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderProperties::test_default_model` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderProperties::test_default_base_url` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderProperties::test_repr` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderProperties::test_chat_model_prefixes` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderProperties::test_reasoning_model_no_temperature` | PASSED | <0.01s |
| `unit/test_openai.py::TestOpenAIProviderProperties::test_gpt41_temperature_passthrough` | PASSED | <0.01s |

#### Provider: Anthropic (50 passed) - 0.13s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_anthropic.py::TestAnthropicProviderInit::test_basic_init` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicProviderInit::test_init_with_custom_params` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicProviderInit::test_ssrf_metadata_blocked` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicProviderInit::test_private_range_blocked` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicProviderInit::test_non_http_scheme_blocked` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicProviderInit::test_lazy_client_initialization` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicProviderInit::test_client_property_creates_client` | PASSED | 0.03s |
| `unit/test_anthropic.py::TestAnthropicProviderInit::test_client_reuses_instance` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestSystemPromptExtraction::test_extract_single_system_prompt` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestSystemPromptExtraction::test_extract_multiple_system_prompts` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestSystemPromptExtraction::test_no_system_prompt` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestSystemPromptExtraction::test_system_prompt_with_cache_control_emits_blocks` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestSystemPromptExtraction::test_mixed_system_prompts_with_partial_cache_control` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestToolConversion::test_convert_single_tool` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestToolConversion::test_convert_multiple_tools` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestToolConversion::test_convert_none_tools` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestToolConversion::test_convert_empty_tools` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicChatCompletion::test_simple_completion` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicChatCompletion::test_completion_with_system_prompt` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicChatCompletion::test_completion_with_model` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicChatCompletion::test_completion_with_temperature` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicChatCompletion::test_completion_claude_opus3_gets_temperature` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicChatCompletion::test_completion_temperature_clamped_above_max` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicChatCompletion::test_completion_with_max_tokens` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicChatCompletion::test_completion_default_max_tokens` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicChatCompletion::test_completion_with_tools` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicChatCompletion::test_completion_mixed_content` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicStreamCompletion::test_stream_completion` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicStreamCompletion::test_stream_includes_usage` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicStreamCompletion::test_stream_with_system_prompt` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicListModels::test_list_models` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicListModels::test_list_models_includes_constraints` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicListModels::test_list_models_sorted_by_date` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicModelConstraints::test_sonnet4_constraints` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicModelConstraints::test_opus4_constraints` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicModelConstraints::test_opus3_constraints` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicModelConstraints::test_haiku_constraints` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicModelConstraints::test_temperature_range` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicErrorHandling::test_error_scrubs_secret` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicErrorHandling::test_rate_limit_error` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicErrorHandling::test_authentication_error` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicErrorHandling::test_context_length_error` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicErrorHandling::test_generic_error` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicErrorHandling::test_stream_error_handling` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicErrorHandling::test_list_models_error_handling` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicProviderProperties::test_provider_name` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicProviderProperties::test_default_model` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicProviderProperties::test_default_base_url` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicProviderProperties::test_claude_temperature_clamped_to_max` | PASSED | <0.01s |
| `unit/test_anthropic.py::TestAnthropicProviderProperties::test_repr` | PASSED | <0.01s |

#### Provider: LangDock (60 passed) - 0.06s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_langdock.py::TestLangDockProviderInit::test_basic_init` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderInit::test_init_with_openai_backend` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderInit::test_init_with_anthropic_backend` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderInit::test_init_with_google_backend` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderInit::test_init_with_agent_backend` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderInit::test_init_agent_without_agent_id_raises` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderInit::test_init_invalid_backend_raises` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderInit::test_init_with_reasoning_effort` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderInit::test_init_with_custom_timeout` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderInit::test_init_with_custom_base_url` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockBackendURLs::test_openai_eu_url` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockBackendURLs::test_openai_us_url` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockBackendURLs::test_anthropic_eu_url` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockBackendURLs::test_google_url` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockBackendURLs::test_agent_url` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockReasoningModels::test_o1_is_reasoning_model` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockReasoningModels::test_o3_is_reasoning_model` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockReasoningModels::test_o4_is_reasoning_model` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockReasoningModels::test_gpt_not_reasoning_model` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockReasoningModels::test_claude_not_reasoning_model` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockTokenAPI::test_gpt4o_uses_new_api` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockTokenAPI::test_gpt5_uses_new_api` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockTokenAPI::test_reasoning_models_use_new_api` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockTokenAPI::test_gpt4_turbo_uses_legacy_api` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockOpenAIChatCompletion::test_simple_completion` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockOpenAIChatCompletion::test_completion_with_temperature` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockOpenAIChatCompletion::test_completion_without_temperature_for_reasoning` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockOpenAIChatCompletion::test_completion_with_reasoning_effort` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockOpenAIChatCompletion::test_completion_with_max_tokens_new_api` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockOpenAIChatCompletion::test_completion_with_tools` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockAnthropicChatCompletion::test_simple_completion` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockAnthropicChatCompletion::test_completion_with_system_message` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockAnthropicChatCompletion::test_completion_with_temperature` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockStreamCompletion::test_stream_completion` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockStreamCompletion::test_stream_includes_usage` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockModelConstraints::test_gpt4o_constraints` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockModelConstraints::test_o1_constraints` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockModelConstraints::test_claude_constraints` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockModelConstraints::test_gemini_constraints` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockListModels::test_list_models_filters_supported` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockListModels::test_list_models_includes_metadata` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockListModels::test_list_models_includes_constraints` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockErrorHandling::test_rate_limit_error` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockErrorHandling::test_authentication_error` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockErrorHandling::test_context_length_error` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockErrorHandling::test_generic_error` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderProperties::test_provider_name` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderProperties::test_default_model_openai` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderProperties::test_default_model_anthropic` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderProperties::test_default_model_google` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderProperties::test_default_model_codestral` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderProperties::test_region_normalization` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockProviderProperties::test_backend_normalization` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockSystemPromptExtraction::test_extract_single_system_prompt` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockSystemPromptExtraction::test_extract_multiple_system_prompts` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockSystemPromptExtraction::test_no_system_prompt` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockSSRFGuard::test_cloud_metadata_endpoint_rejected` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockSSRFGuard::test_non_http_scheme_rejected` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockSSRFGuard::test_localhost_base_url_accepted` | PASSED | <0.01s |
| `unit/test_langdock.py::TestLangDockSSRFGuard::test_default_base_url_skips_validation` | PASSED | <0.01s |

#### Provider: OpenRouter (41 passed) - 0.01s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_openrouter.py::TestOpenRouterProviderInit::test_basic_init` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterProviderInit::test_init_with_custom_base_url` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterProviderInit::test_init_with_site_info` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterProviderInit::test_init_with_timeout` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterProviderProperties::test_provider_name` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterProviderProperties::test_default_model` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterReasoningModels::test_o1_is_reasoning_model` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterReasoningModels::test_o3_is_reasoning_model` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterReasoningModels::test_o4_is_reasoning_model` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterReasoningModels::test_gpt_not_reasoning_model` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterReasoningModels::test_claude_not_reasoning_model` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterReasoningModels::test_llama_not_reasoning_model` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterChatCompletion::test_simple_completion` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterChatCompletion::test_completion_with_temperature` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterChatCompletion::test_completion_without_temperature_for_reasoning` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterChatCompletion::test_completion_with_max_tokens` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterChatCompletion::test_completion_with_tools` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterStreamCompletion::test_simple_stream` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterStreamCompletion::test_stream_skips_sse_comment_lines` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterStreamCompletion::test_stream_finish_reason_propagates` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterStreamCompletion::test_stream_accumulates_tool_calls` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterListModels::test_list_models_returns_all` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterListModels::test_list_models_includes_metadata` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterListModels::test_list_models_includes_constraints` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterListModels::test_list_models_includes_pricing` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterModelConstraints::test_regular_model_constraints` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterModelConstraints::test_reasoning_model_constraints` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterModelConstraints::test_pricing_extraction` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterModelConstraints::test_pricing_with_missing_values` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterErrorHandling::test_error_scrubs_secret` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterErrorHandling::test_rate_limit_error` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterErrorHandling::test_authentication_error` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterErrorHandling::test_context_length_error` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterErrorHandling::test_generic_error` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterContextManager::test_close_client` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterContextManager::test_context_manager` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterFactoryIntegration::test_get_provider_returns_openrouter` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterSSRFGuard::test_cloud_metadata_endpoint_rejected` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterSSRFGuard::test_non_http_scheme_rejected` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterSSRFGuard::test_localhost_base_url_accepted` | PASSED | <0.01s |
| `unit/test_openrouter.py::TestOpenRouterSSRFGuard::test_default_base_url_skips_validation` | PASSED | <0.01s |

#### Provider: Mammouth AI (42 passed) - 0.01s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_mammouth.py::TestMammouthProviderInit::test_basic_init` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthProviderInit::test_init_with_custom_base_url` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthProviderInit::test_init_with_timeout` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthProviderProperties::test_provider_name` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthProviderProperties::test_default_model` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthTemperatureConstraints::test_reasoning_model_no_temperature` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthTemperatureConstraints::test_gpt5_temperature_passthrough` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthTemperatureConstraints::test_gpt41_temperature_passthrough` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthTemperatureConstraints::test_gpt41_valid_temperature_passes_through` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthTemperatureConstraints::test_legacy_model_passthrough` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthTemperatureConstraints::test_claude_max_temperature_clamped` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthTemperatureConstraints::test_unknown_model_uses_defaults` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthTemperatureConstraints::test_constraints_in_list_models` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthReasoningModels::test_o1_is_reasoning_model` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthReasoningModels::test_o3_is_reasoning_model` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthReasoningModels::test_o4_is_reasoning_model` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthReasoningModels::test_gpt_not_reasoning_model` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthReasoningModels::test_claude_not_reasoning_model` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthChatCompletion::test_simple_completion` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthChatCompletion::test_completion_temperature_clamped_for_gpt41` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthChatCompletion::test_completion_no_temperature_for_reasoning` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthChatCompletion::test_completion_with_max_tokens` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthChatCompletion::test_completion_with_tools` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthStreamCompletion::test_basic_streaming` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthStreamCompletion::test_streaming_temperature_clamped` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthListModels::test_list_models_returns_all` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthListModels::test_list_models_includes_metadata` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthListModels::test_list_models_includes_pricing` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthListModels::test_list_models_sorted` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthErrorHandling::test_error_scrubs_secret` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthErrorHandling::test_rate_limit_error` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthErrorHandling::test_authentication_error` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthErrorHandling::test_overloaded_error` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthErrorHandling::test_context_length_error` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthErrorHandling::test_generic_error` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthContextManager::test_close_client` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthContextManager::test_context_manager` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthFactoryIntegration::test_get_provider_returns_mammouth` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthSSRFGuard::test_cloud_metadata_endpoint_rejected` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthSSRFGuard::test_non_http_scheme_rejected` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthSSRFGuard::test_localhost_base_url_accepted` | PASSED | <0.01s |
| `unit/test_mammouth.py::TestMammouthSSRFGuard::test_default_base_url_skips_validation` | PASSED | <0.01s |

#### Provider: Azure AI (50 passed) - 0.04s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_azure.py::TestAzureProviderInit::test_basic_init` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureProviderInit::test_custom_params` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureProviderInit::test_base_url_required` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureProviderInit::test_model_override` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureProviderInit::test_lazy_client` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureProviderInit::test_client_created_with_base_url` | PASSED | 0.02s |
| `unit/test_azure.py::TestAzureMigrationGuardrails::test_legacy_endpoint_rejected` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureMigrationGuardrails::test_legacy_endpoint_message_names_replacement` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureMigrationGuardrails::test_legacy_endpoint_rejected_before_dns` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureMigrationGuardrails::test_api_version_is_deprecated_but_accepted` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureMigrationGuardrails::test_no_api_version_emits_no_warning` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureSSRFGuard::test_ssrf_metadata_blocked` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureSSRFGuard::test_private_range_blocked` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureSSRFGuard::test_non_http_scheme_blocked` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_reasoning_models_detected[o1]` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_reasoning_models_detected[o1-mini]` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_reasoning_models_detected[o3]` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_reasoning_models_detected[o3-mini]` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_reasoning_models_detected[o4-mini]` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_reasoning_models_detected[codex-mini]` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_reasoning_models_detected[DeepSeek-R1]` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_reasoning_models_detected[MAI-DS-R1]` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_non_reasoning_models[gpt-4o]` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_non_reasoning_models[gpt-4.1]` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_non_reasoning_models[gpt-5.2]` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_non_reasoning_models[Llama-3.3-70B-Instruct]` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_reasoning_model_uses_max_completion_tokens` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_standard_model_uses_max_tokens` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureReasoningModels::test_temperature_constraints_available` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureChatCompletion::test_simple_completion` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureChatCompletion::test_messages_passed_as_plain_dicts` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureChatCompletion::test_tools_passed_through` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureChatCompletion::test_tool_calls_parsed` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureStreamCompletion::test_stream_yields_content_then_final` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureStreamCompletion::test_stream_requests_usage` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureListModels::test_returns_static_catalog` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureListModels::test_catalog_covers_openai_and_foundry_models` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureListModels::test_entries_carry_metadata` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureListModels::test_does_not_call_the_api` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureErrorHandling::test_rate_limit` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureErrorHandling::test_authentication` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureErrorHandling::test_context_length` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureErrorHandling::test_generic_error` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureErrorHandling::test_error_scrubs_secret` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureContextManager::test_close_closes_client` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureContextManager::test_context_manager` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureContextManager::test_close_without_client_is_safe` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureContextManager::test_rejected_base_url_leaves_instance_closable` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureFactoryIntegration::test_factory_returns_azure_provider` | PASSED | <0.01s |
| `unit/test_azure.py::TestAzureFactoryIntegration::test_factory_rejects_legacy_endpoint` | PASSED | <0.01s |

#### Provider: Google Vertex AI (45 passed) - 0.02s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_vertex.py::TestVertexProviderInit::test_basic_init` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexProviderInit::test_custom_location` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexProviderInit::test_missing_project_raises` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexProviderInit::test_missing_sdk_raises` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexProviderInit::test_custom_timeout` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexProviderInit::test_api_key_ignored` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexProviderInit::test_api_key_defaults_to_not_used` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexProviderProperties::test_provider_name` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexProviderProperties::test_default_model` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexClientInit::test_client_lazy_init` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexClientInit::test_client_reused` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexTemperatureConstraints::test_gemini_temperature_range` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexTemperatureConstraints::test_gemini_temperature_passthrough` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexTemperatureConstraints::test_gemini_temperature_clamp_high` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexTemperatureConstraints::test_gemini_temperature_zero` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexMessageConversion::test_system_message_extraction` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexMessageConversion::test_multiple_system_messages` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexMessageConversion::test_assistant_role_mapped_to_model` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexMessageConversion::test_user_message` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexMessageConversion::test_tool_message_conversion` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexMessageConversion::test_tool_message_invalid_json` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexMessageConversion::test_no_system_message` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexChatCompletion::test_simple_completion` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexChatCompletion::test_completion_with_custom_model` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexChatCompletion::test_completion_with_max_tokens` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexChatCompletion::test_completion_with_tools` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexChatCompletion::test_completion_finish_reason_stop` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexChatCompletion::test_completion_empty_candidates` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexStreamCompletion::test_basic_streaming` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexStreamCompletion::test_streaming_with_tool_calls` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexListModels::test_list_models_returns_known_models` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexListModels::test_list_models_sorted` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexListModels::test_list_models_metadata` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexErrorHandling::test_error_scrubs_secret` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexErrorHandling::test_rate_limit_error` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexErrorHandling::test_auth_error` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexErrorHandling::test_overloaded_error` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexErrorHandling::test_context_length_error` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexErrorHandling::test_generic_error` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexErrorHandling::test_resource_exhausted_error` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexErrorHandling::test_unauthenticated_error` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexContextManager::test_close` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexContextManager::test_context_manager` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexFactoryIntegration::test_get_provider_vertex` | PASSED | <0.01s |
| `unit/test_vertex.py::TestVertexFactoryIntegration::test_get_provider_vertex_no_api_key_needed` | PASSED | <0.01s |

#### Provider: LiteLLM Gateway (30 passed) - 0.02s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_litellm.py::TestLiteLLMProviderInit::test_basic_init` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMProviderInit::test_base_url_required` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMProviderInit::test_base_url_empty_rejected` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMProviderInit::test_ssrf_metadata_blocked` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMProviderInit::test_non_http_scheme_blocked` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMProviderInit::test_lazy_client` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMProviderInit::test_client_created_with_base_url` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMProviderProperties::test_provider_name` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMProviderProperties::test_default_model_fallback` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMProviderProperties::test_default_model_override` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMChatCompletion::test_simple_completion` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMChatCompletion::test_uses_default_model` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMChatCompletion::test_explicit_model_and_max_tokens` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMChatCompletion::test_tools_passed_through` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMChatCompletion::test_reasoning_content_in_raw_not_in_content` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMChatCompletion::test_tool_calls_parsed` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMStreamCompletion::test_basic_stream` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMStreamCompletion::test_stream_requests_usage` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMListModels::test_returns_all_models_unfiltered` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMErrorHandling::test_rate_limit` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMErrorHandling::test_authentication` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMErrorHandling::test_context_length` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMErrorHandling::test_generic_error` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMErrorHandling::test_error_scrubs_secret` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMAudio::test_text_to_speech_returns_bytes` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMAudio::test_text_to_speech_custom_voice_and_model` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMAudio::test_transcribe_returns_text` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMAudio::test_tts_error_is_provider_error` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMContextManager::test_close_closes_client` | PASSED | <0.01s |
| `unit/test_litellm.py::TestLiteLLMContextManager::test_context_manager` | PASSED | <0.01s |

#### Provider: IONOS AI Model Hub (27 passed) - 0.04s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_ionos.py::TestIonosProviderInit::test_basic_init_defaults_base_url` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosProviderInit::test_base_url_optional` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosProviderInit::test_base_url_override` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosProviderInit::test_ssrf_metadata_blocked` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosProviderInit::test_private_range_blocked` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosProviderInit::test_non_http_scheme_blocked` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosProviderInit::test_lazy_client` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosProviderInit::test_client_created_with_default_base_url` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosProviderProperties::test_provider_name` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosProviderProperties::test_default_model_fallback` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosProviderProperties::test_default_model_override` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosChatCompletion::test_simple_completion` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosChatCompletion::test_uses_default_model` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosChatCompletion::test_explicit_model_and_max_tokens` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosChatCompletion::test_tools_passed_through` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosChatCompletion::test_temperature_clamped` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosChatCompletion::test_tool_calls_parsed` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosStreamCompletion::test_basic_stream` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosStreamCompletion::test_stream_requests_usage` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosListModels::test_returns_all_models_unfiltered` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosErrorHandling::test_rate_limit` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosErrorHandling::test_authentication` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosErrorHandling::test_context_length` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosErrorHandling::test_generic_error` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosErrorHandling::test_error_scrubs_secret` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosContextManager::test_close_closes_client` | PASSED | <0.01s |
| `unit/test_ionos.py::TestIonosContextManager::test_context_manager` | PASSED | <0.01s |

#### Provider: Melious.ai (sovereign EU) (28 passed) - 0.05s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_melious.py::TestMeliousProviderInit::test_basic_init_defaults_base_url` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousProviderInit::test_base_url_optional` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousProviderInit::test_base_url_override` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousProviderInit::test_ssrf_metadata_blocked` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousProviderInit::test_private_range_blocked` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousProviderInit::test_non_http_scheme_blocked` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousProviderInit::test_lazy_client` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousProviderInit::test_client_created_with_default_base_url` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousProviderProperties::test_provider_name` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousProviderProperties::test_default_model_fallback` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousProviderProperties::test_default_model_override` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousChatCompletion::test_simple_completion` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousChatCompletion::test_uses_default_model` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousChatCompletion::test_explicit_model_and_max_tokens` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousChatCompletion::test_tools_passed_through` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousChatCompletion::test_temperature_clamped` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousChatCompletion::test_melious_specific_kwargs_passed_through` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousChatCompletion::test_tool_calls_parsed` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousStreamCompletion::test_basic_stream` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousStreamCompletion::test_stream_requests_usage` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousListModels::test_returns_all_models_unfiltered` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousErrorHandling::test_rate_limit` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousErrorHandling::test_authentication` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousErrorHandling::test_context_length` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousErrorHandling::test_generic_error` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousErrorHandling::test_error_scrubs_secret` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousContextManager::test_close_closes_client` | PASSED | <0.01s |
| `unit/test_melious.py::TestMeliousContextManager::test_context_manager` | PASSED | <0.01s |

#### Provider: Local (LM Studio / Ollama) (35 passed) - 0.03s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_local.py::TestLocalLLMProviderInit::test_default_initialization` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderInit::test_custom_base_url` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderInit::test_ollama_url` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderInit::test_lm_studio_url` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderInit::test_custom_timeout` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderInit::test_custom_api_key` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderChatCompletion::test_chat_completion_success` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderChatCompletion::test_chat_completion_with_model` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderChatCompletion::test_chat_completion_with_temperature` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderChatCompletion::test_chat_completion_with_max_tokens` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderChatCompletion::test_chat_completion_no_usage` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderChatCompletion::test_chat_completion_with_tool_calls` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderErrors::test_connection_error` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderErrors::test_connection_error_scrubs_token_in_base_url_and_message` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderErrors::test_timeout_error` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderErrors::test_authentication_error` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderErrors::test_rate_limit_error` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderErrors::test_context_length_error` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderErrors::test_chat_completion_surfaces_error_body` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderStreaming::test_stream_completion_success` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderStreaming::test_stream_completion_handles_done_marker` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderStreaming::test_stream_completion_skips_empty_lines` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderStreaming::test_stream_completion_connection_error` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderStreaming::test_stream_completion_surfaces_error_event` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderListModels::test_list_models_success` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderListModels::test_list_models_with_context_length` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderListModels::test_list_models_connection_error` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderListModels::test_list_models_empty_response` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderAvailability::test_is_server_available_true` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderAvailability::test_is_server_available_false_connection_error` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderAvailability::test_is_server_available_false_timeout` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderAvailability::test_is_server_available_false_http_error` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderClient::test_client_lazy_initialization` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderClient::test_client_reuses_instance` | PASSED | <0.01s |
| `unit/test_local.py::TestLocalLLMProviderClient::test_client_includes_auth_header` | PASSED | <0.01s |

#### Security (423 passed, 5 xfailed) - 0.05s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `unit/test_encryption.py::TestKeyGeneration::test_generate_key_returns_string` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestKeyGeneration::test_generate_key_is_valid_base64` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestKeyGeneration::test_generate_key_can_initialize_fernet` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestKeyGeneration::test_generate_key_produces_unique_keys` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestKeyGeneration::test_generate_key_creates_working_instance` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestInitialization::test_init_with_string_key` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestInitialization::test_init_with_bytes_key` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestInitialization::test_init_stores_key_as_bytes` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestInitialization::test_init_bytes_key_stays_as_bytes` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestInitialization::test_init_with_invalid_key_raises_error` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestInitialization::test_init_with_empty_string_raises_error` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestInitialization::test_string_and_bytes_key_produce_same_encryption` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestFromKeyFactory::test_from_key_returns_instance` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestFromKeyFactory::test_from_key_with_string` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestFromKeyFactory::test_from_key_with_bytes` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestFromKeyFactory::test_from_key_equivalent_to_constructor` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEncryptDecryptRoundtrip::test_basic_roundtrip` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEncryptDecryptRoundtrip::test_encrypt_returns_bytes` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEncryptDecryptRoundtrip::test_decrypt_returns_string` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEncryptDecryptRoundtrip::test_encrypted_differs_from_plaintext` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEncryptDecryptRoundtrip::test_encrypt_produces_different_ciphertexts` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEncryptDecryptRoundtrip::test_roundtrip_with_long_text` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEncryptDecryptRoundtrip::test_roundtrip_with_special_characters` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEncryptDecryptRoundtrip::test_roundtrip_with_whitespace` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEncryptDecryptRoundtrip::test_roundtrip_with_single_character` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEncryptDecryptRoundtrip::test_decrypt_accepts_string_ciphertext` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEncryptDecryptRoundtrip::test_decrypt_accepts_bytes_ciphertext` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestStringEncryptDecrypt::test_encrypt_to_string_returns_string` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestStringEncryptDecrypt::test_string_roundtrip` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestStringEncryptDecrypt::test_encrypted_string_is_valid_base64` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestStringEncryptDecrypt::test_string_methods_compatible_with_bytes_methods` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestStringEncryptDecrypt::test_string_roundtrip_with_long_text` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEmptyStringHandling::test_encrypt_empty_string_returns_empty_bytes` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEmptyStringHandling::test_decrypt_empty_bytes_returns_empty_string` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEmptyStringHandling::test_decrypt_empty_string_returns_empty_string` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEmptyStringHandling::test_encrypt_to_string_empty_returns_empty` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEmptyStringHandling::test_decrypt_from_string_empty_returns_empty` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestDecryptionFailures::test_wrong_key_raises_invalid_token` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestDecryptionFailures::test_wrong_key_raises_invalid_token_string_methods` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestDecryptionFailures::test_corrupted_ciphertext_raises_error` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestDecryptionFailures::test_random_bytes_raises_error` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestDecryptionFailures::test_truncated_ciphertext_raises_error` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestDecryptionFailures::test_modified_single_byte_raises_error` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestKeyFingerprint::test_fingerprint_returns_string` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestKeyFingerprint::test_fingerprint_is_8_characters` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestKeyFingerprint::test_fingerprint_is_hexadecimal` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestKeyFingerprint::test_fingerprint_is_deterministic` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestKeyFingerprint::test_fingerprint_differs_for_different_keys` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestKeyFingerprint::test_fingerprint_matches_sha256_prefix` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestKeyFingerprint::test_fingerprint_consistent_string_and_bytes_init` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestKeyFingerprint::test_fingerprint_does_not_expose_key` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestUnicodeSupport::test_german_umlauts` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestUnicodeSupport::test_german_sharp_s_and_special_quotes` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestUnicodeSupport::test_emoji_roundtrip` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestUnicodeSupport::test_mixed_unicode_scripts` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestUnicodeSupport::test_unicode_with_string_methods` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestUnicodeSupport::test_multibyte_utf8_characters` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestUnicodeSupport::test_null_bytes_in_text` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestImportErrorHandling::test_init_raises_import_error_without_cryptography` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEdgeCases::test_very_long_plaintext` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEdgeCases::test_single_space` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEdgeCases::test_newline_only` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEdgeCases::test_multiple_sequential_operations` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEdgeCases::test_json_content_roundtrip` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEdgeCases::test_url_content_roundtrip` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEdgeCases::test_multiline_text_roundtrip` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEdgeCases::test_falsy_ciphertext_returns_empty` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestEdgeCases::test_independent_instances_same_key_cross_decrypt` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestRealWorldScenarios::test_api_key_storage_workflow` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestRealWorldScenarios::test_multiple_keys_encrypted_with_same_master` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestRealWorldScenarios::test_key_rotation_scenario` | PASSED | <0.01s |  |
| `unit/test_encryption.py::TestRealWorldScenarios::test_fingerprint_for_key_identification` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFileTypeConfig::test_default_values` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFileTypeConfig::test_custom_values` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFileTypeConfig::test_document_config` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFileValidationResult::test_valid_result` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFileValidationResult::test_invalid_result` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFileValidationResult::test_default_none_values` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_valid_png_extension` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_valid_jpg_extension` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_valid_pdf_extension` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_case_insensitive_extension` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_uppercase_extension` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_mixed_case_extension` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_invalid_extension_exe` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_invalid_extension_php` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_invalid_extension_sh` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_double_extension_attack` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_no_extension` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_empty_filename` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_dot_only_filename` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestExtensionValidation::test_allowed_extensions_listed_in_error` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestMimeTypeValidation::test_magic_disabled_skips_mime_check` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestMimeTypeValidation::test_magic_enabled_detects_mismatch` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestMimeTypeValidation::test_magic_enabled_accepts_match` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestMimeTypeValidation::test_csv_alias_text_csv_accepts_application_csv` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestMimeTypeValidation::test_text_plain_accepts_application_csv` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestMimeTypeValidation::test_jpeg_alias_accepts_image_jpg` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestMimeTypeValidation::test_json_alias_accepts_text_json` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestMimeTypeValidation::test_reverse_alias_application_csv_detected_as_text_csv` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestMimeTypeValidation::test_csv_detected_as_text_plain_rejected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestMimeTypeValidation::test_xml_alias_removed_for_security` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestMimeTypeValidation::test_completely_wrong_mime_rejected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_mz_header_detected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_elf_header_detected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_shebang_header_detected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_php_header_detected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_asp_header_detected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_script_tag_detected_in_text` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_script_tag_uppercase_detected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_javascript_url_detected_in_text` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_vbscript_url_detected_in_text` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_script_in_svg_detected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_script_in_xml_detected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_null_bytes_in_text_detected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_script_not_checked_in_binary_files` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_clean_text_file_passes` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_clean_csv_passes` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_vba_project_bin_detected_in_docx` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_excel_vba_path_detected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_word_vba_path_detected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_ppt_vba_path_detected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_clean_office_file_passes` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestContentScanning::test_scan_content_disabled_skips_check` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSizeValidation::test_file_within_size_limit` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSizeValidation::test_file_exceeds_size_limit` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSizeValidation::test_file_exactly_at_size_limit` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSizeValidation::test_empty_file_passes_size_check` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSizeValidation::test_different_limits_per_type` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSizeValidation::test_large_image_rejected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_normal_filename_unchanged` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_path_traversal_prevented` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_windows_path_traversal_prevented` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_absolute_path_stripped` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_null_bytes_removed` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_hidden_file_dot_stripped` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_multiple_leading_dots_stripped` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_unicode_normalized` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_dangerous_characters_replaced` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_control_characters_replaced` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_long_filename_truncated` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_exactly_200_char_name_not_truncated` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_empty_filename_returns_unnamed` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_none_like_empty_filename` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_only_dots_and_slashes` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_filename_with_spaces_preserved` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_filename_with_dashes_and_underscores` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_sanitized_filename_in_validation_result` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFilenameSanitization::test_no_extension_after_sanitization` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFullValidationPipeline::test_valid_png_full_pipeline` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFullValidationPipeline::test_valid_pdf_full_pipeline` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFullValidationPipeline::test_valid_csv_full_pipeline` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFullValidationPipeline::test_invalid_extension_stops_early` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFullValidationPipeline::test_dangerous_content_stops_at_layer_3` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFullValidationPipeline::test_oversized_file_stops_at_layer_4` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFullValidationPipeline::test_valid_file_with_path_traversal_sanitized` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFullValidationPipeline::test_empty_content_passes_validation` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFullValidationPipeline::test_json_content_passes` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestEdgeCases::test_empty_allowed_types_list` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestEdgeCases::test_single_allowed_type` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestEdgeCases::test_very_small_size_limit` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestEdgeCases::test_zero_size_limit_rejects_any_content` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestEdgeCases::test_content_with_all_header_patterns_at_non_start` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestEdgeCases::test_filename_with_multiple_extensions` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestEdgeCases::test_filename_with_unicode_characters` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestEdgeCases::test_binary_content_in_pdf` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestEdgeCases::test_all_dangerous_header_patterns_defined` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestEdgeCases::test_all_dangerous_text_patterns_defined` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestEdgeCases::test_all_office_macro_patterns_defined` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFactoryAndUtilities::test_create_validator_default` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFactoryAndUtilities::test_create_validator_magic_disabled` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFactoryAndUtilities::test_create_validator_magic_enabled_no_module` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFactoryAndUtilities::test_create_validator_magic_enabled_with_module` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFactoryAndUtilities::test_is_magic_available_returns_bool` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFactoryAndUtilities::test_is_magic_available_reflects_import` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFactoryAndUtilities::test_validator_use_magic_false_when_not_available` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFactoryAndUtilities::test_validator_use_magic_true_when_available` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestFactoryAndUtilities::test_validator_use_magic_false_explicit` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSecurityScenarios::test_polyglot_pdf_executable_rejected` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSecurityScenarios::test_null_byte_injection_in_filename` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSecurityScenarios::test_extension_mismatch_without_magic` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSecurityScenarios::test_html_disguised_as_text_with_script` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSecurityScenarios::test_macro_in_xlsx_with_vba_content` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSecurityScenarios::test_directory_traversal_in_validation` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSecurityScenarios::test_xml_alias_security_with_html_content` | PASSED | <0.01s |  |
| `unit/test_file_validator.py::TestSecurityScenarios::test_case_sensitivity_in_dangerous_patterns` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_ignore_previous_instructions` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_ignore_prior_instructions` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_disregard_previous` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_forget_everything` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_forget_all` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_you_are_now` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_new_instructions` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_override_previous` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_pretend_you_are` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_act_as_if` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_roleplay_as` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_simulate_being` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_show_system_prompt` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_tell_your_instructions` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_reveal_the_prompt` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_what_are_your_instructions` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_jailbreak` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_bypass_safety` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_bypass_restriction` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_dan_mode` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_developer_mode` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_do_anything_now` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_unlocked_mode` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_no_restrictions_mode` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_evil_mode` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionEnglish::test_opposite_mode` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionSystemMarkers::test_system_colon` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionSystemMarkers::test_inst_tag` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionSystemMarkers::test_system_pipe_tag` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionSystemMarkers::test_user_pipe_tag` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionSystemMarkers::test_assistant_pipe_tag` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionSystemMarkers::test_hash_system` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionSystemMarkers::test_hash_human` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionSystemMarkers::test_hash_assistant` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionSystemMarkers::test_system_xml_tag` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCode::test_eval` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCode::test_exec` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCode::test_dunder_import` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCode::test_subprocess` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCode::test_base64_encoding` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCode::test_decode` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCode::test_rot13` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCode::test_hex_encoding` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionGerman::test_ignoriere_vorherige` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionGerman::test_ignoriere_vorherige_singular` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionGerman::test_vergiss_alles` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionGerman::test_vergiss_alle` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionGerman::test_neue_anweisungen` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionGerman::test_du_bist_jetzt` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionGerman::test_du_bist_nun` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionGerman::test_tue_so_als_ob` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionFrench::test_ignore_les_instructions` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionFrench::test_ignorez_toutes_les_instructions` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionFrench::test_ignorer_les_instructions` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionFrench::test_oubliez_tout` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionFrench::test_oublier_tout` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionSpanish::test_ignora_las_instrucciones` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionSpanish::test_ignora_todas_las_instrucciones` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionSpanish::test_olvida_todo` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCleanText::test_simple_greeting` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCleanText::test_technical_question` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCleanText::test_german_business_text` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCleanText::test_french_polite_text` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCleanText::test_spanish_normal_text` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCleanText::test_code_discussion` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCleanText::test_long_clean_text` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionCleanText::test_text_with_numbers_and_symbols` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_cyrillic_a_in_ignore` | XFAILED | <0.01s | NFKD normalization does not map Cyrillic homoglyphs to ASCII equivalents. Cyrillic 'о' (U+043E) stays Cyrillic after NFKD. A confusables table would be needed. |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_cyrillic_e_in_forget` | XFAILED | <0.01s | NFKD normalization does not map Cyrillic homoglyphs to ASCII equivalents. Cyrillic 'е' (U+0435) stays Cyrillic after NFKD. |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_cyrillic_o_in_override` | XFAILED | <0.01s | NFKD normalization does not map Cyrillic homoglyphs to ASCII equivalents. Cyrillic 'о' (U+043E) stays Cyrillic after NFKD. |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_zero_width_space_between_words` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_zero_width_joiner_inside_word` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_zero_width_non_joiner_inside_word` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_word_joiner_bypass` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_bom_character_bypass` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_variation_selector_16_bypass` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_variation_selector_15_bypass` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_left_to_right_mark_bypass` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_right_to_left_mark_bypass` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_multiple_zero_width_chars` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_invisible_times_bypass` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_invisible_separator_bypass` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_mixed_cyrillic_and_zero_width` | XFAILED | <0.01s | NFKD normalization does not map Cyrillic homoglyphs to ASCII equivalents. Zero-width chars are stripped, but Cyrillic 'о'/'а' remain Cyrillic after NFKD. |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_german_pattern_with_zero_width` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestDetectInjectionUnicodeBypass::test_french_pattern_with_zero_width` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_zero_width_space` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_zero_width_joiner` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_zero_width_non_joiner` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_word_joiner` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_bom` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_variation_selector_16` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_variation_selector_15` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_ltr_mark` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_rtl_mark` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_invisible_times` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_invisible_separator` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_invisible_plus` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_strips_function_application` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_multiple_zero_width_chars` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_nfkd_normalization_latin` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_nfkd_normalization_umlaut` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_plain_ascii_unchanged` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestNormalizeText::test_empty_string` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_clean_text_unchanged` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_html_escaping_angle_brackets` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_html_escaping_ampersand` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_html_escaping_quotes` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_html_escaping_single_quote` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_html_escaping_disabled` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_suspicious_text_wrapped` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_suspicious_text_html_escaped_then_wrapped` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_angle_bracket_injection_detected_before_escape` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_empty_string_returns_empty` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_none_like_empty_returns_empty` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_whitespace_only` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_unicode_bypass_in_sanitize` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestSanitizeInput::test_german_injection_wrapped` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestBuildSafeSystemPrompt::test_basic_prompt_with_all_defaults` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestBuildSafeSystemPrompt::test_prompt_without_safety_prefix` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestBuildSafeSystemPrompt::test_prompt_without_safety_suffix` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestBuildSafeSystemPrompt::test_prompt_without_any_safety` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestBuildSafeSystemPrompt::test_prompt_with_context` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestBuildSafeSystemPrompt::test_prompt_with_tools` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestBuildSafeSystemPrompt::test_prompt_with_context_and_tools` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestBuildSafeSystemPrompt::test_prompt_no_context_no_tools` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestBuildSafeSystemPrompt::test_safety_prefix_contains_key_rules` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestBuildSafeSystemPrompt::test_safety_suffix_contains_reminder` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestBuildSafeSystemPrompt::test_ordering_prefix_before_base` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestBuildSafeSystemPrompt::test_ordering_base_before_suffix` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_clean_text_zero_score` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_empty_string_zero_score` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_single_pattern_match` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_two_pattern_matches` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_multiple_patterns_high_score` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_long_text_bonus` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_score_capped_at_one` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_score_type_is_float` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_unicode_bypass_still_scored` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_cyrillic_bypass_still_scored` | XFAILED | <0.01s | NFKD normalization does not map Cyrillic homoglyphs to ASCII equivalents. |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_three_matches_bonus` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_german_injection_scored` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestGetInjectionRiskScore::test_french_injection_scored` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestFormatToolsSection::test_empty_tools_list` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestFormatToolsSection::test_none_like_empty_tools` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestFormatToolsSection::test_single_tool` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestFormatToolsSection::test_multiple_tools` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestFormatToolsSection::test_tool_without_name` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestFormatToolsSection::test_tool_without_description` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestFormatToolsSection::test_tool_without_function_key` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestFormatToolsSection::test_long_description_truncated` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestFormatToolsSection::test_description_exactly_200_not_truncated` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestFormatToolsSection::test_header_text_present` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestFormatToolsSection::test_tool_entries_use_dash_prefix` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_detect_injection_case_insensitive` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_detect_injection_mixed_case` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_detect_injection_with_extra_whitespace` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_detect_injection_very_long_clean_text` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_detect_injection_multiline` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_risk_score_consistency` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_detect_injection_returns_tuple` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_sanitize_preserves_newlines` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_build_prompt_empty_base` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_detect_injection_tab_characters` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_sanitize_input_only_injection_no_html` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_normalize_text_preserves_ascii_letters` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_normalize_text_preserves_digits` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_normalize_text_preserves_punctuation` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_pattern_partial_word_no_false_positive` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestEdgeCases::test_detect_injection_with_only_whitespace` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestExternalContent::test_scan_flags_injection_in_tool_result` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestExternalContent::test_scan_clean_content_is_safe` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestExternalContent::test_scan_empty_content` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestExternalContent::test_wrap_fences_content_as_data` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestExternalContent::test_wrap_warns_on_suspicious_content` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestExternalContent::test_wrap_does_not_html_escape` | PASSED | <0.01s |  |
| `unit/test_injection.py::TestExternalContent::test_wrap_empty_content` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestRateLimitConfig::test_default_values` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestRateLimitConfig::test_custom_values` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestRateLimitConfig::test_partial_custom_values` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestRateLimitConfig::test_zero_limits` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestRateLimitConfig::test_very_large_limits` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestUsageRecord::test_basic_creation` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestUsageRecord::test_zero_counts` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestRateLimitResult::test_allowed_result_defaults` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestRateLimitResult::test_denied_result_with_details` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestRateLimitResult::test_result_with_custom_usage_and_limit` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitAllowed::test_request_allowed_under_all_limits` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitAllowed::test_request_allowed_with_moderate_usage` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitAllowed::test_allowed_result_contains_hourly_usage_and_limit` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitAllowed::test_allowed_just_under_minute_limit` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitAllowed::test_allowed_just_under_hourly_limit` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitAllowed::test_allowed_just_under_daily_token_limit` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitAllowed::test_allowed_with_zero_estimated_tokens` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitBurst::test_burst_limit_exceeded` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitBurst::test_burst_limit_exceeded_over_limit` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitBurst::test_burst_limit_checked_first` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitBurst::test_burst_limit_zero_blocks_everything` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitHourly::test_hourly_limit_exceeded` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitHourly::test_hourly_limit_exceeded_over_limit` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitHourly::test_hourly_limit_checked_after_burst` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitHourly::test_hourly_limit_zero_blocks_after_burst` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitDaily::test_daily_token_limit_exceeded` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitDaily::test_daily_limit_retry_after_seconds_until_midnight` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitDaily::test_daily_limit_with_only_estimated_tokens_exceeding` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitDaily::test_daily_limit_checked_last` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitDaily::test_daily_limit_exact_boundary_allowed` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitDaily::test_daily_limit_one_over_boundary_denied` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitStorageInteraction::test_storage_get_minute_usage_called` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitStorageInteraction::test_storage_get_hourly_usage_called` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitStorageInteraction::test_storage_get_daily_tokens_called` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitStorageInteraction::test_storage_not_called_past_burst_denial` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitStorageInteraction::test_storage_daily_not_called_past_hourly_denial` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitStorageInteraction::test_all_storage_methods_called_when_all_pass` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitStorageInteraction::test_record_usage_is_not_called` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitPriority::test_burst_takes_priority_over_hourly` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitPriority::test_hourly_takes_priority_over_daily` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitEdgeCases::test_user_id_zero` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitEdgeCases::test_large_estimated_tokens` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitEdgeCases::test_negative_estimated_tokens_still_works` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitEdgeCases::test_multiple_users_use_separate_calls` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensWithTiktoken::test_basic_text_estimation` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensWithTiktoken::test_empty_string` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensWithTiktoken::test_long_text` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensWithTiktoken::test_default_model_is_gpt4` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensWithTiktoken::test_different_model_names` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensWithTiktoken::test_unknown_model_uses_default_encoding` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensWithTiktoken::test_claude_model_approximation` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensWithTiktoken::test_unicode_text` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensWithTiktoken::test_multiline_text` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensFallback::test_fallback_uses_char_count_divided_by_four` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensFallback::test_fallback_empty_string` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensFallback::test_fallback_short_string` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensFallback::test_fallback_known_length` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEstimateTokensFallback::test_fallback_ignores_model_parameter` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitIntegration::test_full_workflow_allowed` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitIntegration::test_full_workflow_denied_by_tokens` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestCheckRateLimitIntegration::test_consecutive_checks_accumulate` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEnforceRateLimit::test_atomic_storage_is_recognized_by_protocol` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEnforceRateLimit::test_plain_storage_without_method_is_not_atomic` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEnforceRateLimit::test_prefers_atomic_check_and_record` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEnforceRateLimit::test_non_atomic_records_usage_when_allowed` | PASSED | <0.01s |  |
| `unit/test_rate_limit.py::TestEnforceRateLimit::test_non_atomic_does_not_record_when_denied` | PASSED | <0.01s |  |

#### RAG Pipeline (117 passed) - 0.36s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_chunker.py::TestBasicChunking::test_single_chunk_for_small_text` | PASSED | <0.01s |
| `unit/test_chunker.py::TestBasicChunking::test_multiple_chunks_for_large_text` | PASSED | <0.01s |
| `unit/test_chunker.py::TestBasicChunking::test_chunk_indices_are_sequential` | PASSED | <0.01s |
| `unit/test_chunker.py::TestEmptyTextGuard::test_empty_string_yields_no_chunks` | PASSED | <0.01s |
| `unit/test_chunker.py::TestEmptyTextGuard::test_whitespace_only_yields_no_chunks` | PASSED | <0.01s |
| `unit/test_chunker.py::TestEmptyTextGuard::test_none_like_empty_yields_no_chunks` | PASSED | <0.01s |
| `unit/test_chunker.py::TestEmptyTextGuard::test_encoder_not_called_for_empty_text` | PASSED | <0.01s |
| `unit/test_chunker.py::TestOverlapBehavior::test_overlap_causes_token_reuse` | PASSED | <0.01s |
| `unit/test_chunker.py::TestOverlapBehavior::test_zero_overlap_produces_non_overlapping_chunks` | PASSED | <0.01s |
| `unit/test_chunker.py::TestSentenceBoundaryAdjustment::test_trims_to_sentence_ending_above_70_percent` | PASSED | <0.01s |
| `unit/test_chunker.py::TestSentenceBoundaryAdjustment::test_no_trim_when_boundary_below_70_percent` | PASSED | <0.01s |
| `unit/test_chunker.py::TestSentenceBoundaryAdjustment::test_no_trim_when_no_sentence_boundary` | PASSED | <0.01s |
| `unit/test_chunker.py::TestSentenceBoundaryAdjustment::test_recognizes_all_ending_patterns` | PASSED | <0.01s |
| `unit/test_chunker.py::TestMetadataPropagation::test_metadata_passed_through_single_chunk` | PASSED | <0.01s |
| `unit/test_chunker.py::TestMetadataPropagation::test_metadata_with_chunk_index_in_multi_chunk` | PASSED | <0.01s |
| `unit/test_chunker.py::TestMetadataPropagation::test_none_metadata_defaults_to_empty_dict` | PASSED | <0.01s |
| `unit/test_chunker.py::TestMetadataPropagation::test_original_metadata_not_mutated` | PASSED | <0.01s |
| `unit/test_chunker.py::TestTokenCounting::test_count_tokens_returns_word_count` | PASSED | <0.01s |
| `unit/test_chunker.py::TestTokenCounting::test_count_tokens_single_word` | PASSED | <0.01s |
| `unit/test_chunker.py::TestEdgeCases::test_single_character_text` | PASSED | <0.01s |
| `unit/test_chunker.py::TestEdgeCases::test_text_with_only_punctuation` | PASSED | <0.01s |
| `unit/test_chunker.py::TestEdgeCases::test_very_small_chunk_size` | PASSED | <0.01s |
| `unit/test_chunker.py::TestEdgeCases::test_overlap_equal_to_chunk_size_does_not_infinite_loop` | PASSED | <0.01s |
| `unit/test_chunker.py::TestLazyInitialization::test_encoder_is_none_before_first_access` | PASSED | <0.01s |
| `unit/test_chunker.py::TestLazyInitialization::test_encoder_initialized_on_first_property_access` | PASSED | <0.01s |
| `unit/test_chunker.py::TestLazyInitialization::test_encoder_cached_after_initialization` | PASSED | <0.01s |
| `unit/test_chunker.py::TestLazyInitialization::test_import_error_raised_when_tiktoken_missing` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestContextWindowManagerInit::test_default_parameters` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestContextWindowManagerInit::test_known_model_uses_correct_limit` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestContextWindowManagerInit::test_unknown_model_falls_back_to_128000` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestContextWindowManagerInit::test_custom_ratios_are_stored` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestBudgetValidation::test_sum_exceeds_one_raises_valueerror` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestBudgetValidation::test_negative_history_ratio_raises_valueerror` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestBudgetValidation::test_negative_rag_ratio_raises_valueerror` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestBudgetValidation::test_exact_sum_of_one_is_ok` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestBudgetValidation::test_zero_ratios_are_ok` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestGetModelLimit::test_exact_match` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestGetModelLimit::test_prefix_match` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestGetModelLimit::test_no_match_returns_default` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestGetModelLimit::test_claude_exact_match` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestCountTokens::test_returns_word_count_via_mock` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestCountTokens::test_empty_string` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestAllocateBudget::test_correct_allocation_with_ratios` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestAllocateBudget::test_available_for_content_property` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestAllocateBudget::test_large_system_prompt_reduces_available` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestTruncateMessages::test_keeps_newest_within_budget` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestTruncateMessages::test_empty_list_returns_empty` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestTruncateMessages::test_single_message_over_budget_returns_empty` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestTruncateRagContext::test_highest_scoring_kept` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestTruncateRagContext::test_empty_results_returns_empty` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestBuildContext::test_assembles_system_rag_history_user` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestBuildContext::test_no_rag_results_omits_rag_message` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestFormatRagContext::test_formats_numbered_sources` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestFormatRagContext::test_empty_list_returns_empty_string` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestFormatRagContext::test_none_source_shows_unknown` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestContextBudget::test_available_for_content_calculation` | PASSED | <0.01s |
| `unit/test_context_manager.py::TestContextBudget::test_available_for_content_with_zero_system` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestFieldConfig::test_basic_field` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestFieldConfig::test_relational_field` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestFieldConfig::test_text_field` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestModelConfig::test_basic_model_config` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestModelConfig::test_model_config_with_domain` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestOdooSchemaGenerator::test_generate_schema` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestOdooSchemaGenerator::test_generate_relations` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestOdooSchemaGenerator::test_generate_search_instructions` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestRecordTransformer::test_transform_simple_record` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestRecordTransformer::test_transform_record_with_display_values` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestRecordTransformer::test_transform_multiple_records` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestKnowledgeExporter::test_generate_documentation` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestKnowledgeExporter::test_prepare_for_qdrant` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestKnowledgeExporter::test_prepare_for_langdock` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestKnowledgeExporter::test_export_to_langdock_filenames_cannot_escape_temp_dir` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestKnowledgeExporter::test_empty_records` | PASSED | <0.01s |
| `unit/test_knowledge_service.py::TestExportRecord::test_create_export_record` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveSuccess::test_retrieve_returns_retrieval_results` | PASSED | 0.34s |
| `unit/test_retriever.py::TestRetrieveSuccess::test_retrieve_maps_payload_fields_correctly` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveSuccess::test_retrieve_calls_embedder_with_query` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveSuccess::test_retrieve_calls_qdrant_search` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveSuccess::test_retrieve_respects_custom_top_k` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveSuccess::test_retrieve_uses_default_top_k` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveSuccess::test_retrieve_handles_missing_payload_fields` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveEmptyQuery::test_empty_string_returns_empty_list` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveEmptyQuery::test_whitespace_only_returns_empty_list` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveEmptyQuery::test_tabs_and_newlines_returns_empty_list` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveEmptyQuery::test_empty_query_does_not_call_embedder` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveEmptyQuery::test_empty_query_does_not_call_qdrant` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveWithFilters::test_filter_dict_is_passed_to_qdrant` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveWithFilters::test_no_filters_passes_none` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveWithFilters::test_empty_dict_passes_none` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveEmbeddingFailure::test_embedding_failure_raises_runtime_error` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveEmbeddingFailure::test_embedding_failure_preserves_original_cause` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveQdrantSearchFailure::test_search_failure_raises_connection_error` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveQdrantSearchFailure::test_search_failure_preserves_original_cause` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveWithReranking::test_reranking_boosts_keyword_matches` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveWithReranking::test_reranking_is_applied_when_results_exceed_top_k` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveWithoutReranking::test_no_rerank_returns_results_in_original_order` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveWithoutReranking::test_no_rerank_uses_top_k_as_limit` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRetrieveWithoutReranking::test_no_rerank_preserves_original_scores` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRerank::test_rerank_combines_semantic_and_keyword_scores` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRerank::test_rerank_no_keyword_overlap` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRerank::test_rerank_partial_keyword_overlap` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRerank::test_rerank_sorts_by_combined_score_descending` | PASSED | <0.01s |
| `unit/test_retriever.py::TestRerank::test_rerank_empty_query_no_division_error` | PASSED | <0.01s |
| `unit/test_retriever.py::TestEnsureCollection::test_creates_collection_when_not_exists` | PASSED | <0.01s |
| `unit/test_retriever.py::TestEnsureCollection::test_skips_creation_when_collection_exists` | PASSED | <0.01s |
| `unit/test_retriever.py::TestEnsureCollection::test_uses_embedder_dimensions_when_vector_size_not_given` | PASSED | <0.01s |
| `unit/test_retriever.py::TestEnsureCollection::test_connection_error_on_list_collections_failure` | PASSED | <0.01s |
| `unit/test_retriever.py::TestEnsureCollection::test_connection_error_preserves_original_cause` | PASSED | <0.01s |
| `unit/test_retriever.py::TestUpsert::test_upsert_returns_count_of_inserted_points` | PASSED | <0.01s |
| `unit/test_retriever.py::TestUpsert::test_upsert_empty_chunks_returns_zero` | PASSED | <0.01s |
| `unit/test_retriever.py::TestUpsert::test_upsert_empty_chunks_does_not_call_embedder` | PASSED | <0.01s |
| `unit/test_retriever.py::TestUpsert::test_upsert_calls_embedder_with_contents` | PASSED | <0.01s |
| `unit/test_retriever.py::TestUpsert::test_upsert_calls_qdrant_upsert` | PASSED | <0.01s |
| `unit/test_retriever.py::TestUpsert::test_upsert_batches_large_chunk_lists` | PASSED | <0.01s |
| `unit/test_retriever.py::TestUpsert::test_upsert_embedding_failure_raises_runtime_error` | PASSED | <0.01s |
| `unit/test_retriever.py::TestUpsert::test_upsert_qdrant_failure_raises_connection_error` | PASSED | <0.01s |
| `unit/test_retriever.py::TestUpsert::test_upsert_handles_missing_optional_fields` | PASSED | <0.01s |

#### Services & Core (203 passed) - 0.03s

| Test | Status | Duration |
|------|--------|----------|
| `unit/realtime/test_factory.py::test_registry_contains_mock` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_get_realtime_provider_mock` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_get_realtime_provider_case_insensitive` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_get_realtime_provider_unknown_raises` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_get_realtime_provider_openai_missing_api_key_raises_value_error` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_registry_registered_names_sorted` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_registry_contains_gemini_live` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_registry_contains_nova_sonic` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_get_realtime_provider_nova_sonic_returns_stub` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_get_realtime_provider_gemini_live_developer_missing_api_key_raises` | PASSED | <0.01s |
| `unit/realtime/test_factory.py::test_get_realtime_provider_gemini_live_vertex_missing_access_token_raises` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestCalculateCost::test_exact_match_gpt4o_mini` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestCalculateCost::test_prefix_match_gpt4o_dated` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestCalculateCost::test_longest_prefix_o1_mini_over_o1` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestCalculateCost::test_longest_prefix_claude_sonnet_dated_v2` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestCalculateCost::test_longest_prefix_gpt4o_mini_custom_over_gpt4o` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestCalculateCost::test_unknown_model_uses_default_pricing` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestCalculateCost::test_zero_tokens_returns_zero` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestCalculateCost::test_only_input_tokens_defaults_output_to_zero` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestCalculateCost::test_result_rounded_to_six_decimal_places` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestCalculateCost::test_embedding_model_zero_output_cost` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestCalculateCost::test_openrouter_prefix_openai_gpt4o_mini` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestCalculateCost::test_openrouter_prefix_anthropic_claude_dated` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestGetModelPricing::test_exact_match_returns_correct_pricing` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestGetModelPricing::test_longest_prefix_match_o1_mini_variant` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestGetModelPricing::test_unknown_model_returns_default` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestGetModelPricing::test_openrouter_prefix_resolves_to_real_pricing` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestEstimateMonthlyCost::test_basic_monthly_calculation` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestEstimateMonthlyCost::test_zero_requests_returns_zero` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestEstimateMonthlyCost::test_result_rounded_to_two_decimal_places` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_key_models_exist_in_pricing[gpt-4-turbo]` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_key_models_exist_in_pricing[gpt-4o]` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_key_models_exist_in_pricing[gpt-4o-mini]` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_key_models_exist_in_pricing[gpt-4]` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_key_models_exist_in_pricing[o1]` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_key_models_exist_in_pricing[o1-mini]` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_key_models_exist_in_pricing[o3-mini]` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_key_models_exist_in_pricing[claude-3-5-sonnet-latest]` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_key_models_exist_in_pricing[claude-3-5-sonnet-20241022]` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_key_models_exist_in_pricing[claude-3-opus-latest]` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_key_models_exist_in_pricing[text-embedding-3-small]` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_key_models_exist_in_pricing[text-embedding-3-large]` | PASSED | <0.01s |
| `unit/test_cost_service.py::TestPricingDict::test_all_entries_have_input_and_output_keys` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestErrorClassification::test_timeout_error_classification` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestErrorClassification::test_timeout_error_with_timed_out_keyword` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestErrorClassification::test_rate_limit_error_classification` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestErrorClassification::test_rate_limit_error_by_text` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestErrorClassification::test_auth_error_classification` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestErrorClassification::test_auth_error_by_text` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestErrorClassification::test_token_limit_error_classification` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestErrorClassification::test_token_limit_by_token_keyword` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestErrorClassification::test_generic_error_classification` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestTimeoutRetry::test_timeout_retry_with_callback_success` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestTimeoutRetry::test_timeout_retry_exhausted_falls_back` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestTimeoutRetry::test_timeout_retry_count_increments` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestTimeoutRetry::test_timeout_no_retry_when_count_exhausted` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestTimeoutRetry::test_jitter_in_timeout_retry` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestTimeoutRetry::test_jitter_maximum_value` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestTimeoutRetry::test_jitter_minimum_value` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestFallbackProviderChain::test_fallback_chain_openai_to_langdock` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestFallbackProviderChain::test_fallback_chain_skips_failing_provider` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestFallbackProviderChain::test_all_fallbacks_fail` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestFallbackProviderChain::test_no_fallback_when_get_provider_fn_is_none` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestFallbackProviderChain::test_no_fallback_chain_for_unknown_provider` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestFallbackProviderChain::test_try_fallback_provider_directly_no_get_provider` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestFallbackProviderChain::test_try_fallback_provider_directly_all_fail` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestFallbackProviderChain::test_fallback_chain_definitions` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestFallbackProviderChain::test_fallback_provider_returns_none` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestRateLimitHandling::test_rate_limit_extracts_retry_after` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestRateLimitHandling::test_rate_limit_default_retry_after` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestRateLimitHandling::test_extract_retry_after_various_formats` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestRateLimitHandling::test_extract_retry_after_returns_none` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestGermanErrorMessages::test_timeout_message_in_german` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestGermanErrorMessages::test_rate_limit_message_in_german` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestGermanErrorMessages::test_auth_error_message_in_german` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestGermanErrorMessages::test_token_limit_message_in_german` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestGermanErrorMessages::test_generic_error_message_in_german` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestLoggingCallback::test_log_fn_called_on_rate_limit` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestLoggingCallback::test_log_fn_called_on_auth_error` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestLoggingCallback::test_log_fn_not_called_on_timeout` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestLoggingCallback::test_log_fn_receives_rate_limit_retry_after` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestErrorResult::test_error_result_defaults` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestErrorResult::test_error_result_with_all_fields` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestEnums::test_error_severity_values` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestEnums::test_error_category_values` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestLogScrubbing::test_generic_error_log_scrubs_secret` | PASSED | <0.01s |
| `unit/test_error_handler.py::TestLogScrubbing::test_fallback_failure_log_scrubs_secret` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestProviderError::test_basic_instantiation` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestProviderError::test_with_status_code` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestProviderError::test_with_all_parameters` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestProviderError::test_is_exception` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestProviderError::test_can_be_raised_and_caught` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestProviderError::test_empty_message` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestRateLimitError::test_is_provider_error_subclass` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestRateLimitError::test_typical_rate_limit` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestRateLimitError::test_can_be_caught_as_provider_error` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestRateLimitError::test_can_be_caught_specifically` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestAuthenticationError::test_is_provider_error_subclass` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestAuthenticationError::test_typical_auth_error` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestAuthenticationError::test_can_be_caught_as_provider_error` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestAuthenticationError::test_can_be_caught_specifically` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestContextLengthError::test_is_provider_error_subclass` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestContextLengthError::test_typical_context_error` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestContextLengthError::test_can_be_caught_as_provider_error` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestContextLengthError::test_can_be_caught_specifically` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestExceptionHierarchy::test_exception_types_are_distinct` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestExceptionHierarchy::test_can_discriminate_exception_types` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestExceptionHierarchy::test_order_of_exception_catching` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestErrorAttributes::test_provider_attribute_types` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestErrorAttributes::test_status_code_common_values` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestErrorAttributes::test_retry_after_values` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestErrorAttributes::test_error_message_preserves_details` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestExceptionStringRepresentation::test_str_method` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestExceptionStringRepresentation::test_repr_method` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestExceptionStringRepresentation::test_exception_in_f_string` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestExceptionStringRepresentation::test_exception_args` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestExceptionChaining::test_exception_cause` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestExceptionChaining::test_exception_context` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestExceptionChaining::test_suppress_context` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestRealWorldScenarios::test_openai_rate_limit_response` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestRealWorldScenarios::test_anthropic_auth_error` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestRealWorldScenarios::test_context_length_with_token_counts` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestRealWorldScenarios::test_local_provider_connection_error` | PASSED | <0.01s |
| `unit/test_exceptions.py::TestRealWorldScenarios::test_retry_logic_based_on_error_type` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryCloudProviders::test_get_openai_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryCloudProviders::test_get_anthropic_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryCloudProviders::test_get_langdock_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryCloudProviders::test_get_openrouter_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryCloudProviders::test_get_azure_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryCloudProviders::test_get_azure_provider_rejects_legacy_endpoint` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryCloudProviders::test_get_vertex_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryCloudProviders::test_get_ionos_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryCloudProviders::test_get_melious_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryCloudProviders::test_provider_name_case_insensitive` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryCloudProviders::test_custom_base_url` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryCloudProviders::test_custom_base_url_ssrf_blocked` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryLocalProviders::test_get_local_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryLocalProviders::test_get_local_provider_default_api_key` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryLocalProviders::test_get_lm_studio_alias` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryLocalProviders::test_get_lmstudio_alias` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryLocalProviders::test_get_ollama_alias` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryLocalProviders::test_local_alias_custom_base_url_override` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryLocalProviders::test_local_provider_with_api_key` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryLocalProviders::test_local_alias_case_insensitive` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryErrors::test_unknown_provider_raises_error` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryErrors::test_error_message_lists_available_providers` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryErrors::test_none_api_key_for_cloud_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryErrors::test_none_api_key_for_local_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryKwargs::test_timeout_passed_to_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryKwargs::test_max_retries_passed_to_provider` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryKwargs::test_multiple_kwargs` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryProviderProperties::test_openai_default_model` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryProviderProperties::test_anthropic_default_model` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryProviderProperties::test_local_default_model` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryProviderProperties::test_provider_names_correct` | PASSED | <0.01s |
| `unit/test_factory.py::TestFactoryProviderProperties::test_openrouter_default_model` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_exact_match_gpt41` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_exact_match_reasoning_model` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_exact_match_legacy_openai` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_prefix_match_claude` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_prefix_match_claude_opus` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_claude_models_without_temperature[claude-fable-5]` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_claude_models_without_temperature[claude-mythos-5]` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_claude_models_without_temperature[claude-mythos-preview]` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_claude_models_without_temperature[claude-opus-5]` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_claude_models_without_temperature[claude-opus-4-8]` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_claude_models_without_temperature[claude-opus-4-7]` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_claude_models_without_temperature[claude-sonnet-5]` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_dated_variant_inherits_the_explicit_entry` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_older_claude_models_keep_temperature` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_prefix_match_gemini` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_prefix_match_mistral` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_longest_prefix_match` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_default_fallback_unknown_model` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_deepseek_reasoner` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_deepseek_chat` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_case_insensitive_mistral_uppercase` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_case_insensitive_deepseek_v3_azure_form` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_case_insensitive_deepseek_r1_reasoning` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_case_insensitive_mai_ds_r1` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_case_insensitive_llama_uppercase` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_case_insensitive_cohere_kimi` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestGetTemperatureConstraints::test_no_uppercase_keys_in_constraints` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampTemperature::test_clamp_passthrough_gpt41` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampTemperature::test_clamp_passthrough_gpt5` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampTemperature::test_clamp_above_max_claude` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampTemperature::test_clamp_above_max_mistral` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampTemperature::test_reasoning_model_returns_none` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampTemperature::test_in_range_passthrough` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampTemperature::test_exact_min_boundary` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampTemperature::test_exact_max_boundary` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampTemperature::test_unknown_model_wide_range` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampTemperature::test_deepseek_reasoner_returns_none` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestStripProviderPrefix::test_strip_openai_prefix` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestStripProviderPrefix::test_strip_anthropic_prefix` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestStripProviderPrefix::test_strip_google_prefix` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestStripProviderPrefix::test_no_prefix_unchanged` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestStripProviderPrefix::test_strip_meta_prefix` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestStripProviderPrefix::test_strip_only_first_slash` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampWithPrefixStrip::test_openrouter_gpt41_passthrough` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampWithPrefixStrip::test_openrouter_claude_clamped` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampWithPrefixStrip::test_openrouter_o3_returns_none` | PASSED | <0.01s |
| `unit/test_temperature_constraints.py::TestClampWithPrefixStrip::test_openrouter_unknown_passthrough` | PASSED | <0.01s |

#### MCP Client (99 passed) - 1.56s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_mcp.py::TestMCPClientInitialization::test_init_with_defaults` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientInitialization::test_init_with_custom_timeout` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientInitialization::test_init_with_api_key` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientInitialization::test_init_strips_trailing_slash` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientInitialization::test_get_headers_without_api_key` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientInitialization::test_get_headers_with_api_key` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientConnection::test_connect_not_connected_initially` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientConnection::test_disconnect_clears_state` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientConnection::test_close_calls_disconnect` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientSSEEventHandling::test_handle_endpoint_event_absolute_url` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientSSEEventHandling::test_handle_endpoint_event_relative_url` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientSSEEventHandling::test_handle_message_event` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientSSEEventHandling::test_handle_message_event_unknown_request_id` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientSSEEventHandling::test_handle_message_event_invalid_json` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientSSEEventHandling::test_handle_endpoint_event_rejects_private_ip` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientSSEEventHandling::test_handle_endpoint_event_rejects_non_http_scheme` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientRequests::test_send_request_not_connected` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientRequests::test_send_request_success` | PASSED | 0.05s |
| `unit/test_mcp.py::TestMCPClientRequests::test_send_request_timeout` | PASSED | 1.01s |
| `unit/test_mcp.py::TestMCPClientRequests::test_send_request_http_error` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientRequests::test_send_request_increments_id` | PASSED | 0.06s |
| `unit/test_mcp.py::TestMCPClientToolOperations::test_list_tools_success` | PASSED | 0.05s |
| `unit/test_mcp.py::TestMCPClientToolOperations::test_list_tools_empty` | PASSED | 0.06s |
| `unit/test_mcp.py::TestMCPClientToolOperations::test_call_tool_success` | PASSED | 0.05s |
| `unit/test_mcp.py::TestMCPClientToolOperations::test_call_tool_error` | PASSED | 0.05s |
| `unit/test_mcp.py::TestMCPClientToolOperations::test_get_tool_schema_found` | PASSED | 0.06s |
| `unit/test_mcp.py::TestMCPClientToolOperations::test_get_tool_schema_not_found` | PASSED | 0.06s |
| `unit/test_mcp.py::TestMCPClientToolOperations::test_call_tool_extracts_text_content` | PASSED | 0.06s |
| `unit/test_mcp.py::TestMCPClientContextManager::test_context_manager_enter_exit` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientContextManager::test_context_manager_exception_cleanup` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientInitialization::test_init_with_defaults` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientInitialization::test_init_with_args` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientInitialization::test_init_with_env` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientInitialization::test_init_with_custom_timeout` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientInitialization::test_init_rejects_code_injection_env[LD_PRELOAD]` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientInitialization::test_init_rejects_code_injection_env[DYLD_INSERT_LIBRARIES]` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientInitialization::test_init_rejects_code_injection_env[PYTHONSTARTUP]` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientInitialization::test_init_rejects_code_injection_env[ld_preload]` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientInitialization::test_init_rejects_code_injection_env[BASH_ENV]` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientInitialization::test_init_allows_pythonpath_env` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientProcessManagement::test_start_creates_subprocess` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientProcessManagement::test_start_already_started` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientProcessManagement::test_start_does_not_leak_secrets_to_subprocess` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientProcessManagement::test_stop_terminates_process` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientProcessManagement::test_stop_kills_on_timeout` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientProcessManagement::test_stop_not_started` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientRequests::test_send_request_not_started` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientRequests::test_send_request_success` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientRequests::test_send_request_timeout` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientRequests::test_send_request_error_response` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientRequests::test_send_request_process_closed` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientToolOperations::test_list_tools_async` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientToolOperations::test_call_tool_async_success` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientToolOperations::test_call_tool_async_error` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientToolOperations::test_list_tools_async_error` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientContextManager::test_async_context_manager` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioMCPClientContextManager::test_sync_context_manager` | PASSED | <0.01s |
| `unit/test_mcp.py::TestGetMCPClient::test_get_mcp_client_sse` | PASSED | <0.01s |
| `unit/test_mcp.py::TestGetMCPClient::test_get_mcp_client_stdio` | PASSED | <0.01s |
| `unit/test_mcp.py::TestGetMCPClient::test_get_mcp_client_invalid_transport` | PASSED | <0.01s |
| `unit/test_mcp.py::TestGetMCPClient::test_get_mcp_client_missing_url` | PASSED | <0.01s |
| `unit/test_mcp.py::TestGetMCPClient::test_get_mcp_client_missing_command` | PASSED | <0.01s |
| `unit/test_mcp.py::TestGetMCPClient::test_get_mcp_client_with_timeout` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPToolResult::test_tool_result_success` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPToolResult::test_tool_result_failure` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPToolResult::test_tool_result_defaults` | PASSED | <0.01s |
| `unit/test_mcp.py::TestMCPClientVersion::test_client_uses_package_version` | PASSED | <0.01s |
| `unit/test_mcp.py::TestURLValidation::test_valid_http_url` | PASSED | <0.01s |
| `unit/test_mcp.py::TestURLValidation::test_valid_https_url` | PASSED | <0.01s |
| `unit/test_mcp.py::TestURLValidation::test_invalid_scheme_ftp` | PASSED | <0.01s |
| `unit/test_mcp.py::TestURLValidation::test_invalid_scheme_file` | PASSED | <0.01s |
| `unit/test_mcp.py::TestURLValidation::test_empty_hostname_rejected` | PASSED | <0.01s |
| `unit/test_mcp.py::TestURLValidation::test_localhost_127_allowed` | PASSED | <0.01s |
| `unit/test_mcp.py::TestURLValidation::test_private_ip_blocked` | PASSED | <0.01s |
| `unit/test_mcp.py::TestURLValidation::test_link_local_blocked` | PASSED | <0.01s |
| `unit/test_mcp.py::TestURLValidation::test_mcpclient_validates_url` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_allowed_command_python` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_allowed_command_python3` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_allowed_command_node` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_allowed_command_uvx` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_blocked_command_bash` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_blocked_command_curl` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_blocked_command_rm` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_shell_metachar_in_args_semicolon` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_shell_metachar_in_args_pipe` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_shell_metachar_in_args_backtick` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_clean_args_accepted` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_stdio_client_validates_command` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioCommandValidation::test_stdio_client_validates_args` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioEnvWhitelistHardening::test_pythonpath_not_forwarded_to_subprocess` | PASSED | <0.01s |
| `unit/test_mcp.py::TestStdioEnvWhitelistHardening::test_pythonpath_via_explicit_env_still_works` | PASSED | <0.01s |
| `unit/test_mcp.py::TestDNSRebindingProtection::test_validate_url_returns_resolved_ips` | PASSED | <0.01s |
| `unit/test_mcp.py::TestDNSRebindingProtection::test_validate_url_rejects_unresolvable_in_strict_mode` | PASSED | <0.01s |
| `unit/test_mcp.py::TestDNSRebindingProtection::test_validate_url_allows_unresolvable_in_lan_mode` | PASSED | <0.01s |
| `unit/test_mcp.py::TestDNSRebindingProtection::test_pinned_transport_rejects_rebinding` | PASSED | <0.01s |
| `unit/test_mcp.py::TestDNSRebindingProtection::test_pinned_transport_passes_when_resolution_matches` | PASSED | <0.01s |
| `unit/test_mcp.py::TestDNSRebindingProtection::test_pinned_transport_skips_check_for_unpinned_hosts` | PASSED | <0.01s |
| `unit/test_mcp.py::TestDNSRebindingProtection::test_mcpclient_pins_base_url_on_init` | PASSED | <0.01s |
| `unit/test_mcp.py::TestDNSRebindingProtection::test_mcpclient_pins_endpoint_from_sse_event` | PASSED | <0.01s |

#### Other (637 passed, 1 skipped) - 4.53s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `unit/realtime/test_contracts.py::test_event_type_string_values` | PASSED | <0.01s |  |
| `unit/realtime/test_contracts.py::test_event_type_count` | PASSED | <0.01s |  |
| `unit/realtime/test_contracts.py::test_input_audio_sample_rate` | PASSED | <0.01s |  |
| `unit/realtime/test_contracts.py::test_normalized_event_typeddict` | PASSED | <0.01s |  |
| `unit/realtime/test_contracts.py::test_capabilities_defaults` | PASSED | <0.01s |  |
| `unit/realtime/test_contracts.py::test_capabilities_frozen` | PASSED | <0.01s |  |
| `unit/realtime/test_contracts.py::test_adapter_contract_runtime_checkable` | PASSED | <0.01s |  |
| `unit/realtime/test_import_guard.py::test_import_guard_friendly_error` | PASSED | <0.01s |  |
| `unit/realtime/test_import_guard.py::test_always_importable_without_websockets` | PASSED | <0.01s |  |
| `unit/realtime/test_import_guard.py::test_realtime_providers_constant` | PASSED | <0.01s |  |
| `unit/realtime/test_mock.py::test_isinstance_check` | PASSED | <0.01s |  |
| `unit/realtime/test_mock.py::test_connect_sets_connected` | PASSED | <0.01s |  |
| `unit/realtime/test_mock.py::test_close_sets_disconnected` | PASSED | <0.01s |  |
| `unit/realtime/test_mock.py::test_context_manager` | PASSED | <0.01s |  |
| `unit/realtime/test_mock.py::test_enqueue_and_iter` | PASSED | <0.01s |  |
| `unit/realtime/test_mock.py::test_append_client_audio_even_ok` | PASSED | <0.01s |  |
| `unit/realtime/test_mock.py::test_append_client_audio_odd_raises` | PASSED | <0.01s |  |
| `unit/realtime/test_pyproject.py::test_realtime_extra_declared` | PASSED | <0.01s |  |
| `unit/realtime/test_pyproject.py::test_dev_extra_has_pytest_asyncio` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsRealtimeConfig::test_frozen_dataclass` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsRealtimeConfig::test_default_sample_rate` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsRealtimeConfig::test_default_base_url` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsRealtimeConfig::test_default_voice_none` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsRealtimeConfig::test_default_instructions_none` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsRealtimeConfig::test_custom_base_url` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsCapabilities::test_no_manual_turn_commit` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsCapabilities::test_tool_result_mode_elevenlabs_native` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsCapabilities::test_session_sample_rate_16k` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsCapabilities::test_server_vad_true` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsCapabilities::test_tool_calling_true` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestConstructorValidation::test_empty_api_key_raises` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestConstructorValidation::test_whitespace_api_key_raises` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestConstructorValidation::test_empty_agent_id_raises` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestConstructorValidation::test_whitespace_agent_id_raises` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestConstructorValidation::test_valid_config_does_not_raise` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestConnectionErrorEndpoint::test_api_key_not_in_endpoint` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestConnectionErrorEndpoint::test_agent_id_in_endpoint` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestConnectionErrorEndpoint::test_endpoint_starts_with_wss` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestConnectionErrorEndpoint::test_no_auth_header_in_url` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestConnectLifecycle::test_isinstance_realtime_adapter_contract` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestConnectLifecycle::test_provider_name` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestConnectLifecycle::test_capabilities_property` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_conversation_initiation_metadata_maps_to_session_ready` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_audio_maps_to_response_audio_delta` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_agent_response_maps_to_response_done` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_agent_response_complete_maps_to_response_done` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_user_transcript_maps_to_input_audio_committed` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_interruption_maps_to_input_speech_started` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_client_tool_call_maps_to_tool_call_completed` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_tool_call_completed_payload_has_call_id` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_tool_call_completed_payload_has_name` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_ping_returns_none_sentinel` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_agent_response_correction_maps_to_unhandled` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_unknown_event_maps_to_unhandled` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsEventMapping::test_missing_type_maps_to_unhandled` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsAudioInput::test_audio_chunk_format_has_user_audio_chunk_key` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsAudioInput::test_audio_chunk_format_no_type_key` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsAudioInput::test_audio_chunk_is_base64` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsAudioInput::test_empty_audio_is_noop` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsTurnControl::test_commit_client_turn_noop` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsTurnControl::test_create_response_noop` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsTurnControl::test_cancel_response_noop` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsToolResult::test_tool_result_uses_client_tool_result_type` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsToolResult::test_tool_result_uses_tool_call_id_not_call_id` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsToolResult::test_tool_result_tool_call_id_value` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsToolResult::test_tool_result_result_field` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_elevenlabs.py::TestElevenLabsToolResult::test_tool_result_is_error_false` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestGeminiLiveConfig::test_frozen` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestGeminiLiveConfig::test_has_dataclass_fields` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestGeminiLiveConfig::test_default_model_contains_gemini` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestGeminiLiveConfig::test_default_model_is_verified_alias` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestGeminiLiveConfig::test_default_mode_is_developer` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestGeminiLiveConfig::test_default_region_is_europe_west4` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestGeminiLiveConfig::test_custom_fields` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestCapabilities::test_server_vad_is_false` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestCapabilities::test_manual_turn_commit_required_is_true` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestCapabilities::test_tool_result_mode_is_provider_call_id` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestCapabilities::test_all_streaming_flags` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestCapabilities::test_tool_calling_true` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestCapabilities::test_voice_selection_false` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestCapabilities::test_interruption_cancel_false` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConstructorValidation::test_empty_api_key_for_developer_raises_value_error` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConstructorValidation::test_whitespace_api_key_for_developer_raises_value_error` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConstructorValidation::test_empty_access_token_for_vertex_raises_value_error` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConstructorValidation::test_whitespace_access_token_for_vertex_raises_value_error` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConstructorValidation::test_unknown_mode_raises_value_error` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConstructorValidation::test_empty_model_raises_value_error` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConstructorValidation::test_valid_developer_config_does_not_raise` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConstructorValidation::test_valid_vertex_config_does_not_raise` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestEndpointModes::test_developer_mode_url_contains_key_param` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestEndpointModes::test_developer_mode_has_no_authorization_header` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestEndpointModes::test_developer_mode_url_is_wss` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestEndpointModes::test_developer_mode_url_contains_generativelanguage` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestEndpointModes::test_vertex_mode_url_contains_aiplatform` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestEndpointModes::test_vertex_mode_url_contains_region` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestEndpointModes::test_vertex_mode_has_authorization_header` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestEndpointModes::test_vertex_mode_has_project_header` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestEndpointModes::test_vertex_mode_url_does_not_contain_key_param` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConnectionErrorEndpoint::test_developer_endpoint_does_not_contain_api_key` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConnectionErrorEndpoint::test_vertex_endpoint_does_not_contain_access_token` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConnectionErrorEndpoint::test_developer_endpoint_is_wss_url` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConnectionErrorEndpoint::test_vertex_endpoint_is_wss_url` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestRedaction::test_redact_key_param_from_developer_url` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestRedaction::test_redact_url_without_key_param_unchanged` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestRedaction::test_redact_bearer_token_from_error_text` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestRedaction::test_redact_api_key_from_error_text` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestRedaction::test_redact_empty_text_returns_empty` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestSetupEvent::test_build_setup_event_adds_models_prefix` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestSetupEvent::test_build_setup_event_does_not_double_prefix` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestSetupEvent::test_build_setup_event_includes_system_instruction` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestSetupEvent::test_build_setup_event_no_system_instruction_when_none` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestSetupEvent::test_build_setup_event_top_level_key_is_setup` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestSetupEvent::test_build_setup_event_contains_model` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestToolSchemaConversion::test_tool_definition_uses_parameters_field` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestToolSchemaConversion::test_to_gemini_schema_strips_additional_properties` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestToolSchemaConversion::test_to_gemini_schema_empty_object_returns_none` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestToolSchemaConversion::test_to_gemini_schema_none_input_returns_none` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestToolSchemaConversion::test_dict_tool_passthrough` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestIterNormalizedEvents::test_setup_complete_maps_to_session_ready` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestIterNormalizedEvents::test_server_content_audio_maps_to_audio_delta` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestIterNormalizedEvents::test_server_content_turn_complete_maps_to_response_done` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestIterNormalizedEvents::test_tool_call_maps_to_tool_call_completed` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestIterNormalizedEvents::test_tool_call_payload_has_call_id_and_name` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestIterNormalizedEvents::test_tool_call_cancellation_maps_to_tool_call_cancelled` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestIterNormalizedEvents::test_error_frame_maps_to_error` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestIterNormalizedEvents::test_unknown_key_maps_to_unhandled` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestIterNormalizedEvents::test_all_results_have_source_and_raw_fields` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestManualTurnCommit::test_commit_client_turn_sends_audio_stream_end` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestToolResult::test_submit_tool_result_sends_correct_shape` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestToolResult::test_submit_tool_result_decodes_json_output` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestToolResult::test_submit_tool_result_fallback_for_malformed_json` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConnectLifecycle::test_on_connected_does_not_call_initialize_session` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_gemini.py::TestConnectLifecycle::test_implements_contract` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestContractConformance::test_isinstance_realtime_adapter_contract` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestAllMethodsRaise::test_async_method_raises[connect-kwargs0]` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestAllMethodsRaise::test_async_method_raises[close-kwargs1]` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestAllMethodsRaise::test_async_method_raises[initialize_session-kwargs2]` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestAllMethodsRaise::test_async_method_raises[update_session-kwargs3]` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestAllMethodsRaise::test_async_method_raises[append_client_audio-kwargs4]` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestAllMethodsRaise::test_async_method_raises[commit_client_turn-kwargs5]` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestAllMethodsRaise::test_async_method_raises[create_response-kwargs6]` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestAllMethodsRaise::test_async_method_raises[cancel_response-kwargs7]` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestAllMethodsRaise::test_async_method_raises[register_tools-kwargs8]` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestAllMethodsRaise::test_async_method_raises[submit_tool_result-kwargs9]` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestAllMethodsRaise::test_iter_normalized_events_raises` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_nova.py::TestErrorMessages::test_message_references_v190` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestOpenAIRealtimeConfig::test_frozen` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestOpenAIRealtimeConfig::test_default_model_is_gpt_realtime` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestOpenAIRealtimeConfig::test_default_voice_is_ash` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestOpenAIRealtimeConfig::test_default_include_turn_detection_true` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestOpenAIRealtimeConfig::test_default_instructions_is_none` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestOpenAIRealtimeConfig::test_custom_fields` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestCapabilities::test_server_vad_true` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestCapabilities::test_manual_turn_commit_required_false` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestCapabilities::test_tool_result_mode_conversation_item` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestCapabilities::test_all_streaming_flags` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestCapabilities::test_tool_calling_true` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestCapabilities::test_voice_selection_true` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestCapabilities::test_interruption_cancel_true` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestCapabilities::test_startup_validation_true` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestConstructorValidation::test_empty_api_key_raises_value_error` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestConstructorValidation::test_whitespace_api_key_raises_value_error` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestConstructorValidation::test_empty_model_raises_value_error` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestConstructorValidation::test_whitespace_model_raises_value_error` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestConstructorValidation::test_valid_key_and_model_does_not_raise` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestVADSessionPayload::test_turn_detection_present_when_include_true` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestVADSessionPayload::test_turn_detection_absent_when_include_false` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestVADSessionPayload::test_turn_detection_type_is_server_vad` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestVADSessionPayload::test_session_update_event_type` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestVADSessionPayload::test_session_model_matches_config` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestConnectionErrorEndpoint::test_does_not_contain_api_key` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestConnectionErrorEndpoint::test_contains_model` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestConnectionErrorEndpoint::test_is_wss_url` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestNormalizeTools::test_tool_definition_conversion` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestNormalizeTools::test_dict_passthrough` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestNormalizeTools::test_none_returns_none` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestNormalizeTools::test_empty_list_returns_none` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestNormalizeTools::test_mixed_list` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_session_created_maps_to_session_ready` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_session_updated_maps_to_session_ready` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_response_audio_delta_normalized` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_response_audio_done_normalized` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_response_done_normalized` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_input_speech_started_normalized` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_input_speech_stopped_normalized` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_response_created_normalized` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_input_audio_committed_normalized` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_error_normalized` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_unknown_event_normalized` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_missing_type_normalized` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestIterNormalizedEvents::test_raw_and_source_fields_present` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestToolCallNormalization::test_function_call_arguments_done_maps_to_tool_call_completed` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestToolCallNormalization::test_function_call_arguments_done_has_item_sub_dict` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestToolCallNormalization::test_function_call_top_level_fields` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestToolCallNormalization::test_function_call_item_id_in_item` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestToolCallNormalization::test_function_call_response_id_in_payload` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestToolCallNormalization::test_function_call_item_type_is_function_call` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestToolCallNormalization::test_response_output_item_done_with_function_call_maps_to_tool_call_completed` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestToolCallNormalization::test_response_output_item_done_non_function_call_maps_to_unhandled` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestConnectLifecycle::test_on_connected_calls_initialize_session` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestConnectLifecycle::test_implements_contract` | PASSED | <0.01s |  |
| `unit/realtime/test_realtime_openai.py::TestCloseLifecycle::test_close_does_not_raise_when_not_connected` | PASSED | <0.01s |  |
| `unit/realtime/test_websocket_client.py::test_connect_with_backoff_3_failures_then_success` | PASSED | <0.01s |  |
| `unit/realtime/test_websocket_client.py::test_connect_with_backoff_all_failures_raises` | PASSED | 2.02s |  |
| `unit/realtime/test_websocket_client.py::test_realtime_closed_error_fields` | PASSED | <0.01s |  |
| `unit/realtime/test_websocket_client.py::test_realtime_rate_limit_error` | PASSED | <0.01s |  |
| `unit/realtime/test_websocket_client.py::test_error_hierarchy` | PASSED | <0.01s |  |
| `unit/realtime/test_websocket_client.py::test_base_class_is_abstract` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestHealthAndProviders::test_health_returns_ok_without_auth` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestHealthAndProviders::test_providers_requires_auth` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestHealthAndProviders::test_providers_lists_known_names` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_returns_provider_response` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_authentication_error_returns_401` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_rate_limit_returns_429_with_retry_after` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_context_length_returns_413` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_unknown_provider_returns_400` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_with_tools_forwards_to_provider` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_provider_extra_forwarded_to_factory` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_stream_provider_extra_forwarded_to_factory` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestChatStreamEndpoint::test_stream_chat_emits_chunk_and_done` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestChatStreamEndpoint::test_stream_provider_error_emits_error_event` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestChatStreamEndpoint::test_stream_unknown_provider_returns_400` | PASSED | <0.01s |  |
| `unit/server/test_app.py::TestChatStreamEndpoint::test_stream_requires_auth` | PASSED | <0.01s |  |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_health_bypasses_auth` | PASSED | <0.01s |  |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_missing_authorization_header_is_401` | PASSED | <0.01s |  |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_wrong_scheme_is_401` | PASSED | <0.01s |  |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_wrong_token_is_401` | PASSED | <0.01s |  |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_correct_token_passes` | PASSED | <0.01s |  |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_token_compared_constant_time_against_prefix_match` | PASSED | <0.01s |  |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_empty_token_in_constructor_raises` | PASSED | <0.01s |  |
| `unit/server/test_cli_serve.py::TestReadAuthToken::test_fd_takes_precedence_and_closes_fd` | PASSED | <0.01s |  |
| `unit/server/test_cli_serve.py::TestReadAuthToken::test_fd_strips_whitespace_and_newline` | PASSED | <0.01s |  |
| `unit/server/test_cli_serve.py::TestReadAuthToken::test_argv_token_when_no_fd` | PASSED | <0.01s |  |
| `unit/server/test_cli_serve.py::TestReadAuthToken::test_env_var_used_as_fallback` | PASSED | <0.01s |  |
| `unit/server/test_cli_serve.py::TestReadAuthToken::test_missing_token_raises` | PASSED | <0.01s |  |
| `unit/server/test_cli_serve.py::TestReadAuthToken::test_short_token_raises` | PASSED | <0.01s |  |
| `unit/server/test_cli_serve.py::TestServeCommand::test_missing_token_exits_nonzero` | PASSED | <0.01s |  |
| `unit/server/test_cli_serve.py::TestServeCommand::test_short_token_exits_nonzero` | PASSED | <0.01s |  |
| `unit/server/test_cli_serve.py::TestServeCommand::test_valid_token_invokes_run_server` | PASSED | <0.01s |  |
| `unit/server/test_cli_serve.py::TestServeCommand::test_serve_help_lists_options` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestParentAlive::test_own_process_is_alive` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestParentAlive::test_zero_and_negative_pids_rejected` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestParentAlive::test_missing_process_is_not_alive` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestParentAlive::test_permission_error_counts_as_alive` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestParentAlive::test_other_oserror_counts_as_dead` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestBindListeningSocket::test_port_zero_binds_ephemeral_port` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestBindListeningSocket::test_reuseaddr_is_set` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestBindListeningSocket::test_reuseport_is_not_set` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestParentWatchdog::test_signals_self_when_parent_disappears` | PASSED | 0.01s |  |
| `unit/server/test_lifecycle.py::TestParentWatchdog::test_keeps_polling_while_parent_lives` | PASSED | 0.08s |  |
| `unit/server/test_lifecycle.py::TestRunServer::test_announces_bound_port_on_stdout` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestRunServer::test_prebound_socket_is_handed_to_uvicorn` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestRunServer::test_socket_is_closed_after_serving` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestRunServer::test_socket_closed_even_when_serve_raises` | PASSED | <0.01s |  |
| `unit/server/test_lifecycle.py::TestRunServer::test_watchdog_started_only_with_parent_pid` | PASSED | <0.01s |  |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_content_only_chunk_emits_chunk_event` | PASSED | <0.01s |  |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_empty_content_is_skipped` | PASSED | <0.01s |  |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_final_chunk_emits_done_with_finish_reason` | PASSED | <0.01s |  |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_final_chunk_with_usage_emits_usage_event` | PASSED | <0.01s |  |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_zero_token_usage_does_not_emit_usage_event` | PASSED | <0.01s |  |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_tool_call_delta_passes_through` | PASSED | <0.01s |  |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_final_chunk_with_tool_calls_emits_tool_calls_event` | PASSED | <0.01s |  |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_full_stream_event_order` | PASSED | <0.01s |  |
| `unit/test_capability_catalog.py::TestCapabilities::test_resolved_flags` | PASSED | <0.01s |  |
| `unit/test_capability_catalog.py::TestCapabilities::test_limits_and_pricing` | PASSED | <0.01s |  |
| `unit/test_capability_catalog.py::TestCapabilities::test_reasoning_model` | PASSED | <0.01s |  |
| `unit/test_capability_catalog.py::TestMatching::test_openrouter_style_prefix_stripped` | PASSED | <0.01s |  |
| `unit/test_capability_catalog.py::TestMatching::test_prefix_match_dated_variant` | PASSED | <0.01s |  |
| `unit/test_capability_catalog.py::TestMatching::test_alias_match` | PASSED | <0.01s |  |
| `unit/test_capability_catalog.py::TestMatching::test_unknown_returns_none` | PASSED | <0.01s |  |
| `unit/test_capability_catalog.py::TestMatching::test_empty_returns_none` | PASSED | <0.01s |  |
| `unit/test_capability_catalog.py::TestProviderScoping::test_provider_hint_disambiguates` | PASSED | <0.01s |  |
| `unit/test_capability_catalog.py::TestMetadataExposed::test_meta_and_providers_available` | PASSED | <0.01s |  |
| `unit/test_capability_catalog.py::TestSnapshotAndRemote::test_from_snapshot_loads_known_model` | PASSED | <0.01s |  |
| `unit/test_capability_catalog.py::TestSnapshotAndRemote::test_from_remote_falls_back_to_snapshot` | PASSED | <0.01s |  |
| `unit/test_cli_api_key.py::TestResolveApiKey::test_explicit_flag_wins_over_everything` | PASSED | <0.01s |  |
| `unit/test_cli_api_key.py::TestResolveApiKey::test_provider_specific_env_used_when_no_flag` | PASSED | <0.01s |  |
| `unit/test_cli_api_key.py::TestResolveApiKey::test_provider_specific_env_wins_over_generic` | PASSED | <0.01s |  |
| `unit/test_cli_api_key.py::TestResolveApiKey::test_generic_fallback_when_no_provider_specific` | PASSED | <0.01s |  |
| `unit/test_cli_api_key.py::TestResolveApiKey::test_returns_none_when_nothing_set` | PASSED | <0.01s |  |
| `unit/test_cli_api_key.py::TestResolveApiKey::test_cross_provider_env_does_not_leak` | PASSED | <0.01s |  |
| `unit/test_cli_api_key.py::TestResolveApiKey::test_provider_name_is_case_insensitive` | PASSED | <0.01s |  |
| `unit/test_cli_api_key.py::TestResolveApiKey::test_unknown_provider_falls_back_to_generic` | PASSED | <0.01s |  |
| `unit/test_cli_api_key.py::TestResolveApiKey::test_none_provider_uses_generic` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_successful_chat` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_custom_model_and_temperature` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_missing_api_key` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_local_provider_no_key` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_empty_stdin` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_invalid_json` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_missing_messages` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_empty_messages` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_invalid_message_role` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_invalid_message_no_content` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_invalid_message_no_role` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_message_not_dict` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_provider_error` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_input_size_limit` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_multi_message_conversation` | PASSED | <0.01s |  |
| `unit/test_cli_chat.py::TestChatCommand::test_tool_role_accepted` | PASSED | <0.01s |  |
| `unit/test_cli_image.py::TestImageCommand::test_successful_generation` | PASSED | <0.01s |  |
| `unit/test_cli_image.py::TestImageCommand::test_output_message_contains_path` | PASSED | <0.01s |  |
| `unit/test_cli_image.py::TestImageCommand::test_provider_error_exits_nonzero` | PASSED | <0.01s |  |
| `unit/test_cli_image.py::TestImageCommand::test_missing_prompt_exits_nonzero` | PASSED | <0.01s |  |
| `unit/test_cli_image.py::TestImageCommand::test_missing_api_key_exits_nonzero` | PASSED | <0.01s |  |
| `unit/test_cli_image.py::TestImageCommand::test_prompt_file` | PASSED | <0.01s |  |
| `unit/test_cli_image.py::TestImageCommand::test_custom_model_forwarded` | PASSED | <0.01s |  |
| `unit/test_cli_image.py::TestImageCommand::test_openrouter_provider_accepted` | PASSED | <0.01s |  |
| `unit/test_cli_image.py::TestImageCommand::test_fit_option_resizes_image` | PASSED | 0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_successful_batch_creates_files` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_dest_defaults_to_recipe_directory` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_provider_called_once_for_batch` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_dry_run_no_api_calls` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_dry_run_lists_asset_ids` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_dry_run_does_not_need_api_key` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_only_filter_generates_single_asset` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_only_multiple_ids` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_only_unknown_id_exits_nonzero` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_invalid_schema_prefix_exits_nonzero` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_missing_assets_key_exits_nonzero` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_empty_assets_list_exits_nonzero` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_asset_missing_required_field_exits_nonzero` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_invalid_json_exits_nonzero` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_one_asset_fails_others_still_generated` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_failed_asset_id_appears_in_output` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_fit_option_resizes_asset` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_cli_provider_overrides_defaults` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_cli_model_overrides_defaults` | PASSED | <0.01s |  |
| `unit/test_cli_listing_assets.py::TestListingAssetsCommand::test_missing_api_key_exits_nonzero` | PASSED | <0.01s |  |
| `unit/test_config.py::TestConfigPath::test_explicit_override_wins` | PASSED | <0.01s |  |
| `unit/test_config.py::TestConfigPath::test_xdg_config_home` | PASSED | <0.01s |  |
| `unit/test_config.py::TestConfigPath::test_default_home` | PASSED | <0.01s |  |
| `unit/test_config.py::TestLoadConfig::test_missing_file_returns_empty` | PASSED | <0.01s |  |
| `unit/test_config.py::TestLoadConfig::test_malformed_toml_raises` | PASSED | <0.01s |  |
| `unit/test_config.py::TestLoadConfig::test_permission_warning_when_world_readable` | PASSED | <0.01s |  |
| `unit/test_config.py::TestLoadConfig::test_no_warning_when_locked_down` | PASSED | <0.01s |  |
| `unit/test_config.py::TestAccessors::test_provider_fields` | PASSED | <0.01s |  |
| `unit/test_config.py::TestAccessors::test_provider_name_case_insensitive` | PASSED | <0.01s |  |
| `unit/test_config.py::TestAccessors::test_unknown_provider_returns_none` | PASSED | <0.01s |  |
| `unit/test_config.py::TestAccessors::test_none_provider_returns_none` | PASSED | <0.01s |  |
| `unit/test_config.py::TestAccessors::test_default_provider` | PASSED | <0.01s |  |
| `unit/test_config.py::TestAccessors::test_chat_defaults` | PASSED | <0.01s |  |
| `unit/test_config.py::TestAccessors::test_chat_defaults_absent` | PASSED | <0.01s |  |
| `unit/test_config.py::TestAccessors::test_bool_is_not_accepted_as_number` | PASSED | <0.01s |  |
| `unit/test_config.py::TestResolverPrecedence::test_api_key_flag_beats_all` | PASSED | <0.01s |  |
| `unit/test_config.py::TestResolverPrecedence::test_api_key_env_beats_config` | PASSED | <0.01s |  |
| `unit/test_config.py::TestResolverPrecedence::test_api_key_generic_env_beats_config` | PASSED | <0.01s |  |
| `unit/test_config.py::TestResolverPrecedence::test_api_key_config_used_when_no_flag_or_env` | PASSED | <0.01s |  |
| `unit/test_config.py::TestResolverPrecedence::test_base_url_flag_beats_config` | PASSED | <0.01s |  |
| `unit/test_config.py::TestResolverPrecedence::test_base_url_from_config` | PASSED | <0.01s |  |
| `unit/test_config.py::TestResolverPrecedence::test_model_from_config` | PASSED | <0.01s |  |
| `unit/test_config.py::TestResolverPrecedence::test_provider_from_config_default` | PASSED | <0.01s |  |
| `unit/test_config.py::TestResolverPrecedence::test_provider_flag_beats_config` | PASSED | <0.01s |  |
| `unit/test_config.py::TestWriteTemplate::test_creates_file_0600` | PASSED | <0.01s |  |
| `unit/test_config.py::TestWriteTemplate::test_refuses_overwrite_without_force` | PASSED | <0.01s |  |
| `unit/test_config.py::TestWriteTemplate::test_force_overwrites` | PASSED | <0.01s |  |
| `unit/test_config.py::TestRedact::test_masks_long_value` | PASSED | <0.01s |  |
| `unit/test_config.py::TestRedact::test_short_value_fully_masked` | PASSED | <0.01s |  |
| `unit/test_config.py::TestConfigCLI::test_config_path_command` | PASSED | <0.01s |  |
| `unit/test_config.py::TestConfigCLI::test_config_init_then_show` | PASSED | <0.01s |  |
| `unit/test_config.py::TestConfigCLI::test_config_init_refuses_overwrite` | PASSED | <0.01s |  |
| `unit/test_config.py::TestConfigCLI::test_config_show_masks_keys` | PASSED | <0.01s |  |
| `unit/test_config.py::TestConfigIntegration::test_test_provider_uses_config_key` | PASSED | <0.01s |  |
| `unit/test_config.py::test_module_exposes_cli_resolvers` | PASSED | <0.01s |  |
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
| `unit/test_embedder.py::TestOpenAIEmbedder::test_unknown_model_raises` | PASSED | <0.01s |  |
| `unit/test_embedder.py::TestOpenAIEmbedder::test_dimensions_from_catalog` | PASSED | <0.01s |  |
| `unit/test_embedder.py::TestLangDockEmbedder::test_region_sets_base_url` | PASSED | <0.01s |  |
| `unit/test_embedder.py::TestLangDockEmbedder::test_default_region_is_eu` | PASSED | <0.01s |  |
| `unit/test_embedder.py::TestMeliousEmbedder::test_default_base_url` | PASSED | <0.01s |  |
| `unit/test_embedder.py::TestMeliousEmbedder::test_base_url_override` | PASSED | <0.01s |  |
| `unit/test_embedder.py::TestMeliousEmbedder::test_ssrf_metadata_blocked` | PASSED | <0.01s |  |
| `unit/test_embedder.py::TestMeliousEmbedder::test_private_range_blocked` | PASSED | <0.01s |  |
| `unit/test_embedder.py::TestMeliousEmbedder::test_non_http_scheme_blocked` | PASSED | <0.01s |  |
| `unit/test_embedder.py::TestMeliousEmbedder::test_default_dimensions` | PASSED | <0.01s |  |
| `unit/test_embedder.py::TestMeliousEmbedder::test_configurable_dimensions` | PASSED | <0.01s |  |
| `unit/test_embedder.py::TestMeliousEmbedder::test_skips_static_model_validation` | PASSED | <0.01s |  |
| `unit/test_embedder.py::TestMeliousEmbedder::test_embed_uses_openai_compatible_client` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestBackendDispatch::test_chat_completion_routes_to_backend[openai-_openai_chat_completion-extra0]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestBackendDispatch::test_chat_completion_routes_to_backend[anthropic-_anthropic_chat_completion-extra1]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestBackendDispatch::test_chat_completion_routes_to_backend[google-_google_chat_completion-extra2]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestBackendDispatch::test_chat_completion_routes_to_backend[codestral-_codestral_completion-extra3]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestBackendDispatch::test_chat_completion_routes_to_backend[agent-_agent_chat_completion-extra4]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestBackendDispatch::test_unknown_backend_cannot_be_constructed` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestBackendDispatch::test_agent_backend_requires_agent_id` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestBackendDispatch::test_default_model_per_backend` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentMessageFiltering::test_system_messages_are_dropped` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentMessageFiltering::test_user_assistant_tool_are_kept` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentMessageFiltering::test_unknown_role_is_dropped` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentMessageConversion::test_converts_to_uimessage_parts` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentMessageConversion::test_ids_are_sequential_after_filtering` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentMessageConversion::test_multimodal_list_content_is_flattened_to_text` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentMessageConversion::test_attachment_ids_move_to_metadata` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentMessageConversion::test_no_metadata_key_without_attachments` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentMessageConversion::test_empty_content_becomes_empty_text_part` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentChatCompletion::test_extracts_last_assistant_message` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentChatCompletion::test_request_goes_through_the_pinned_client` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentChatCompletion::test_no_usable_messages_returns_prompt_instead_of_raising` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentChatCompletion::test_non_200_raises_provider_error_with_status` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentChatCompletion::test_missing_assistant_message_yields_empty_content` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestAgentStreamCompletion::test_yields_a_single_final_chunk` | PASSED | 0.04s |  |
| `unit/test_langdock_backends.py::TestAgentStreamCompletion::test_no_content_yields_nothing` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGeminiPartsConversion::test_plain_string` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGeminiPartsConversion::test_empty_string_still_yields_a_part` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGeminiPartsConversion::test_data_url_image_becomes_inline_data` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGeminiPartsConversion::test_external_image_url_is_skipped` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGeminiPartsConversion::test_text_and_image_are_both_kept` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGeminiPartsConversion::test_malformed_data_url_is_dropped_not_raised` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGoogleChatCompletion::test_concatenates_all_text_parts` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGoogleChatCompletion::test_request_url_targets_generate_content` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGoogleChatCompletion::test_assistant_role_is_mapped_to_model` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGoogleChatCompletion::test_system_message_becomes_system_instruction` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGoogleChatCompletion::test_no_system_instruction_key_without_system_message` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGoogleChatCompletion::test_max_tokens_defaults_when_not_given` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestGoogleChatCompletion::test_empty_candidates_yield_empty_content` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestCodestralCompletion::test_plain_prompt_without_fim_markers` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestCodestralCompletion::test_fim_markers_split_prompt_and_suffix` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestCodestralCompletion::test_targets_fim_endpoint` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestCodestralCompletion::test_usage_is_mapped` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestCodestralCompletion::test_max_tokens_default` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestModelConstraints::test_reasoning_model_reports_no_temperature_support` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestModelConstraints::test_gpt4o_supports_vision_and_temperature` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestModelConstraints::test_gemini_supports_vision` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestModelConstraints::test_claude_sonnet_supports_vision` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestModelConstraints::test_context_length_from_table` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestModelConstraints::test_unknown_model_gets_a_fallback_context_length` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestModelConstraints::test_codestral_output_ceiling` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestErrorMapping::test_exceptions_map_to_typed_errors[Rate limit exceeded-RateLimitError]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestErrorMapping::test_exceptions_map_to_typed_errors[HTTP 429 returned-RateLimitError]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestErrorMapping::test_exceptions_map_to_typed_errors[authentication failed-AuthenticationError]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestErrorMapping::test_exceptions_map_to_typed_errors[401 Unauthorized-AuthenticationError]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestErrorMapping::test_exceptions_map_to_typed_errors[context length exceeded-ContextLengthError]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestErrorMapping::test_exceptions_map_to_typed_errors[too many tokens-ContextLengthError]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestErrorMapping::test_exceptions_map_to_typed_errors[something else entirely-ProviderError]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestExportManagerDownloadGuard::test_internal_target_is_rejected` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestExportManagerDownloadGuard::test_non_http_scheme_is_rejected` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestExportManagerDownloadGuard::test_public_url_is_fetched_and_returned` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestExportManagerDownloadGuard::test_non_200_maps_to_provider_error` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestEmptyResponseRegressions::test_google_empty_candidates_does_not_raise` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestEmptyResponseRegressions::test_codestral_empty_choices_does_not_raise` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestTypedErrorsSurviveTheHandler::test_agent_status_code_is_preserved` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestTypedErrorsSurviveTheHandler::test_agent_stream_status_code_is_preserved` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestListModels::test_google_returns_the_two_supported_gemini_models` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestListModels::test_codestral_listing_is_deliberately_empty` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestListModels::test_agent_listing_is_tagged_for_the_agent_backend` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestListModels::test_agent_listing_failure_degrades_to_empty_list` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestListModels::test_openai_listing_filters_to_supported_prefixes` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestListModels::test_anthropic_listing_falls_back_to_known_models` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestListModels::test_models_carry_capability_constraints` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestStatusErrorMapping::test_status_codes_map_to_typed_errors[401-AuthenticationError]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestStatusErrorMapping::test_status_codes_map_to_typed_errors[403-AuthenticationError]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestStatusErrorMapping::test_status_codes_map_to_typed_errors[429-RateLimitError]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestStatusErrorMapping::test_status_codes_map_to_typed_errors[500-ProviderError]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestStatusErrorMapping::test_status_codes_map_to_typed_errors[404-ProviderError]` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestExportManager::test_get_agent_unwraps_the_agent_envelope` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestExportManager::test_get_agent_passes_through_unwrapped_payload` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestExportManager::test_get_agent_sends_the_id_as_query_param` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestExportManager::test_get_agent_maps_401_to_authentication_error` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestExportManager::test_export_report_rejects_unknown_report` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestExportManager::test_export_report_unwraps_data` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestExportManager::test_export_report_sends_from_to_and_timezone` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestExportManager::test_export_report_maps_429` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestKnowledgeManager::test_list_files_targets_the_folder` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestKnowledgeManager::test_delete_file_returns_true_on_success` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestKnowledgeManager::test_delete_file_raises_on_error_status` | PASSED | <0.01s |  |
| `unit/test_langdock_backends.py::TestKnowledgeManager::test_search_posts_the_query` | PASSED | <0.01s |  |
| `unit/test_openai_image.py::TestOpenAIImageGeneration::test_supports_image_generation_flag` | PASSED | <0.01s |  |
| `unit/test_openai_image.py::TestOpenAIImageGeneration::test_default_image_model` | PASSED | <0.01s |  |
| `unit/test_openai_image.py::TestOpenAIImageGeneration::test_generate_image_returns_image_result` | PASSED | <0.01s |  |
| `unit/test_openai_image.py::TestOpenAIImageGeneration::test_generate_image_uses_default_model` | PASSED | <0.01s |  |
| `unit/test_openai_image.py::TestOpenAIImageGeneration::test_generate_image_no_response_format_for_gpt_image_1` | PASSED | <0.01s |  |
| `unit/test_openai_image.py::TestOpenAIImageGeneration::test_generate_image_sends_response_format_for_dalle3` | PASSED | <0.01s |  |
| `unit/test_openai_image.py::TestOpenAIImageGeneration::test_generate_image_custom_size` | PASSED | <0.01s |  |
| `unit/test_openai_image.py::TestOpenAIImageGeneration::test_generate_image_custom_model` | PASSED | <0.01s |  |
| `unit/test_openai_image.py::TestOpenAIImageGeneration::test_generate_image_base64_decoding` | PASSED | <0.01s |  |
| `unit/test_openai_image.py::TestOpenAIImageGeneration::test_generate_image_authentication_error` | PASSED | <0.01s |  |
| `unit/test_openai_image.py::TestOpenAIImageGeneration::test_generate_image_rate_limit_error` | PASSED | <0.01s |  |
| `unit/test_openai_image.py::TestOpenAIImageGeneration::test_generate_image_forwards_n_1` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_supports_image_generation_flag` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_default_image_model` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_generate_image_returns_image_result` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_generate_image_uses_default_model` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_generate_image_modalities_in_payload` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_generate_image_prompt_in_message` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_generate_image_data_url_parsing` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_generate_image_no_images_raises_provider_error` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_generate_image_missing_images_key_raises_provider_error` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_generate_image_http_401_raises_authentication_error` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_generate_image_http_429_raises_rate_limit_error` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_generate_image_custom_model` | PASSED | <0.01s |  |
| `unit/test_openrouter_image.py::TestOpenRouterImageGeneration::test_generate_image_invalid_data_url_raises_error` | PASSED | <0.01s |  |
| `unit/test_pdf.py::TestAvailability::test_available_when_pymupdf_installed` | PASSED | <0.01s |  |
| `unit/test_pdf.py::TestConversion::test_single_page_returns_one_png` | PASSED | 0.04s |  |
| `unit/test_pdf.py::TestConversion::test_jpeg_format_selected` | PASSED | 0.03s |  |
| `unit/test_pdf.py::TestConversion::test_all_pages_converted` | PASSED | 0.07s |  |
| `unit/test_pdf.py::TestConversion::test_max_pages_truncates` | PASSED | 0.05s |  |
| `unit/test_pdf.py::TestConversion::test_higher_dpi_produces_larger_image` | PASSED | 0.10s |  |
| `unit/test_pdf.py::TestConversion::test_corrupt_pdf_returns_empty_list_instead_of_raising` | PASSED | <0.01s |  |
| `unit/test_pdf.py::TestInputValidation::test_invalid_format_rejected` | PASSED | <0.01s |  |
| `unit/test_pdf.py::TestInputValidation::test_oversized_input_rejected` | PASSED | <0.01s |  |
| `unit/test_pdf.py::TestResourceClamping::test_page_count_clamped_to_hard_limit` | PASSED | 1.08s |  |
| `unit/test_pdf.py::TestResourceClamping::test_zero_max_pages_still_renders_one_page` | PASSED | 0.02s |  |
| `unit/test_pdf.py::TestResourceClamping::test_excessive_dpi_clamped` | PASSED | 0.70s |  |
| `unit/test_pdf.py::TestResourceClamping::test_zero_dpi_clamped_to_minimum` | PASSED | <0.01s |  |
| `unit/test_pdf.py::TestBase64Wrapper::test_returns_decodable_base64` | PASSED | 0.02s |  |
| `unit/test_pdf.py::TestBase64Wrapper::test_matches_raw_conversion` | PASSED | 0.09s |  |
| `unit/test_pdf.py::TestBase64Wrapper::test_corrupt_pdf_returns_empty_list` | PASSED | <0.01s |  |
| `unit/test_pricing_catalog.py::TestUnitConversion::test_input_output_converted_to_per_1k` | PASSED | <0.01s |  |
| `unit/test_pricing_catalog.py::TestUnitConversion::test_embedding_zero_output` | PASSED | <0.01s |  |
| `unit/test_pricing_catalog.py::TestMatching::test_exact_match` | PASSED | <0.01s |  |
| `unit/test_pricing_catalog.py::TestMatching::test_prefix_match_dated_variant` | PASSED | <0.01s |  |
| `unit/test_pricing_catalog.py::TestMatching::test_openrouter_style_prefix_stripped` | PASSED | <0.01s |  |
| `unit/test_pricing_catalog.py::TestMatching::test_unknown_returns_none` | PASSED | <0.01s |  |
| `unit/test_pricing_catalog.py::TestMatching::test_empty_returns_none` | PASSED | <0.01s |  |
| `unit/test_pricing_catalog.py::TestMatching::test_entry_without_price_skipped` | PASSED | <0.01s |  |
| `unit/test_pricing_catalog.py::TestProviderScoping::test_provider_hint_prefers_matching_litellm_provider` | PASSED | <0.01s |  |
| `unit/test_pricing_catalog.py::TestSnapshotAndRemote::test_from_snapshot_loads_known_model` | PASSED | <0.01s |  |
| `unit/test_pricing_catalog.py::TestSnapshotAndRemote::test_from_remote_falls_back_to_snapshot` | PASSED | <0.01s |  |
| `unit/test_pricing_shim.py::test_shim_reexports_the_canonical_objects` | PASSED | <0.01s |  |
| `unit/test_pricing_shim.py::test_shim_exports_are_declared` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestScrubSecrets::test_masks_openai_key` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestScrubSecrets::test_masks_provider_prefixes` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestScrubSecrets::test_masks_bearer_token` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestScrubSecrets::test_masks_key_query_param` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestScrubSecrets::test_masks_json_api_key` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestScrubSecrets::test_preserves_plain_text` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestScrubSecrets::test_handles_empty` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestValidateUrl::test_rejects_non_http_scheme` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestValidateUrl::test_rejects_missing_hostname` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestValidateUrl::test_strict_blocks_private_ip` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestValidateUrl::test_strict_blocks_cloud_metadata` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestValidateUrl::test_strict_allows_localhost` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestValidateUrl::test_lan_mode_allows_private_but_blocks_metadata` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestLocalProviderBaseUrl::test_rejects_metadata_base_url` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestLocalProviderBaseUrl::test_accepts_localhost_default` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestRetryAfterCap::test_caps_huge_retry_after` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestRetryAfterCap::test_passes_reasonable_value` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestRetryAfterCap::test_returns_none_when_absent` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestRetryAfterCap::test_rate_limit_result_scrubs_key` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestCostNegativeGuard::test_negative_input_raises` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestCostNegativeGuard::test_negative_output_raises` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestCostNegativeGuard::test_zero_is_allowed` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestFileValidatorFailClosed::test_mime_verified_true_with_magic` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestFileValidatorFailClosed::test_mime_not_verified_when_magic_disabled` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestFileValidatorFailClosed::test_require_magic_raises_when_unavailable` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestPdfLimits::test_oversized_pdf_raises` | PASSED | <0.01s |  |
| `unit/test_security_hardening.py::TestPdfLimits::test_invalid_format_raises` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestEmptyState::test_result_is_none_before_anything_is_added` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestEmptyState::test_falsy_input_is_ignored` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestEmptyState::test_bool_reflects_emptiness` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestDictDeltas::test_fragments_are_concatenated` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestDictDeltas::test_missing_index_defaults_to_zero` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestDictDeltas::test_id_arriving_late_is_still_captured` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestDictDeltas::test_id_is_not_overwritten_by_a_later_empty_one` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestDictDeltas::test_missing_id_yields_empty_string_not_none` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestDictDeltas::test_type_is_always_function` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestOrdering::test_results_are_ordered_by_index_not_arrival` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestOrdering::test_parallel_calls_accumulate_independently` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestSdkObjectDeltas::test_fragments_are_concatenated` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestSdkObjectDeltas::test_delta_without_function_is_tolerated` | PASSED | <0.01s |  |
| `unit/test_stream_accumulator.py::TestSdkObjectDeltas::test_object_and_dict_deltas_produce_the_same_shape` | PASSED | <0.01s |  |
| `unit/test_tool_normalization.py::TestToChatTool::test_uses_the_nested_chat_completions_shape` | PASSED | <0.01s |  |
| `unit/test_tool_normalization.py::TestToChatTool::test_strict_is_emitted_only_when_set` | PASSED | <0.01s |  |
| `unit/test_tool_normalization.py::TestToChatTool::test_result_is_json_serializable` | PASSED | <0.01s |  |
| `unit/test_tool_normalization.py::TestNormalizeTools::test_none_and_empty_become_none` | PASSED | <0.01s |  |
| `unit/test_tool_normalization.py::TestNormalizeTools::test_dicts_pass_through_as_copies` | PASSED | <0.01s |  |
| `unit/test_tool_normalization.py::TestNormalizeTools::test_tool_definitions_are_converted` | PASSED | <0.01s |  |
| `unit/test_tool_normalization.py::TestNormalizeTools::test_mixed_lists_are_handled` | PASSED | <0.01s |  |
| `unit/test_tool_normalization.py::TestNormalizeTools::test_output_is_always_json_serializable` | PASSED | <0.01s |  |
| `unit/test_tool_normalization.py::TestProvidersAcceptToolDefinition::test_openai_provider_sends_dicts` | PASSED | <0.01s |  |
| `unit/test_tool_normalization.py::TestProvidersAcceptToolDefinition::test_anthropic_converter_receives_dicts` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestNAT64Synthesis::test_dual_result_with_synthesized_ipv6_accepted` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestNAT64Synthesis::test_synthesized_ipv6_only_accepted` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestNAT64Synthesis::test_synthesized_ipv6_accepted_in_lan_mode` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestNAT64DoesNotWeakenSSRFProtection::test_metadata_endpoint_blocked` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestNAT64DoesNotWeakenSSRFProtection::test_metadata_endpoint_blocked_in_lan_mode` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestNAT64DoesNotWeakenSSRFProtection::test_private_range_blocked_in_strict_mode` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestNAT64DoesNotWeakenSSRFProtection::test_loopback_blocked_in_strict_mode` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestNAT64DoesNotWeakenSSRFProtection::test_private_range_allowed_in_lan_mode` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestNAT64DoesNotWeakenSSRFProtection::test_one_bad_address_rejects_the_whole_url` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestIPv4MappedAddresses::test_public_mapped_address_accepted` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestIPv4MappedAddresses::test_private_mapped_address_blocked` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestNativeIPv6Unchanged::test_global_ipv6_accepted` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestNativeIPv6Unchanged::test_reserved_ipv6_still_blocked` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestNativeIPv6Unchanged::test_unique_local_ipv6_blocked_in_strict_mode` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestPinnedTransportRebinding::test_rebinding_to_cloud_metadata_is_blocked` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestPinnedTransportRebinding::test_rebinding_to_private_range_is_blocked` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestPinnedTransportRebinding::test_rebinding_via_nat64_wrapped_metadata_is_blocked` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestPinnedTransportRebinding::test_rotation_to_another_public_ip_is_allowed` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestPinnedTransportRebinding::test_unchanged_resolution_is_allowed` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestPinnedTransportRebinding::test_lan_mode_allows_private_target_but_still_blocks_metadata` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestPinnedTransportRebinding::test_strict_mode_rejects_unresolvable_host_at_request_time` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestValidatingTransport::test_public_host_passes` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestValidatingTransport::test_metadata_endpoint_blocked` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestValidatingTransport::test_private_range_blocked` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestValidatingTransport::test_any_disallowed_address_in_the_set_blocks` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestValidatingTransport::test_non_http_scheme_blocked` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestValidatingTransport::test_unresolvable_host_blocked` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestValidatingTransport::test_lan_mode_allows_private_but_not_metadata` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestClientLibrarySplit::test_default_transport_is_built_against_httpx2` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestClientLibrarySplit::test_transport_can_be_built_against_httpx_for_the_anthropic_sdk` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestClientLibrarySplit::test_validating_transport_honours_the_same_choice` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestClientLibrarySplit::test_guard_still_fires_on_the_httpx_variant` | PASSED | <0.01s |  |
| `unit/test_url_validation.py::TestClientLibrarySplit::test_anthropic_provider_builds_an_httpx_client` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestParseSize::test_basic` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestParseSize::test_square` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestParseSize::test_uppercase` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestParseSize::test_invalid_format_no_x` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestParseSize::test_invalid_format_non_integer` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestParseSize::test_zero_dimension_rejected` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestParseSize::test_negative_dimension_rejected` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestSavePng::test_creates_file` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestSavePng::test_returns_resolved_path` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestSavePng::test_creates_parent_directories` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestSavePng::test_accepts_string_path` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestSavePng::test_base_dir_allows_path_inside` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestSavePng::test_base_dir_rejects_parent_traversal` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestSavePng::test_base_dir_rejects_absolute_escape` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestFitToCover::test_square_to_square` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestFitToCover::test_wide_to_square` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestFitToCover::test_tall_to_square` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestFitToCover::test_cover_is_default_mode` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestFitToCover::test_output_is_png_bytes` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestFitToContain::test_output_dimensions` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestFitToContain::test_wide_source_in_square_box` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestFitToContain::test_tall_source_in_square_box` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestFitToStretch::test_stretches_to_exact_dimensions` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestFitToStretch::test_output_is_png` | PASSED | <0.01s |  |
| `unit/test_utils_image.py::TestFitToInvalidMode::test_invalid_mode_raises_value_error` | PASSED | <0.01s |  |

### Local Server Tests (1 passed)

#### Other (1 passed) - <0.01s

| Test | Status | Duration |
|------|--------|----------|
| `unit/test_pricing_catalog.py::TestProviderScoping::test_local_provider_returns_none` | PASSED | <0.01s |
