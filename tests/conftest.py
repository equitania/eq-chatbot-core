"""
Pytest fixtures and configuration for eq_chatbot_core tests.

This module provides:
- Environment-based test configuration via .env.test
- Provider-specific fixtures for cloud and local LLM testing
- Mock fixtures for unit tests
- Skip markers for conditional test execution
- Markdown test report generation (auto-generated on every run)
"""

import os
import platform
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Load test environment from .env.test if it exists
_env_file = Path(__file__).parent / ".env.test"
if _env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file)
    except ImportError:
        # python-dotenv not installed, read manually
        with open(_env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def test_config() -> dict[str, Any]:
    """Session-scoped test configuration from environment variables."""
    return {
        # Cloud API Keys
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
        "langdock_api_key": os.getenv("LANGDOCK_API_KEY"),
        "mammouth_api_key": os.getenv("MAMMOUTH_API_KEY"),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        "openrouter_site_url": os.getenv("OPENROUTER_SITE_URL"),
        "openrouter_site_name": os.getenv("OPENROUTER_SITE_NAME"),
        "azure_api_key": os.getenv("AZURE_API_KEY"),
        "azure_endpoint": os.getenv("AZURE_ENDPOINT"),
        "azure_model": os.getenv("AZURE_TEST_MODEL", "gpt-4o"),
        # Vertex AI
        "vertex_project": os.getenv("VERTEX_PROJECT"),
        "vertex_location": os.getenv("VERTEX_LOCATION", "europe-west1"),
        "vertex_model": os.getenv("VERTEX_TEST_MODEL", "gemini-2.5-flash"),
        # Local Server URLs
        "lm_studio_url": os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1"),
        "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
        # Test Models
        "openai_model": os.getenv("OPENAI_TEST_MODEL", "gpt-4o-mini"),
        "anthropic_model": os.getenv("ANTHROPIC_TEST_MODEL", "claude-3-haiku-20240307"),
        "langdock_model": os.getenv("LANGDOCK_TEST_MODEL", "gpt-5.2"),
        "mammouth_model": os.getenv("MAMMOUTH_TEST_MODEL", "gpt-4.1-nano"),
        "openrouter_model": os.getenv("OPENROUTER_TEST_MODEL", "openai/gpt-4o-mini"),
        "local_model": os.getenv("LOCAL_TEST_MODEL", "phi-4-mini"),
        # Test Settings
        "skip_live_tests": os.getenv("SKIP_LIVE_TESTS", "false").lower() == "true",
        "skip_local_tests": os.getenv("SKIP_LOCAL_TESTS", "true").lower() == "true",
        "max_tokens": int(os.getenv("TEST_MAX_TOKENS", "20")),
        "timeout": int(os.getenv("TEST_TIMEOUT", "30")),
    }


@pytest.fixture
def openai_api_key(test_config) -> str | None:
    """OpenAI API key from environment."""
    return test_config["openai_api_key"]


@pytest.fixture
def anthropic_api_key(test_config) -> str | None:
    """Anthropic API key from environment."""
    return test_config["anthropic_api_key"]


@pytest.fixture
def langdock_api_key(test_config) -> str | None:
    """LangDock API key from environment."""
    return test_config["langdock_api_key"]


@pytest.fixture
def mammouth_api_key(test_config) -> str | None:
    """Mammouth AI API key from environment."""
    return test_config["mammouth_api_key"]


@pytest.fixture
def openrouter_api_key(test_config) -> str | None:
    """OpenRouter API key from environment."""
    return test_config["openrouter_api_key"]


@pytest.fixture
def azure_api_key(test_config) -> str | None:
    """Azure API key from environment."""
    return test_config["azure_api_key"]


@pytest.fixture
def skip_live_tests(test_config) -> bool:
    """Whether to skip live API tests."""
    return test_config["skip_live_tests"]


@pytest.fixture
def skip_local_tests(test_config) -> bool:
    """Whether to skip local server tests."""
    return test_config["skip_local_tests"]


# =============================================================================
# Skip Condition Helpers
# =============================================================================


def skip_if_no_openai_key():
    """Skip test if OPENAI_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set",
    )


def skip_if_no_anthropic_key():
    """Skip test if ANTHROPIC_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set",
    )


