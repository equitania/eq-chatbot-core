# Test Report - 2026-08-19 18:59:43

**eq_chatbot_core v3.1.0** | 96.71s | Python 3.13.12 | macOS-26.6.2-arm64-arm-64bit-Mach-O

> **Result: ALL PASSED - 39 tests OK, 27 skipped**

Command: `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/.venv/bin/pytest tests/integration -q --no-header`

## Summary

| Status | Count |
|--------|-------|
| Passed | 39 |
| Failed | 0 |
| Skipped | 27 |
| **Total** | **66** |

## Configuration Status

**Action required** — missing API credentials cause tests to be skipped. Set the variables below in `tests/.env.test` to enable the affected tests:

| Provider | Missing variable(s) | Tests skipped | Action |
|----------|---------------------|---------------|--------|
| **Ionos** | `IONOS_API_KEY` | 4 | Add `IONOS_API_KEY=...` to `tests/.env.test` |

Credentials configured: `OpenAI`, `Anthropic`, `LangDock`, `OpenRouter`, `Mammouth`, `LiteLLM`, `Melious`

## Models In Use

Resolved live from `tests/model_registry.py` against each provider's `list_models()`. By convention the `primary` in each chain is the cheapest available model; fallbacks rescue the run when the primary is deprecated.

| Provider | Model Used | Cost (per 1M tok) | Source | Status |
|----------|-----------|-------------------|--------|--------|
| OpenAI | `gpt-4o-mini` | $0.15 / $0.60 per 1M tok | Registry primary | OK |
| Anthropic | `claude-haiku-4-5-20251001` | $1.00 / $5.00 per 1M tok | Registry primary | OK |
| LangDock (OpenAI backend) | `gpt-5.2` | LangDock gateway (see langdock.com pricing) | Registry primary | OK |
| LangDock (Anthropic backend) | `claude-sonnet-4-6-default` | LangDock gateway (see langdock.com pricing) | Registry primary | OK |
| OpenRouter | `mistralai/mistral-nemo` | $0.02 / $0.03 per 1M tok | Registry primary | OK |
| Mammouth AI | `gpt-5.4-nano` | ~$0.05 / $0.40 per 1M tok (gateway, passthrough) | Registry primary | OK |
| LiteLLM Gateway | — | gateway (deployment-dependent) | — | SKIPPED — provider not exercised this run |
| IONOS AI Model Hub | — | ~$0.16 per 1M tok (EU-hosted, Berlin/de-txl) | — | SKIPPED — set `IONOS_API_KEY` in `tests/.env.test` |
| Melious.ai | `nemotron-3-nano-30b-a3b` | not published by the API (sovereign EU gateway, 30B MoE / 3B active) | Registry primary | OK |
| Privatemode.ai | — | local proxy (confidential computing, EU) | — | SKIPPED — provider not exercised this run |
| Local (LM Studio / Ollama) | `glm-4.7-flash:latest` | $0 (local) | Env override | OK |

## Skipped Tests

