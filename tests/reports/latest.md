# Test Report - 2026-02-10 11:33:52

**eq_chatbot_core v1.0.0** | 15.88s | Python 3.13.2 | macOS-26.2-arm64-arm-64bit-Mach-O

> **Result: ALL PASSED - 25 tests OK, 15 skipped**

Command: `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/.venv/bin/pytest tests/integration/ -v -m integration or local`

## Summary

| Status | Count |
|--------|-------|
| Passed | 25 |
| Failed | 0 |
| Skipped | 15 |
| **Total** | **40** |

## Skipped Tests

| Test | Reason |
|------|--------|
| `integration/test_local_live.py::TestLMStudioLive::test_connection` | Skipped: LM Studio server not available at localhost:1234 |
| `integration/test_local_live.py::TestLMStudioLive::test_list_models` | Skipped: LM Studio server not available at localhost:1234 |
| `integration/test_local_live.py::TestLMStudioLive::test_simple_completion` | Skipped: LM Studio server not available at localhost:1234 |
| `integration/test_local_live.py::TestLMStudioLive::test_system_message` | Skipped: LM Studio server not available at localhost:1234 |
| `integration/test_local_live.py::TestLMStudioLive::test_streaming_completion` | Skipped: LM Studio server not available at localhost:1234 |
| `integration/test_local_live.py::TestLMStudioLive::test_multiple_turns` | Skipped: LM Studio server not available at localhost:1234 |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_provider_properties` | Skipped: LM Studio server not available |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_chat_completion_returns_llm_response` | Skipped: LM Studio server not available |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_stream_completion_yields_chunks` | Skipped: LM Studio server not available |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_temperature_parameter` | Skipped: LM Studio server not available |
| `integration/test_mcp_live.py::TestMCPLive::test_connect_to_server` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_live` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_detailed` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_call_tool_live` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_connection_error_handling` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |

## Results by Module

| Module | Passed | Failed | Skipped | XFailed | Total | Duration |
|--------|--------|--------|---------|---------|-------|----------|
| **Provider: OpenAI** | 17 | 0 | 0 | 0 | 17 | 12.38s |
| **Provider: Mammouth AI** | 6 | 0 | 0 | 0 | 6 | 3.24s |
| **Provider: Local (LM Studio / Ollama)** | 1 | 0 | 10 | 0 | 11 | 0.05s |
| **MCP Client** | 1 | 0 | 5 | 0 | 6 | <0.01s |

## Detailed Results

### Integration Tests (25 passed, 15 skipped)

#### Provider: OpenAI (17 passed) - 12.38s

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_openai_live.py::TestOpenAILive::test_simple_completion` | PASSED | 1.55s |
| `integration/test_openai_live.py::TestOpenAILive::test_list_models` | PASSED | 0.68s |
| `integration/test_openai_live.py::TestOpenAILive::test_streaming_completion` | PASSED | 0.84s |
| `integration/test_openai_live.py::TestOpenAILive::test_system_message` | PASSED | 0.74s |
| `integration/test_openai_live.py::TestOpenAILive::test_json_mode` | PASSED | 0.70s |
| `integration/test_openai_live.py::TestAnthropicLive::test_simple_completion` | PASSED | 1.22s |
| `integration/test_openai_live.py::TestAnthropicLive::test_list_models` | PASSED | 0.25s |
| `integration/test_openai_live.py::TestAnthropicLive::test_streaming_completion` | PASSED | 0.63s |
| `integration/test_openai_live.py::TestAnthropicLive::test_system_message` | PASSED | 0.69s |
| `integration/test_openai_live.py::TestLangDockLive::test_simple_completion` | PASSED | 0.73s |
| `integration/test_openai_live.py::TestLangDockLive::test_list_models` | PASSED | 0.16s |
| `integration/test_openai_live.py::TestLangDockLive::test_streaming_completion` | PASSED | 0.68s |
| `integration/test_openai_live.py::TestLangDockLive::test_system_message` | PASSED | 0.72s |
| `integration/test_openai_live.py::TestLangDockLive::test_eu_region` | PASSED | 1.03s |
| `integration/test_openai_live.py::TestLangDockAnthropicBackend::test_anthropic_completion` | PASSED | 1.24s |
| `integration/test_openai_live.py::TestLangDockAnthropicBackend::test_anthropic_list_models` | PASSED | 0.18s |
| `integration/test_openai_live.py::TestCostEffectivePatterns::test_minimal_token_usage` | PASSED | 0.36s |

#### Provider: Mammouth AI (6 passed) - 3.24s

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_mammouth_live.py::TestMammouthLive::test_simple_completion` | PASSED | 0.75s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_list_models` | PASSED | 0.12s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_list_models_has_temperature_constraints` | PASSED | 0.12s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_streaming_completion` | PASSED | 0.90s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_system_message` | PASSED | 0.68s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_context_manager` | PASSED | 0.66s |

#### Provider: Local (LM Studio / Ollama) (1 passed, 10 skipped) - 0.05s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_local_live.py::TestLMStudioLive::test_connection` | SKIPPED | - | Skipped: LM Studio server not available at localhost:1234 |
| `integration/test_local_live.py::TestLMStudioLive::test_list_models` | SKIPPED | - | Skipped: LM Studio server not available at localhost:1234 |
| `integration/test_local_live.py::TestLMStudioLive::test_simple_completion` | SKIPPED | - | Skipped: LM Studio server not available at localhost:1234 |
| `integration/test_local_live.py::TestLMStudioLive::test_system_message` | SKIPPED | - | Skipped: LM Studio server not available at localhost:1234 |
| `integration/test_local_live.py::TestLMStudioLive::test_streaming_completion` | SKIPPED | - | Skipped: LM Studio server not available at localhost:1234 |
| `integration/test_local_live.py::TestLMStudioLive::test_multiple_turns` | SKIPPED | - | Skipped: LM Studio server not available at localhost:1234 |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_provider_properties` | SKIPPED | - | Skipped: LM Studio server not available |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_chat_completion_returns_llm_response` | SKIPPED | - | Skipped: LM Studio server not available |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_stream_completion_yields_chunks` | SKIPPED | - | Skipped: LM Studio server not available |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_temperature_parameter` | SKIPPED | - | Skipped: LM Studio server not available |
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
