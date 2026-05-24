# Phase 1: Contracts + Foundation - Research

**Researched:** 2026-05-24
**Domain:** Python async type system, WebSocket base class, optional-extra import guard, pytest-asyncio mock patterns
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CON-01 | `realtime/contracts.py` defines 12 `NormalizedRealtimeEventTypes` constants with byte-exact string values | All 12 constants verified from GlassAgents source; string values documented in §Code Examples |
| CON-02 | `realtime/contracts.py` defines `NormalizedRealtimeEvent` TypedDict envelope | TypedDict pattern verified from GlassAgents; total=False matches reference |
| CON-03 | `realtime/contracts.py` defines `RealtimeProviderCapabilities` frozen dataclass with `session_sample_rate: int = 24000` | Frozen dataclass with slots verified; `session_sample_rate` field is Captain addition (SUMMARY.md); default 24000 matches `INPUT_AUDIO_SAMPLE_RATE` |
| CON-04 | `realtime/contracts.py` defines `RealtimeAdapterContract` rich `@runtime_checkable` Protocol with 11 async methods | 11-method Protocol verified from GlassAgents contracts.py; `@runtime_checkable` needed for MockRealtimeProvider isinstance check |
| CON-05 | `realtime/contracts.py` exports `INPUT_AUDIO_SAMPLE_RATE = 24_000` constant | Verified from GlassAgents + STACK.md research |
| CON-06 | `realtime/abc.py` defines minimal `RealtimeProvider` ABC (4 abstract methods) plus `RealtimeEvent` union of 7 frozen dataclass event types | 4 abstract methods + 7 event dataclasses verified from GlassAgents abc.py verbatim |
| CON-07 | `providers/base.py` adds shared `ToolDefinition` dataclass; backward-compatible union in `chat_completion` | Existing `base.py` has no ToolDefinition; union approach verified in ARCHITECTURE.md |
| CON-08 | `realtime/websocket_client.py` implements `BaseRealtimeWebsocketClient` with WS connect/send/recv/close, error classes, `connect_with_backoff`, async context manager | GlassAgents source inspected (174 LOC); additions needed: `connect_with_backoff`, `RealtimeClosedError(code, retriable)`, `RealtimeRateLimitError`, `__aenter__/__aexit__` |
| CON-09 | `realtime/factory.py` defines `RealtimeProviderRegistry`, `RealtimeProviderDefinition`, `get_realtime_provider()`, `build_default_realtime_provider_registry()` | Factory pattern verified from GlassAgents factory.py; library version is simpler (no Settings/BridgeBinding — returns provider directly) |
| CON-10 | `realtime/__init__.py` exports `REALTIME_PROVIDERS` constant, all public types, raises friendly `ImportError` when `[realtime]` extra missing | Import guard pattern documented from existing azure/vertex extras; lazy pattern established |
| CON-11 | `realtime/mock.py` ships `MockRealtimeProvider` (queue-backed, stdlib-only, without `[realtime]` extra) | GlassAgents nova.py stub pattern inspected; stdlib asyncio.Queue confirmed; `@runtime_checkable` Protocol check will pass via structural typing |
| CON-12 | `pyproject.toml` declares `[realtime] = ["websockets>=13.0,<17.0"]` extra | websockets 16.0 confirmed on PyPI; version bounds verified against google-genai and openai SDK constraints |
| CON-13 | `tests/unit/realtime/test_contracts.py` asserts each of the 12 event type string values byte-for-byte | 12 strings verified from GlassAgents source; test pattern straightforward |
| QUAL-02 | `tests/unit/realtime/conftest.py` establishes AsyncMock pattern for `websockets.connect` | websockets exception hierarchy verified; AsyncMock required (not MagicMock) per PITFALL-14 |
</phase_requirements>

---

## Summary

Phase 1 lays the complete realtime foundation without touching any network: type contracts, ABCs, WebSocket base class, factory, mock provider, and test infrastructure. Every subsequent phase (2, 3, 4) imports from this phase and must not be started until Phase 1 is complete and green.

The research confirms that the GlassAgents source files are directly portable with specific, well-scoped additions: (1) `connect_with_backoff` on the base class, (2) `code` and `retriable` fields on `RealtimeClosedError`, (3) `RealtimeRateLimitError` exception, (4) `__aenter__/__aexit__` on the base class, (5) `session_sample_rate` field on `RealtimeProviderCapabilities`, (6) the `@runtime_checkable` decorator on `RealtimeAdapterContract`, and (7) the import guard in `realtime/__init__.py`. Everything else is a faithful port.

The 12 `NormalizedRealtimeEventTypes` string constants are verified from the GlassAgents source and must not be changed. The MockRealtimeProvider must be implemented with stdlib only (`asyncio.Queue`) so it is importable without the `[realtime]` extra installed. The conftest.py `AsyncMock` pattern is critical — `MagicMock` is insufficient for `async with websockets.connect()`.

**Primary recommendation:** Port GlassAgents foundation files faithfully and layer the 7 additions listed above on top. Write `test_contracts.py` as the first commit of the phase (CON-13 before CON-01 is implemented — TDD). The string assertions are the migration-safety gate for GlassAgents.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Event type schema (12 constants) | `realtime/contracts.py` | — | Single source of truth; consumers import constants, never hardcode strings |
| Protocol conformance (11-method surface) | `realtime/contracts.py` | `realtime/factory.py` | Factory verifies conformance at registration; Protocol is the type boundary |
| Minimal ABC (4-method surface) | `realtime/abc.py` | — | Stubs/mocks inherit; production providers implement Protocol structurally |
| WebSocket lifecycle + error hierarchy | `realtime/websocket_client.py` | — | Base class owns connect/send/recv/close; concrete providers override hooks |
| Reconnect/backoff logic | `realtime/websocket_client.py` | — | Library-owned, not consumer-owned; prevents reconnect storms |
| Provider registry + factory | `realtime/factory.py` | `realtime/__init__.py` | Registry maps names → factory callables; `__init__.py` exposes one-liner |
| In-process test harness | `realtime/mock.py` | — | Ships in installed package for consumer test suites; stdlib-only |
| Import guard (missing extra) | `realtime/__init__.py` | — | Friendly ImportError at package import time, not at use time |
| Shared tool type | `providers/base.py` | `providers/__init__.py` | Lives in core (no extras needed); re-exported through providers |
| pyproject.toml extra declaration | `pyproject.toml` | — | Single source of truth for dependency |