| Test | Reason / Action |
|------|-----------------|
| `integration/test_ionos_live.py::TestIonosLive::test_simple_completion` | **ACTION** — set `IONOS_API_KEY` in `tests/.env.test` to enable this test |
| `integration/test_ionos_live.py::TestIonosLive::test_streaming_completion` | **ACTION** — set `IONOS_API_KEY` in `tests/.env.test` to enable this test |
| `integration/test_ionos_live.py::TestIonosLive::test_list_models` | **ACTION** — set `IONOS_API_KEY` in `tests/.env.test` to enable this test |
| `integration/test_ionos_live.py::TestIonosLive::test_context_manager` | **ACTION** — set `IONOS_API_KEY` in `tests/.env.test` to enable this test |
| `integration/test_litellm_live.py::TestLiteLLMLive::test_simple_completion` | Skipped: LiteLLM gateway at https://api.ccsio.ai/v1 not usable (AuthenticationError: Error code: 401 - {'error': {'message': 'Authentication Error, Invalid proxy server token passed. Received API Key = ***, Key Hash (Token) =31b22469da4224427dbb4fe5ea45c45e3a142ec3076b70db70b4150ef58e47fd. Unable to find token in cache or `LiteLLM_VerificationTokenTable`', 'type': 'token_not_found_in_db', 'param': 'key', 'code': '401'}}) |
| `integration/test_litellm_live.py::TestLiteLLMLive::test_streaming_completion` | Skipped: LiteLLM gateway at https://api.ccsio.ai/v1 not usable (AuthenticationError: Error code: 401 - {'error': {'message': 'Authentication Error, Invalid proxy server token passed. Received API Key = ***, Key Hash (Token) =31b22469da4224427dbb4fe5ea45c45e3a142ec3076b70db70b4150ef58e47fd. Unable to find token in cache or `LiteLLM_VerificationTokenTable`', 'type': 'token_not_found_in_db', 'param': 'key', 'code': '401'}}) |
| `integration/test_litellm_live.py::TestLiteLLMLive::test_list_models` | Skipped: LiteLLM gateway at https://api.ccsio.ai/v1 not usable (AuthenticationError: Error code: 401 - {'error': {'message': 'Authentication Error, Invalid proxy server token passed. Received API Key = ***, Key Hash (Token) =31b22469da4224427dbb4fe5ea45c45e3a142ec3076b70db70b4150ef58e47fd. Unable to find token in cache or `LiteLLM_VerificationTokenTable`', 'type': 'token_not_found_in_db', 'param': 'key', 'code': '401'}}) |
| `integration/test_litellm_live.py::TestLiteLLMLive::test_tts_stt_roundtrip` | Skipped: TTS unavailable on this gateway: Error code: 401 - {'error': {'message': 'Authentication Error, Invalid proxy server token passed. Received API Key = ***, Key Hash (Token) =31b22469da4224427dbb4fe5ea45c45e3a142ec3076b70db70b4150ef58e47fd. Unable to find token in cache or `LiteLLM_VerificationTokenTable`', 'type': 'token_not_found_in_db', 'param': 'key', 'code': '401'}} |
| `integration/test_litellm_live.py::TestLiteLLMLive::test_context_manager` | Skipped: LiteLLM gateway at https://api.ccsio.ai/v1 not usable (AuthenticationError: Error code: 401 - {'error': {'message': 'Authentication Error, Invalid proxy server token passed. Received API Key = ***, Key Hash (Token) =31b22469da4224427dbb4fe5ea45c45e3a142ec3076b70db70b4150ef58e47fd. Unable to find token in cache or `LiteLLM_VerificationTokenTable`', 'type': 'token_not_found_in_db', 'param': 'key', 'code': '401'}}) |
| `integration/test_local_live.py::TestLMStudioLive::test_connection` | Skipped: LM Studio unreachable at localhost:1234, or running without a chat model loaded |
| `integration/test_local_live.py::TestLMStudioLive::test_list_models` | Skipped: LM Studio unreachable at localhost:1234, or running without a chat model loaded |
| `integration/test_local_live.py::TestLMStudioLive::test_simple_completion` | Skipped: LM Studio unreachable at localhost:1234, or running without a chat model loaded |
| `integration/test_local_live.py::TestLMStudioLive::test_system_message` | Skipped: LM Studio unreachable at localhost:1234, or running without a chat model loaded |
| `integration/test_local_live.py::TestLMStudioLive::test_streaming_completion` | Skipped: LM Studio unreachable at localhost:1234, or running without a chat model loaded |
| `integration/test_local_live.py::TestLMStudioLive::test_multiple_turns` | Skipped: LM Studio unreachable at localhost:1234, or running without a chat model loaded |
| `integration/test_mcp_live.py::TestMCPLive::test_connect_to_server` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_live` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_detailed` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_call_tool_live` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_connection_error_handling` | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_privatemode_live.py::TestPrivatemodeLive::test_simple_completion` | Skipped: Privatemode proxy unreachable at http://localhost:8080/v1 (Connection error.) |
| `integration/test_privatemode_live.py::TestPrivatemodeLive::test_streaming_completion` | Skipped: Privatemode proxy unreachable at http://localhost:8080/v1 (Connection error.) |
| `integration/test_privatemode_live.py::TestPrivatemodeLive::test_thinking_can_be_disabled_via_chat_template_kwargs` | Skipped: Privatemode proxy unreachable at http://localhost:8080/v1 (Connection error.) |
| `integration/test_privatemode_live.py::TestPrivatemodeLive::test_list_models` | Skipped: Privatemode proxy unreachable at http://localhost:8080/v1 (Connection error.) |
| `integration/test_privatemode_live.py::TestPrivatemodeLive::test_context_manager` | Skipped: Privatemode proxy unreachable at http://localhost:8080/v1 (Connection error.) |
| `integration/test_realtime_elevenlabs.py::test_elevenlabs_session_ready_and_disconnect` | Skipped: ELEVENLABS_API_KEY / ELEVENLABS_AGENT_ID not set — skipping ElevenLabs integration test |
| `integration/test_realtime_gemini_live.py::test_gemini_live_vertex_eu_session_ready_and_pcm_chunk` | Skipped: GEMINI_VERTEX_ACCESS_TOKEN / VERTEX_PROJECT_ID not set — skipping Vertex EU integration test |

## Results by Module

| Module | Test Model | Passed | Failed | Skipped | XFailed | Total | Duration |
|--------|------------|--------|--------|---------|---------|-------|----------|
| **Provider: OpenAI** | `gpt-4o-mini` | 17 | 0 | 0 | 0 | 17 | 13.68s |
| **Provider: OpenRouter** | `mistralai/mistral-nemo` | 5 | 0 | 0 | 0 | 5 | 21.23s |
| **Provider: Mammouth AI** | `gpt-5.4-nano` | 6 | 0 | 0 | 0 | 6 | 3.81s |
| **Provider: LiteLLM Gateway** | - | 0 | 0 | 5 | 0 | 5 | 1.64s |
| **Provider: IONOS AI Model Hub** | - | 0 | 0 | 4 | 0 | 4 | <0.01s |
| **Provider: Melious.ai (sovereign EU)** | `nemotron-3-nano-30b-a3b` | 4 | 0 | 0 | 0 | 4 | 2.10s |
| **Provider: Privatemode.ai (end-to-end encrypted)** | - | 0 | 0 | 5 | 0 | 5 | 1.21s |
| **Provider: Local (LM Studio / Ollama)** | `glm-4.7-flash:latest` | 5 | 0 | 6 | 0 | 11 | 46.02s |
| **MCP Client** | - | 1 | 0 | 5 | 0 | 6 | 0.02s |
| **Other** | - | 1 | 0 | 2 | 0 | 3 | 3.86s |

## Detailed Results

### Integration Tests (39 passed, 27 skipped)

#### Provider: OpenAI (17 passed) - 13.68s | Model: `gpt-4o-mini`

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_openai_live.py::TestOpenAILive::test_simple_completion` | PASSED | 1.41s |
| `integration/test_openai_live.py::TestOpenAILive::test_list_models` | PASSED | 0.86s |
| `integration/test_openai_live.py::TestOpenAILive::test_streaming_completion` | PASSED | 0.95s |
| `integration/test_openai_live.py::TestOpenAILive::test_system_message` | PASSED | 0.63s |
| `integration/test_openai_live.py::TestOpenAILive::test_json_mode` | PASSED | 1.03s |
| `integration/test_openai_live.py::TestAnthropicLive::test_simple_completion` | PASSED | 0.78s |
| `integration/test_openai_live.py::TestAnthropicLive::test_list_models` | PASSED | 0.32s |
| `integration/test_openai_live.py::TestAnthropicLive::test_streaming_completion` | PASSED | 1.11s |
| `integration/test_openai_live.py::TestAnthropicLive::test_system_message` | PASSED | 1.01s |
| `integration/test_openai_live.py::TestLangDockLive::test_simple_completion` | PASSED | 0.91s |
| `integration/test_openai_live.py::TestLangDockLive::test_list_models` | PASSED | 0.20s |
| `integration/test_openai_live.py::TestLangDockLive::test_streaming_completion` | PASSED | 0.81s |
| `integration/test_openai_live.py::TestLangDockLive::test_system_message` | PASSED | 0.91s |
| `integration/test_openai_live.py::TestLangDockLive::test_eu_region` | PASSED | 0.95s |
| `integration/test_openai_live.py::TestLangDockAnthropicBackend::test_anthropic_completion` | PASSED | 0.99s |
| `integration/test_openai_live.py::TestLangDockAnthropicBackend::test_anthropic_list_models` | PASSED | 0.22s |
| `integration/test_openai_live.py::TestCostEffectivePatterns::test_minimal_token_usage` | PASSED | 0.59s |

