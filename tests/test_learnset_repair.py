"""Unit tests for the FULL-mode learnset repair pass (#95)."""
from __future__ import annotations

import pytest

from chrooked_pokedex.web import learnset_repair as lr

pytestmark = pytest.mark.unit


def _move(name: str, type_: str, category: str, power: int | None = None) -> dict:
    return {"move": name, "type": type_, "category": category, "power": power}


MOVE_POOL = [
    _move("Growl", "Normal", "status"),
    _move("Roost", "Flying", "status"),
    _move("Substitute", "Normal", "status"),
    _move("Protect", "Normal", "status"),
    _move("Ember", "Fire", "special", 40),
    _move("Fire Fang", "Fire", "special", 65),
    _move("Flamethrower", "Fire", "special", 90),
    _move("Hydro Pump", "Water", "special", 120),
]


def test_messy_draft_comes_back_audit_clean_with_repair_notes() -> None:
    """40BP-after-90BP inversion, a status capstone, and an adjacent-level pair
    — all in one draft — must all be gone after repair, with a note each."""
    draft = [
        {"level": 1, "move": "Growl"},
        {"level": 1, "move": "Substitute"},
        {"level": 9, "move": "Flamethrower"},  # descending: 90 before 40/65
        {"level": 26, "move": "Ember"},
        {"level": 44, "move": "Fire Fang"},
        {"level": 58, "move": "Substitute"},
        {"level": 59, "move": "Protect"},  # < 2-level gap from L58
        {"level": 65, "move": "Hydro Pump"},
        {"level": 72, "move": "Roost"},  # status as the final (capstone) row
    ]
    # Duplicate "Substitute" (L1 kit + L58) is fine for this pass — it only
    # audits pacing/ascent/gap/capstone, not the repeat-move rule.

    before = lr.audit_draft(draft, MOVE_POOL)
    assert before, "fixture must start dirty"

    repaired, notes = lr.repair_draft(draft, MOVE_POOL)

    assert notes, "the messy draft must produce at least one repair note"
    assert all(n.startswith("repair: ") for n in notes)
    after = lr.audit_draft(repaired, MOVE_POOL)
    assert after == [], f"still dirty after repair: {after}"

    # never drops a row
    assert len(repaired) == len(draft)
    assert {r["move"] for r in repaired} == {"Growl", "Substitute", "Flamethrower",
                                              "Ember", "Fire Fang", "Protect",
                                              "Hydro Pump", "Roost"}
    # the capstone is no longer a status move
    final = max(repaired, key=lambda r: r["level"])
    assert final["move"] != "Roost"


def test_ladder_ascent_reorders_within_existing_slots() -> None:
    draft = [
        {"level": 9, "move": "Flamethrower"},
        {"level": 26, "move": "Ember"},
        {"level": 44, "move": "Fire Fang"},
    ]
    repaired, notes = lr.repair_draft(draft, MOVE_POOL)
    by_move = {r["move"]: r["level"] for r in repaired}
    assert by_move["Ember"] == 9
    assert by_move["Fire Fang"] == 26
    assert by_move["Flamethrower"] == 44
    assert notes


def test_empty_draft_is_a_no_op() -> None:
    assert lr.audit_draft([], MOVE_POOL) == []
    repaired, notes = lr.repair_draft([], MOVE_POOL)
    assert repaired == []
    assert notes == []


def test_all_status_draft_flags_unfixable_capstone() -> None:
    """No non-status row exists to swap in — the violation is real and stays."""
    draft = [{"level": 1, "move": "Growl"}, {"level": 50, "move": "Roost"}]
    problems = lr.audit_draft(draft, MOVE_POOL)
    assert any("final learnset row" in p for p in problems)

    repaired, notes = lr.repair_draft(draft, MOVE_POOL)
    assert notes == []  # nothing could legally be done
    assert repaired == draft


def test_anchor_status_row_is_exempt_from_capstone_rule() -> None:
    draft = [{"level": 1, "move": "Growl"}, {"level": 72, "move": "Roost"}]
    problems = lr.audit_draft(draft, MOVE_POOL, anchors=["Roost"])
    assert problems == []

    repaired, notes = lr.repair_draft(draft, MOVE_POOL, anchors=["Roost"])
    assert notes == []
    assert repaired == sorted(draft, key=lambda r: (r["level"], r["move"]))


def test_anchor_row_is_never_dropped_even_when_reseated() -> None:
    """An anchor may move level (pacing/ascent), but must survive the pass."""
    draft = [
        {"level": 1, "move": "Growl"},
        {"level": 9, "move": "Flamethrower"},  # anchor, but out of pacing order
        {"level": 26, "move": "Ember"},
    ]
    repaired, notes = lr.repair_draft(draft, MOVE_POOL, anchors=["Flamethrower"])
    assert any(r["move"] == "Flamethrower" for r in repaired)
    assert len(repaired) == len(draft)


def test_row_count_bounds_are_audit_only() -> None:
    draft = [{"level": 1, "move": "Growl"}]
    problems = lr.audit_draft(draft, MOVE_POOL, size_bounds=(16, 26))
    assert any("row count" in p for p in problems)
    # repair cannot fix a count problem by re-seating — row count is unchanged
    repaired, _notes = lr.repair_draft(draft, MOVE_POOL)
    assert len(repaired) == len(draft)


def test_nearest_free_level_walks_outward_preferring_up() -> None:
    assert lr.nearest_free_level(10, set(), 2, 75) == 10
    assert lr.nearest_free_level(10, {10}, 2, 75) == 11
    assert lr.nearest_free_level(10, {9, 10, 11}, 2, 75) == 12


def test_assign_to_slots_reuses_existing_levels_in_ascending_key_order() -> None:
    items = ["c", "a", "b"]
    pairs = lr.assign_to_slots([30, 10, 20], items, key=lambda x: x)
    assert pairs == [(10, "a"), (20, "b"), (30, "c")]
