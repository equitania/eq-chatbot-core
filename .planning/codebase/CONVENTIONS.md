# Coding Conventions

**Analysis Date:** 2026-05-11

## Naming Patterns

**Files:**
- Modules use `snake_case.py`: `openai_provider.py`, `error_handler.py`, `rate_limit.py`
- Provider files suffix with `_provider`: `openai_provider.py`, `anthropic_provider.py`
- Test files prefix with `test_`: `test_openai.py`, `test_openai_live.py`
- Integration tests suffix with `_live`: `test_openai_live.py`, `test_mammouth_live.py`

**Classes:**
- `PascalCase` throughout: `OpenAIProvider`, `BaseLLMProvider`, `ChatbotErrorHandler`, `FernetEncryption`
- Provider classes named `{Name}Provider`: `OpenAIProvider`, `AnthropicProvider`, `LocalLLMProvider`
- Exception classes suffix with `Error`: `ProviderError`, `RateLimitError`, `AuthenticationError`
- Data containers use descriptive names: `LLMResponse`, `StreamChunk`, `ModelInfo`, `ErrorResult`, `ModelChain`

**Functions:**
- `snake_case` for all functions and methods
- Private methods prefix with `_`: `_handle_timeout`, `_try_fallback_provider`, `_resolve_test_model`
- Module-level private helpers prefix with `_`: `_logger`, `_session_start_time`, `_MODULE_GROUPS`
- Boolean properties use `is_` / `has_` prefix: `is_fallback`, `has_error`, `is_server_available`

**Variables and Constants:**
- `SCREAMING_SNAKE_CASE` for module-level constants: `DEFAULT_BASE_URL`, `FALLBACK_CHAINS`, `MODEL_TEMPERATURE_CONSTRAINTS`, `TEST_MAX_TOKENS`
- Local variables `snake_case`
- Type annotation constants use `dict[str, str]` style (not `Dict`)

**Test Classes:**
- `Test{Subject}` pattern: `TestOpenAIProviderInit`, `TestOpenAIChatCompletion`, `TestOpenAILive`
- Live/integration tests use `{Provider}Live` suffix: `TestOpenAILive`, `TestAnthropicLive`

## Code Style

**Formatter:**
- `ruff format` — line-ending: auto
- Line length: 120 characters (configured in `pyproject.toml`)

**Linter:**
- `ruff check` with rules: E, W, F, I (isort), B (bugbear), C4 (comprehensions), UP (pyupgrade)
- Ignored: E501 (line too long, handled by formatter), B008 (defaults)
- Test files additionally ignore E402 (intentional late imports after `sys.modules` mocking), B017 (broad `pytest.raises`)

**Type Checking:**
- `mypy` in strict mode (`strict = true`), `ignore_missing_imports = true`
- Target: Python 3.10 (`python_version = "3.10"`)
- Use `from __future__ import annotations` when needed for forward references
- Use `from collections.abc import Iterator` (not `typing.Iterator`) — modern style enforced by UP rules
- Use `X | Y` union syntax (not `Union[X, Y]`) — enforced by UP rules
- Use `X | None` (not `Optional[X]`) — enforced by UP rules

## Import Organization

**Order (enforced by ruff isort):**
1. Standard library (`import os`, `import sys`, `from __future__ import annotations`)
2. Third-party (`import pytest`, `import click`, `import httpx`)
3. First-party (`from eq_chatbot_core.providers import ...`)

**Path Aliases:**
- `known-first-party = ["eq_chatbot_core"]` in `pyproject.toml`
- No path aliases — always use full package paths: `from eq_chatbot_core.providers.base import LLMResponse`

**Lazy Imports Pattern:**
- Heavy/optional SDK imports are deferred inside functions or the `get_provider` factory to avoid `ImportError` at module load time when optional extras are not installed
- Example: `from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider` inside `get_provider()` body
- `TYPE_CHECKING` guard used in `__init__.py` to reference types without circular imports:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from eq_chatbot_core.providers.base import BaseLLMProvider
  ```

**Module-level mocking in unit tests:**
- Always mock the SDK before importing the provider under test:
  ```python
  import sys
  from unittest.mock import MagicMock
  mock_openai_module = MagicMock()
  sys.modules["openai"] = mock_openai_module
  from eq_chatbot_core.providers.openai_provider import OpenAIProvider
  ```
- Ruff E402 suppressed for test files specifically for this pattern.

## Docstrings

**Style:** Google-style docstrings with `Args:`, `Returns:`, `Raises:`, `Yields:` sections.

**Module docstrings:** All modules have a module-level docstring. Providers' `__init__.py` includes usage examples.

**Class docstrings:** Brief one-line summary for dataclasses and ABCs.

**Method docstrings:** All public methods documented. Private helpers use brief single-line docstrings.

**Field docstrings:** `@dataclass` fields use inline docstrings (not comments):
```python
@dataclass
class LLMResponse:
    content: str
    """The generated text content."""
    input_tokens: int = 0
    """Number of input tokens used."""
