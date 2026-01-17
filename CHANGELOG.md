# Changelog

All notable changes to eq-chatbot-core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
