# Test Report - 2026-05-08 11:33:09

**eq_chatbot_core v1.7.0** | 57.21s | Python 3.13.12 | macOS-26.4.1-arm64-arm-64bit-Mach-O

> **Result: ALL PASSED - 40 tests OK, 15 skipped**

Command: `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/.venv/lib/python3.13/site-packages/pytest/__main__.py tests/integration/ --no-cov`

## Summary

| Status | Count |
|--------|-------|
| Passed | 40 |
| Failed | 0 |
| Skipped | 15 |
| **Total** | **55** |

## Configuration Status

Credentials configured: `OpenAI`, `Anthropic`, `LangDock`, `OpenRouter`, `Mammouth`, `Azure`, `Vertex`

## Models In Use

Resolved live from `tests/model_registry.py` against each provider's `list_models()`. By convention the `primary` in each chain is the cheapest available model; fallbacks rescue the run when the primary is deprecated.

| Provider | Model Used | Cost (per 1M tok) | Source | Status |
|----------|-----------|-------------------|--------|--------|
| OpenAI | `gpt-4o-mini` | $0.15 / $0.60 per 1M tok | Registry primary | OK |
| Anthropic | `claude-haiku-4-5` | $1.00 / $5.00 per 1M tok | Registry primary | INFO — `list_models()` does not list `claude-haiku-4-5` (9 listed); chat call will validate |
| LangDock (OpenAI backend) | `gpt-5.2` | LangDock gateway (see langdock.com pricing) | Registry primary | OK |
| LangDock (Anthropic backend) | `claude-sonnet-4-6-default` | LangDock gateway (see langdock.com pricing) | Registry primary | OK |
| OpenRouter | `deepseek/deepseek-v4-flash` | OpenRouter gateway (see openrouter.ai/models) | Registry primary | OK |
| Mammouth AI | `gpt-4.1-nano` | $0.10 / $0.40 per 1M tok | Registry primary | OK |
| Azure AI | — | deployment-dependent | — | SKIPPED — provider not exercised this run |
| Google Vertex AI | — | $0.15 / $0.60 per 1M tok | — | SKIPPED — provider not exercised this run |
| Local (LM Studio / Ollama) | `google/gemma-4-e4b` | $0 (local) | Registry primary | INFO — `list_models()` does not list `google/gemma-4-e4b` (3 listed); chat call will validate |

## Skipped Tests

