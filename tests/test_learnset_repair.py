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


# ===========================================================================
# House rules (M3, #105) — scrub_draft + the five audits
# ===========================================================================

HOUSE_POOL = MOVE_POOL + [
    _move("Dark Void", "Dark", "status"),
    _move("Excalibur", "Steel", "physical", 90),
    _move("Dragon Dance", "Dragon", "status"),
    _move("Iron Defense", "Steel", "status"),
    _move("Howl", "Normal", "status"),
    _move("Tackle", "Normal", "physical", 40),
    _move("Body Slam", "Normal", "physical", 85),
    _move("Retaliate", "Normal", "physical", 70),
    _move("Giga Impact", "Normal", "physical", 120),
]


def test_house_rules_loader_reads_the_rubric_block() -> None:
    rules = lr.house_rules()
    assert "Glaive Rush" in rules["banned_moves"]
    assert rules["late_floor"]["Dragon Dance"] == 60
    assert rules["status_clump"] == {"window": 10, "max": 3}


def test_scrub_removes_banned_move_with_one_note() -> None:
    draft = [{"level": 1, "move": "Tackle"}, {"level": 20, "move": "Dark Void"}]
    rows, notes = lr.scrub_draft(draft, HOUSE_POOL)
    assert [r["move"] for r in rows] == ["Tackle"]
    assert len(notes) == 1 and notes[0].startswith("scrub: ")
    assert draft[1]["move"] == "Dark Void"  # inputs untouched


def test_scrub_keeps_anchored_banned_move_and_notes_it() -> None:
    draft = [{"level": 1, "move": "Tackle"}, {"level": 20, "move": "Dark Void"}]
    rows, notes = lr.scrub_draft(draft, HOUSE_POOL, anchors=["Dark Void"])
    assert any(r["move"] == "Dark Void" for r in rows)
    assert notes == ["scrub: kept banned Dark Void at L20 — anchor overrides ban"]


def test_scrub_removes_protected_move_unless_anchored() -> None:
    draft = [{"level": 1, "move": "Tackle"}, {"level": 40, "move": "Excalibur"}]
    rows, notes = lr.scrub_draft(draft, HOUSE_POOL)
    assert [r["move"] for r in rows] == ["Tackle"]
    assert notes and notes[0].startswith("scrub: removed Excalibur")

    rows, notes = lr.scrub_draft(draft, HOUSE_POOL, anchors=["Excalibur"])
    assert len(rows) == 2 and notes == []


def test_scrub_drops_the_later_copy_of_an_l0_move() -> None:
    draft = [{"level": 0, "move": "Body Slam"}, {"level": 44, "move": "Body Slam"}]
    rows, notes = lr.scrub_draft(draft, HOUSE_POOL)
    assert rows == [{"level": 0, "move": "Body Slam"}]
    assert len(notes) == 1


def test_scrub_drops_the_l0_copy_when_the_move_is_anchored() -> None:
    draft = [{"level": 0, "move": "Body Slam"}, {"level": 44, "move": "Body Slam"}]
    rows, notes = lr.scrub_draft(draft, HOUSE_POOL, anchors=["Body Slam"])
    assert rows == [{"level": 44, "move": "Body Slam"}]
    assert notes == ["scrub: removed the L0 copy of Body Slam — the anchored later copy stays"]


def test_anchor_is_never_scrubbed() -> None:
    draft = [
        {"level": 0, "move": "Excalibur"},
        {"level": 12, "move": "Dark Void"},
        {"level": 50, "move": "Excalibur"},
    ]
    rows, _notes = lr.scrub_draft(draft, HOUSE_POOL, anchors=["Dark Void", "Excalibur"])
    assert {r["move"] for r in rows} == {"Dark Void", "Excalibur"}


def test_late_floor_audits_and_repairs_dragon_dance() -> None:
    draft = [
        {"level": 9, "move": "Tackle"},
        {"level": 30, "move": "Dragon Dance"},
        {"level": 70, "move": "Giga Impact"},  # keeps a non-status capstone
    ]
    assert any("Dragon Dance" in p and "L60" in p for p in lr.audit_draft(draft, HOUSE_POOL))
    repaired, notes = lr.repair_draft(draft, HOUSE_POOL)
    dd = next(r for r in repaired if r["move"] == "Dragon Dance")
    assert dd["level"] >= 60
    assert any(n.startswith("repair: ") and "Dragon Dance" in n for n in notes)
    assert not any("Dragon Dance" in p for p in lr.audit_draft(repaired, HOUSE_POOL))


