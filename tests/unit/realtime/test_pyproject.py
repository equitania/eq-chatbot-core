"""CON-12: Static check that pyproject.toml declares the [realtime] extra with correct websockets version bounds."""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib requires Python 3.11+")

from pathlib import Path  # noqa: E402

import tomllib  # noqa: E402


@pytest.mark.unit
def test_realtime_extra_declared() -> None:
    """CON-12: websockets>=13.0,<17.0 declared in pyproject.toml [realtime] extra."""
    pyproject_path = Path(__file__).parent.parent.parent.parent / "pyproject.toml"
    assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    optional_deps = data.get("project", {}).get("optional-dependencies", {})
    assert "realtime" in optional_deps, "Missing [realtime] extra in pyproject.toml"
    realtime_deps = optional_deps["realtime"]
    websockets_deps = [d for d in realtime_deps if d.startswith("websockets")]
    assert len(websockets_deps) == 1, f"Expected 1 websockets dep, got: {websockets_deps}"
    dep_str = websockets_deps[0]
    assert ">=13.0" in dep_str, f"Missing >=13.0 lower bound: {dep_str}"
    assert "<17.0" in dep_str, f"Missing <17.0 upper bound: {dep_str}"


@pytest.mark.unit
def test_dev_extra_has_pytest_asyncio() -> None:
    """Verify pytest-asyncio is in [dev] extra — required for all async realtime unit tests."""
    pyproject_path = Path(__file__).parent.parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    dev_deps = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    asyncio_deps = [d for d in dev_deps if "pytest-asyncio" in d]
    assert len(asyncio_deps) >= 1, "pytest-asyncio not found in [dev] extra"
