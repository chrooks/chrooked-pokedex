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


def test_fully_evolved_carries_from_base_and_defaults_false() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    snapshot = {
        "version": "1.11.2",
        "species": {
            # Carries the flag explicitly (final form).
            "goodra": {**_SNAPSHOT["species"]["goodra"], "fully_evolved": True},
            # Omits the flag (older snapshot shape) — must default to False.
            "pikachu": _SNAPSHOT["species"]["pikachu"],
        },
        "moves": {},
        "abilities": {},
        "type_chart": [],
    }
    entries = dexmod.build_dex(snapshot, ruleset)
    assert _entry(entries, "goodra")["fully_evolved"] is True
    assert _entry(entries, "pikachu")["fully_evolved"] is False


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


# --- Abilities merge (slice 1) -------------------------------------------- #
#
# `build_abilities` brings abilities to species parity: full base ⊕ Ruleset,
# overridden flagged with a base→now diff, base-only unflagged, Ruleset-created
# surfaced. The sample Ruleset owns one ability (`poisonheal`); the synthetic
# base below makes it an override, leaves `overgrow` base-only, and an extra
# Ruleset-only id below proves the created path.

_ABILITY_SNAPSHOT = {
    "version": "1.11.2",
    "species": {},
    "moves": {},
    "type_chart": [],
    "abilities": {
        "overgrow": {
            "chrooked_id": "overgrow",
            "name": "Overgrow",
            "description": "Ups Grass moves in a pinch.",
            "aka": {"pokeemerald": "ABILITY_OVERGROW"},
        },
        "poisonheal": {
            "chrooked_id": "poisonheal",
            "name": "Poison Heal",
            "description": "A base description the Ruleset replaces.",
            "aka": {"pokeemerald": "ABILITY_POISON_HEAL"},
        },
    },
}


def test_abilities_covers_full_base_not_just_ruleset() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    entries = dexmod.build_abilities(_ABILITY_SNAPSHOT, ruleset)
    ids = {e["chrooked_id"] for e in entries}
    # Both base abilities present even though the Ruleset only touches one.
    assert {"overgrow", "poisonheal"} <= ids
    # Sorted by display name.
    names = [e["name"] for e in entries]
    assert names == sorted(names)


def test_base_only_ability_is_unflagged_with_empty_base() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    overgrow = _entry(dexmod.build_abilities(_ABILITY_SNAPSHOT, ruleset), "overgrow")
    assert overgrow["overridden_fields"] == []
    assert overgrow["base"] == {}
    assert overgrow["name"] == "Overgrow"
    assert overgrow["description"] == "Ups Grass moves in a pinch."


def test_overridden_ability_flags_changed_fields_with_base_diff() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    poisonheal = _entry(dexmod.build_abilities(_ABILITY_SNAPSHOT, ruleset), "poisonheal")
    # The Ruleset def's description differs from base -> flagged with base→now.
    assert "description" in poisonheal["overridden_fields"]
    assert poisonheal["base"]["description"] == "A base description the Ruleset replaces."
    assert poisonheal["description"] == (
        "Heals each turn instead of taking poison damage."
    )
    # Name is identical to base, so it is NOT flagged and carries no base value.
    assert "name" not in poisonheal["overridden_fields"]
    assert "name" not in poisonheal["base"]


def test_created_ability_is_flagged_with_no_base() -> None:
    # A Ruleset id with no base match (here: poisonheal absent from base) is a
    # created ability — flagged for the fields it provides, with empty base.
    ruleset = Ruleset.load(_SAMPLE)
    base_without_poisonheal = {
        **_ABILITY_SNAPSHOT,
        "abilities": {"overgrow": _ABILITY_SNAPSHOT["abilities"]["overgrow"]},
    }
    entries = dexmod.build_abilities(base_without_poisonheal, ruleset)
    poisonheal = _entry(entries, "poisonheal")
    assert poisonheal["base"] == {}
    assert set(poisonheal["overridden_fields"]) == {"name", "description"}
    assert poisonheal["name"] == "Poison Heal"
