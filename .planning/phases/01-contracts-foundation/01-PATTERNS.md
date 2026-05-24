# Phase 1: Contracts + Foundation - Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 14 (8 source files + 6 test files)
**Analogs found:** 13 / 14

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/eq_chatbot_core/realtime/contracts.py` | model | event-driven | `src/eq_chatbot_core/providers/base.py` | role-match (dataclasses + exception hierarchy pattern) |
| `src/eq_chatbot_core/realtime/abc.py` | model | event-driven | `src/eq_chatbot_core/providers/base.py` (BaseLLMProvider ABC) | exact (ABC + frozen dataclasses) |
| `src/eq_chatbot_core/realtime/websocket_client.py` | service | streaming | `src/eq_chatbot_core/providers/base.py` (error class hierarchy) | role-match (ABC base + error classes) |
| `src/eq_chatbot_core/realtime/factory.py` | service | request-response | `src/eq_chatbot_core/providers/__init__.py` (get_provider) | exact (dict-based factory + ValueError on unknown) |
| `src/eq_chatbot_core/realtime/__init__.py` | config | request-response | `src/eq_chatbot_core/providers/__init__.py` + `providers/azure_provider.py` | exact (constants list + deferred import guard) |
| `src/eq_chatbot_core/realtime/mock.py` | service | event-driven | `tests/conftest.py` (mock_openai_client, mock_anthropic_client fixtures) | partial (stdlib mock, no async queue analog in codebase) |
| `src/eq_chatbot_core/realtime/providers/__init__.py` | config | — | `src/eq_chatbot_core/providers/__init__.py` (empty sub-package pattern) | exact (empty package marker) |
| `src/eq_chatbot_core/providers/base.py` | model | request-response | self (existing file, MODIFIED) | exact (add ToolDefinition frozen dataclass) |
| `pyproject.toml` | config | — | `pyproject.toml` (existing [azure], [vertex], [security] extras) | exact |
| `tests/unit/realtime/__init__.py` | config | — | `tests/unit/__init__.py` (if exists, empty) | exact |
| `tests/unit/realtime/conftest.py` | test | event-driven | `tests/conftest.py` (mock_openai_client fixture) | role-match (must use AsyncMock, not MagicMock) |
| `tests/unit/realtime/test_contracts.py` | test | — | `tests/unit/test_openai.py` (sys.modules mock + @pytest.mark.unit) | exact |
| `tests/unit/realtime/test_mock.py` | test | event-driven | `tests/unit/test_openai.py` (fixture + assertion pattern) | role-match |
| `tests/unit/realtime/test_websocket_client.py` | test | streaming | `tests/unit/test_openai.py` (mocked module pattern) | role-match |

---

## Pattern Assignments

### `src/eq_chatbot_core/realtime/contracts.py` (model, event-driven)

**Analog:** `src/eq_chatbot_core/providers/base.py`

**Imports pattern** (lines 1-9 of analog):
```python
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
```
For contracts.py, adapt to:
```python
from dataclasses import dataclass
from typing import Any, TypedDict
```

**Core dataclass pattern** — frozen dataclass with `slots=True` (lines 11-39 of analog):
```python
@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int = 0
    # ... fields with docstrings
