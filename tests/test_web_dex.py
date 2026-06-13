"""Milestone 0/1 — the base ⊕ Ruleset merge that powers the Canon dex.

`web/dex.build_dex` overlays each `SpeciesOverride` onto the base snapshot and
reports which top-level fields the Ruleset changed. These tests merge the
in-repo `sample_ruleset` fixture onto a tiny synthetic base so they stay
hermetic and fast.
"""

from __future__ import annotations

from pathlib import Path

from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.web import dex as dexmod

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SAMPLE = _REPO_ROOT / "tests" / "fixtures" / "sample_ruleset"

# Base values for the two species the assertions touch. Goodra is base mono-Dragon
# with vanilla abilities/stats; Pikachu is untouched by the sample Ruleset.
_SNAPSHOT = {
    "version": "1.11.2",
    "species": {
        "goodra": {
            "dex": 706,
            "chrooked_id": "goodra",
            "name": "Goodra",
            "types": ["Dragon"],
            "abilities": {"primary": "Sap Sipper", "secondary": None, "hidden": "Gooey"},
            "stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60},
            "learnset": [{"level": 1, "move": "Tackle"}],
        },
        "pikachu": {
            "dex": 25,
            "chrooked_id": "pikachu",
            "name": "Pikachu",
            "types": ["Electric"],
            "abilities": {"primary": "Static", "secondary": None, "hidden": "Lightning Rod"},
            "stats": {"hp": 35, "atk": 55, "def": 40, "spa": 50, "spd": 50, "spe": 90},
            "learnset": [{"level": 1, "move": "Thunder Shock"}],
        },
    },
    "moves": {},
    "abilities": {},
    "type_chart": [],
}


def _entry(entries: list[dict], cid: str) -> dict:
    return next(e for e in entries if e["chrooked_id"] == cid)


def test_overridden_species_merges_ruleset_onto_base() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    goodra = _entry(dexmod.build_dex(_SNAPSHOT, ruleset), "goodra")

    # types is a whole-list override -> replaced
    assert goodra["types"] == ["Water", "Dragon"]
    # abilities is a partial override -> changed slots win, untouched slots persist
    assert goodra["abilities"]["primary"] == "Poison Heal"
    assert goodra["abilities"]["hidden"] == "Sap Sipper"
    assert goodra["abilities"]["secondary"] is None
    # stats is partial -> spe overridden, the rest from base
    assert goodra["stats"]["spe"] == 80
    assert goodra["stats"]["hp"] == 90
    # learnset is whole-list -> replaced, cites Excalibur
    assert [m["move"] for m in goodra["learnset"]] == [
        "Dragon Breath",
        "Liquidation",
        "Excalibur",
    ]
    assert goodra["evolution"]["from"] == "Sliggoo"
    assert goodra["dex"] == 706


def test_overridden_species_carries_base_values_for_the_diff() -> None:
    # The detail ledger's diff toggle shows base -> now, so every overridden
    # field's pre-override value rides along under `base`.
    ruleset = Ruleset.load(_SAMPLE)
    goodra = _entry(dexmod.build_dex(_SNAPSHOT, ruleset), "goodra")
    assert goodra["base"]["types"] == ["Dragon"]
    assert goodra["base"]["stats"]["spe"] == 60
    assert goodra["base"]["abilities"]["primary"] == "Sap Sipper"
    assert [m["move"] for m in goodra["base"]["learnset"]] == ["Tackle"]


def test_untouched_species_has_empty_base() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    pikachu = _entry(dexmod.build_dex(_SNAPSHOT, ruleset), "pikachu")
    assert pikachu["base"] == {}


def test_overridden_fields_lists_every_changed_kind() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    goodra = _entry(dexmod.build_dex(_SNAPSHOT, ruleset), "goodra")
    assert set(goodra["overridden_fields"]) == {
        "types",
        "abilities",
        "stats",
        "learnset",
        "evolution",
    }


def test_untouched_species_is_pure_base_with_no_flags() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    pikachu = _entry(dexmod.build_dex(_SNAPSHOT, ruleset), "pikachu")
    assert pikachu["overridden_fields"] == []
    assert pikachu["types"] == ["Electric"]
    assert pikachu["stats"]["spe"] == 90
    assert pikachu["abilities"]["primary"] == "Static"


def test_dex_covers_every_base_species() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    entries = dexmod.build_dex(_SNAPSHOT, ruleset)
    assert {e["chrooked_id"] for e in entries} == {"goodra", "pikachu"}
