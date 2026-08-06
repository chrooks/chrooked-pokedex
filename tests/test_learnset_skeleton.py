"""Unit tests for the deterministic learnset slot skeleton.

The skeleton is the FULL-mode placement authority: code fixes levels, band
windows, and per-slot candidates; the model only picks. These tests pin the
properties that make bad drafts impossible:

- band gates: an attacking rung only offers moves inside its band's BP range;
- fuel: an -ate species is forced Normal fuel even when the granted type is
  an own type (the Sylveon case); flag boosters reserve flagged moves;
- flavor ladders come from ``flavor_types``, never from weakness math;
- the singleton-collision guard keeps two slots from demanding one lone move;
- validate_against_skeleton rejects a draft missing a slot or off-candidate.
"""
from __future__ import annotations

from typing import Any

import pytest

from chrooked_pokedex.web import learnset_skeleton as sk

pytestmark = pytest.mark.unit


def _mv(
    name: str,
    type_: str,
    power: int | None,
    category: str = "Special",
    **extra: Any,
) -> dict[str, Any]:
    row = {
        "move": name, "type": type_, "category": category, "power": power,
        "accuracy": 100, "effect": "hit", "flags": [], "secondary": False,
        "custom": False,
    }
    row.update(extra)
    return row


def _pool() -> list[dict[str, Any]]:
    """A pool wide enough to fill every Dragon band plus fuel and status."""
    return [
        _mv("Twister", "Dragon", 40),
        _mv("Dragon Breath", "Dragon", 60),
        _mv("Dragon Pulse", "Dragon", 85),
        _mv("Clanging Scales", "Dragon", 110),
        _mv("Draco Meteor", "Dragon", 130),
        _mv("Water Gun", "Water", 40),
        _mv("Brine", "Water", 65),
        _mv("Surf", "Water", 90),
        _mv("Echoed Voice", "Normal", 40, flags=["sound"]),
        _mv("Hyper Voice", "Normal", 90, flags=["sound"]),
        _mv("Slam", "Normal", 80, category="Physical"),
        _mv("Protect", "Normal", None, category="Status"),
        _mv("Toxic", "Poison", None, category="Status"),
        _mv("Amnesia", "Psychic", None, category="Status"),
        _mv("Rain Dance", "Water", None, category="Status"),
    ]


def _entry(**over: Any) -> dict[str, Any]:
    entry = {
        "chrooked_id": "testmon",
        "name": "Testmon",
        "types": ["Dragon"],
        "stats": {"hp": 90, "atk": 60, "def": 70, "spa": 110, "spd": 100, "spe": 60},
        "abilities": {"primary": "Overgrow", "secondary": None, "hidden": None},
        "learnset": [],
        "evolution": {"from": "testling", "method": {}},
        "evolves_into": [],
    }
    entry.update(over)
    return entry


_ABILITIES = [
    {"chrooked_id": "overgrow", "name": "Overgrow", "description": "x"},
    {"chrooked_id": "pixilate", "name": "Pixilate", "description": "Normal moves become Fairy."},
    {"chrooked_id": "amplifier", "name": "Amplifier", "description": "Sound moves +30%."},
    {"chrooked_id": "steelworker", "name": "Steelworker", "description": "Boosts Steel."},
]


def test_band_rungs_only_offer_in_band_powers() -> None:
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool())
    by_power = {r["move"]: r["power"] for r in _pool()}
    bands = {b["label"]: (b["lo_power"], b["hi_power"]) for b in sk._bands()}
    for slot in skeleton["slots"]:
        if slot["role"] != "stab":
            continue
        label = slot["label"].rsplit("(", 1)[1].rstrip("BP)")
        lo, hi = bands[label]
        for cand in slot["candidates"]:
            assert lo <= by_power[cand] <= hi, f"{cand} out of band in {slot['label']}"


def test_special_bias_excludes_physical_candidates() -> None:
    """SpA 110 > Atk 60 — Slam (physical Normal) must not appear in STAB rungs."""
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool())
    for slot in skeleton["slots"]:
        if slot["role"] == "stab":
            assert "Slam" not in slot["candidates"]