```
Apply this `@dataclass` pattern to `RealtimeProviderCapabilities` as `@dataclass(frozen=True, slots=True)`.

**Exception hierarchy pattern** (lines 213-251 of analog):
```python
class ProviderError(Exception):
    def __init__(
        self,
        message: str,
        provider: str,
        status_code: int | None = None,
        retry_after: int | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retry_after = retry_after

class RateLimitError(ProviderError):
    pass

class AuthenticationError(ProviderError):
    pass
```
Apply this hierarchy pattern to the realtime error classes:
`RealtimeClientError` (base) → `RealtimeConnectionError`, `RealtimeClosedError(code, retriable)`, `RealtimeRateLimitError`, `RealtimeProtocolError`.

**TypedDict pattern** — not present in analog; use stdlib directly:
```python
from typing import Any, TypedDict

class NormalizedRealtimeEvent(TypedDict, total=False):
    type: str
    payload: dict[str, Any]
    source: str
    raw: Any
```

**Protocol pattern** — not present in analog; use stdlib `typing.Protocol`:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class RealtimeAdapterContract(Protocol):
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    # ... 9 more async methods
```

---

### `src/eq_chatbot_core/realtime/abc.py` (model, event-driven)

**Analog:** `src/eq_chatbot_core/providers/base.py`

**ABC pattern** (lines 68-184 of analog):
```python
class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: str, base_url: str | None = None, ...):
        self.api_key = api_key
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def default_model(self) -> str: ...

    @abstractmethod
    def chat_completion(self, messages, model, ...) -> LLMResponse: ...
```
Copy this ABC pattern for `RealtimeProvider` ABC (4 abstract methods: `connect`, `close`, `initialize_session`, `iter_normalized_events`). No `__init__` required at ABC level.

**Frozen dataclass for event types** — same pattern as `LLMResponse` / `StreamChunk`:
```python
@dataclass(frozen=True)
class AudioDeltaEvent:
    audio: bytes
    item_id: str
    # ...
```
Use `@dataclass(frozen=True, slots=True)` for all 7 event dataclasses.

---

### `src/eq_chatbot_core/realtime/websocket_client.py` (service, streaming)

**Analog:** `src/eq_chatbot_core/providers/base.py` (error hierarchy) + `providers/azure_provider.py` (graceful import guard)

**Graceful import guard** — copy from `azure_provider.py` lines 31-51:
```python
_azure_available = True
try:
    from azure.ai.inference import ChatCompletionsClient
    # ...
except ImportError:
    _azure_available = False
    ChatCompletionsClient = None  # type: ignore[assignment, misc]
```
Adapt for websockets:
```python
_websockets_available = True
try:
    import websockets
    from websockets import exceptions as ws_exceptions
except ImportError:
    _websockets_available = False
    websockets = None  # type: ignore[assignment]
    ws_exceptions = None  # type: ignore[assignment]
```

**Class-level logger pattern** (line 29 of analog):
```python
_logger = logging.getLogger(__name__)
```

**ABC structure** — copy from `base.py` lines 68-184:
```python
class BaseRealtimeWebsocketClient(ABC):
    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self._url = url
        self._headers = headers or {}
        self._ws: Any = None  # websockets connection

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    @abstractmethod
    async def _on_connected(self) -> None: ...

    @abstractmethod
    async def _on_message(self, raw: str) -> None: ...

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def connect_with_backoff(self, max_attempts=5, ...) -> None: ...
    async def __aenter__(self): ...
    async def __aexit__(self, *_): ...
```

**Error class pattern** — extend `ProviderError` hierarchy from `base.py` lines 213-251 (see above). Realtime errors inherit from a new `RealtimeClientError(Exception)` base (NOT `ProviderError`, since realtime layer is transport-layer, not provider-API-layer).

---

### `src/eq_chatbot_core/realtime/factory.py` (service, request-response)

**Analog:** `src/eq_chatbot_core/providers/__init__.py`

**Dict-based factory pattern** (lines 90-149 of analog):
```python
def get_provider(provider_name: str, api_key: str | None = None, ...) -> "BaseLLMProvider":
    from eq_chatbot_core.providers.openai_provider import OpenAIProvider
    # ... deferred imports inside function body

    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        # ...
    }

    provider_name_lower = provider_name.lower()
    provider_class = providers.get(provider_name_lower)

    if provider_class is None:
        available = list(providers.keys())
        raise ValueError(f"Unknown provider: {provider_name}. Available: {', '.join(sorted(set(available)))}")

    return provider_class(api_key=api_key or "", ...)
```
Copy this exact pattern for `get_realtime_provider(name, **kwargs)`:
- Deferred imports inside function body
- Dict mapping name → class
- `.lower()` normalization
- `ValueError` with sorted available list on unknown name
- Direct instantiation and return

**Registry dataclass pattern** — add a `RealtimeProviderRegistry` and `RealtimeProviderDefinition` dataclass above the factory function, using `@dataclass` pattern from `base.py`.

---

### `src/eq_chatbot_core/realtime/__init__.py` (config, request-response)

**Analog 1:** `src/eq_chatbot_core/providers/__init__.py` — constants list + deferred imports

**Constants list pattern** (lines 35-36 of analog):
```python
CLOUD_PROVIDERS: list[str] = ["openai", "anthropic", "langdock", "openrouter", "mammouth", "azure", "vertex"]
LOCAL_PROVIDERS: list[str] = ["local", "lm_studio", "lmstudio", "ollama"]
```
Copy for:
```python
REALTIME_PROVIDERS: list[str] = ["openai", "gemini_live", "nova_sonic", "mock"]
```

**TYPE_CHECKING guard pattern** (lines 38-41 of analog):
```python
from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
    from eq_chatbot_core.providers.base import BaseLLMProvider
```

**Exports-after-function pattern** (lines 152-188 of analog):
```python
# Exports for public API - after get_provider to avoid circular imports
from eq_chatbot_core.providers.base import (  # noqa: E402
    AuthenticationError,
    BaseLLMProvider,
    ...
)
__all__ = [...]
```

**Analog 2:** `src/eq_chatbot_core/providers/azure_provider.py` — graceful import guard

**Deferred import guard pattern** (lines 31-51 of analog):
```python
_azure_available = True
try:
    from azure.ai.inference import ChatCompletionsClient
except ImportError:
    _azure_available = False
```
In `realtime/__init__.py`, gate `get_realtime_provider` at function-call time (NOT module-import time) so `MockRealtimeProvider` and contracts remain importable without `[realtime]`:
```python
def get_realtime_provider(name: str, **kwargs):
    try:
        import websockets  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "eq-chatbot-core[realtime] is required for realtime voice support. "
            "Install with: pip install eq-chatbot-core[realtime]"
        ) from exc
    from eq_chatbot_core.realtime.factory import _get_realtime_provider_impl
    return _get_realtime_provider_impl(name, **kwargs)
```

---

### `src/eq_chatbot_core/realtime/mock.py` (service, event-driven)

**Analog:** `tests/conftest.py` (mock_openai_client, mock_anthropic_client fixtures — lines 641-677)

The existing mocks in conftest.py use `MagicMock()`. `MockRealtimeProvider` is a real class (ships in the installed package), not a pytest fixture. Closest structural analog is the fixture pattern for intent, but the implementation uses `asyncio.Queue`.

**No direct codebase analog exists** for a stdlib-only async queue-backed mock class. Use the pattern from RESEARCH.md §Pattern 6 directly.

Key constraints derived from analog study:
- Stdlib-only: `import asyncio` only (no `websockets`, no third-party)
- Implements all 11 methods of `RealtimeAdapterContract` structurally (duck-typing)
- `asyncio.Queue` for `enqueue_event` / `iter_normalized_events`
- `__aenter__` / `__aexit__` matching the websocket client pattern

---

### `src/eq_chatbot_core/providers/base.py` MODIFIED (model, request-response)

**Analog:** self (existing file — MODIFICATION only)

**Existing frozen dataclass pattern** (lines 11-66):
```python
@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
```

**Addition:** Insert `ToolDefinition` frozen dataclass BEFORE `BaseLLMProvider` class (after imports, ~line 10):
```python
@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Typed tool/function definition shared by chat and realtime providers.

    Parameters must use flat JSON Schema (no $ref, $defs, allOf, anyOf, oneOf).
    """
    name: str
    description: str
    parameters: dict[str, Any]
    strict: bool = False
```

**Backward-compatible union** in `chat_completion` signature (line 115):
```python
# BEFORE:
tools: list[dict[str, Any]] | None = None,

# AFTER (non-breaking):
tools: list["ToolDefinition"] | list[dict[str, Any]] | None = None,
```

---

### `pyproject.toml` (config)

**Analog:** `pyproject.toml` lines 55-80 — existing optional-dependency extras

**Pattern** (lines 55-80):
```toml
local = [
    "sentence-transformers>=3.0.0,<6.0.0",
]
security = [
    "puremagic>=1.10,<3.0",
]
pdf = [
    "pymupdf>=1.26.0,<2.0.0",
]
azure = [
    "azure-ai-inference>=1.0.0b9",
    "azure-core>=1.30.0",
]
vertex = [
    "google-genai>=1.0.0",
]
```

**Addition** (insert after `vertex` extra, before `server`):
```toml
realtime = [
    "websockets>=13.0,<17.0",
]
```

---

### `tests/unit/realtime/conftest.py` (test, event-driven)

**Analog:** `tests/conftest.py` (mock_openai_client fixture — lines 641-661)

**Existing mock fixture pattern** (lines 641-661 of analog):
```python
@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for unit testing."""
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(...)]
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=8)
    client.chat.completions.create.return_value = mock_response
    return client
```

**CRITICAL DEVIATION:** The websockets mock MUST use `AsyncMock`, not `MagicMock`. Copy `sys.modules` injection pattern from `tests/unit/test_openai.py` lines 7-14:
```python
import sys
from unittest.mock import MagicMock
sys.modules["openai"] = MagicMock()
```
But for websockets, use `AsyncMock` for the `connect` call:
```python
import sys
from unittest.mock import AsyncMock, MagicMock
import pytest

@pytest.fixture(autouse=True, scope="session")
def mock_websockets_module():
    mock_ws_module = MagicMock()
    mock_ws_instance = AsyncMock()
    mock_ws_instance.closed = False
    mock_ws_instance.recv = AsyncMock(return_value='{"type": "test"}')
    mock_ws_instance.send = AsyncMock()
    mock_ws_instance.close = AsyncMock()

    # MUST be AsyncMock: `async with websockets.connect(...)` requires __aenter__/__aexit__
    mock_ws_module.connect = AsyncMock(return_value=mock_ws_instance)
    mock_ws_module.connect.return_value.__aenter__ = AsyncMock(return_value=mock_ws_instance)
    mock_ws_module.connect.return_value.__aexit__ = AsyncMock(return_value=False)

    # Use REAL exception classes so except clauses work correctly
    from websockets.exceptions import (
        ConnectionClosed, ConnectionClosedOK, ConnectionClosedError,
        InvalidStatus, WebSocketException,
    )
    mock_ws_module.exceptions = MagicMock()
    mock_ws_module.exceptions.ConnectionClosed = ConnectionClosed
    mock_ws_module.exceptions.ConnectionClosedOK = ConnectionClosedOK
    mock_ws_module.exceptions.ConnectionClosedError = ConnectionClosedError
    mock_ws_module.exceptions.InvalidStatus = InvalidStatus
    mock_ws_module.exceptions.WebSocketException = WebSocketException

    sys.modules["websockets"] = mock_ws_module
    sys.modules["websockets.exceptions"] = mock_ws_module.exceptions
    yield mock_ws_module

@pytest.fixture
def mock_ws_instance(mock_websockets_module):
    """Function-scoped: fresh WS instance per test to prevent state leakage."""
    instance = AsyncMock()
    instance.closed = False
    instance.recv = AsyncMock(return_value='{"type": "test"}')
    instance.send = AsyncMock()
    instance.close = AsyncMock()
    return instance
```

**Fixture scope rule** (from RESEARCH.md §Pattern 7):
- `scope="session"` for module-level `sys.modules` injection
- `scope="function"` (default) for provider instances — prevents event loop / state leakage between tests

---

### `tests/unit/realtime/test_contracts.py` (test)

**Analog:** `tests/unit/test_openai.py` lines 1-21

**Module-level mock injection pattern** (lines 7-14 of analog):
```python
import sys
from unittest.mock import MagicMock

# Mock the openai module before importing provider
mock_openai_module = MagicMock()
sys.modules["openai"] = mock_openai_module

from eq_chatbot_core.providers.openai_provider import OpenAIProvider
```
For test_contracts.py, no mock injection needed (contracts.py is stdlib-only). Import directly:
```python
import pytest
from eq_chatbot_core.realtime.contracts import (
    NormalizedRealtimeEventTypes,
    NormalizedRealtimeEvent,
    RealtimeProviderCapabilities,
    RealtimeAdapterContract,
    INPUT_AUDIO_SAMPLE_RATE,
)
```

**`@pytest.mark.unit` pattern** — copy from analog. Every function in this file is `@pytest.mark.unit`.

**Inline assert pattern** (not a helper function — ruff assertion rewriting works on inline asserts):
```python
@pytest.mark.unit
def test_event_type_string_values():
    assert NormalizedRealtimeEventTypes.SESSION_READY == "session.ready"
    assert NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA == "response.audio.delta"
    # ... all 12 inline
```

---

### `tests/unit/realtime/test_mock.py` (test, event-driven)

**Analog:** `tests/unit/test_openai.py` — fixture + assertion structure

**Async test pattern** — `asyncio_mode = "auto"` is already configured in `pyproject.toml` (line 137). Async test functions need no `@pytest.mark.asyncio` decorator:
```python
@pytest.mark.unit
async def test_mock_connect():
    provider = MockRealtimeProvider()
    await provider.connect()
    assert provider._connected is True
```

**isinstance Protocol check** (success criterion CON-11):
```python
@pytest.mark.unit
def test_isinstance_check():
    from eq_chatbot_core.realtime.contracts import RealtimeAdapterContract
    from eq_chatbot_core.realtime.mock import MockRealtimeProvider
    assert isinstance(MockRealtimeProvider(), RealtimeAdapterContract)
```

---

### `tests/unit/realtime/test_websocket_client.py` (test, streaming)

**Analog:** `tests/unit/test_openai.py` — sys.modules mock + `@pytest.mark.unit`

**patch.object backoff test pattern** (from RESEARCH.md §Pattern 3 — no direct codebase analog):
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.unit
async def test_connect_with_backoff_3_failures_then_success():
    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    attempt_count = 0
    async def mock_connect(self_inner):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 4:
            raise RealtimeConnectionError("transient failure")

    client = ConcreteTestClient()
    with patch.object(type(client), "connect", mock_connect), \
         patch("eq_chatbot_core.realtime.websocket_client.asyncio.sleep", fake_sleep), \
         patch("eq_chatbot_core.realtime.websocket_client.random.uniform", return_value=0.0):
        await client.connect_with_backoff(max_attempts=5, base_delay_s=1.0)

    assert attempt_count == 4
    assert len(sleep_calls) == 3
```

---

## Shared Patterns

### Deferred Imports (Import Guard)
**Source:** `src/eq_chatbot_core/providers/__init__.py` lines 90-98 + `providers/azure_provider.py` lines 31-51
**Apply to:** `realtime/__init__.py` (factory function body), `realtime/websocket_client.py` (module-level guard)

The deferred-import pattern keeps the package importable without the extra installed. In `__init__.py`, the guard fires at call time (inside the function). In `websocket_client.py`, it fires at module import time (module is only imported when the factory is called).

```python
# Pattern A: module-level graceful import (websocket_client.py)
_websockets_available = True
try:
    import websockets
    from websockets import exceptions as ws_exceptions
except ImportError:
    _websockets_available = False

# Pattern B: function-body deferred import (__init__.py)
def get_realtime_provider(name: str, **kwargs):
    try:
        import websockets  # noqa: F401
    except ImportError as exc:
        raise ImportError("Install with: pip install eq-chatbot-core[realtime]") from exc
    from eq_chatbot_core.realtime.factory import _get_realtime_provider_impl
    return _get_realtime_provider_impl(name, **kwargs)
```

### Frozen Dataclass
**Source:** `src/eq_chatbot_core/providers/base.py` lines 11-66
**Apply to:** `realtime/contracts.py` (`RealtimeProviderCapabilities`), `realtime/abc.py` (7 event dataclasses), `providers/base.py` (`ToolDefinition`)

```python
@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    strict: bool = False
```

### ValueError for Unknown Provider Name
**Source:** `src/eq_chatbot_core/providers/__init__.py` lines 140-142
**Apply to:** `realtime/factory.py` (`get_realtime_provider`)

```python
if provider_class is None:
    available = list(providers.keys())
    raise ValueError(f"Unknown provider: {provider_name}. Available: {', '.join(sorted(set(available)))}")
```

### sys.modules Mock Injection
**Source:** `tests/unit/test_openai.py` lines 7-14
**Apply to:** `tests/unit/realtime/conftest.py` (session-scoped), `tests/unit/realtime/test_import_guard.py` (to test the guard itself)

```python
import sys
from unittest.mock import MagicMock
sys.modules["library_name"] = MagicMock()
# Then import the module under test
from eq_chatbot_core.realtime.websocket_client import BaseRealtimeWebsocketClient
```

### pytest.mark.unit Marker
**Source:** `tests/unit/test_openai.py` (all test functions), `pyproject.toml` line 139
**Apply to:** Every test function in `tests/unit/realtime/`

`asyncio_mode = "auto"` (pyproject.toml line 137) means async test functions need no `@pytest.mark.asyncio` decorator.

### ruff per-file-ignores for Test Files
**Source:** `pyproject.toml` lines 116-120
```toml
[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["E402", "B017"]
```
`E402` is already ignored for all test files — the `sys.modules` injection before imports is explicitly covered. No change needed.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/eq_chatbot_core/realtime/mock.py` | service | event-driven | No stdlib-only async queue-backed mock class exists in the codebase. All existing mocks are pytest fixtures (conftest.py) using `MagicMock`, not installable provider classes using `asyncio.Queue`. Use RESEARCH.md §Pattern 6 directly. |

---

## Metadata

**Analog search scope:**
- `src/eq_chatbot_core/providers/` (base.py, __init__.py, azure_provider.py)
- `tests/conftest.py`
- `tests/unit/test_openai.py`
- `pyproject.toml`

**Files scanned:** 6 analog files read in full
**Pattern extraction date:** 2026-05-24

**Critical warnings for planner:**
1. `realtime/mock.py` has no codebase analog — use RESEARCH.md §Pattern 6 verbatim
2. `tests/unit/realtime/conftest.py` MUST use `AsyncMock` for `websockets.connect`, NOT `MagicMock` (PITFALL-14)
3. Fixture scope: `scope="session"` for `sys.modules` injection, `scope="function"` for provider instances (PITFALL-16)
4. `asyncio_mode = "auto"` is already active — no `@pytest.mark.asyncio` needed on async test functions
5. `realtime/__init__.py` must NOT import `websockets` at module level — only inside `get_realtime_provider()` function body
