"""Milestone 1 — the engine-neutral schema and Ruleset model.

The real `ruleset/` folder at the repo root is the canonical schema reference,
so these tests load it directly. Tests that need a deliberately-broken file
write a throwaway Ruleset under tmp_path.
"""

from pathlib import Path

import pytest

from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.schema import MoveDef

_REPO_ROOT = Path(__file__).resolve().parent.parent
# The controlled sample Ruleset — the canonical schema reference for tests.
# It lives in tests/fixtures (not the repo-root ruleset/) so that seeding real
# Dreamstone data into ruleset/ in Milestone 2 cannot disturb these assertions.
_RULESET_DIR = _REPO_ROOT / "tests" / "fixtures" / "sample_ruleset"


def test_loads_real_ruleset() -> None:
    ruleset = Ruleset.load(_RULESET_DIR)
    assert ruleset.meta["base_version"] == "1.11.2"
    assert "goodra" in ruleset.species
    assert "excalibur" in ruleset.moves


def test_goodra_has_only_overridden_scalar_fields() -> None:
    goodra = Ruleset.load(_RULESET_DIR).species["goodra"]
    assert goodra.name == "Goodra"
    assert goodra.types == ("Water", "Dragon")
    assert goodra.abilities.primary == "Poison Heal"
    assert goodra.abilities.hidden == "Sap Sipper"
    # secondary was never overridden, so it stays absent
    assert goodra.abilities.secondary is None
    # only the overridden stat is present; nothing else
    assert goodra.stats == {"spe": 80}


def test_goodra_learnset_is_ordered_and_whole() -> None:
    goodra = Ruleset.load(_RULESET_DIR).species["goodra"]
    assert goodra.learnset is not None
    levels = [(m.level, m.move) for m in goodra.learnset]
    assert levels == [
        (1, "Dragon Breath"),
        (30, "Liquidation"),
        (45, "Excalibur"),
    ]


def test_excalibur_resolves_to_ruleset_owned_move() -> None:
    ruleset = Ruleset.load(_RULESET_DIR)
    move = ruleset.owned_move("Excalibur")
    assert isinstance(move, MoveDef)
    assert move.chrooked_id == "excalibur"
    assert move.type == "Steel"
    assert move.category == "physical"
    assert move.power == 90


def test_type_chart_override_present() -> None:
    ruleset = Ruleset.load(_RULESET_DIR)
    entry = next(
        e for e in ruleset.type_chart
        if e.attacker == "Flying" and e.defender == "Ice"
    )
    assert entry.multiplier == 0.5


def test_unknown_species_field_raises_clear_error(tmp_path: Path) -> None:
    bad = tmp_path / "ruleset"
    (bad / "species").mkdir(parents=True)
    (bad / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (bad / "species" / "bad.yaml").write_text(
        "name: Bad\nchrooked_id: bad\ntyps: [Fire]\n"  # 'typs' is a typo
    )

    with pytest.raises(ValueError) as excinfo:
        Ruleset.load(bad)
    message = str(excinfo.value)
    assert "typs" in message
    assert "bad.yaml" in message