```

**No docstrings required for:** `__repr__`, `@property` implementations, trivial pass-through methods.

## Section Separators in Large Files

Files with multiple logical groups use `# ===` dividers:
```python
# =============================================================================
# Chat Completion Tests
# =============================================================================
```
Used consistently in `conftest.py`, test files, and large provider implementations.

## Error Handling

**Provider errors:** Convert SDK-specific exceptions to the hierarchy in `src/eq_chatbot_core/providers/base.py`:
```
ProviderError (base, has provider + status_code + retry_after)
├── RateLimitError     # HTTP 429
├── AuthenticationError # HTTP 401/403
├── ContextLengthError  # token limit exceeded
└── OverloadedError     # HTTP 529/503, retryable
```

**Error classification:** Parse `str(error)` for HTTP status codes and keywords — providers use string matching on the generic `Exception` message rather than SDK-specific exception types to remain portable.

**Service-layer errors:** `ChatbotErrorHandler` (`src/eq_chatbot_core/services/error_handler.py`) wraps provider errors, applies exponential backoff with jitter, tries fallback providers, and returns `ErrorResult` dataclasses (never raises to callers).

**Default error messages:** German-language user-facing messages in `DEFAULT_ERROR_MESSAGES` dict; overridable via constructor argument.

## Logging

**Framework:** `logging` from stdlib. No third-party logging libraries.

**Logger instantiation:**
```python
import logging
logger = logging.getLogger(__name__)         # public name in modules
_logger = logging.getLogger(__name__)        # private (underscore) in some modules
```

**Log levels:**
- `logger.warning(...)` — rate limits, timeout retries, temperature clamping
- `logger.error(...)` — unexpected/generic provider errors
- `logger.info(...)` — fallback provider selection
- `logger.debug(...)` — retry callback failures (low-signal noise)

**Format:** Use `%`-style lazy formatting for performance:
```python
_logger.warning("Temperature %.2f below minimum %.2f for model %s", temperature, min_temp, model)
```
Exception: f-strings acceptable in non-critical paths: `logger.info(f"Falling back to {fallback_name}")`

## Function Design

**Size:** Methods stay focused — most under 30 lines. Long dispatch methods split into `_handle_*` private helpers.

**Parameters:**
- Required args positional, optional args keyword-only
- `**kwargs: Any` passed through on provider methods to support provider-specific extras
- Type annotations on all public method signatures (mypy strict mode enforced)

**Return Values:**
- Always typed: `-> LLMResponse`, `-> Iterator[StreamChunk]`, `-> ErrorResult`
- Dataclasses preferred over raw dicts for structured returns
- `None` return only on void/side-effect methods

**Properties vs Methods:**
- Use `@property` for computed values without side effects: `provider_name`, `default_model`, `total_tokens`, `is_fallback`
- Abstract properties defined with `@property @abstractmethod`

## Module Design

**Exports and `__all__`:**
- Each package `__init__.py` defines `__all__` explicitly
- Public API exported from package root: `from eq_chatbot_core.providers import get_provider, LLMResponse`
- Internal modules not re-exported: `temperature_constraints`, `base` (accessed via package)

**Barrel files:**
- `src/eq_chatbot_core/providers/__init__.py` — re-exports public classes + `get_provider` factory
- `src/eq_chatbot_core/security/__init__.py` — re-exports security utilities
- Avoids circular imports by deferring heavy imports inside `get_provider()` body

**Single source of truth:**
- `src/eq_chatbot_core/version.py` — version string, read by hatchling and `_get_version()`
- `src/eq_chatbot_core/providers/temperature_constraints.py` — shared temperature clamping, used by ALL providers
- `tests/model_registry.py` — all test model choices with fallback chains (version-controlled)
- `pyproject.toml` — all dependencies; never create `requirements.txt`

## Git Commit Prefixes

- `[ADD]` — new features or extensions
- `[CHG]` — modifications to existing code
- `[FIX]` — bug fixes

Version headers in files: increment version number + update date to DD.MM.YYYY when changing versioned files.

---

*Convention analysis: 2026-05-11*
