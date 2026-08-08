"""Status conditions as a first-class Ruleset kind.

Statuses are Ruleset-owned outright — there is no base snapshot to diff against,
because upstream has no status concept. These tests pin the two things that matter:
the real `ruleset/status/` folder loads, and the strict-key boundary still rejects
a typo instead of silently dropping it.
"""

from pathlib import Path

import pytest

from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.loader import load_status

RULESET_DIR = Path(__file__).resolve().parents[1] / "ruleset"

EXPECTED_IDS = {
    "frostbite", "burn", "paralysis", "poison", "badlypoisoned", "sleep",
}


@pytest.mark.unit
def test_real_ruleset_loads_every_status() -> None:
    ruleset = Ruleset.load(RULESET_DIR)
    assert set(ruleset.statuses) == EXPECTED_IDS

    frostbite = ruleset.statuses["frostbite"]
    assert frostbite.name == "Frostbite"
    # The reskin decision lives in data: the engine keeps its FROZEN symbol.
    assert frostbite.aka["rejuv"] == "FROZEN"
    assert frostbite.effects


@pytest.mark.unit
def test_freeze_is_gone() -> None:
    """Frostbite replaced freeze outright — no status record should resurrect it."""
    ruleset = Ruleset.load(RULESET_DIR)
    assert "freeze" not in ruleset.statuses


@pytest.mark.unit
def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bogus.yaml"
    path.write_text(
        "name: Bogus\nchrooked_id: bogus\ncolour: blue\n", encoding="utf-8"
    )
    with pytest.raises(ValueError) as excinfo:
        load_status(path)
    assert "colour" in str(excinfo.value)


@pytest.mark.unit
def test_missing_required_field_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "nameless.yaml"
    path.write_text("chrooked_id: nameless\n", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        load_status(path)
    assert "name" in str(excinfo.value)
