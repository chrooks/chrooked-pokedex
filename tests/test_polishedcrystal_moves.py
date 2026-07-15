"""Moves category for the polishedcrystal Applier (AC1, AC4).

Stat edits land on the `move NAME, ...` macro line in data/moves/moves.asm.
A FAITHFUL-wrapped move (if DEF(FAITHFUL) / else / endc) is edited only in
its else branch — Chris's changes are a rebalance; the FAITHFUL build stays
honest. Untouched lines stay byte-identical. A move the target lacks is a
blocked report entry, never a write.
"""

import shutil
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.polishedcrystal.move_apply import apply_moves
from chrooked_pokedex.appliers.polishedcrystal.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.schema import AdditionalEffect, MoveDef
from chrooked_pokedex.report import ApplyReport

FIXTURE = Path(__file__).parent / "fixtures" / "polishedcrystal"


@pytest.fixture()
def target(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "pc")
    return tmp_path / "pc"


def _apply(target, moves):
    ruleset = Ruleset(moves=moves)
    report = ApplyReport()
    resmap = build_resolution_map(target)
    changed = apply_moves(target, ruleset, resmap, report)
    return changed, report


@pytest.mark.unit
def test_unconditional_move_edited_in_place(target):
    moves = {
        "karate-chop": MoveDef(
            name="Karate Chop", chrooked_id="karate-chop", type="Fighting",
            category="physical", power=60, accuracy=100, pp=25,
        )
    }
    before = (target / "data/moves/moves.asm").read_text().splitlines()
    changed, report = _apply(target, moves)
    after = (target / "data/moves/moves.asm").read_text().splitlines()

    assert changed == [target / "data/moves/moves.asm"]
    (edited,) = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert "KARATE_CHOP" in after[edited]
    assert " 60," in after[edited]
    assert report.entries[0].status == "applied"


@pytest.mark.unit
def test_faithful_wrapped_move_edits_else_branch_only(target):
    moves = {
        "cut": MoveDef(
            name="Cut", chrooked_id="cut", type="Water",
            category="physical", power=70, accuracy=100, pp=30,
        )
    }
    before = (target / "data/moves/moves.asm").read_text().splitlines()
    _, report = _apply(target, moves)
    after = (target / "data/moves/moves.asm").read_text().splitlines()

    diffs = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(diffs) == 1
    edited = diffs[0]
    # The faithful branch (between `if DEF(FAITHFUL)` and `else`) is untouched:
    # the edited CUT line must come after an `else` that follows `if DEF(FAITHFUL)`.
    preceding = before[:edited]
    assert "else" in [line.strip() for line in preceding[-2:]] or any(
        line.strip() == "else" for line in preceding[preceding.index("if DEF(FAITHFUL)"):]
    )
    assert "WATER" in after[edited] and " 70," in after[edited]
    assert report.entries[0].status == "applied"


@pytest.mark.unit
def test_missing_move_blocks_with_no_write(target):
    moves = {
        "chrooked-slam": MoveDef(
            name="Chrooked Slam", chrooked_id="chrooked-slam", type="Dark",
            category="physical", power=90, accuracy=100, pp=10,
        )
    }
    before = (target / "data/moves/moves.asm").read_bytes()
    changed, report = _apply(target, moves)

    assert changed == []
    assert (target / "data/moves/moves.asm").read_bytes() == before
    assert report.entries[0].status == "blocked"
    assert "CHROOKED_SLAM" in report.entries[0].reason


@pytest.mark.unit
def test_engine_code_fields_report_partial(target):
    moves = {
        "gust": MoveDef(
            name="Gust", chrooked_id="gust", type="Flying", category="special",
            power=50, accuracy=100, pp=35, priority=1, flags=("wind",),
            additional_effects=(AdditionalEffect(effect="flinch", chance=30),),
        )
    }
    _, report = _apply(target, moves)
    entry = report.entries[0]
    assert entry.status == "partial"
    assert "priority" in entry.partial_fields
    assert "flags" in entry.partial_fields
    # The chance arg itself IS written (arg 7), but the effect identity is
    # engine code we cannot verify:
    assert "additional_effects" in entry.partial_fields