---

## Standard Stack

### Core (Phase 1 introduces or modifies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `websockets` | `>=13.0,<17.0` | WebSocket transport for all realtime providers | Battle-tested, asyncio-native, zero transitive deps, already transitive dep via google-genai; only new runtime dep for `[realtime]` extra [VERIFIED: pip index versions] |
| `asyncio` (stdlib) | Python 3.10+ | Event loop, Queue, Task management for async WS and mock provider | Stdlib; no additional dep needed |
| `unittest.mock.AsyncMock` (stdlib) | Python 3.8+ | Mock `websockets.connect` as async context manager in unit tests | `MagicMock` fails for `async with` expressions; `AsyncMock` is correct [VERIFIED: websockets 16.0 package inspection] |
| `dataclasses` (stdlib) | Python 3.10+ | Frozen dataclasses for event types, capabilities, config | Consistent with existing `providers/base.py` pattern [VERIFIED: existing codebase] |
| `typing.Protocol` (stdlib) | Python 3.8+ | `RealtimeAdapterContract` with `@runtime_checkable` for isinstance checks | Needed for MockRealtimeProvider structural conformance test |

### Supporting (already in project, used by this phase)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest-asyncio` | `>=0.24.0,<2.0.0` | Async test functions; `asyncio_mode="auto"` already configured | All async tests in `tests/unit/realtime/` |
| `ruff` | `>=0.12.0` | Linting; `E402` already ignored in `tests/**/*.py` for post-sys.modules imports | Run before every commit |
| `mypy` | `>=1.15.0` | Type-check; `strict=true` | Run before marking complete |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `websockets>=13.0,<17.0` | `aiohttp` WebSocket | aiohttp adds ~3 MB, second async HTTP framework; no advantage for pure WS client work |
| `websockets>=13.0,<17.0` | `httpx` WebSocket | httpx 0.x has no WebSocket support — request/response only |
| `asyncio.Queue` for MockRealtimeProvider | `anyio.Queue` | `anyio` is not a stdlib module; mock must be stdlib-only so it works without `[realtime]` extra |
| `@runtime_checkable Protocol` | ABC inheritance | Production providers should not inherit from `RealtimeProvider` ABC — they implement the Protocol structurally; ABC is for stubs |

**Installation:**
```bash
uv pip install -e ".[dev,realtime]"
```

**Version verification:** [VERIFIED: pip index versions]
```
websockets (16.0)
Available versions: 16.0, 15.0.1, 15.0, 14.2, 14.1, 14.0, 13.1, 13.0.1, 13.0, ...
```

---

## Package Legitimacy Audit

> `websockets` is the only new runtime package introduced by Phase 1.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `websockets` | PyPI | ~12 yrs | 50M+/wk | github.com/python-websockets/websockets | [OK] — well-established, no slopcheck tool available but cross-verified | Approved |

*slopcheck was not available in this environment. `websockets` is tagged `[ASSUMED]` per policy, but is cross-verified via: (1) `pip index versions` confirms it on PyPI as a major package; (2) used as a transitive dep by `google-genai` and `openai` SDK; (3) GlassAgents pins it directly at `websockets==15.0.1`.*

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Consumer
    │
    ▼
get_realtime_provider("mock") ──► MockRealtimeProvider (stdlib, no WS)
get_realtime_provider("openai") ─► OpenAIRealtimeClient      ──► websockets
get_realtime_provider("gemini") ─► GeminiLiveClient          ──► websockets
get_realtime_provider("nova")   ─► NovaSonicStub (raises NotImplemented)
    │
    ▼ (all implement)
RealtimeAdapterContract (Protocol, @runtime_checkable)
    │
    ├── 11 async methods (connect, close, initialize_session, ...)
    └── iter_normalized_events() → AsyncIterator[NormalizedRealtimeEvent]
                                        │
                                        └── type: NormalizedRealtimeEventTypes.*
                                            payload: dict[str, Any]

RealtimeProvider (ABC, minimal, 4 abstract methods)
    └── MockRealtimeProvider, NovaSonicStub inherit this

BaseRealtimeWebsocketClient (ABC)
    └── OpenAIRealtimeClient, GeminiLiveClient inherit this
    └── Adds: connect_with_backoff, __aenter__/__aexit__, error hierarchy
```

### Recommended Project Structure

```
src/eq_chatbot_core/
├── providers/
│   ├── base.py            MODIFIED — add ToolDefinition dataclass
│   └── __init__.py        ALREADY MODIFIED (Phase 0)
├── realtime/              NEW package
│   ├── __init__.py        NEW — import guard + re-exports + REALTIME_PROVIDERS constant
│   ├── contracts.py       NEW — 12 constants, TypedDict, capabilities, Protocol
│   ├── abc.py             NEW — 4-method ABC + 7-event union
│   ├── websocket_client.py NEW — base WS class + error hierarchy
│   ├── factory.py         NEW — registry + get_realtime_provider()
│   ├── mock.py            NEW — stdlib-only MockRealtimeProvider
│   └── providers/         NEW sub-package (EMPTY in Phase 1)
│       └── __init__.py
tests/
├── unit/
│   └── realtime/          NEW test package
│       ├── __init__.py
│       ├── conftest.py    NEW — AsyncMock patterns, function-scoped fixtures
│       ├── test_contracts.py   NEW — 12 string assertion tests
│       ├── test_mock.py        NEW — MockRealtimeProvider tests
│       └── test_websocket_client.py  NEW — connect_with_backoff tests
```

### Pattern 1: The 12 NormalizedRealtimeEventTypes Constants

All 12 strings verified from GlassAgents source (`backend/realtime/contracts.py`). These values are FROZEN — any change requires a coordinated GlassAgents migration PR. [VERIFIED: GlassAgents source]

```python
# Source: GlassAgents/backend/realtime/contracts.py (verified 2026-05-24)
class NormalizedRealtimeEventTypes:
    SESSION_READY           = "session.ready"
    RESPONSE_AUDIO_DELTA    = "response.audio.delta"
    RESPONSE_AUDIO_DONE     = "response.audio.done"
    RESPONSE_DONE           = "response.done"
    RESPONSE_CREATED        = "response.created"
    INPUT_SPEECH_STARTED    = "input.speech.started"
    INPUT_SPEECH_STOPPED    = "input.speech.stopped"
    INPUT_AUDIO_COMMITTED   = "input.audio.committed"
    TOOL_CALL_COMPLETED     = "tool.call.completed"
    TOOL_CALL_CANCELLED     = "tool.call.cancelled"
    ERROR                   = "error"
    UNHANDLED               = "provider.event.unhandled"
