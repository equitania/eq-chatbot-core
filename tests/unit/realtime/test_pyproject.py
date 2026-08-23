"""CON-12: Static check that pyproject.toml declares the [realtime] extra with correct websockets version bounds."""

import re
import tomllib
from pathlib import Path

import pytest


@pytest.mark.unit
def test_realtime_extra_declared() -> None:
    """CON-12: the [realtime] extra bounds websockets on both sides.

    The bounds are asserted by intent, not as a literal string: floors are raised
    to the current release as a matter of policy, and a test that pins the exact
    floor blocks its own upgrade. What must hold is that the floor never drops
    back to a version whose socket API this codebase no longer handles, and that
    the ceiling still fences off the next major.
    """
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

    floor = re.search(r">=\s*([0-9]+(?:\.[0-9]+)*)", dep_str)
    assert floor, f"No lower bound at all: {dep_str}"
    floor_parts = tuple(int(part) for part in floor.group(1).split("."))
    assert floor_parts >= (13, 0), f"Lower bound fell below 13.0: {dep_str}"
    assert "<18.0" in dep_str, f"Missing <18.0 upper bound: {dep_str}"


@pytest.mark.unit
def test_dev_extra_has_pytest_asyncio() -> None:
    """Verify pytest-asyncio is in [dev] extra — required for all async realtime unit tests."""
    pyproject_path = Path(__file__).parent.parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    dev_deps = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    asyncio_deps = [d for d in dev_deps if "pytest-asyncio" in d]
    assert len(asyncio_deps) >= 1, "pytest-asyncio not found in [dev] extra"