| Test | Reason / Action |
|------|-----------------|
| `integration/test_azure_live.py::TestAzureLive::test_simple_completion` | Skipped: Azure SDK not installed (use [azure] extra): Azure AI SDK not installed. Install with: pip install eq-chatbot-core[azure] or: pip install azure-ai-inference azure-core |
| `integration/test_azure_live.py::TestAzureLive::test_streaming_completion` | Skipped: Azure SDK not installed (use [azure] extra): Azure AI SDK not installed. Install with: pip install eq-chatbot-core[azure] or: pip install azure-ai-inference azure-core |
| `integration/test_azure_live.py::TestAzureLive::test_system_message` | Skipped: Azure SDK not installed (use [azure] extra): Azure AI SDK not installed. Install with: pip install eq-chatbot-core[azure] or: pip install azure-ai-inference azure-core |
| `integration/test_azure_live.py::TestAzureLive::test_list_models` | Skipped: Azure SDK not installed (use [azure] extra): Azure AI SDK not installed. Install with: pip install eq-chatbot-core[azure] or: pip install azure-ai-inference azure-core |
| `integration/test_azure_live.py::TestAzureLive::test_context_manager` | Skipped: Azure SDK not installed (use [azure] extra): Azure AI SDK not installed. Install with: pip install eq-chatbot-core[azure] or: pip install azure-ai-inference azure-core |
| `integration/test_mcp_live.py::TestMCPLive::test_connect_to_server` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_live` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_detailed` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_call_tool_live` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_connection_error_handling` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_vertex_live.py::TestVertexLive::test_simple_completion` | Skipped: Vertex SDK not installed (use [vertex] extra): Google Gen AI SDK not installed. Install with: pip install eq-chatbot-core[vertex] or: pip install google-genai |
| `integration/test_vertex_live.py::TestVertexLive::test_streaming_completion` | Skipped: Vertex SDK not installed (use [vertex] extra): Google Gen AI SDK not installed. Install with: pip install eq-chatbot-core[vertex] or: pip install google-genai |
| `integration/test_vertex_live.py::TestVertexLive::test_system_message` | Skipped: Vertex SDK not installed (use [vertex] extra): Google Gen AI SDK not installed. Install with: pip install eq-chatbot-core[vertex] or: pip install google-genai |
| `integration/test_vertex_live.py::TestVertexLive::test_list_models` | Skipped: Vertex SDK not installed (use [vertex] extra): Google Gen AI SDK not installed. Install with: pip install eq-chatbot-core[vertex] or: pip install google-genai |
| `integration/test_vertex_live.py::TestVertexLive::test_context_manager` | Skipped: Vertex SDK not installed (use [vertex] extra): Google Gen AI SDK not installed. Install with: pip install eq-chatbot-core[vertex] or: pip install google-genai |

## Results by Module

| Module | Test Model | Passed | Failed | Skipped | XFailed | Total | Duration |
|--------|------------|--------|--------|---------|---------|-------|----------|
| **Provider: OpenAI** | `gpt-4o-mini` | 17 | 0 | 0 | 0 | 17 | 13.40s |
| **Provider: OpenRouter** | `deepseek/deepseek-v4-flash` | 5 | 0 | 0 | 0 | 5 | 5.05s |
| **Provider: Mammouth AI** | `gpt-4.1-nano` | 6 | 0 | 0 | 0 | 6 | 3.80s |
| **Provider: Azure AI** | - | 0 | 0 | 5 | 0 | 5 | <0.01s |
| **Provider: Google Vertex AI** | - | 0 | 0 | 5 | 0 | 5 | <0.01s |
| **Provider: Local (LM Studio / Ollama)** | `google/gemma-4-e4b` | 11 | 0 | 0 | 0 | 11 | 31.21s |
| **MCP Client** | - | 1 | 0 | 5 | 0 | 6 | <0.01s |

## Detailed Results

### Integration Tests (40 passed, 15 skipped)

#### Provider: OpenAI (17 passed) - 13.40s | Model: `gpt-4o-mini`

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_openai_live.py::TestOpenAILive::test_simple_completion` | PASSED | 0.57s |
| `integration/test_openai_live.py::TestOpenAILive::test_list_models` | PASSED | 1.06s |
| `integration/test_openai_live.py::TestOpenAILive::test_streaming_completion` | PASSED | 1.21s |
| `integration/test_openai_live.py::TestOpenAILive::test_system_message` | PASSED | 0.94s |
| `integration/test_openai_live.py::TestOpenAILive::test_json_mode` | PASSED | 1.43s |
| `integration/test_openai_live.py::TestAnthropicLive::test_simple_completion` | PASSED | 0.83s |
| `integration/test_openai_live.py::TestAnthropicLive::test_list_models` | PASSED | 0.23s |
| `integration/test_openai_live.py::TestAnthropicLive::test_streaming_completion` | PASSED | 0.96s |
| `integration/test_openai_live.py::TestAnthropicLive::test_system_message` | PASSED | 1.05s |
| `integration/test_openai_live.py::TestLangDockLive::test_simple_completion` | PASSED | 0.67s |
| `integration/test_openai_live.py::TestLangDockLive::test_list_models` | PASSED | 0.16s |
| `integration/test_openai_live.py::TestLangDockLive::test_streaming_completion` | PASSED | 0.66s |
| `integration/test_openai_live.py::TestLangDockLive::test_system_message` | PASSED | 0.80s |
| `integration/test_openai_live.py::TestLangDockLive::test_eu_region` | PASSED | 0.98s |
| `integration/test_openai_live.py::TestLangDockAnthropicBackend::test_anthropic_completion` | PASSED | 0.93s |
| `integration/test_openai_live.py::TestLangDockAnthropicBackend::test_anthropic_list_models` | PASSED | 0.20s |
| `integration/test_openai_live.py::TestCostEffectivePatterns::test_minimal_token_usage` | PASSED | 0.73s |

