"""Milestone 1 — the read-only Ruleset-owned collections.

`web/collections` serializes the four non-dex kinds (moves, abilities,
type-chart, behaviors) into JSON-able lists for the read-only tabs. These
tests run against the in-repo `sample_ruleset` fixture so they stay hermetic.
"""

from __future__ import annotations

from pathlib import Path

from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.web import collections as col

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SAMPLE = _REPO_ROOT / "tests" / "fixtures" / "sample_ruleset"


def _ruleset() -> Ruleset:
    return Ruleset.load(_SAMPLE)


def test_moves_surface_full_definition() -> None:
    moves = col.build_moves(_ruleset())
    excalibur = next(m for m in moves if m["chrooked_id"] == "excalibur")
    assert excalibur["name"] == "Excalibur"
    assert excalibur["type"] == "Steel"
    assert excalibur["category"] == "physical"
    assert excalibur["power"] == 90
    assert excalibur["accuracy"] == 100
    assert excalibur["pp"] == 10
    # behavior-carrying fields are surfaced even when defaulted
    assert "effect" in excalibur
    assert "flags" in excalibur
    assert isinstance(excalibur["additional_effects"], list)


def test_moves_are_sorted_by_name() -> None:
    moves = col.build_moves(_ruleset())
    names = [m["name"] for m in moves]
    assert names == sorted(names)


def test_abilities_surface_name_and_description() -> None:
    abilities = col.build_abilities(_ruleset())
    poison_heal = next(a for a in abilities if a["chrooked_id"] == "poisonheal")
    assert poison_heal["name"] == "Poison Heal"
    assert "Heals" in poison_heal["description"]


def test_type_chart_surfaces_overrides() -> None:
    chart = col.build_type_chart(_ruleset())
    assert {"attacker": "Flying", "defender": "Ice", "multiplier": 0.5} in chart


def test_behaviors_surface_effects_and_test_cases() -> None:
    behaviors = col.build_behaviors(_ruleset())
    excalibur = next(b for b in behaviors if b["chrooked_id"] == "excalibur")
    assert excalibur["applies_to"] == "move"
    assert excalibur["effects"][0]["trigger"] == "damage-calc"
    assert (
        excalibur["test_cases"][0]["given"]
        == "Excalibur is used on a Dragon-type target"
    )
    assert excalibur["engine_hints"]["pokeemerald"] == "see MOVE_EXCALIBUR effect script"


def test_collections_are_empty_lists_when_kind_absent() -> None:
    # A Ruleset folder with no abilities/ dir yields an empty list, never an error.
    empty = Ruleset()
    assert col.build_moves(empty) == []
    assert col.build_abilities(empty) == []
    assert col.build_type_chart(empty) == []
    assert col.build_behaviors(empty) == []
