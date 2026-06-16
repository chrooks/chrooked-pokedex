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


# --------------------------------------------------------------------------- #
# Moves merge (slice 2) — `build_moves` brings moves to species parity, exactly
# like `build_abilities`: full base ⊕ Ruleset, overridden flagged with a base→now
# diff, base-only unflagged, Ruleset-created surfaced. The synthetic base below
# makes the sample Ruleset's owned move (`excalibur`) a CREATED move (no base),
# and adds a second base move (`tackle`) the Ruleset overrides, plus a base-only
# move (`ember`) the Ruleset never touches.

_MOVE_SNAPSHOT = {
    "version": "1.11.2",
    "species": {},
    "abilities": {},
    "type_chart": [],
    "moves": {
        "ember": {
            "chrooked_id": "ember",
            "name": "Ember",
            "aka": {"pokeemerald": "MOVE_EMBER"},
            "type": "Fire",
            "category": "special",
            "power": 40,
            "accuracy": 100,
            "pp": 25,
            "description": "A weak fire attack.",
            "effect": "hit",
            "argument": None,
            "additional_effects": [{"effect": "burn", "chance": 10}],
            "flags": [],
            "priority": 0,
            "target": "selected",
        },
        # The sample Ruleset owns `excalibur` (Steel, power 90). Put a DIFFERENT
        # base entry under that id so the merge has a real base→now diff.
        "excalibur": {
            "chrooked_id": "excalibur",
            "name": "Excalibur",
            "aka": {"pokeemerald": "MOVE_EXCALIBUR"},
            "type": "Normal",
            "category": "physical",
            "power": 50,
            "accuracy": 95,
            "pp": 15,
            "description": "A base blade strike.",
            "effect": "hit",
            "argument": None,
            "additional_effects": [],
            "flags": [],
            "priority": 0,
            "target": "selected",
        },
    },
}


def test_moves_covers_full_base_not_just_ruleset() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    entries = dexmod.build_moves(_MOVE_SNAPSHOT, ruleset)
    ids = {e["chrooked_id"] for e in entries}
    # Both base moves present even though the Ruleset only touches one.
    assert {"ember", "excalibur"} <= ids
    # Sorted by display name.
    names = [e["name"] for e in entries]
    assert names == sorted(names)


def test_base_only_move_is_unflagged_with_empty_base() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    ember = _entry(dexmod.build_moves(_MOVE_SNAPSHOT, ruleset), "ember")
    assert ember["overridden_fields"] == []
    assert ember["base"] == {}
    assert ember["name"] == "Ember"
    assert ember["type"] == "Fire"
    # the full MoveEntry contract fields ride through
    assert ember["additional_effects"] == [{"effect": "burn", "chance": 10}]


def test_overridden_move_flags_changed_fields_with_base_diff() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    excalibur = _entry(dexmod.build_moves(_MOVE_SNAPSHOT, ruleset), "excalibur")
    # The Ruleset def (Steel/90/100) differs from base (Normal/50/95) -> flagged
    # with base→now per field.
    assert "type" in excalibur["overridden_fields"]
    assert "power" in excalibur["overridden_fields"]
    assert excalibur["type"] == "Steel"
    assert excalibur["power"] == 90
    assert excalibur["base"]["type"] == "Normal"
    assert excalibur["base"]["power"] == 50
    # name is identical to base -> NOT flagged, no base value
    assert "name" not in excalibur["overridden_fields"]
    assert "name" not in excalibur["base"]


def test_created_move_is_flagged_with_no_base() -> None:
    # A Ruleset id with no base match (excalibur absent from base) is a created
    # move — flagged for the fields it provides, with empty base.
    ruleset = Ruleset.load(_SAMPLE)
    base_without_excalibur = {
        **_MOVE_SNAPSHOT,
        "moves": {"ember": _MOVE_SNAPSHOT["moves"]["ember"]},
    }
    entries = dexmod.build_moves(base_without_excalibur, ruleset)
    excalibur = _entry(entries, "excalibur")
    assert excalibur["base"] == {}
    # required + set fields are provided; defaults (effect=hit, target=selected,
    # priority=0, no additional effects/flags/argument) are NOT claimed.
    provided = set(excalibur["overridden_fields"])
    assert {"name", "type", "category", "power", "accuracy", "pp"} <= provided
    assert "effect" not in provided  # left at the schema default ('hit')
    assert "target" not in provided  # left at the schema default ('selected')
    assert excalibur["name"] == "Excalibur"


