# Changelog

All notable changes to eq-chatbot-core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.15.0] - 2026-02-09

### Changed

- Tighten dependency version ranges with upper bounds (openai <3, anthropic <1, httpx <1, etc.)
- Replace python-magic with puremagic (pure Python, no libmagic system dependency)
- Replace black dependency, use ruff format exclusively
- Add twine to dev dependencies, add Python 3.13 classifier
- Update pre-commit config: replace black hook with ruff-format

### Added

- MCP client SSRF protection (private IP blocking, HTTP/HTTPS scheme validation)
- MCP stdio command whitelist (python, node, uvx, uv) and shell metachar validation
- 22 new unit tests for MCP validation (940 total, 0 failures)

### Fixed

- Replace bare `except Exception` handlers with specific catches + logging

## [0.14.0] - 2026-02-07

### Added

- Configurable error messages to ChatbotErrorHandler (i18n-ready)
- MCP client thread-safety (`_pending_lock` for concurrent requests)
- Unicode NFKD normalization to injection detection
- Error handling to retriever (embedder + Qdrant failures)
- Context manager budget validation (ratio sum check)
- Longest-prefix matching to cost service
- Jitter to error handler retry backoff
- 9 new unit test modules (918 tests total, 0 failures)
- TASKS.md tracking document

### Fixed

- Chunker infinite-loop bug when `chunk_overlap >= chunk_size`
- Anthropic tool input serialization (`json.dumps` instead of `str`)

### Changed

- Stricter MIME-type aliases in file validator
- Add SSE parse error logging to OpenRouter provider
- Update pricing table (Feb 2025: Claude 4.x, o3, gpt-4o corrected)
- Raise minimum dependency versions (cryptography>=44, openai>=1.58, etc.)
- Modernize ruff config to `[tool.ruff.lint]` section

## [0.13.0] - 2025-01-22

### Added

- **OverloadedError Exception**: New exception type for transient server overload errors (529/503)
  - Distinct from RateLimitError for better retry handling
  - Used by Anthropic provider for overload_error responses
  - Properly exported from providers module

### Fixed

- **CLI AttributeError**: Fixed CLI `list-models` command crashing
  - Changed `m.model_id` to `m.id` (matching ModelInfo dataclass)
  - Removed non-existent `supports_temperature` and `max_tokens` attributes
  - Fixed token usage display using correct `LLMResponse` attributes
- **README Examples**: Updated code examples to use correct API
  - `response.usage.total_tokens` → `response.total_tokens`
  - `model.model_id` → `model.id`
- **Export Completeness**: Added `OverloadedError` to `__all__` in providers module
- **MANIFEST.in**: Added manifest file to include LICENSE, README, CHANGELOG in sdist

### Changed

- Improved JSON output in `list-models` command with more model metadata
  - Now includes: id, name, provider, supports_vision, supports_tools, supports_streaming, context_length

## [0.12.0] - 2025-01-17

### Added

- **OpenRouter Provider**: Access to 400+ AI models through unified API
  - Supports OpenAI, Anthropic, Google, Meta, Mistral, and many more models
  - Model ID format: `provider/model-name` (e.g., `openai/gpt-4o`, `anthropic/claude-3.5-sonnet`)
  - Reasoning model detection for O1/O3/O4 series (auto-disables temperature)
  - Streaming with tool-call accumulation
  - Dynamic model list with constraints and pricing metadata
  - Vision support detection from input_modalities
  - Pricing extraction (input/output/image costs)
- OpenRouter support in provider factory: `get_provider("openrouter", api_key="...")`
- Comprehensive unit tests for OpenRouter provider (31 tests)

## [0.9.1] - 2025-12-30

### Fixed

- LangDock Provider: Added tool call accumulation for Anthropic backend streaming
  - Handles content_block_start events for tool_use blocks
  - Handles input_json_delta events for tool arguments
  - Returns complete tool_calls on final StreamChunk
- MCP tool execution now works correctly with LangDock Anthropic backend

## [0.9.0] - 2025-12-30

### Added

- `StreamChunk.tool_calls` field for complete tool call data on final streaming chunk
- Tool call accumulation in streaming for all providers:
  - OpenAI Provider: Accumulates tool_call_delta into complete tool_calls
  - LangDock Provider: Same accumulation for OpenAI-compatible streaming
  - Anthropic Provider: Handles content_block_start/input_json_delta events

### Fixed

- Streaming with function calling now properly returns accumulated tool calls
- Tool execution loop can now access complete tool call data from final StreamChunk

## [0.6.0] - 2025-12-29

### Added

- First standalone PyPI release
- CLI tool `eq-chatbot` with commands:
  - `test-provider` - Test LLM provider connections
  - `list-models` - List available models from providers
  - `info` - Show package information
- Click framework for CLI implementation
- MIT License

### Changed

- Extracted from v18-chatbot monorepo to standalone package
- License changed from Proprietary to MIT
- Updated project URLs to GitHub
- Development status changed to Beta

### Previous History

This package was previously developed as part of the v18-chatbot project:

- 0.5.6: LangDock attachment upload URL fix
- 0.5.5: LangDock provider upload_attachment wrapper
- 0.5.4: LangDock Agent file upload support
- 0.5.3: Agent multimodal warning
- 0.5.2: Anthropic provider vision detection fix
- 0.5.1: Gemini multimodal format conversion
- 0.5.0: PDF-to-image conversion, model-based content format
- 0.4.2: Vision support detection improvements
- 0.4.1: File validator false positive fixes
- 0.4.0: Initial providers, security, RAG modules