#### Provider: OpenRouter (5 passed) - 21.23s | Model: `mistralai/mistral-nemo`

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_openrouter_live.py::TestOpenRouterLive::test_simple_completion` | PASSED | 1.38s |
| `integration/test_openrouter_live.py::TestOpenRouterLive::test_list_models` | PASSED | 0.17s |
| `integration/test_openrouter_live.py::TestOpenRouterLive::test_streaming_completion` | PASSED | 3.27s |
| `integration/test_openrouter_live.py::TestOpenRouterLive::test_system_message` | PASSED | 7.58s |
| `integration/test_openrouter_live.py::TestOpenRouterLive::test_provider_prefix_routing` | PASSED | 8.83s |

#### Provider: Mammouth AI (6 passed) - 3.81s | Model: `gpt-5.4-nano`

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_mammouth_live.py::TestMammouthLive::test_simple_completion` | PASSED | 0.85s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_list_models` | PASSED | 0.18s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_list_models_has_temperature_constraints` | PASSED | 0.15s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_streaming_completion` | PASSED | 0.81s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_system_message` | PASSED | 0.77s |
| `integration/test_mammouth_live.py::TestMammouthLive::test_context_manager` | PASSED | 1.05s |

#### Provider: LiteLLM Gateway (5 skipped) - 1.64s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_litellm_live.py::TestLiteLLMLive::test_simple_completion` | SKIPPED | - | Skipped: LiteLLM gateway at https://api.ccsio.ai/v1 not usable (AuthenticationError: Error code: 401 - {'error': {'message': 'Authentication Error, Invalid proxy server token passed. Received API Key = ***, Key Hash (Token) =31b22469da4224427dbb4fe5ea45c45e3a142ec3076b70db70b4150ef58e47fd. Unable to find token in cache or `LiteLLM_VerificationTokenTable`', 'type': 'token_not_found_in_db', 'param': 'key', 'code': '401'}}) |
| `integration/test_litellm_live.py::TestLiteLLMLive::test_streaming_completion` | SKIPPED | - | Skipped: LiteLLM gateway at https://api.ccsio.ai/v1 not usable (AuthenticationError: Error code: 401 - {'error': {'message': 'Authentication Error, Invalid proxy server token passed. Received API Key = ***, Key Hash (Token) =31b22469da4224427dbb4fe5ea45c45e3a142ec3076b70db70b4150ef58e47fd. Unable to find token in cache or `LiteLLM_VerificationTokenTable`', 'type': 'token_not_found_in_db', 'param': 'key', 'code': '401'}}) |
| `integration/test_litellm_live.py::TestLiteLLMLive::test_list_models` | SKIPPED | - | Skipped: LiteLLM gateway at https://api.ccsio.ai/v1 not usable (AuthenticationError: Error code: 401 - {'error': {'message': 'Authentication Error, Invalid proxy server token passed. Received API Key = ***, Key Hash (Token) =31b22469da4224427dbb4fe5ea45c45e3a142ec3076b70db70b4150ef58e47fd. Unable to find token in cache or `LiteLLM_VerificationTokenTable`', 'type': 'token_not_found_in_db', 'param': 'key', 'code': '401'}}) |
| `integration/test_litellm_live.py::TestLiteLLMLive::test_tts_stt_roundtrip` | SKIPPED | - | Skipped: TTS unavailable on this gateway: Error code: 401 - {'error': {'message': 'Authentication Error, Invalid proxy server token passed. Received API Key = ***, Key Hash (Token) =31b22469da4224427dbb4fe5ea45c45e3a142ec3076b70db70b4150ef58e47fd. Unable to find token in cache or `LiteLLM_VerificationTokenTable`', 'type': 'token_not_found_in_db', 'param': 'key', 'code': '401'}} |
| `integration/test_litellm_live.py::TestLiteLLMLive::test_context_manager` | SKIPPED | - | Skipped: LiteLLM gateway at https://api.ccsio.ai/v1 not usable (AuthenticationError: Error code: 401 - {'error': {'message': 'Authentication Error, Invalid proxy server token passed. Received API Key = ***, Key Hash (Token) =31b22469da4224427dbb4fe5ea45c45e3a142ec3076b70db70b4150ef58e47fd. Unable to find token in cache or `LiteLLM_VerificationTokenTable`', 'type': 'token_not_found_in_db', 'param': 'key', 'code': '401'}}) |

