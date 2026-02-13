# Test Report - 2026-02-13 11:48:36

**eq_chatbot_core v1.1.0** | 412.70s | Python 3.13.2 | macOS-26.3-arm64-arm-64bit-Mach-O

> **Result: FAILED - 5 failure(s), 0 error(s)**

Command: `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/.venv/bin/pytest tests/integration/ -v --tb=short`

## Summary

| Status | Count |
|--------|-------|
| Passed | 35 |
| Failed | 5 |
| Skipped | 5 |
| **Total** | **45** |

## Test Configuration

| Provider | Test Model | Source |
|----------|------------|--------|
| OpenAI | `gpt-4o-mini` | `OPENAI_TEST_MODEL` |
| Anthropic | `claude-3-haiku-20240307` | `ANTHROPIC_TEST_MODEL` |
| LangDock | `gpt-5.2` | `LANGDOCK_TEST_MODEL` |
| Mammouth | `gpt-4.1-nano` | `MAMMOUTH_TEST_MODEL` |
| Azure | `Phi-4` | `AZURE_TEST_MODEL` |
| Local | `nvidia/nemotron-3-nano` | `LOCAL_TEST_MODEL` |

## Failed Tests

| Test | Error |
|------|-------|
| `integration/test_local_live.py::TestLMStudioLive::test_simple_completion` | E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400 |
| `integration/test_local_live.py::TestLMStudioLive::test_system_message` | E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400 |
| `integration/test_local_live.py::TestLMStudioLive::test_streaming_completion` | E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400 |
| `integration/test_local_live.py::TestLMStudioLive::test_multiple_turns` | E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400 |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_temperature_parameter` | E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400 |

## Skipped Tests

| Test | Reason |
|------|--------|
| `integration/test_mcp_live.py::TestMCPLive::test_connect_to_server` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_live` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_detailed` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_call_tool_live` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_connection_error_handling` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |

## Results by Module

| Module | Test Model | Passed | Failed | Skipped | XFailed | Total | Duration |
|--------|------------|--------|--------|---------|---------|-------|----------|
| **Provider: OpenAI** | `gpt-4o-mini` | 17 | 0 | 0 | 0 | 17 | 11.27s |
| **Provider: Mammouth AI** | `gpt-4.1-nano` | 6 | 0 | 0 | 0 | 6 | 3.04s |
| **Provider: Azure AI** | `Phi-4` | 5 | 0 | 0 | 0 | 5 | 327.75s |
| **Provider: Local (LM Studio / Ollama)** **!!** | `nvidia/nemotron-3-nano` | 6 | 5 | 0 | 0 | 11 | 70.13s |
| **MCP Client** | - | 1 | 0 | 5 | 0 | 6 | <0.01s |

## Detailed Results

### Integration Tests (35 passed, 5 failed, 5 skipped)

#### Provider: OpenAI (17 passed) - 11.27s | Model: `gpt-4o-mini`

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_openai_live.py::TestOpenAILive::test_simple_completion` | PASSED | 1.03s |
| `integration/test_openai_live.py::TestOpenAILive::test_list_models` | PASSED | 0.74s |
| `integration/test_openai_live.py::TestOpenAILive::test_streaming_completion` | PASSED | 1.23s |
| `integration/test_openai_live.py::TestOpenAILive::test_system_message` | PASSED | 0.62s |
| `integration/test_openai_live.py::TestOpenAILive::test_json_mode` | PASSED | 0.53s |
| `integration/test_openai_live.py::TestAnthropicLive::test_simple_completion` | PASSED | 1.22s |
| `integration/test_openai_live.py::TestAnthropicLive::test_list_models` | PASSED | 0.28s |
| `integration/test_openai_live.py::TestAnthropicLive::test_streaming_completion` | PASSED | 0.54s |
| `integration/test_openai_live.py::TestAnthropicLive::test_system_message` | PASSED | 0.59s |
| `integration/test_openai_live.py::TestLangDockLive::test_simple_completion` | PASSED | 0.62s |
| `integration/test_openai_live.py::TestLangDockLive::test_list_models` | PASSED | 0.19s |
| `integration/test_openai_live.py::TestLangDockLive::test_streaming_completion` | PASSED | 0.60s |
| `integration/test_openai_live.py::TestLangDockLive::test_system_message` | PASSED | 0.66s |
| `integration/test_openai_live.py::TestLangDockLive::test_eu_region` | PASSED | 0.64s |
| `integration/test_openai_live.py::TestLangDockAnthropicBackend::test_anthropic_completion` | PASSED | 0.99s |
| `integration/test_openai_live.py::TestLangDockAnthropicBackend::test_anthropic_list_models` | PASSED | 0.18s |
| `integration/test_openai_live.py::TestCostEffectivePatterns::test_minimal_token_usage` | PASSED | 0.62s |

#### Provider: Mammouth AI (6 passed) - 3.04s | Model: `gpt-4.1-nano`

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_mammouth_live.py::TestMammouthLive::test_simple_completion` | PASSED | 0.60s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_list_models` | PASSED | 0.14s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_list_models_has_temperature_constraints` | PASSED | 0.14s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_streaming_completion` | PASSED | 0.81s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_system_message` | PASSED | 0.60s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_context_manager` | PASSED | 0.75s |

#### Provider: Azure AI (5 passed) - 327.75s | Model: `Phi-4`

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_azure_live.py::TestAzureLive::test_simple_completion` | PASSED | 41.55s |
| `integration/test_azure_live.py::TestAzureLive::test_streaming_completion` | PASSED | 37.68s |
| `integration/test_azure_live.py::TestAzureLive::test_system_message` | PASSED | 127.79s |
| `integration/test_azure_live.py::TestAzureLive::test_list_models` | PASSED | <0.01s |
| `integration/test_azure_live.py::TestAzureLive::test_context_manager` | PASSED | 120.74s |

#### Provider: Local (LM Studio / Ollama) (6 passed, 5 failed) - 70.13s | Model: `nvidia/nemotron-3-nano`

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_local_live.py::TestLMStudioLive::test_connection` | PASSED | 0.01s |  |
| `integration/test_local_live.py::TestLMStudioLive::test_list_models` | PASSED | 0.01s |  |
| `integration/test_local_live.py::TestLMStudioLive::test_simple_completion` | FAILED | 0.02s | E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400 |
| `integration/test_local_live.py::TestLMStudioLive::test_system_message` | FAILED | 0.01s | E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400 |
| `integration/test_local_live.py::TestLMStudioLive::test_streaming_completion` | FAILED | 0.01s | E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400 |
| `integration/test_local_live.py::TestLMStudioLive::test_multiple_turns` | FAILED | 0.01s | E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400 |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_provider_properties` | PASSED | 0.01s |  |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_chat_completion_returns_llm_response` | PASSED | 68.37s |  |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_stream_completion_yields_chunks` | PASSED | 0.72s |  |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_temperature_parameter` | FAILED | 0.93s | E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400 |
| `integration/test_local_live.py::TestLocalProviderErrorsLive::test_invalid_url_connection_error` | PASSED | 0.01s |  |

#### MCP Client (1 passed, 5 skipped) - <0.01s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_mcp_live.py::TestMCPLive::test_connect_to_server` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_live` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_detailed` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_call_tool_live` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_connection_error_handling` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPStdioLive::test_stdio_client_not_installed` | PASSED | <0.01s |  |
