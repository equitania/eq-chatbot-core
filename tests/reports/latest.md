# Test Report - 2026-05-07 12:20:20

**eq_chatbot_core v1.6.0** | 0.22s | Python 3.13.12 | macOS-26.4.1-arm64-arm-64bit-Mach-O

> **Result: ALL PASSED - 38 tests OK**

Command: `/Users/picard/gitbase/PyPi-Projects/eq_chatbot_core/.venv/bin/pytest tests/unit/server/ -q --tb=short`

## Summary

| Status | Count |
|--------|-------|
| Passed | 38 |
| Failed | 0 |
| **Total** | **38** |

## Test Configuration

| Provider | Test Model | Source |
|----------|------------|--------|
| OpenAI | `gpt-4o-mini` | `OPENAI_TEST_MODEL` |
| Anthropic | `claude-3-haiku-20240307` | `ANTHROPIC_TEST_MODEL` |
| LangDock | `gpt-5.2` | `LANGDOCK_TEST_MODEL` |
| Mammouth | `gpt-4.1-nano` | `MAMMOUTH_TEST_MODEL` |
| Azure | `Phi-4` | `AZURE_TEST_MODEL` |
| Vertex | `gemini-2.5-flash` | `VERTEX_TEST_MODEL` |
| Local | `nvidia/nemotron-3-nano` | `LOCAL_TEST_MODEL` |

## Results by Module

| Module | Test Model | Passed | Failed | Skipped | XFailed | Total | Duration |
|--------|------------|--------|--------|---------|---------|-------|----------|
| **Other** | - | 38 | 0 | 0 | 0 | 38 | 0.03s |

## Detailed Results

### Unit Tests (38 passed)

#### Other (38 passed) - 0.03s

| Test | Status | Duration |
|------|--------|----------|
| `unit/server/test_app.py::TestHealthAndProviders::test_health_returns_ok_without_auth` | PASSED | <0.01s |
| `unit/server/test_app.py::TestHealthAndProviders::test_providers_requires_auth` | PASSED | <0.01s |
| `unit/server/test_app.py::TestHealthAndProviders::test_providers_lists_known_names` | PASSED | <0.01s |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_returns_provider_response` | PASSED | <0.01s |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_authentication_error_returns_401` | PASSED | <0.01s |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_rate_limit_returns_429_with_retry_after` | PASSED | <0.01s |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_context_length_returns_413` | PASSED | <0.01s |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_unknown_provider_returns_400` | PASSED | <0.01s |
| `unit/server/test_app.py::TestChatEndpoint::test_chat_with_tools_forwards_to_provider` | PASSED | <0.01s |
| `unit/server/test_app.py::TestChatStreamEndpoint::test_stream_chat_emits_chunk_and_done` | PASSED | <0.01s |
| `unit/server/test_app.py::TestChatStreamEndpoint::test_stream_provider_error_emits_error_event` | PASSED | <0.01s |
| `unit/server/test_app.py::TestChatStreamEndpoint::test_stream_unknown_provider_returns_400` | PASSED | <0.01s |
| `unit/server/test_app.py::TestChatStreamEndpoint::test_stream_requires_auth` | PASSED | <0.01s |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_health_bypasses_auth` | PASSED | <0.01s |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_missing_authorization_header_is_401` | PASSED | <0.01s |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_wrong_scheme_is_401` | PASSED | <0.01s |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_wrong_token_is_401` | PASSED | <0.01s |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_correct_token_passes` | PASSED | <0.01s |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_token_compared_constant_time_against_prefix_match` | PASSED | <0.01s |
| `unit/server/test_auth.py::TestBearerTokenMiddleware::test_empty_token_in_constructor_raises` | PASSED | <0.01s |
| `unit/server/test_cli_serve.py::TestReadAuthToken::test_fd_takes_precedence_and_closes_fd` | PASSED | <0.01s |
| `unit/server/test_cli_serve.py::TestReadAuthToken::test_fd_strips_whitespace_and_newline` | PASSED | <0.01s |
| `unit/server/test_cli_serve.py::TestReadAuthToken::test_argv_token_when_no_fd` | PASSED | <0.01s |
| `unit/server/test_cli_serve.py::TestReadAuthToken::test_env_var_used_as_fallback` | PASSED | <0.01s |
| `unit/server/test_cli_serve.py::TestReadAuthToken::test_missing_token_raises` | PASSED | <0.01s |
| `unit/server/test_cli_serve.py::TestReadAuthToken::test_short_token_raises` | PASSED | <0.01s |
| `unit/server/test_cli_serve.py::TestServeCommand::test_missing_token_exits_nonzero` | PASSED | <0.01s |
| `unit/server/test_cli_serve.py::TestServeCommand::test_short_token_exits_nonzero` | PASSED | <0.01s |
| `unit/server/test_cli_serve.py::TestServeCommand::test_valid_token_invokes_run_server` | PASSED | <0.01s |
| `unit/server/test_cli_serve.py::TestServeCommand::test_serve_help_lists_options` | PASSED | <0.01s |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_content_only_chunk_emits_chunk_event` | PASSED | <0.01s |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_empty_content_is_skipped` | PASSED | <0.01s |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_final_chunk_emits_done_with_finish_reason` | PASSED | <0.01s |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_final_chunk_with_usage_emits_usage_event` | PASSED | <0.01s |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_zero_token_usage_does_not_emit_usage_event` | PASSED | <0.01s |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_tool_call_delta_passes_through` | PASSED | <0.01s |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_final_chunk_with_tool_calls_emits_tool_calls_event` | PASSED | <0.01s |
| `unit/server/test_streaming.py::TestStreamChunkToSseEvents::test_full_stream_event_order` | PASSED | <0.01s |