#### Provider: IONOS AI Model Hub (4 skipped) - <0.01s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_ionos_live.py::TestIonosLive::test_simple_completion` | SKIPPED | - | Skipped: IONOS_API_KEY not set |
| `integration/test_ionos_live.py::TestIonosLive::test_streaming_completion` | SKIPPED | - | Skipped: IONOS_API_KEY not set |
| `integration/test_ionos_live.py::TestIonosLive::test_list_models` | SKIPPED | - | Skipped: IONOS_API_KEY not set |
| `integration/test_ionos_live.py::TestIonosLive::test_context_manager` | SKIPPED | - | Skipped: IONOS_API_KEY not set |

#### Provider: Melious.ai (sovereign EU) (4 passed) - 2.10s | Model: `nemotron-3-nano-30b-a3b`

| Test | Status | Duration |
|------|--------|----------|
| `integration/test_melious_live.py::TestMeliousLive::test_simple_completion` | PASSED | 0.64s |
| `integration/test_melious_live.py::TestMeliousLive::test_streaming_completion` | PASSED | 0.89s |
| `integration/test_melious_live.py::TestMeliousLive::test_list_models` | PASSED | 0.14s |
| `integration/test_melious_live.py::TestMeliousLive::test_context_manager` | PASSED | 0.43s |