#### Provider: OpenRouter (5 passed) - 5.05s | Model: `deepseek/deepseek-v4-flash`

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_openrouter_live.py::TestOpenRouterLive::test_simple_completion` | PASSED | 1.36s |
| `integration/test_openrouter_live.py::TestOpenRouterLive::test_list_models` | PASSED | 0.15s |
| `integration/test_openrouter_live.py::TestOpenRouterLive::test_streaming_completion` | PASSED | 1.49s |
| `integration/test_openrouter_live.py::TestOpenRouterLive::test_system_message` | PASSED | 1.00s |
| `integration/test_openrouter_live.py::TestOpenRouterLive::test_provider_prefix_routing` | PASSED | 1.05s |

#### Provider: Mammouth AI (6 passed) - 3.80s | Model: `gpt-4.1-nano`

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_mammouth_live.py::TestMammouthLive::test_simple_completion` | PASSED | 0.91s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_list_models` | PASSED | 0.11s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_list_models_has_temperature_constraints` | PASSED | 0.10s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_streaming_completion` | PASSED | 0.88s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_system_message` | PASSED | 0.86s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_context_manager` | PASSED | 0.94s |

#### Provider: Azure AI (5 skipped) - <0.01s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_azure_live.py::TestAzureLive::test_simple_completion` | SKIPPED | - | Skipped: Azure SDK not installed (use [azure] extra): Azure AI SDK not installed. Install with: pip install eq-chatbot-core[azure] or: pip install azure-ai-inference azure-core |
| `integration/test_azure_live.py::TestAzureLive::test_streaming_completion` | SKIPPED | - | Skipped: Azure SDK not installed (use [azure] extra): Azure AI SDK not installed. Install with: pip install eq-chatbot-core[azure] or: pip install azure-ai-inference azure-core |
| `integration/test_azure_live.py::TestAzureLive::test_system_message` | SKIPPED | - | Skipped: Azure SDK not installed (use [azure] extra): Azure AI SDK not installed. Install with: pip install eq-chatbot-core[azure] or: pip install azure-ai-inference azure-core |
| `integration/test_azure_live.py::TestAzureLive::test_list_models` | SKIPPED | - | Skipped: Azure SDK not installed (use [azure] extra): Azure AI SDK not installed. Install with: pip install eq-chatbot-core[azure] or: pip install azure-ai-inference azure-core |
| `integration/test_azure_live.py::TestAzureLive::test_context_manager` | SKIPPED | - | Skipped: Azure SDK not installed (use [azure] extra): Azure AI SDK not installed. Install with: pip install eq-chatbot-core[azure] or: pip install azure-ai-inference azure-core |

#### Provider: Google Vertex AI (5 skipped) - <0.01s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_vertex_live.py::TestVertexLive::test_simple_completion` | SKIPPED | - | Skipped: Vertex SDK not installed (use [vertex] extra): Google Gen AI SDK not installed. Install with: pip install eq-chatbot-core[vertex] or: pip install google-genai |
| `integration/test_vertex_live.py::TestVertexLive::test_streaming_completion` | SKIPPED | - | Skipped: Vertex SDK not installed (use [vertex] extra): Google Gen AI SDK not installed. Install with: pip install eq-chatbot-core[vertex] or: pip install google-genai |
| `integration/test_vertex_live.py::TestVertexLive::test_system_message` | SKIPPED | - | Skipped: Vertex SDK not installed (use [vertex] extra): Google Gen AI SDK not installed. Install with: pip install eq-chatbot-core[vertex] or: pip install google-genai |
| `integration/test_vertex_live.py::TestVertexLive::test_list_models` | SKIPPED | - | Skipped: Vertex SDK not installed (use [vertex] extra): Google Gen AI SDK not installed. Install with: pip install eq-chatbot-core[vertex] or: pip install google-genai |
| `integration/test_vertex_live.py::TestVertexLive::test_context_manager` | SKIPPED | - | Skipped: Vertex SDK not installed (use [vertex] extra): Google Gen AI SDK not installed. Install with: pip install eq-chatbot-core[vertex] or: pip install google-genai |

#### Provider: Local (LM Studio / Ollama) (11 passed) - 31.21s | Model: `google/gemma-4-e4b`

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_local_live.py::TestLMStudioLive::test_connection` | PASSED | <0.01s |
| `integration/test_local_live.py::TestLMStudioLive::test_list_models` | PASSED | <0.01s |
| `integration/test_local_live.py::TestLMStudioLive::test_simple_completion` | PASSED | 0.40s |
| `integration/test_local_live.py::TestLMStudioLive::test_system_message` | PASSED | 0.28s |
| `integration/test_local_live.py::TestLMStudioLive::test_streaming_completion` | PASSED | 4.54s |
| `integration/test_local_live.py::TestLMStudioLive::test_multiple_turns` | PASSED | 6.43s |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_provider_properties` | PASSED | 0.01s |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_chat_completion_returns_llm_response` | PASSED | 9.03s |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_stream_completion_yields_chunks` | PASSED | 9.88s |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_temperature_parameter` | PASSED | 0.61s |
| `integration/test_local_live.py::TestLocalProviderErrorsLive::test_invalid_url_connection_error` | PASSED | 0.01s |

#### MCP Client (1 passed, 5 skipped) - <0.01s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_mcp_live.py::TestMCPLive::test_connect_to_server` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_live` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_detailed` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_call_tool_live` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_connection_error_handling` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPStdioLive::test_stdio_client_not_installed` | PASSED | <0.01s |  |