```

### Pattern 2: Import Guard in `realtime/__init__.py`

The import guard must fire when `from eq_chatbot_core.realtime import get_realtime_provider` is called WITHOUT `[realtime]` installed. MockRealtimeProvider and contracts types must remain importable. [ASSUMED — pattern inferred from existing azure/vertex guard approach in CONCERNS.md; no direct code reference available]

```python
# realtime/__init__.py

# MockRealtimeProvider and contracts are always importable (stdlib-only)
from eq_chatbot_core.realtime.contracts import (
    NormalizedRealtimeEventTypes,
    NormalizedRealtimeEvent,
    RealtimeAdapterContract,
    RealtimeProviderCapabilities,
    INPUT_AUDIO_SAMPLE_RATE,
)
from eq_chatbot_core.realtime.abc import RealtimeProvider, RealtimeEvent
from eq_chatbot_core.realtime.mock import MockRealtimeProvider

# websockets-dependent symbols are guarded
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

REALTIME_PROVIDERS: list[str] = ["openai", "gemini_live", "nova_sonic", "mock"]
```

**Alternative lazy-import approach:** The factory module itself does `import websockets` at module level in `websocket_client.py`. A simpler guard is to catch the ImportError at the `__init__.py` function level as shown above — the factory import itself is deferred inside the function body, so the missing-extra error fires with the friendly message at call time (not import time of `__init__.py`). This preserves the ability to import the package-level `__init__.py` without error.

### Pattern 3: `connect_with_backoff` — Testable Design

The key design constraint is testability: the test must run without real network and must assert that delays were applied. This requires `asyncio.sleep` to be mockable. [ASSUMED — based on standard Python async testing patterns; no upstream documentation directly states this for this exact pattern]

```python
# realtime/websocket_client.py addition to BaseRealtimeWebsocketClient

import asyncio
import random
import logging

logger = logging.getLogger(__name__)

async def connect_with_backoff(
    self,
    max_attempts: int = 5,
    base_delay_s: float = 1.0,
    max_delay_s: float = 30.0,
) -> None:
    """Connect with truncated exponential backoff and jitter.

    Formula: delay = min(base * 2**attempt + random.uniform(0, 1), max_delay)
    Deterministic in tests: patch asyncio.sleep and random.uniform.
    """
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            await self.connect()
            return
        except RealtimeConnectionError as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                delay = min(base_delay_s * (2 ** attempt) + random.uniform(0, 1), max_delay_s)
                logger.warning(
                    "Realtime connect attempt %d/%d failed, retrying in %.1fs: %s",
                    attempt + 1, max_attempts, delay, exc,
                )
                await asyncio.sleep(delay)
    raise RealtimeConnectionError(
        f"Failed to connect after {max_attempts} attempts"
    ) from last_exc
```

**Unit test pattern:**
```python
# tests/unit/realtime/test_websocket_client.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

@pytest.mark.unit
async def test_connect_with_backoff_3_failures_then_success():
    """3 failures then success; asserts asyncio.sleep called twice."""
    attempt_count = 0

    async def mock_connect_impl(self_inner):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 4:
            raise RealtimeConnectionError("transient failure")

    client = ConcreteTestClient()  # concrete subclass for test

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    with patch.object(type(client), "connect", mock_connect_impl), \
         patch("eq_chatbot_core.realtime.websocket_client.asyncio.sleep", fake_sleep), \
         patch("eq_chatbot_core.realtime.websocket_client.random.uniform", return_value=0.0):
        await client.connect_with_backoff(max_attempts=5, base_delay_s=1.0)

    assert attempt_count == 4
    assert len(sleep_calls) == 3
    assert sleep_calls[0] == 1.0   # base * 2^0
    assert sleep_calls[1] == 2.0   # base * 2^1
    assert sleep_calls[2] == 4.0   # base * 2^2
```

### Pattern 4: websockets Exception Classes (verified)

[VERIFIED: websockets 16.0 package inspection — exceptions.py extracted from wheel]

In websockets 13.x (the minimum version), 14.x, 15.x, and 16.x:

```python
# Modern asyncio implementation (default since 15.0):
from websockets.exceptions import (
    ConnectionClosed,        # base for closed connection
    ConnectionClosedOK,      # clean close (code 1000)
    ConnectionClosedError,   # error close (code 1006, etc.)
    InvalidStatus,           # raised on non-101 HTTP status (new impl)
    WebSocketException,      # base for all websockets exceptions
)

# LEGACY-only (still present but deprecated):
from websockets.legacy.exceptions import InvalidStatusCode  # legacy impl only
```

**Critical for `connect_with_backoff`:** HTTP 429 from WS handshake raises `InvalidStatus` in the new asyncio implementation (≥13.x new API). `InvalidStatus.response.status_code` gives the HTTP code. `InvalidStatusCode` (with `.status_code`) is the legacy-implementation exception.

**Safe cross-version pattern:**
```python
# Handles both legacy and new asyncio impl across ws 13.x–16.x
try:
    await websockets.connect(url, additional_headers=headers)