#### Provider: Privatemode.ai (end-to-end encrypted) (5 skipped) - 1.21s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_privatemode_live.py::TestPrivatemodeLive::test_simple_completion` | SKIPPED | - | Skipped: Privatemode proxy unreachable at http://localhost:8080/v1 (Connection error.) |
| `integration/test_privatemode_live.py::TestPrivatemodeLive::test_streaming_completion` | SKIPPED | - | Skipped: Privatemode proxy unreachable at http://localhost:8080/v1 (Connection error.) |
| `integration/test_privatemode_live.py::TestPrivatemodeLive::test_thinking_can_be_disabled_via_chat_template_kwargs` | SKIPPED | - | Skipped: Privatemode proxy unreachable at http://localhost:8080/v1 (Connection error.) |
| `integration/test_privatemode_live.py::TestPrivatemodeLive::test_list_models` | SKIPPED | - | Skipped: Privatemode proxy unreachable at http://localhost:8080/v1 (Connection error.) |
| `integration/test_privatemode_live.py::TestPrivatemodeLive::test_context_manager` | SKIPPED | - | Skipped: Privatemode proxy unreachable at http://localhost:8080/v1 (Connection error.) |

#### Provider: Local (LM Studio / Ollama) (5 passed, 6 skipped) - 46.02s | Model: `glm-4.7-flash:latest`

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_local_live.py::TestLMStudioLive::test_connection` | SKIPPED | - | Skipped: LM Studio unreachable at localhost:1234, or running without a chat model loaded |
| `integration/test_local_live.py::TestLMStudioLive::test_list_models` | SKIPPED | - | Skipped: LM Studio unreachable at localhost:1234, or running without a chat model loaded |
| `integration/test_local_live.py::TestLMStudioLive::test_simple_completion` | SKIPPED | - | Skipped: LM Studio unreachable at localhost:1234, or running without a chat model loaded |
| `integration/test_local_live.py::TestLMStudioLive::test_system_message` | SKIPPED | - | Skipped: LM Studio unreachable at localhost:1234, or running without a chat model loaded |
| `integration/test_local_live.py::TestLMStudioLive::test_streaming_completion` | SKIPPED | - | Skipped: LM Studio unreachable at localhost:1234, or running without a chat model loaded |
| `integration/test_local_live.py::TestLMStudioLive::test_multiple_turns` | SKIPPED | - | Skipped: LM Studio unreachable at localhost:1234, or running without a chat model loaded |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_provider_properties` | PASSED | <0.01s |  |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_chat_completion_returns_llm_response` | PASSED | 22.12s |  |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_stream_completion_yields_chunks` | PASSED | 12.30s |  |
| `integration/test_local_live.py::TestLocalProviderGeneric::test_temperature_parameter` | PASSED | 11.58s |  |
| `integration/test_local_live.py::TestLocalProviderErrorsLive::test_invalid_url_connection_error` | PASSED | 0.01s |  |

#### MCP Client (1 passed, 5 skipped) - 0.02s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_mcp_live.py::TestMCPLive::test_connect_to_server` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_live` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_list_tools_detailed` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_call_tool_live` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPLive::test_connection_error_handling` | SKIPPED | - | Skipped: MCP server not available (set MCP_TEST_URL in .env.test) |
| `integration/test_mcp_live.py::TestMCPStdioLive::test_stdio_client_not_installed` | PASSED | 0.02s |  |

#### Other (1 passed, 2 skipped) - 3.86s

| Test | Status | Duration | Detail |
|------|--------|----------|--------|
| `integration/test_realtime_elevenlabs.py::test_elevenlabs_session_ready_and_disconnect` | SKIPPED | - | Skipped: ELEVENLABS_API_KEY / ELEVENLABS_AGENT_ID not set — skipping ElevenLabs integration test |
| `integration/test_realtime_gemini_live.py::test_gemini_live_vertex_eu_session_ready_and_pcm_chunk` | SKIPPED | - | Skipped: GEMINI_VERTEX_ACCESS_TOKEN / VERTEX_PROJECT_ID not set — skipping Vertex EU integration test |
| `integration/test_realtime_openai_live.py::test_openai_realtime_session_ready_and_pcm_chunk` | PASSED | 3.86s |  |
