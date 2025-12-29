# CLAUDE.md

Development guidance for eq-chatbot-core PyPI package.

## Project Overview

Standalone Python library for LLM chatbot integration. Originally extracted from the v18-chatbot Odoo project for independent PyPI publishing.

## Commands

### Development Setup

```bash
# Create virtual environment
uv venv
source .venv/bin/activate  # or: venv+

# Install in development mode with all dependencies
uv pip install -e ".[dev,pdf,security]"

# Or install with pip
pip install -e ".[dev,pdf,security]"
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=eq_chatbot_core --cov-report=html

# Run specific test file
pytest tests/test_providers.py -v

# Run specific test
pytest tests/test_providers.py::test_openai_completion -v
```

### Linting & Formatting

```bash
# Check code style
ruff check src/

# Check formatting
black src/ --check

# Auto-format code
black src/

# Fix lint issues
ruff check src/ --fix

# Type checking
mypy src/
```

### Building & Publishing

```bash
# Build package
python -m build

# Check package
twine check dist/*

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

### CLI Testing

```bash
# Test CLI after installation
eq-chatbot info
eq-chatbot test-provider -p openai -k YOUR_KEY
eq-chatbot list-models -p anthropic -k YOUR_KEY
```

## Architecture

### Provider Pattern

All LLM providers inherit from `BaseLLMProvider` and implement:

```python
class BaseLLMProvider:
    def chat_completion(messages, model, **kwargs) -> LLMResponse
    def stream_completion(messages, model, **kwargs) -> Iterator[StreamChunk]
    def list_models() -> list[ModelInfo]
```

### Module Structure

```
src/eq_chatbot_core/
├── __init__.py          # Package exports
├── version.py           # Version string
├── cli.py               # Click CLI commands
├── providers/           # LLM adapters
│   ├── base.py          # Base classes, response models
│   ├── openai_provider.py
│   ├── anthropic_provider.py
│   └── langdock_provider.py
├── security/            # Security utilities
│   ├── encryption.py    # Fernet encryption
│   ├── injection.py     # Prompt injection detection
│   ├── rate_limit.py    # Rate limiting
│   └── file_validator.py
├── rag/                 # RAG components
│   ├── chunker.py       # Text chunking
│   ├── embedder.py      # Embedding generation
│   ├── retriever.py     # Vector retrieval
│   └── context_manager.py
├── mcp/                 # MCP clients
│   ├── http_client.py   # HTTP/SSE transport
│   └── stdio_client.py  # stdio transport
├── services/            # Business logic
│   ├── cost_service.py  # Token cost calculation
│   └── error_handler.py
└── utils/               # Utilities
    ├── pricing.py       # Pricing data
    └── pdf.py           # PDF utilities
```

## Release Process

1. Update version in `src/eq_chatbot_core/version.py`
2. Update CHANGELOG.md with changes
3. Run tests: `pytest tests/ -v`
4. Run linting: `ruff check src/ && black src/ --check`
5. Build: `python -m build`
6. Test on TestPyPI: `twine upload --repository testpypi dist/*`
7. Verify: `pip install -i https://test.pypi.org/simple/ eq-chatbot-core`
8. Upload to PyPI: `twine upload dist/*`
9. Create git tag: `git tag -a v0.6.0 -m "Release 0.6.0"`
10. Push tag: `git push origin v0.6.0`

## Git Commit Conventions

- `[ADD]` - New features
- `[CHG]` - Modifications
- `[FIX]` - Bug fixes

## Dependencies

### Core Dependencies

- `openai` - OpenAI API client
- `anthropic` - Anthropic API client
- `httpx` - HTTP client for LangDock
- `pydantic` - Data validation
- `cryptography` - Fernet encryption
- `click` - CLI framework
- `tiktoken` - Token counting
- `qdrant-client` - Vector database client

### Optional Dependencies

- `[dev]` - pytest, ruff, black, mypy, pre-commit
- `[security]` - python-magic for MIME validation
- `[pdf]` - pymupdf for PDF to image conversion