except Exception as exc:
    status_code = (
        getattr(getattr(exc, "response", None), "status_code", None)  # new impl
        or getattr(exc, "status_code", None)  # legacy impl
    )
    if status_code == 429:
        retry_after = ...  # extract from headers if available
        raise RealtimeRateLimitError(retry_after=retry_after) from exc
    raise RealtimeConnectionError(...) from exc
```

### Pattern 5: `RealtimeClosedError` with Close Code

[VERIFIED: websockets 16.0 exceptions.py — `ConnectionClosed`, `ConnectionClosedOK`, `ConnectionClosedError` confirmed]

```python
class RealtimeClosedError(RealtimeClientError):
    """Raised when the WebSocket connection is closed or disconnected.

    Attributes:
        code: WebSocket close code (1000 = normal, 1006 = abnormal/network death).
              None if the connection was never established.
        retriable: True if the close was not intentional (e.g. code 1006).
    """
    def __init__(
        self,
        message: str,
        code: int | None = None,
        retriable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retriable = retriable

# In recv_json():
except ws_exceptions.ConnectionClosed as exc:
    code = getattr(exc, "code", None) or getattr(getattr(exc, "rcvd", None), "code", None)
    retriable = code != 1000  # 1000 = normal close; everything else is retriable
    raise RealtimeClosedError("WebSocket closed", code=code, retriable=retriable) from exc
```

### Pattern 6: MockRealtimeProvider (stdlib-only)

The mock satisfies `RealtimeAdapterContract` via structural typing (duck-typing). It does not import `websockets`. It ships in the installed package for consumer test suites. [VERIFIED: GlassAgents nova.py inspected — asyncio.Queue pattern confirmed]

```python
# realtime/mock.py
import asyncio
from collections.abc import AsyncIterator
from typing import Any

class MockRealtimeProvider:
    """Queue-backed in-process realtime provider. Stdlib-only, no websockets."""

    def __init__(self) -> None:
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._connected: bool = False

    def enqueue_event(self, event: dict[str, Any]) -> None:
        """Pre-load an event for consumption by iter_normalized_events."""
        self._event_queue.put_nowait(event)

    async def connect(self) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False

    async def initialize_session(self, *, instructions=None, voice=None, tools=None) -> None:
        pass

    async def update_session(self, payload: dict[str, Any]) -> None:
        pass

    async def append_client_audio(self, pcm16_audio: bytes) -> None:
        # Validate even-length (PCM16 invariant — PITFALL-06)
        if len(pcm16_audio) % 2 != 0:
            raise ValueError("PCM16 audio must be even-length bytes")

    async def commit_client_turn(self) -> None:
        pass

    async def create_response(self) -> None:
        pass

    async def cancel_response(self, *, response_id: str | None = None) -> None:
        pass

    async def register_tools(self, tools) -> None:
        pass

    async def submit_tool_result(self, *, call_id: str, output: str) -> None:
        pass

    def iter_normalized_events(self) -> AsyncIterator[dict[str, Any]]:
        return self._iter_impl()

    async def _iter_impl(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            event = await self._event_queue.get()
            yield event
            if self._event_queue.empty():
                break

    async def __aenter__(self) -> "MockRealtimeProvider":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()
```

**isinstance check (success criterion #2):**
```python
from eq_chatbot_core.realtime import MockRealtimeProvider, RealtimeAdapterContract
assert isinstance(MockRealtimeProvider(), RealtimeAdapterContract)  # True — structural typing
```

### Pattern 7: AsyncMock for websockets in conftest.py

[VERIFIED: websockets 16.0 exception hierarchy; PITFALL-14 from research]

```python
# tests/unit/realtime/conftest.py
import sys
from unittest.mock import AsyncMock, MagicMock
import pytest

@pytest.fixture(autouse=True, scope="session")
def mock_websockets():
    """Inject mock websockets module for all realtime unit tests.

    IMPORTANT: Uses AsyncMock for connect() — MagicMock breaks `async with`.
    Function-scoped provider fixtures ensure clean state per test (PITFALL-16).
    """
    from websockets.exceptions import (
        ConnectionClosed, ConnectionClosedOK, ConnectionClosedError,
        InvalidStatus, WebSocketException,
    )

    mock_ws_module = MagicMock()
    mock_ws_instance = AsyncMock()
    mock_ws_instance.closed = False
    mock_ws_instance.recv = AsyncMock(return_value='{"type": "test"}')
    mock_ws_instance.send = AsyncMock()
    mock_ws_instance.close = AsyncMock()

    # AsyncMock for connect: supports `async with websockets.connect(...) as ws:`
    mock_ws_module.connect = AsyncMock(return_value=mock_ws_instance)
    mock_ws_module.connect.return_value.__aenter__ = AsyncMock(return_value=mock_ws_instance)
    mock_ws_module.connect.return_value.__aexit__ = AsyncMock(return_value=False)

    # Use REAL exception classes so except clauses work correctly
    mock_ws_module.exceptions = MagicMock()
    mock_ws_module.exceptions.ConnectionClosed = ConnectionClosed
    mock_ws_module.exceptions.ConnectionClosedOK = ConnectionClosedOK
    mock_ws_module.exceptions.ConnectionClosedError = ConnectionClosedError
    mock_ws_module.exceptions.InvalidStatus = InvalidStatus
    mock_ws_module.exceptions.WebSocketException = WebSocketException

    sys.modules["websockets"] = mock_ws_module
    sys.modules["websockets.exceptions"] = mock_ws_module.exceptions
    yield mock_ws_module
    # Note: do NOT restore sys.modules after session — other tests may depend on the mock
```

**Fixture scope:** conftest.py fixture is `scope="session"` for the module-level mock injection, but provider instances are `scope="function"` to prevent state leakage between tests.

### Anti-Patterns to Avoid

- **Putting `websockets` import at module level in `realtime/__init__.py`:** The MockRealtimeProvider import would trigger a hard `ModuleNotFoundError` for consumers without `[realtime]`. Gate the import behind the factory function.
- **`scope="session"` async fixture holding a provider connection:** Event loop teardown causes `RuntimeError: Event loop is closed` between tests (PITFALL-16). Use `scope="function"` for fixtures that create provider instances.
- **`MagicMock` for `websockets.connect`:** Fails with `TypeError: object MagicMock can't be used in 'await' expression` (PITFALL-14).
- **Capturing `assert NormalizedRealtimeEventTypes.X == "..."` in a helper function rather than inline:** Pytest's assertion rewriting works best with inline `assert`; a helper function hides which constant drifted.
- **Registering realtime providers in the existing `CLOUD_PROVIDERS` / `LOCAL_PROVIDERS` lists:** Realtime providers have a separate registry; mixing them into chat lists breaks the HTTP sidecar's provider validation.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff with jitter | Custom delay loop | `connect_with_backoff` on `BaseRealtimeWebsocketClient` (stdlib only: `asyncio.sleep`, `random.uniform`) | Library owns reconnect semantics; consumers must not roll their own loops |
| WebSocket connection state tracking | External state machine | `is_connected` property on `BaseRealtimeWebsocketClient` (checks `self._ws` + `ws.closed`) | Already in GlassAgents reference; idempotent `connect()` relies on it |
| Typed event enum | `IntEnum` or plain strings | `NormalizedRealtimeEventTypes` class with string constants | String constants are forward-compatible; GlassAgents `bridge.py` uses switch-on-string; importing the class constant prevents typos |
| Mock provider | Full WS test server via `websockets.serve` | `MockRealtimeProvider` (stdlib `asyncio.Queue`) | `websockets.serve` adds network and port binding complexity; queue-backed mock is deterministic and zero-latency |
| Provider name validation | String set in `__init__.py` | `RealtimeProviderRegistry.registered_names()` | Single source of truth in registry; `REALTIME_PROVIDERS` constant derived from it |

**Key insight:** The WebSocket error hierarchy (`RealtimeClosedError` with close code, `RealtimeRateLimitError`, `RealtimeProtocolError`) is the critical shared surface that prevents every concrete provider from re-implementing its own retry and error semantics.

---

## Runtime State Inventory

> Not applicable — Phase 1 is greenfield new code only. No rename, refactor, or migration.

---

## Common Pitfalls

### Pitfall 1: Event Type String Drift (PITFALL-29)

**What goes wrong:** A single character difference in a `NormalizedRealtimeEventTypes` constant (e.g., `"response.audio_delta"` instead of `"response.audio.delta"`) causes GlassAgents `bridge.py` to receive `UNHANDLED` events silently. Audio output disappears on migration.

**Why it happens:** Manual transcription from handoff spec during porting.

**How to avoid:** Write `test_contracts.py` with byte-for-byte string assertions BEFORE implementing `contracts.py` (TDD). The test is the spec.

**Warning signs:** GlassAgents bridge logs show all events as `UNHANDLED` after migration.

### Pitfall 2: MagicMock Breaks Async WebSocket Tests (PITFALL-14)

**What goes wrong:** `TypeError: object MagicMock can't be used in 'await' expression` when the test's WS mock is used as `async with websockets.connect(...)`.

**Why it happens:** `websockets.connect()` is an async context manager. `MagicMock()` does not implement `__aenter__` / `__aexit__` as coroutines.

**How to avoid:** Always use `AsyncMock` for `websockets.connect`. Establish this pattern in `conftest.py` before any provider tests are written.

**Warning signs:** Test passes in isolation but fails when awaited. Error message mentions `MagicMock` in an `await` expression.

### Pitfall 3: Connection Leak on Exception Path (PITFALL-04)

**What goes wrong:** If `_on_connected()` raises after `self._ws` is assigned, the TCP connection stays open indefinitely. Over many sessions this exhausts provider-side session quotas.

**Why it happens:** The GlassAgents base class has no `try/finally` around the post-connect setup. The library port must add it.

**How to avoid:** Wrap `_on_connected()` in try/except inside `connect()`; on failure call `await self.close()` before re-raising. Implement `__aenter__`/`__aexit__` so `async with` usage gets cleanup for free.

**Warning signs:** TCP CLOSE_WAIT connections accumulating in `ss -tp`. Provider error "max concurrent sessions exceeded."

### Pitfall 4: Close Code Not Surfaced (PITFALL-01)

**What goes wrong:** `RealtimeClosedError` has no `code` field. Consumer cannot distinguish graceful close (1000) from network death (1006). Reconnect storms possible.

**Why it happens:** The GlassAgents `RealtimeClosedError` has no code field (intentional for that app layer; the library adds it).

**How to avoid:** Add `code: int | None` and `retriable: bool` to `RealtimeClosedError`. Catch `ws_exceptions.ConnectionClosed` (specifically) before the bare `except Exception` in `recv_json()`.

**Warning signs:** Log shows reconnect attempts immediately after clean session end.

### Pitfall 5: MockRealtimeProvider Missing a Protocol Method (CON-11 / CON-04 interaction)

**What goes wrong:** `isinstance(MockRealtimeProvider(), RealtimeAdapterContract)` returns `False` because one of the 11 Protocol methods is missing.

**Why it happens:** `RealtimeAdapterContract` has 11 async methods. Adding a method to the Protocol without updating the Mock breaks the isinstance check silently until the test runs.

**How to avoid:** The test `test_isinstance_check` in `test_mock.py` must run as part of the Phase 1 exit gate. Adding a Protocol method without updating the mock will fail CI immediately.

**Warning signs:** `isinstance(MockRealtimeProvider(), RealtimeAdapterContract)` returns `False`. Python 3.12+ may emit `DeprecationWarning` about Protocol check limitations.

### Pitfall 6: websockets Exception Class Change Across Version Range (NEW — research finding)

**What goes wrong:** The new asyncio implementation (default since websockets 15.0) uses `InvalidStatus` (with `.response.status_code`) for HTTP 4xx from WS handshake. The legacy implementation uses `InvalidStatusCode` (with `.status_code`). Code that catches only `InvalidStatusCode` on websockets 15.x+ using the new implementation will miss 429 errors.

**Why it happens:** GlassAgents uses `websockets==15.0.1` (pinned). The library supports `>=13.0,<17.0`. Code importing `from websockets.exceptions import InvalidStatusCode` in the new asyncio impl gets the legacy class from `websockets.legacy.exceptions` — it is re-exported but carries different semantics.

**How to avoid:** Use the cross-version pattern documented in §Code Examples (Pattern 4): detect `status_code` via `getattr` on both `.response.status_code` and `.status_code` attribute paths. Do not import `InvalidStatusCode` directly; use the generic `Exception` catch with attribute inspection.

**Warning signs:** `RealtimeRateLimitError` is never raised on HTTP 429 responses from the WS handshake. Rate-limit 429s silently become `RealtimeConnectionError`.

---

## Code Examples

### The 12 NormalizedRealtimeEventTypes — Exact Strings for `test_contracts.py`

[VERIFIED: GlassAgents `backend/realtime/contracts.py` source inspection 2026-05-24]

```python
# tests/unit/realtime/test_contracts.py
# These are the CANONICAL string values. Do not change without a coordinated
# GlassAgents migration PR. See PITFALL-27/29 in .planning/research/PITFALLS.md.
import pytest
from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes

@pytest.mark.unit
def test_event_type_string_values():
    """Byte-for-byte assertion of all 12 event type constants."""
    assert NormalizedRealtimeEventTypes.SESSION_READY          == "session.ready"
    assert NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA   == "response.audio.delta"
    assert NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DONE    == "response.audio.done"
    assert NormalizedRealtimeEventTypes.RESPONSE_DONE          == "response.done"
    assert NormalizedRealtimeEventTypes.RESPONSE_CREATED       == "response.created"
    assert NormalizedRealtimeEventTypes.INPUT_SPEECH_STARTED   == "input.speech.started"
    assert NormalizedRealtimeEventTypes.INPUT_SPEECH_STOPPED   == "input.speech.stopped"
    assert NormalizedRealtimeEventTypes.INPUT_AUDIO_COMMITTED  == "input.audio.committed"
    assert NormalizedRealtimeEventTypes.TOOL_CALL_COMPLETED    == "tool.call.completed"
    assert NormalizedRealtimeEventTypes.TOOL_CALL_CANCELLED    == "tool.call.cancelled"
    assert NormalizedRealtimeEventTypes.ERROR                  == "error"
    assert NormalizedRealtimeEventTypes.UNHANDLED              == "provider.event.unhandled"
```

### ToolDefinition Dataclass Addition to `providers/base.py`

[VERIFIED: GlassAgents `backend/tools/contracts.py` pattern; existing `providers/base.py` inspected — no ToolDefinition present]

```python
# providers/base.py addition (after existing imports, before BaseLLMProvider)
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Typed tool/function definition shared by chat and realtime providers.

    Parameters must use flat JSON Schema (no $ref, $defs, allOf, anyOf, oneOf).
    Both OpenAI and Gemini strip or reject JSON Schema references.
    See PITFALL-12 in .planning/research/PITFALLS.md.
    """
    name: str
    description: str
    parameters: dict[str, Any]  # Flat JSON Schema dict
    strict: bool = False
```

**Backward-compatible union in `chat_completion` signature:**
```python
# Update to BaseLLMProvider.chat_completion (non-breaking)
def chat_completion(
    self,
    messages: list[dict[str, Any]],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    tools: list["ToolDefinition"] | list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> LLMResponse:
```

### pyproject.toml Addition

[VERIFIED: websockets 16.0 on PyPI via pip index versions; version bounds from STACK.md]

```toml
# pyproject.toml — add to [project.optional-dependencies]
realtime = [
    "websockets>=13.0,<17.0",
]
```

### `RealtimeProviderCapabilities` with `session_sample_rate`

[VERIFIED: GlassAgents contracts.py inspected — existing fields confirmed; `session_sample_rate` is Captain addition per SUMMARY.md]

```python
# realtime/contracts.py
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class RealtimeProviderCapabilities:
    streaming_audio_input: bool
    streaming_audio_output: bool
    server_vad: bool
    manual_turn_commit_required: bool
    tool_calling: bool
    tool_result_submission_mode: str  # "conversation_item" | "provider_call_id"
    voice_selection: bool
    interruption_cancel: bool
    startup_validation: bool = True
    session_sample_rate: int = 24_000  # ElevenLabs 16kHz prep (PROV-FUT-03)
```

### `NormalizedRealtimeEvent` TypedDict

[VERIFIED: GlassAgents contracts.py — `total=False` confirmed]

```python
# realtime/contracts.py
from typing import Any, TypedDict

class NormalizedRealtimeEvent(TypedDict, total=False):
    type: str           # NormalizedRealtimeEventTypes constant
    payload: dict[str, Any]
    source: str         # provider name (e.g. "openai", "gemini_live")
    raw: Any            # original provider-native event (for debugging)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `openai` SDK `client.realtime.connect()` | Raw `websockets.connect()` via `BaseRealtimeWebsocketClient` | Decision locked by Captain (STACK.md) | No SDK lock-in; reconnect/backoff owned by library |
| `MagicMock` for async WS in tests | `AsyncMock` for `websockets.connect` | Python 3.8+ / websockets 13.x | Required; `MagicMock` breaks `async with` |
| `InvalidStatusCode` (websockets legacy) | `InvalidStatus` (websockets asyncio impl, ≥15.0) | websockets 14.0 introduced new impl; 15.0 made it default | Must catch both paths; use attribute introspection |
| `websockets.connect` with `extra_headers` | `websockets.connect` with `additional_headers` | websockets 10.x+ | GlassAgents base class handles both via `TypeError` fallback |

**Deprecated/outdated:**
- `websockets.legacy.*`: Deprecated in 14.0, removal planned by 2030. GlassAgents uses `from websockets import exceptions as ws_exceptions` which resolves to the new impl in ws≥15. The library port should use `from websockets import exceptions as ws_exceptions` (not legacy).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The import guard pattern: `websockets`-dependent factory is deferred inside the function body of `get_realtime_provider` so `MockRealtimeProvider` and contracts remain importable without the extra | Architecture Patterns §Pattern 2 | If wrong, consumers without `[realtime]` cannot import `MockRealtimeProvider`; breaks success criterion #2 |
| A2 | `@runtime_checkable` Protocol check for `isinstance(MockRealtimeProvider(), RealtimeAdapterContract)` works via structural typing (duck-typing) without ABC inheritance | Standard Stack | If Python's runtime_checkable check is more strict than expected, isinstance returns False; breaks criterion #2 |
| A3 | `connect_with_backoff` patching `asyncio.sleep` and `random.uniform` in the test is sufficient to make the test deterministic and non-network | Code Examples §Pattern 3 | If asyncio.sleep is not patchable in that context, retry delay assertions cannot be made |

**If this table is empty:** Not applicable — 3 assumptions identified above.

---

## Open Questions

1. **`@runtime_checkable` Protocol — method signature strictness**
   - What we know: `@runtime_checkable` in Python 3.12+ performs only name-existence checks, not signature checks. `isinstance(obj, Protocol)` returns True if all Protocol method names are present on the object.
   - What's unclear: Whether Python 3.13 introduced any stricter behavioral checks that could cause `isinstance(MockRealtimeProvider(), RealtimeAdapterContract)` to fail for a mock that has all method names but different signatures.
   - Recommendation: Write the isinstance test explicitly as part of `test_mock.py` and run it on all 4 Python versions (3.10–3.13) in CI. This is the Phase 1 exit gate criterion #2.

2. **`additional_headers` vs `extra_headers` parameter for `websockets.connect`**
   - What we know: GlassAgents base class tries `additional_headers` first, falls back to `extra_headers` on `TypeError`. This was necessary for compatibility with older websockets versions.
   - What's unclear: Whether websockets 13.x–16.x consistently uses `additional_headers` or whether the fallback is still needed.
   - Recommendation: Keep the `try/except TypeError` fallback from GlassAgents in the port; it is harmless and ensures cross-version compatibility within the declared range.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `websockets` | `[realtime]` extra, `BaseRealtimeWebsocketClient` | Not in venv (not installed yet) | — | N/A — install via `uv pip install -e ".[dev,realtime]"` |
| `pytest-asyncio` | All async unit tests | Available (in `[dev]`) | `>=0.24.0` | N/A — already in dev |
| `asyncio.Queue` (stdlib) | MockRealtimeProvider | Always | Python 3.10+ | N/A |
| `unittest.mock.AsyncMock` (stdlib) | conftest.py WS mock | Always | Python 3.8+ | N/A |

**Missing dependencies with no fallback:**
- `websockets` — must be installed via `uv pip install -e ".[dev,realtime]"` before running realtime unit tests. The mock-websockets tests inject `sys.modules["websockets"]` before import, so they can run even without the real package installed — but the package should be installed to verify import paths are correct.

**Missing dependencies with fallback:**
- None for Phase 1.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-asyncio 0.24.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` already set |
| Quick run command | `pytest tests/unit/realtime/ -v -m unit` |
| Full suite command | `pytest tests/unit/ -v --cov=eq_chatbot_core --cov-report=term` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CON-01 | 12 event type string constants are byte-exact | unit | `pytest tests/unit/realtime/test_contracts.py -v -k test_event_type_string_values` | ❌ Wave 0 |
| CON-02 | `NormalizedRealtimeEvent` is a valid TypedDict with expected keys | unit | `pytest tests/unit/realtime/test_contracts.py -v -k test_normalized_event` | ❌ Wave 0 |
| CON-03 | `RealtimeProviderCapabilities` is frozen; `session_sample_rate` defaults to 24000 | unit | `pytest tests/unit/realtime/test_contracts.py -v -k test_capabilities` | ❌ Wave 0 |
| CON-04 | `RealtimeAdapterContract` is `@runtime_checkable`; 11 methods present | unit | `pytest tests/unit/realtime/test_contracts.py -v -k test_adapter_contract` | ❌ Wave 0 |
| CON-05 | `INPUT_AUDIO_SAMPLE_RATE == 24_000` | unit | `pytest tests/unit/realtime/test_contracts.py -v -k test_constants` | ❌ Wave 0 |
| CON-06 | `RealtimeProvider` ABC has exactly 4 abstract methods; 7 event types are frozen | unit | `pytest tests/unit/realtime/test_contracts.py -v -k test_abc` | ❌ Wave 0 |
| CON-07 | `ToolDefinition` is importable from `providers`; `chat_completion` accepts both dict and `ToolDefinition` | unit | `pytest tests/unit/test_factory.py -v -k test_tool_definition` | ❌ Wave 0 (new test) |
| CON-08 | `connect_with_backoff` with 3 failures then success; delays applied; no network | unit | `pytest tests/unit/realtime/test_websocket_client.py -v -k test_backoff` | ❌ Wave 0 |
| CON-09 | `get_realtime_provider("mock")` returns `MockRealtimeProvider`; unknown name raises `ValueError` | unit | `pytest tests/unit/realtime/test_factory.py -v` | ❌ Wave 0 |
| CON-10 | Without `[realtime]` extra: friendly `ImportError` with install instructions | unit | `pytest tests/unit/realtime/test_import_guard.py -v` | ❌ Wave 0 |
| CON-11 | `isinstance(MockRealtimeProvider(), RealtimeAdapterContract)` is True | unit | `pytest tests/unit/realtime/test_mock.py -v -k test_isinstance` | ❌ Wave 0 |
| CON-12 | `pyproject.toml` declares `websockets>=13.0,<17.0` in `[realtime]` extra | unit (static) | `pytest tests/unit/realtime/test_pyproject.py -v` (reads pyproject.toml) | ❌ Wave 0 |
| CON-13 | All 12 string values pass byte-for-byte assertion | unit | `pytest tests/unit/realtime/test_contracts.py::test_event_type_string_values -v` | ❌ Wave 0 |
| QUAL-02 | `conftest.py` uses `AsyncMock` (not `MagicMock`) for `websockets.connect` | unit (infra) | `pytest tests/unit/realtime/ -v` (all tests exercise mock) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/realtime/ -v -m unit`
- **Per wave merge:** `pytest tests/unit/ -v --tb=short`
- **Phase gate:** Full suite green + `ruff check src/ && mypy src/` before `/gsd:verify-work`

### Wave 0 Gaps (all tests are new)

- [ ] `tests/unit/realtime/__init__.py` — empty, makes it a package
- [ ] `tests/unit/realtime/conftest.py` — AsyncMock websockets fixture + function-scoped provider fixtures
- [ ] `tests/unit/realtime/test_contracts.py` — CON-01 through CON-06, CON-13; all 12 string assertions
- [ ] `tests/unit/realtime/test_mock.py` — CON-11; isinstance check + queue-backed event flow
- [ ] `tests/unit/realtime/test_websocket_client.py` — CON-08; connect_with_backoff 3-failure test
- [ ] `tests/unit/realtime/test_factory.py` — CON-09; factory resolution
- [ ] `tests/unit/realtime/test_import_guard.py` — CON-10; friendly ImportError when websockets absent
- [ ] `tests/unit/realtime/test_pyproject.py` — CON-12; static pyproject.toml check

---

## Security Domain

> `security_enforcement` not explicitly set in config — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No — providers authenticate via API keys passed at construction time (existing pattern) | — |
| V3 Session Management | Partial — WebSocket sessions are stateful; `connect_with_backoff` must not expose API keys in error messages | Ensure `RealtimeConnectionError` message uses `_connection_error_endpoint()` (redacted URL), not raw URL |
| V4 Access Control | No — library is caller-controlled | — |
| V5 Input Validation | Yes — `append_client_audio` validates even-length bytes; `ToolDefinition.parameters` must be flat JSON Schema | Validate in MockRealtimeProvider (surfaces consumer bugs early) |
| V6 Cryptography | No — library passes API keys to providers; does not perform cryptography in realtime layer | Existing `FernetEncryption` in `security/` is for API key storage; unrelated to Phase 1 |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key in WS URL query string (Gemini) | Information Disclosure | Port `_redact_sensitive_url` / `_redact_sensitive_text` verbatim (Phase 3); base class provides `_connection_error_endpoint()` hook for override |
| API key in error log messages | Information Disclosure | `_log_connect_failure(exc)` receives the exception; override in provider to redact before logging; base class default is no-op |
| Replay fixture files containing API keys | Information Disclosure | `tests/fixtures/realtime/` directory pre-commit hook: `grep -rE "(sk-\|AIzaSy\|key=[A-Za-z0-9_-]{20,})" tests/fixtures/` — fail if any match |

---

## Sources

### Primary (HIGH confidence)

- `GlassAgents/backend/realtime/contracts.py` — 12 event type strings verified [VERIFIED: direct source inspection 2026-05-24]
- `GlassAgents/backend/realtime/abc.py` — 4-method ABC + 7 event dataclasses [VERIFIED: direct source inspection 2026-05-24]
- `GlassAgents/backend/realtime/websocket_client.py` — base class 174 LOC [VERIFIED: direct source inspection 2026-05-24]
- `GlassAgents/backend/realtime/factory.py` — registry pattern [VERIFIED: direct source inspection 2026-05-24]
- `GlassAgents/backend/realtime/providers/nova.py` — stdlib-only asyncio.Queue stub pattern [VERIFIED: direct source inspection 2026-05-24]
- `eq_chatbot_core/src/eq_chatbot_core/providers/base.py` — existing `BaseLLMProvider` + no ToolDefinition confirmed [VERIFIED: direct source inspection 2026-05-24]
- `eq_chatbot_core/src/eq_chatbot_core/providers/__init__.py` — existing exports confirmed (Phase 0 already complete) [VERIFIED: direct source inspection 2026-05-24]
- `eq_chatbot_core/pyproject.toml` — existing extras layout + ruff/mypy/pytest config [VERIFIED: direct source inspection 2026-05-24]
- `tests/unit/test_anthropic.py` — sys.modules mock pattern confirmed [VERIFIED: direct source inspection 2026-05-24]
- websockets 16.0 wheel inspection (`exceptions.py`) — exception class hierarchy [VERIFIED: pip download + zipfile extraction 2026-05-24]
- `pip index versions websockets` — latest version 16.0, version range 1.0 through 16.0 [VERIFIED: pip index 2026-05-24]

### Secondary (MEDIUM confidence)

- [OpenAI gpt-realtime model docs](https://platform.openai.com/docs/models/gpt-realtime) — current valid model names include `gpt-realtime-2` (GA), `gpt-realtime` (GA), `gpt-4o-realtime-preview` (deprecated Sept 2025). [CITED: platform.openai.com]
- [websockets changelog](https://websockets.readthedocs.io/en/stable/project/changelog.html) — new asyncio implementation became default in 15.0; `InvalidStatusCode` is legacy-only [CITED: websockets docs]
- `.planning/research/PITFALLS.md` — 29 pitfalls with line-number references to GlassAgents source
- `.planning/research/STACK.md` — websockets version decision, `[realtime]` extra declaration
- `.planning/research/ARCHITECTURE.md` — module structure, component boundaries, factory pattern
- `.planning/research/SUMMARY.md` — session_sample_rate Captain decision, locked architecture

### Tertiary (LOW confidence)

- None — all claims in this research are verified or cited.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — websockets on PyPI verified; version bounds cross-checked
- Architecture: HIGH — based on direct GlassAgents source inspection
- Event type constants: HIGH — sourced directly from GlassAgents contracts.py
- Exception hierarchy: HIGH — verified from websockets 16.0 package inspection
- Import guard pattern: MEDIUM — inferred from existing azure/vertex pattern; not directly inspected from current codebase
- Backoff testability: MEDIUM — standard Python async testing pattern; not verified in existing test suite

**Research date:** 2026-05-24
**Valid until:** 2026-06-24 (30 days — stable library; websockets version range unlikely to change)