def skip_if_no_langdock_key():
    """Skip test if LANGDOCK_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.getenv("LANGDOCK_API_KEY"),
        reason="LANGDOCK_API_KEY not set",
    )


def skip_if_no_mammouth_key():
    """Skip test if MAMMOUTH_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.getenv("MAMMOUTH_API_KEY"),
        reason="MAMMOUTH_API_KEY not set",
    )


def skip_if_no_openrouter_key():
    """Skip test if OPENROUTER_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.getenv("OPENROUTER_API_KEY"),
        reason="OPENROUTER_API_KEY not set",
    )


def skip_if_no_azure_key():
    """Skip test if AZURE_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.getenv("AZURE_API_KEY"),
        reason="AZURE_API_KEY not set",
    )


def skip_if_live_tests_disabled():
    """Skip test if SKIP_LIVE_TESTS is true."""
    return pytest.mark.skipif(
        os.getenv("SKIP_LIVE_TESTS", "false").lower() == "true",
        reason="SKIP_LIVE_TESTS is true",
    )


def skip_if_local_tests_disabled():
    """Skip test if SKIP_LOCAL_TESTS is true."""
    return pytest.mark.skipif(
        os.getenv("SKIP_LOCAL_TESTS", "true").lower() == "true",
        reason="SKIP_LOCAL_TESTS is true",
    )


# =============================================================================
# Provider Fixtures
# =============================================================================