def test_ate_on_own_type_still_demands_normal_fuel() -> None:
    """The Sylveon case: Pixilate on a pure Fairy-type still reserves Normal fuel."""
    entry = _entry(
        types=["Fairy"],
        abilities={"primary": "Pixilate", "secondary": None, "hidden": None},
    )
    skeleton = sk.build_skeleton(entry, _ABILITIES, _pool())
    fuel = [s for s in skeleton["slots"] if s["role"] == "fuel"]
    assert fuel, "Pixilate produced no fuel slots"
    for slot in fuel:
        types = {r["type"] for r in _pool() if r["move"] in slot["candidates"]}
        assert types == {"Normal"}


def test_sound_booster_reserves_sound_moves() -> None:
    entry = _entry(
        abilities={"primary": "Amplifier", "secondary": None, "hidden": None}
    )
    skeleton = sk.build_skeleton(entry, _ABILITIES, _pool())
    fuel = [s for s in skeleton["slots"] if s["role"] == "fuel"]
    assert fuel
    sound = {"Echoed Voice", "Hyper Voice"}
    for slot in fuel:
        assert set(slot["candidates"]) <= sound


def test_stab_grant_ability_adds_a_ladder() -> None:
    """Steelworker on a non-Steel species grows a Steel ladder (Chris's ruling)."""
    pool = _pool() + [
        _mv("Mirror Shot", "Steel", 65),
        _mv("Flash Cannon", "Steel", 80),
        _mv("Steel Beam", "Steel", 140),
    ]
    entry = _entry(
        abilities={"primary": "Steelworker", "secondary": None, "hidden": None}
    )
    skeleton = sk.build_skeleton(entry, _ABILITIES, pool)
    steel = [
        s for s in skeleton["slots"]
        if s["role"] == "stab" and "Steel" in s["label"]
    ]
    assert steel, "Steelworker granted no Steel ladder"


def test_flavor_types_grow_flavor_ladders() -> None:
    skeleton = sk.build_skeleton(_entry(flavor_types=["Water"]), _ABILITIES, _pool())
    flavor = [s for s in skeleton["slots"] if s["role"] == "flavor"]
    assert flavor
    water = {"Water Gun", "Brine", "Surf"}
    for slot in flavor:
        assert set(slot["candidates"]) <= water


def test_no_flavor_types_no_flavor_slots() -> None:
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool())
    assert not [s for s in skeleton["slots"] if s["role"] == "flavor"]


def test_validate_flags_missing_slot_and_off_candidate_rows() -> None:
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool())
    rows = [
        {"level": s["level"], "move": s["candidates"][0], "reasoning": ""}
        for s in skeleton["slots"]
    ]
    assert sk.validate_against_skeleton(rows, skeleton) == []
    # Remove one row → its slot is reported.
    errors = sk.validate_against_skeleton(rows[:-1], skeleton)
    assert errors and "expected" in errors[0]
    # A row at a level with no slot is reported.
    errors = sk.validate_against_skeleton(
        rows + [{"level": 69, "move": "Protect", "reasoning": ""}], skeleton
    )
    assert any("no slot" in e for e in errors)


def test_l0_reward_keeps_singleton_claimed_moves() -> None:
    """A singleton rung's move stays available to the L0 reward — the repeat
    rule allows one L0 plus one non-zero level of the same move, so the reward
    draft (e.g. Luster Cannon at L0 AND its lone 91-110 rung) must validate."""
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool())
    singles = {
        s["candidates"][0]
        for s in skeleton["slots"]
        if len(s["candidates"]) == 1 and s["level"] > 0
    }
    assert singles, "test needs at least one singleton slot"
    reward = next(s for s in skeleton["slots"] if s["role"] == "reward")
    assert singles <= set(reward["candidates"])
    # And a draft using the same move at L0 and its singleton level validates.
    rows = []
    for slot in skeleton["slots"]:
        pick = slot["candidates"][0]
        rows.append({"level": slot["level"], "move": pick, "reasoning": ""})
    picked_single = next(iter(singles))
    rows = [r for r in rows if r["level"] != 0]
    rows.append({"level": 0, "move": picked_single, "reasoning": ""})
    errors = [
        e for e in sk.validate_against_skeleton(rows, skeleton) if "level 0" in e
    ]
    assert errors == []


def test_singleton_claim_strikes_other_slots() -> None:
    """A lone-candidate slot's move never doubles as another slot's only fill."""
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool())
    singles = [
        s["candidates"][0]
        for s in skeleton["slots"]
        if len(s["candidates"]) == 1 and s["level"] > 0
    ]
    for slot in skeleton["slots"]:
        if len(slot["candidates"]) > 1:
            assert not set(slot["candidates"]) <= set(singles)