def test_status_clump_audits_and_spreads_surplus_rows() -> None:
    draft = [
        {"level": 5, "move": "Tackle"},
        {"level": 7, "move": "Growl"},
        {"level": 10, "move": "Howl"},
        {"level": 13, "move": "Protect"},
        {"level": 16, "move": "Substitute"},
        {"level": 40, "move": "Body Slam"},
    ]
    assert any("status clump" in p for p in lr.audit_draft(draft, HOUSE_POOL))
    repaired, notes = lr.repair_draft(draft, HOUSE_POOL)
    assert len(repaired) == len(draft)
    assert any("status rows within" in n for n in notes)
    assert not any("status clump" in p for p in lr.audit_draft(repaired, HOUSE_POOL))


def test_stab_hole_only_audits_when_stab_types_given() -> None:
    draft = [
        {"level": 5, "move": "Tackle"},
        {"level": 30, "move": "Retaliate"},
        {"level": 62, "move": "Giga Impact"},
    ]
    assert not any("STAB hole" in p for p in lr.audit_draft(draft, HOUSE_POOL))
    problems = lr.audit_draft(draft, HOUSE_POOL, stab_types=["Normal"])
    assert any("Normal STAB hole" in p and "L30" in p and "L62" in p for p in problems)
    # audit-only: repair leaves the levels alone
    repaired, _ = lr.repair_draft(draft, HOUSE_POOL)
    assert {r["level"] for r in repaired} == {5, 30, 62}


def test_early_rung_flags_a_draft_with_no_damage_by_l16() -> None:
    draft = [{"level": 1, "move": "Growl"}, {"level": 20, "move": "Retaliate"}]
    assert any("early rung" in p for p in lr.audit_draft(draft, HOUSE_POOL))
    fixed = [{"level": 1, "move": "Growl"}, {"level": 5, "move": "Tackle"},
             {"level": 20, "move": "Retaliate"}]
    assert not any("early rung" in p for p in lr.audit_draft(fixed, HOUSE_POOL))


def test_l0_outranks_flags_a_reward_stronger_than_the_next_two_rungs() -> None:
    draft = [
        {"level": 0, "move": "Giga Impact"},
        {"level": 5, "move": "Tackle"},
        {"level": 20, "move": "Retaliate"},
    ]
    assert any("L0 Giga Impact" in p and "outranks" in p for p in lr.audit_draft(draft, HOUSE_POOL))
    ok = [{"level": 0, "move": "Retaliate"}, {"level": 5, "move": "Tackle"},
          {"level": 20, "move": "Body Slam"}]
    assert not any("outranks" in p for p in lr.audit_draft(ok, HOUSE_POOL))


def test_stoutland_style_draft_scrubs_spreads_and_flags_the_hole() -> None:
    """Design-log scenario: Body Slam at L0 and L44, Dark Void at L12, four
    status rows in L7–L16, and a 40→70→120 Normal ladder with a 25-level gap."""
    draft = [
        {"level": 0, "move": "Body Slam"},
        {"level": 5, "move": "Tackle"},
        {"level": 7, "move": "Growl"},
        {"level": 10, "move": "Howl"},
        {"level": 12, "move": "Dark Void"},
        {"level": 13, "move": "Iron Defense"},
        {"level": 16, "move": "Protect"},
        {"level": 20, "move": "Retaliate"},
        {"level": 44, "move": "Body Slam"},
        {"level": 45, "move": "Giga Impact"},
    ]
    scrubbed, scrub_notes = lr.scrub_draft(draft, HOUSE_POOL)
    names = [(r["level"], r["move"]) for r in scrubbed]
    assert (12, "Dark Void") not in names
    assert (44, "Body Slam") not in names
    assert (0, "Body Slam") in names
    assert len(scrub_notes) == 2 and all(n.startswith("scrub: ") for n in scrub_notes)

    repaired, notes = lr.repair_draft(scrubbed, HOUSE_POOL)
    assert len(repaired) == len(scrubbed)
    assert any("status rows within" in n for n in notes)
    after = lr.audit_draft(repaired, HOUSE_POOL, stab_types=["Normal"])
    assert not any("status clump" in p for p in after)
    assert any("Normal STAB hole" in p for p in after)