@pytest.fixture
def openai_provider(openai_api_key, test_config):
    """Create OpenAI provider for testing (requires API key)."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set")

    from eq_chatbot_core.providers import get_provider

    return get_provider("openai", api_key=openai_api_key)


@pytest.fixture
def anthropic_provider(anthropic_api_key, test_config):
    """Create Anthropic provider for testing (requires API key)."""
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    from eq_chatbot_core.providers import get_provider

    return get_provider("anthropic", api_key=anthropic_api_key)


@pytest.fixture
def local_provider_lm_studio(test_config):
    """Create LM Studio provider for testing."""
    if test_config["skip_local_tests"]:
        pytest.skip("SKIP_LOCAL_TESTS is true")

    from eq_chatbot_core.providers import get_provider

    provider = get_provider("lm_studio")

    # Check if server is available
    if not provider.is_server_available():
        pytest.skip(f"LM Studio server not available at {test_config['lm_studio_url']}")

    return provider


@pytest.fixture
def local_provider_ollama(test_config):
    """Create Ollama provider for testing."""
    if test_config["skip_local_tests"]:
        pytest.skip("SKIP_LOCAL_TESTS is true")

    from eq_chatbot_core.providers import get_provider

    provider = get_provider("ollama")

    # Check if server is available
    if not provider.is_server_available():
        pytest.skip(f"Ollama server not available at {test_config['ollama_url']}")

    return provider


# =============================================================================
# Mock Fixtures (for Unit Tests)
# =============================================================================


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for unit testing."""
    client = MagicMock()

    # Mock chat completion response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(content="Hello! How can I help?", tool_calls=None),
            finish_reason="stop",
        )
    ]
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=8)
    mock_response.model = "gpt-4o"
    mock_response.model_dump.return_value = {"id": "test"}

    client.chat.completions.create.return_value = mock_response

    return client


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for unit testing."""
    client = MagicMock()

    # Mock message response
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Hello! How can I help?")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage = MagicMock(input_tokens=10, output_tokens=8)
    mock_response.model = "claude-3-5-sonnet-20241022"

    client.messages.create.return_value = mock_response

    return client


@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for local provider unit testing."""
    import httpx

    client = MagicMock(spec=httpx.Client)

    # Mock chat completion response
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "test-123",
        "object": "chat.completion",
        "model": "local-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from local model!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
    }

    client.post.return_value = mock_response
    client.get.return_value = mock_response

    return client


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_messages() -> list[dict[str, str]]:
    """Sample message list for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ]


@pytest.fixture
def minimal_test_messages() -> list[dict[str, str]]:
    """Minimal messages for cost-effective API testing."""
    return [{"role": "user", "content": "Say 'test' only."}]


@pytest.fixture
def encryption_key() -> str:
    """Generate encryption key for tests."""
    from eq_chatbot_core.security.encryption import FernetEncryption

    return FernetEncryption.generate_key()


# =============================================================================
# Pytest Configuration
# =============================================================================


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (mocked, fast, no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (real API calls, requires keys)")
    config.addinivalue_line("markers", "local: Local LLM server tests (requires running server)")
    config.addinivalue_line("markers", "expensive: Tests with expensive models (skip in CI by default)")
    config.addinivalue_line("markers", "slow: Slow-running tests")


def pytest_collection_modifyitems(config, items):
    """Apply skip markers based on environment configuration."""
    skip_live = os.getenv("SKIP_LIVE_TESTS", "false").lower() == "true"
    skip_local = os.getenv("SKIP_LOCAL_TESTS", "true").lower() == "true"

    for item in items:
        # Skip integration tests if SKIP_LIVE_TESTS is true
        if "integration" in item.keywords and skip_live:
            item.add_marker(pytest.mark.skip(reason="SKIP_LIVE_TESTS is true"))

        # Skip local tests if SKIP_LOCAL_TESTS is true
        if "local" in item.keywords and skip_local:
            item.add_marker(pytest.mark.skip(reason="SKIP_LOCAL_TESTS is true"))

        # Skip expensive tests in CI environments
        if "expensive" in item.keywords and os.getenv("CI"):
            item.add_marker(pytest.mark.skip(reason="Expensive tests skipped in CI"))


# =============================================================================
# Markdown Test Report Generator
# =============================================================================

# Store session start time
_session_start_time = None


def _get_version() -> str:
    """Read version from eq_chatbot_core."""
    try:
        from eq_chatbot_core.version import __version__

        return __version__
    except ImportError:
        return "unknown"


def _get_test_category(nodeid: str, markers: list[str]) -> str:
    """Determine test category from markers or path."""
    if "integration" in markers:
        return "integration"
    if "local" in markers:
        return "local"
    if "unit" in markers:
        return "unit"
    # Fallback: infer from path
    if "/integration/" in nodeid or "integration" in nodeid:
        return "integration"
    if "/local/" in nodeid or "local" in nodeid:
        return "local"
    return "unit"


# Module-to-group mapping for report structure
_MODULE_GROUPS = {
    "OpenAI": {
        "label": "Provider: OpenAI",
        "modules": ["test_openai", "test_openai_live"],
    },
    "Anthropic": {
        "label": "Provider: Anthropic",
        "modules": ["test_anthropic", "test_anthropic_live"],
    },
    "LangDock": {
        "label": "Provider: LangDock",
        "modules": ["test_langdock", "test_langdock_live"],
    },
    "OpenRouter": {
        "label": "Provider: OpenRouter",
        "modules": ["test_openrouter", "test_openrouter_live"],
    },
    "Mammouth": {
        "label": "Provider: Mammouth AI",
        "modules": ["test_mammouth", "test_mammouth_live"],
    },
    "Azure": {
        "label": "Provider: Azure AI",
        "modules": ["test_azure", "test_azure_live"],
    },
    "Vertex": {
        "label": "Provider: Google Vertex AI",
        "modules": ["test_vertex", "test_vertex_live"],
    },
    "Local": {
        "label": "Provider: Local (LM Studio / Ollama)",
        "modules": ["test_local", "test_local_live"],
    },
    "Security": {
        "label": "Security",
        "modules": ["test_encryption", "test_injection", "test_rate_limit", "test_file_validator"],
    },
    "RAG": {
        "label": "RAG Pipeline",
        "modules": ["test_chunker", "test_retriever", "test_context_manager", "test_knowledge_service"],
    },
    "Services": {
        "label": "Services & Core",
        "modules": [
            "test_cost_service",
            "test_error_handler",
            "test_factory",
            "test_exceptions",
            "test_temperature_constraints",
        ],
    },
    "MCP": {
        "label": "MCP Client",
        "modules": ["test_mcp", "test_mcp_live"],
    },
}

# Mapping from module group to test model environment variable and default
_GROUP_TEST_MODELS = {
    "OpenAI": ("OPENAI_TEST_MODEL", "gpt-4o-mini"),
    "Anthropic": ("ANTHROPIC_TEST_MODEL", "claude-3-haiku-20240307"),
    "LangDock": ("LANGDOCK_TEST_MODEL", "gpt-5.2"),
    "OpenRouter": ("OPENROUTER_TEST_MODEL", "openai/gpt-4o-mini"),
    "Mammouth": ("MAMMOUTH_TEST_MODEL", "gpt-4.1-nano"),
    "Azure": ("AZURE_TEST_MODEL", "gpt-4o"),
    "Vertex": ("VERTEX_TEST_MODEL", "gemini-2.5-flash"),
    "Local": ("LOCAL_TEST_MODEL", "phi-4-mini"),
}

# Mapping from module group to required environment variables (auth credentials).
# Used by the configuration-status section of the Markdown report so missing
# credentials are surfaced as actionable items instead of silent skips.
_GROUP_REQUIRED_ENV = {
    "OpenAI": ["OPENAI_API_KEY"],
    "Anthropic": ["ANTHROPIC_API_KEY"],
    "LangDock": ["LANGDOCK_API_KEY"],
    "OpenRouter": ["OPENROUTER_API_KEY"],
    "Mammouth": ["MAMMOUTH_API_KEY"],
    "Azure": ["AZURE_API_KEY", "AZURE_ENDPOINT"],
    "Vertex": ["VERTEX_PROJECT"],  # auth via gcloud ADC, project still required
    "Local": [],  # no key — uses local servers
}


def _get_test_models() -> dict[str, str]:
    """Read configured test models from environment variables."""
    models = {}
    for group_key, (env_var, default) in _GROUP_TEST_MODELS.items():
        models[group_key] = os.getenv(env_var, default)
    return models


def _get_module_group(nodeid: str) -> str:
    """Determine module group from test file name."""
    # Extract filename without extension from nodeid
    # e.g. "tests/unit/test_openai.py::TestClass::test_method" -> "test_openai"
    parts = nodeid.split("::")
    filepath = parts[0]  # "tests/unit/test_openai.py"
    filename = filepath.rsplit("/", 1)[-1].replace(".py", "")  # "test_openai"

    for group_key, group_info in _MODULE_GROUPS.items():
        if filename in group_info["modules"]:
            return group_key
    return "Other"


def _format_duration(seconds: float) -> str:
    """Format duration as human-readable string."""
    if seconds < 0.01:
        return "<0.01s"
    return f"{seconds:.2f}s"


def _escape_md(text: str) -> str:
    """Escape pipe characters for Markdown table cells."""
    return text.replace("|", "\\|").replace("\n", " ")


def _short_nodeid(nodeid: str) -> str:
    """Shorten nodeid by removing common prefixes."""
    # Remove tests/ prefix for brevity
    if nodeid.startswith("tests/"):
        return nodeid[6:]
    return nodeid


def _format_skip_reason(reason: str) -> str:
    """
    Turn ambiguous skip messages into actionable instructions.

    Specifically: any reason mentioning "<VAR>_API_KEY not set" or
    "<VAR>_KEY not set" (with or without a "Skipped: " prefix from pytest)
    becomes "ACTION — set <VAR> in tests/.env.test". Other reasons
    (SKIP_LIVE_TESTS, SKIP_LOCAL_TESTS, server unreachable) pass through
    unchanged so existing behavior isn't masked.
    """
    import re

    match = re.search(r"\b([A-Z][A-Z0-9_]*_KEY)\s+not\s+set\b", reason)
    if match:
        var_name = match.group(1)
        return f"**ACTION** — set `{var_name}` in `tests/.env.test` to enable this test"
    return reason


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Collect test results for Markdown report generation."""
    outcome = yield
    report = outcome.get_result()

    # Only process the 'call' phase (not setup/teardown) for pass/fail
    # but also capture 'setup' phase for skip (skips happen during setup)
    if report.when == "call" or (report.when == "setup" and report.skipped):
        results = getattr(item.config, "_md_report_results", None)
        if results is None:
            item.config._md_report_results = []
            results = item.config._md_report_results

        # Determine outcome
        test_outcome = report.outcome  # "passed", "failed", "skipped"

        # Check for xfail
        wasxfail = getattr(report, "wasxfail", "")
        if wasxfail:
            test_outcome = "xfailed"

        # Extract skip reason
        skip_reason = ""
        if report.skipped:
            if hasattr(report, "longrepr") and isinstance(report.longrepr, tuple):
                skip_reason = str(report.longrepr[2]) if len(report.longrepr) > 2 else ""
            elif wasxfail:
                skip_reason = wasxfail

        # Extract error message for failures
        error_msg = ""
        if report.failed and report.longrepr:
            longrepr_str = str(report.longrepr)
            # Take last line (usually the assertion error)
            lines = longrepr_str.strip().split("\n")
            error_msg = lines[-1].strip() if lines else longrepr_str[:200]

        # Collect markers
        markers = [m.name for m in item.iter_markers()]

        results.append(
            {
                "nodeid": item.nodeid,
                "outcome": test_outcome,
                "duration": getattr(report, "duration", 0.0),
                "skip_reason": skip_reason,
                "error_msg": error_msg,
                "markers": markers,
                "category": _get_test_category(item.nodeid, markers),
                "group": _get_module_group(item.nodeid),
            }
        )