# --------------------------------------------------------------------------- #
# Type-chart merge (slice 3) — `build_type_chart` brings the type chart to canon
# parity per CELL: the FULL base matrix ⊕ Ruleset overrides. A cell the Ruleset
# touches is flagged overridden with the pre-override base_multiplier; a base-only
# cell is unflagged with base_multiplier=None. The sample Ruleset owns one cell
# (Flying→Ice 0.5); the synthetic base below makes it a real override (base 2.0)
# and leaves Fire→Grass as a base-only cell.

def _cell(cells: list[dict], attacker: str, defender: str) -> dict:
    return next(
        c for c in cells if c["attacker"] == attacker and c["defender"] == defender
    )


_TYPE_CHART_SNAPSHOT = {
    "version": "1.11.2",
    "species": {},
    "abilities": {},
    "moves": {},
    "type_chart": [
        {"attacker": "Flying", "defender": "Ice", "multiplier": 2.0},
        {"attacker": "Fire", "defender": "Grass", "multiplier": 2.0},
        {"attacker": "Water", "defender": "Fire", "multiplier": 2.0},
    ],
}


def test_type_chart_emits_full_grid_sorted_by_pair() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    cells = dexmod.build_type_chart(_TYPE_CHART_SNAPSHOT, ruleset)
    # every base cell shows through (3 here), none dropped, none invented.
    assert len(cells) == 3
    pairs = [(c["attacker"], c["defender"]) for c in cells]
    assert pairs == sorted(pairs)  # deterministic order by (attacker, defender)


def test_base_only_type_cell_is_unflagged_with_null_base_multiplier() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    cells = dexmod.build_type_chart(_TYPE_CHART_SNAPSHOT, ruleset)
    fire_grass = _cell(cells, "Fire", "Grass")
    assert fire_grass["overridden"] is False
    assert fire_grass["multiplier"] == 2.0  # the base value passes through
    assert fire_grass["base_multiplier"] is None


def test_overridden_type_cell_carries_base_multiplier() -> None:
    ruleset = Ruleset.load(_SAMPLE)
    cells = dexmod.build_type_chart(_TYPE_CHART_SNAPSHOT, ruleset)
    flying_ice = _cell(cells, "Flying", "Ice")
    assert flying_ice["overridden"] is True
    assert flying_ice["multiplier"] == 0.5  # the Ruleset override wins
    assert flying_ice["base_multiplier"] == 2.0  # the base it replaced


def test_type_chart_override_with_no_base_cell_is_created() -> None:
    # A Ruleset override referencing a pair absent from the base matrix surfaces as
    # a created cell: overridden=True, base_multiplier=None. (Shouldn't occur with
    # a full base matrix, but the merge must not drop it.)
    ruleset = Ruleset.load(_SAMPLE)
    base_without_flying_ice = {
        **_TYPE_CHART_SNAPSHOT,
        "type_chart": [
            c
            for c in _TYPE_CHART_SNAPSHOT["type_chart"]
            if not (c["attacker"] == "Flying" and c["defender"] == "Ice")
        ],
    }
    cells = dexmod.build_type_chart(base_without_flying_ice, ruleset)
    flying_ice = _cell(cells, "Flying", "Ice")
    assert flying_ice["overridden"] is True
    assert flying_ice["multiplier"] == 0.5
    assert flying_ice["base_multiplier"] is None


def test_type_chart_multipliers_are_always_floats() -> None:
    # fix2: a base cell stored as an int (or an override loaded as int from YAML)
    # must surface as a float so multiplier/base_multiplier are JSON-consistent.
    ruleset = Ruleset.load(_SAMPLE)
    # Flying→Ice base stored as int 2 here; the Ruleset override is 0.5.
    int_base_snapshot = {
        **_TYPE_CHART_SNAPSHOT,
        "type_chart": [
            {"attacker": "Flying", "defender": "Ice", "multiplier": 2},  # int base
            {"attacker": "Fire", "defender": "Grass", "multiplier": 2},  # int base
        ],
    }
    cells = dexmod.build_type_chart(int_base_snapshot, ruleset)
    # base-only cell: multiplier coerced to float, base_multiplier stays None.
    fire_grass = _cell(cells, "Fire", "Grass")
    assert isinstance(fire_grass["multiplier"], float)
    assert fire_grass["base_multiplier"] is None
    # overridden cell: both multiplier and base_multiplier are floats.
    flying_ice = _cell(cells, "Flying", "Ice")
    assert isinstance(flying_ice["multiplier"], float)
    assert isinstance(flying_ice["base_multiplier"], float)
    assert flying_ice["base_multiplier"] == 2.0
