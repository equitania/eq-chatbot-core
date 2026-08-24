"""Static check that the [docs] extra states the openpyxl floor itself.

Nothing else in the chain does. `markitdown[xlsx]` asks for a bare `openpyxl` and
a bare `pandas`; the floor `openpyxl>=3.1.5` lives only in pandas' own `excel`
extra, which markitdown does not request. So a resolver may leave an older
openpyxl in place - and Odoo pins exactly 3.1.2 - after which every `.xlsx`
conversion dies with "Pandas requires version '3.1.5' or newer of 'openpyxl'",
reaching the caller as "no text could be extracted".

Guarded by a test because the declaration looks redundant: markitdown already
brings openpyxl in, so the line invites deletion during a tidy-up. It is not
redundant, it is the only place the version is stated.
"""

import tomllib
from pathlib import Path

import pytest

PYPROJECT = Path(__file__).parent.parent.parent / "pyproject.toml"
# The version pandas declares for its Excel support. Raising this is fine;
# dropping below it reopens the defect.
REQUIRED_FLOOR = (3, 1, 5)


def _docs_extra() -> list[str]:
    with open(PYPROJECT, "rb") as handle:
        data = tomllib.load(handle)
    extras = data.get("project", {}).get("optional-dependencies", {})
    assert "docs" in extras, "Missing [docs] extra in pyproject.toml"
    return extras["docs"]


@pytest.mark.unit
def test_docs_extra_declares_openpyxl() -> None:
    entries = [d for d in _docs_extra() if d.replace("-", "_").startswith("openpyxl")]
    assert entries, (
        "[docs] must declare openpyxl itself - markitdown[xlsx] requires it without a "
        "version, and the >=3.1.5 floor pandas needs is stated nowhere else in the chain"
    )
    assert len(entries) == 1, f"Expected exactly one openpyxl entry, got: {entries}"


@pytest.mark.unit
def test_the_floor_is_high_enough_for_pandas() -> None:
    """Asserted by intent: raising the floor is fine, dropping under it is not."""
    entry = next(d for d in _docs_extra() if d.startswith("openpyxl"))
    floor_text = entry.split(">=", 1)[1].split(",", 1)[0].strip()
    floor = tuple(int(part) for part in floor_text.split("."))

    assert floor >= REQUIRED_FLOOR, (
        f"openpyxl floor {floor_text} is below the {'.'.join(map(str, REQUIRED_FLOOR))} "
        "that pandas requires for .xlsx - spreadsheets would fail at conversion time"
    )


@pytest.mark.unit
def test_the_extra_still_fences_off_the_next_major() -> None:
    entry = next(d for d in _docs_extra() if d.startswith("openpyxl"))

    assert "<4" in entry, f"openpyxl entry should cap the next major: {entry}"