def pytest_sessionstart(session):
    """Record session start time."""
    global _session_start_time
    _session_start_time = time.time()


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Generate Markdown test report at end of test session."""
    results = getattr(config, "_md_report_results", [])
    if not results:
        return

    global _session_start_time
    total_duration = time.time() - _session_start_time if _session_start_time else 0.0

    # Prepare report directory
    report_dir = Path(__file__).parent / "reports"
    report_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = report_dir / f"test-report-{timestamp}.md"
    latest_path = report_dir / "latest.md"

    # Count results by outcome
    counts = {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0, "error": 0}
    for r in results:
        outcome = r["outcome"]
        if outcome in counts:
            counts[outcome] += 1
        else:
            counts["error"] += 1

    total = sum(counts.values())
    version = _get_version()

    # Build Markdown content
    lines = []

    # Overall result line
    if counts["failed"] > 0 or counts["error"] > 0:
        result_text = f"FAILED - {counts['failed']} failure(s), {counts['error']} error(s)"
    else:
        result_text = f"ALL PASSED - {counts['passed']} tests OK"
        if counts["xfailed"] > 0:
            result_text += f", {counts['xfailed']} expected failures"
        if counts["skipped"] > 0:
            result_text += f", {counts['skipped']} skipped"

    report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Header with date
    lines.append(f"# Test Report - {report_date}")
    lines.append("")
    lines.append(
        f"**eq_chatbot_core v{version}** | {_format_duration(total_duration)} | "
        f"Python {platform.python_version()} | {platform.platform()}"
    )
    lines.append("")
    lines.append(f"> **Result: {result_text}**")
    lines.append("")
    lines.append(f"Command: `{' '.join(sys.argv)}`")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|--------|-------|")

    status_labels = {
        "passed": "Passed",
        "failed": "Failed",
        "skipped": "Skipped",
        "xfailed": "XFailed (expected)",
        "error": "Error",
    }
    for status, label in status_labels.items():
        count = counts[status]
        if count > 0 or status in ("passed", "failed"):
            lines.append(f"| {label} | {count} |")
    lines.append(f"| **Total** | **{total}** |")
    lines.append("")

    # Configuration Status section - flag missing credentials per provider
    # so silent skips become actionable: shows which env vars to set in
    # tests/.env.test and how many tests are blocked by each gap.
    skipped_by_group: dict[str, int] = {}
    for r in results:
        if r["outcome"] == "skipped":
            skipped_by_group[r["group"]] = skipped_by_group.get(r["group"], 0) + 1

    config_gaps: list[tuple[str, list[str], int]] = []
    config_ok: list[str] = []
    for group_key, required_vars in _GROUP_REQUIRED_ENV.items():
        if not required_vars:
            continue
        missing = [v for v in required_vars if not os.getenv(v)]
        if missing:
            blocked = skipped_by_group.get(group_key, 0)
            config_gaps.append((group_key, missing, blocked))
        else:
            config_ok.append(group_key)

    lines.append("## Configuration Status")
    lines.append("")
    if config_gaps:
        lines.append(
            "**Action required** — missing API credentials cause tests to be skipped. "
            "Set the variables below in `tests/.env.test` to enable the affected tests:"
        )
        lines.append("")
        lines.append("| Provider | Missing variable(s) | Tests skipped | Action |")
        lines.append("|----------|---------------------|---------------|--------|")
        for group_key, missing, blocked in config_gaps:
            missing_cell = ", ".join(f"`{v}`" for v in missing)
            action = f"Add `{missing[0]}=...` to `tests/.env.test`"
            lines.append(f"| **{group_key}** | {missing_cell} | {blocked} | {action} |")
        lines.append("")
    if config_ok:
        ok_cells = ", ".join(f"`{p}`" for p in config_ok)
        lines.append(f"Credentials configured: {ok_cells}")
        lines.append("")
    if not config_gaps and not config_ok:
        lines.append("_(no provider credentials required for this run)_")
        lines.append("")

    # Test Configuration section - show configured models + key status
    test_models = _get_test_models()
    lines.append("## Test Configuration")
    lines.append("")
    lines.append("| Provider | Test Model | Model Source | API Key |")
    lines.append("|----------|------------|--------------|---------|")
    for group_key, (env_var, default) in _GROUP_TEST_MODELS.items():
        model = test_models.get(group_key, default)
        env_value = os.getenv(env_var)
        source = f"`{env_var}`" if env_value else "default"
        required = _GROUP_REQUIRED_ENV.get(group_key, [])
        if not required:
            key_cell = "n/a"
        else:
            missing = [v for v in required if not os.getenv(v)]
            if missing:
                key_cell = f"**MISSING** — set `{missing[0]}`"
            else:
                key_cell = "set"
        lines.append(f"| {group_key} | `{model}` | {source} | {key_cell} |")
    lines.append("")

    # Failed tests section
    failed = [r for r in results if r["outcome"] == "failed"]
    if failed:
        lines.append("## Failed Tests")
        lines.append("")
        lines.append("| Test | Error |")
        lines.append("|------|-------|")
        for r in failed:
            nodeid = _escape_md(_short_nodeid(r["nodeid"]))
            error = _escape_md(r["error_msg"][:200])
            lines.append(f"| `{nodeid}` | {error} |")
        lines.append("")

    # Skipped tests section
    skipped = [r for r in results if r["outcome"] == "skipped"]
    if skipped:
        lines.append("## Skipped Tests")
        lines.append("")
        lines.append("| Test | Reason / Action |")
        lines.append("|------|-----------------|")
        for r in skipped:
            nodeid = _escape_md(_short_nodeid(r["nodeid"]))
            raw_reason = r["skip_reason"] or "No reason given"
            # Translate "<X>_API_KEY not set" into an actionable instruction
            # so the report tells the user exactly what to fix in .env.test.
            reason = _escape_md(_format_skip_reason(raw_reason))
            lines.append(f"| `{nodeid}` | {reason} |")
        lines.append("")

    # Module group overview table
    lines.append("## Results by Module")
    lines.append("")
    lines.append("| Module | Test Model | Passed | Failed | Skipped | XFailed | Total | Duration |")
    lines.append("|--------|------------|--------|--------|---------|---------|-------|----------|")

    # Build group stats - ordered by _MODULE_GROUPS definition
    all_group_keys = list(_MODULE_GROUPS.keys())
    # Add "Other" if there are ungrouped tests
    if any(r["group"] == "Other" for r in results):
        all_group_keys.append("Other")

    for group_key in all_group_keys:
        group_results = [r for r in results if r["group"] == group_key]
        if not group_results:
            continue

        label = _MODULE_GROUPS[group_key]["label"] if group_key in _MODULE_GROUPS else "Other"
        model = test_models.get(group_key, "-")
        model_cell = f"`{model}`" if model != "-" else "-"
        g_passed = sum(1 for r in group_results if r["outcome"] == "passed")
        g_failed = sum(1 for r in group_results if r["outcome"] == "failed")
        g_skipped = sum(1 for r in group_results if r["outcome"] == "skipped")
        g_xfailed = sum(1 for r in group_results if r["outcome"] == "xfailed")
        g_total = len(group_results)
        g_duration = sum(r["duration"] for r in group_results)

        # Mark failed groups
        status_marker = " **!!**" if g_failed > 0 else ""
        lines.append(
            f"| **{label}**{status_marker} | {model_cell} | {g_passed} | {g_failed} | "
            f"{g_skipped} | {g_xfailed} | {g_total} | {_format_duration(g_duration)} |"
        )

    lines.append("")

    # Detailed results by module group, then by category
    lines.append("## Detailed Results")
    lines.append("")

    categories = {"unit": "Unit Tests", "integration": "Integration Tests", "local": "Local Server Tests"}

    for cat_key, cat_label in categories.items():
        cat_results = [r for r in results if r["category"] == cat_key]
        if not cat_results:
            continue

        cat_passed = sum(1 for r in cat_results if r["outcome"] == "passed")
        cat_failed = sum(1 for r in cat_results if r["outcome"] == "failed")
        cat_skipped = sum(1 for r in cat_results if r["outcome"] == "skipped")
        cat_xfailed = sum(1 for r in cat_results if r["outcome"] == "xfailed")

        parts = []
        if cat_passed:
            parts.append(f"{cat_passed} passed")
        if cat_failed:
            parts.append(f"{cat_failed} failed")
        if cat_skipped:
            parts.append(f"{cat_skipped} skipped")
        if cat_xfailed:
            parts.append(f"{cat_xfailed} xfailed")

        lines.append(f"### {cat_label} ({', '.join(parts)})")
        lines.append("")

        # Sub-group by module group within this category
        for group_key in all_group_keys:
            group_info = _MODULE_GROUPS.get(group_key, {"label": "Other"})
            group_cat_results = [r for r in cat_results if r["group"] == group_key]
            if not group_cat_results:
                continue

            gp = sum(1 for r in group_cat_results if r["outcome"] == "passed")
            gf = sum(1 for r in group_cat_results if r["outcome"] == "failed")
            gs = sum(1 for r in group_cat_results if r["outcome"] == "skipped")
            gx = sum(1 for r in group_cat_results if r["outcome"] == "xfailed")
            g_dur = sum(r["duration"] for r in group_cat_results)

            sub_parts = []
            if gp:
                sub_parts.append(f"{gp} passed")
            if gf:
                sub_parts.append(f"{gf} failed")
            if gs:
                sub_parts.append(f"{gs} skipped")
            if gx:
                sub_parts.append(f"{gx} xfailed")

            model_suffix = ""
            group_model = test_models.get(group_key)
            if group_model:
                model_suffix = f" | Model: `{group_model}`"

            lines.append(
                f"#### {group_info['label']} ({', '.join(sub_parts)}) - {_format_duration(g_dur)}{model_suffix}"
            )
            lines.append("")

            has_details = any(r["skip_reason"] or r["error_msg"] for r in group_cat_results)

            if has_details:
                lines.append("| Test | Status | Duration | Detail |")
                lines.append("|------|--------|----------|--------|")
            else:
                lines.append("| Test | Status | Duration |")
                lines.append("|------|--------|----------|")

            for r in group_cat_results:
                nodeid = _escape_md(_short_nodeid(r["nodeid"]))
                status = r["outcome"].upper()
                duration = _format_duration(r["duration"]) if r["outcome"] != "skipped" else "-"
                detail = _escape_md(r["skip_reason"] or r["error_msg"])

                if has_details:
                    lines.append(f"| `{nodeid}` | {status} | {duration} | {detail} |")
                else:
                    lines.append(f"| `{nodeid}` | {status} | {duration} |")

            lines.append("")

    # Write report
    report_content = "\n".join(lines)
    report_path.write_text(report_content, encoding="utf-8")

    # Copy to latest.md
    shutil.copy2(report_path, latest_path)

    # Print path in terminal
    terminalreporter.write_sep("=", "Markdown Test Report")
    terminalreporter.write_line(f"Report: {report_path}")
    terminalreporter.write_line(f"Latest: {latest_path}")
