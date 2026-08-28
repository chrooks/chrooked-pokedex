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
    stray_level = next(
        lvl for lvl in range(2, 71)
        if lvl not in {s["level"] for s in skeleton["slots"]}
    )
    errors = sk.validate_against_skeleton(
        rows + [{"level": stray_level, "move": "Protect", "reasoning": ""}],
        skeleton,
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


def test_battle_gimmicks_are_not_learnset_moves() -> None:
    """Z-moves and Dynamax/G-Max moves never belong in a generated learnset.

    Dynamax moves are tagged by effect (Max Guard hides behind ``protect``, so
    the name prefix catches it); a Z-move's only tell in a pool row is 1 PP.
    """
    gimmicks = [
        _mv("G-Max Wildfire", "Fire", 10, effect="max_move", pp=10),
        _mv("Max Flare", "Fire", 1, effect="max_move", pp=10),
        _mv("Max Guard", "Normal", None, category="Status", effect="protect", pp=10),
        _mv("Inferno Overdrive", "Fire", 1, pp=1),
        _mv("Catastropika", "Electric", 210, pp=1),
    ]
    for row in gimmicks:
        assert sk.is_battle_gimmick(row), f"{row['move']} slipped through"
    for row in _pool():
        assert not sk.is_battle_gimmick(row), f"{row['move']} wrongly flagged"


def test_suggest_learnset_strips_gimmicks_from_the_pool() -> None:
    """The choke point: a gimmick in the pool reaches neither prompt nor skeleton."""
    from chrooked_pokedex.web import suggest as suggestmod

    pool = _pool() + [
        _mv("G-Max Wildfire", "Dragon", 130, effect="max_move", pp=10),
        _mv("Devastating Drake", "Dragon", 130, pp=1),
    ]
    seen: dict[str, str] = {}

    class _Capture:
        def propose(self, *, system, cached_context, user, schema, max_tokens=0):
            seen["blob"] = cached_context + user
            raise RuntimeError("captured")

    with pytest.raises(RuntimeError):
        suggestmod.suggest_learnset(
            provider=_Capture(), entry=_entry(), move_pool=pool,
            abilities=_ABILITIES, mode="full",
        )
    assert "G-Max Wildfire" not in seen["blob"]
    assert "Devastating Drake" not in seen["blob"]
    assert "Draco Meteor" in seen["blob"], "the real pool must survive the strip"


# --------------------------------------------------------------------------- #
# Anchors — moves the user names outright (#89)
# --------------------------------------------------------------------------- #


def test_anchor_becomes_its_own_required_slot() -> None:
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool(), anchors=["Brine"])
    anchored = [s for s in skeleton["slots"] if s["candidates"] == ["Brine"]]
    assert len(anchored) == 1
    slot = anchored[0]
    assert slot["required"] is True
    assert slot["role"] == "named"
    assert "ANCHOR" in slot["label"]
    assert slot["level"] > 1


def test_anchor_is_canonicalized_from_a_casefolded_name() -> None:
    """The boundary canonicalizes, but the skeleton must not depend on that."""
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool(), anchors=["bRiNe"])
    assert any(s["candidates"] == ["Brine"] for s in skeleton["slots"])


def test_anchor_is_struck_from_every_other_levelled_slot() -> None:
    """The singleton-collision guard reserves the anchor for its own slot.

    L0 is exempt by design — a move may sit at L0 AND at a real level — so the
    reward slot may still offer the anchor. Every levelled slot must not.
    """
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool(), anchors=["Brine"])
    holders = [
        s for s in skeleton["slots"]
        if s["level"] > 0 and "Brine" in s["candidates"]
    ]
    assert len(holders) == 1
    assert holders[0]["candidates"] == ["Brine"]


def test_anchors_survive_the_size_cap_trim() -> None:
    """Anchors are priority 0 — the trim eats flavor and status first."""
    anchors = ["Twister", "Brine", "Surf", "Slam", "Protect", "Toxic"]
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool(), anchors=anchors)
    seated = {c for s in skeleton["slots"] for c in s["candidates"] if len(s["candidates"]) == 1}
    for anchor in anchors:
        assert anchor in seated, f"{anchor} lost its slot"


def test_anchor_not_in_the_pool_is_skipped_without_raising() -> None:
    """The request boundary rejects these; build_skeleton stays total anyway."""
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool(), anchors=["Flurb"])
    assert all("Flurb" not in s["candidates"] for s in skeleton["slots"])


def test_duplicate_anchors_make_one_slot() -> None:
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool(), anchors=["Brine", "brine"])
    assert sum(1 for s in skeleton["slots"] if s["candidates"] == ["Brine"]) == 1


def test_no_anchors_leaves_the_skeleton_unchanged() -> None:
    """`anchors=[]` must behave exactly like omitting the argument."""
    base = sk.build_skeleton(_entry(), _ABILITIES, _pool())
    empty = sk.build_skeleton(_entry(), _ABILITIES, _pool(), anchors=[])
    assert base == empty


def test_dropped_slots_are_tagged_by_cause() -> None:
    """Every drop says whether a slot took the space or the pool was empty."""
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool())
    for note in skeleton["dropped"]:
        assert note.startswith(("crowded: ", "unfillable: ")), note


def test_anchors_crowding_out_a_slot_is_reported() -> None:
    """Anchors claim grid seats; what they displace must not vanish silently."""
    anchors = ["Twister", "Brine", "Surf", "Slam", "Protect", "Toxic", "Amnesia"]
    skeleton = sk.build_skeleton(_entry(), _ABILITIES, _pool(), anchors=anchors)
    crowded = [n for n in skeleton["dropped"] if n.startswith("crowded: ")]
    assert crowded, skeleton["dropped"]


def test_anchor_slots_seat_by_effective_power() -> None:
    """A user-named anchor seats where its power belongs, never first-free.

    Regression for the Breloom draft: 40BP Mach Punch landed at L47 and a
    status slot became the L72 capstone because band-less slots took grid
    leftovers in order.
    """
    pool = _pool() + [
        _mv("Mach Punch", "Fighting", 40, category="Physical"),
        _mv("Wood Hammer", "Grass", 120, category="Physical"),
    ]
    skeleton = sk.build_skeleton(
        _entry(), _ABILITIES, pool, direction="",
        anchors=["Mach Punch", "Wood Hammer"],
    )
    levels = {
        s["candidates"][0]: s["level"]
        for s in skeleton["slots"]
        if s["role"] == "named"
    }
    assert levels["Mach Punch"] <= 19, "a 40BP anchor belongs in the early game"
    assert levels["Wood Hammer"] >= 50, "a 120BP anchor belongs in the late game"
