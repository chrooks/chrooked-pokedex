"""The utility classifier and the grade table.

Two separate mechanisms on purpose: the classifier is a binary "may this move
fill an attacking slot", the grade is a ranking among utility moves. Conflating
them is what makes this kind of system brittle.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from chrooked_pokedex.web import learnset_skeleton as ls

pytestmark = pytest.mark.unit

_SNAPSHOT = Path("ruleset/.base/1.11.2.json")


def _base_moves() -> dict[str, dict]:
    return json.loads(_SNAPSHOT.read_text("utf-8"))["moves"]


# --- classifier -------------------------------------------------------------

def test_status_moves_are_utility() -> None:
    moves = _base_moves()
    assert ls.is_utility_move(moves["thunderwave"])
    assert ls.is_utility_move(moves["swordsdance"])


def test_nuzzle_is_utility_not_a_ramp_rung() -> None:
    """The regression this whole filter exists for: 20 BP, 100% paralysis."""
    assert ls.is_utility_move(_base_moves()["nuzzle"])


def test_real_attacks_are_not_utility() -> None:
    moves = _base_moves()
    for mid in ("spark", "thunderbolt", "wildcharge", "boomburst"):
        assert not ls.is_utility_move(moves[mid]), mid


def test_a_strong_move_with_a_100pct_secondary_is_still_an_attack() -> None:
    """Trop Kick is 70 BP with a guaranteed Attack drop — an attack that debuffs,
    not a debuff that scratches. The BP floor is what separates it from Nuzzle."""
    assert not ls.is_utility_move(_base_moves()["tropkick"])


def test_attacking_filters_reject_utility_moves() -> None:
    """The wiring: an attacking slot filter must not accept Nuzzle."""
    nuzzle = _base_moves()["nuzzle"]
    filt = {"move_type": "Electric", "attacking": True}
    assert not ls._matches(nuzzle, filt, None)
    assert ls._matches(_base_moves()["spark"], filt, None)


# --- grade ------------------------------------------------------------------

def test_grade_table_payoffs_are_positive_numbers() -> None:
    t = ls._grade_table()
    bad = {k: v for k, v in t["payoff"].items() if not isinstance(v, (int, float)) or v <= 0}
    assert not bad, bad


def test_bands_descend_and_end_at_zero() -> None:
    floors = [f for _, f in ls._grade_table()["bands"]]
    assert floors == sorted(floors, reverse=True)
    assert floors[-1] == 0, "the last band must catch every remaining score"


def test_accuracy_dominates_within_one_effect_family() -> None:
    """Spore and Hypnosis are the same effect; only reliability separates them."""
    moves = _base_moves()
    spore, _ = ls.grade_utility(moves["spore"])
    hypnosis, _ = ls.grade_utility(moves["hypnosis"])
    assert spore > hypnosis


def _pool() -> dict[str, dict]:
    """The MERGED pool, which is what the skeleton actually grades. Grading the
    base snapshot instead misses every Ruleset override — Dark Void is 85
    accuracy here, not the base 50, and that is the difference between A+ and D."""
    from pathlib import Path

    from chrooked_pokedex.model.ruleset import Ruleset
    from chrooked_pokedex.web import dex as dexmod
    from chrooked_pokedex.web import snapshot as snapmod

    snap = snapmod.load_snapshot(_SNAPSHOT)
    rules = Ruleset.load(Path("ruleset"))
    return {r["move"]: r for r in dexmod.build_move_pool(snap, rules)}


def test_calibration_anchors() -> None:
    """The three grades the weights were fitted to, graded off the merged pool."""
    pool = _pool()
    for name, want in (("Dark Void", "A+"), ("Spore", "A"), ("Hypnosis", "D+")):
        assert ls.grade_utility(pool[name])[1] == want, name


def test_pool_rows_carry_what_the_grader_reads() -> None:
    """build_move_pool must expose target and additional_effects, or spread never
    applies and the 100%-status classifier never fires."""
    pool = _pool()
    assert pool["Dark Void"]["target"] == "both", "spread target lost"
    assert pool["Nuzzle"]["additional_effects"], "secondary effects lost"
    assert ls.is_utility_move(pool["Nuzzle"])
    assert not ls.is_utility_move(pool["Spark"])


def test_powder_immunity_costs_spore_a_grade() -> None:
    """Spore has perfect accuracy; only the powder immunity keeps it off A+."""
    t = ls._grade_table()
    spore = _base_moves()["spore"]
    graded, _ = ls.grade_utility(spore, t)
    clean = dict(t, immunity_by_move={})
    assert ls.grade_utility(spore, clean)[0] > graded


def test_every_status_move_grades_without_raising() -> None:
    t = ls._grade_table()
    for mid, m in _base_moves().items():
        if (m.get("category") or "") == "status":
            score, letter = ls.grade_utility(m, t)
            assert score >= 0, mid
            assert letter, mid
