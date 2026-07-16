"""Move takeover: an `aka: polishedcrystal:` hint means the Ruleset move OWNS
that slot — stats, effect class, display name, and description all follow.

The host's old identity is retired: its `li` name entry is rewritten, its
description label is unshared from any stacked block into its own text, and
it is removed from the crit-ratio table when the new move isn't a crit move.
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

WATER_WHIP = MoveDef(
    name="Water Whip", chrooked_id="waterwhip", type="Water", category="physical",
    power=60, accuracy=100, pp=15,
    description="A whip of water that may make the foe flinch.",
    aka={"polishedcrystal": "CRABHAMMER"},
    additional_effects=(AdditionalEffect(effect="flinch", chance=20),),
)


@pytest.fixture()
def target(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "pc")
    return tmp_path / "pc"


def _apply(target, moves):
    report = ApplyReport()
    resmap = build_resolution_map(target)
    changed = apply_moves(target, Ruleset(moves=moves), resmap, report)
    return changed, report


@pytest.mark.unit
def test_takeover_writes_stats_and_effect_class(target):
    _apply(target, {"waterwhip": WATER_WHIP})
    line = [
        l for l in (target / "data/moves/moves.asm").read_text().splitlines()
        if l.startswith("\tmove CRABHAMMER,")
    ][0]
    assert "EFFECT_FLINCH_HIT" in line
    assert " 60," in line and "WATER" in line and " 20," in line


@pytest.mark.unit
def test_takeover_renames_the_li_entry(target):
    before = (target / "data/moves/names.asm").read_text()
    _apply(target, {"waterwhip": WATER_WHIP})
    after = (target / "data/moves/names.asm").read_text()
    assert '\tli "Water Whip"' in after
    assert '\tli "Crabhammer"' not in after
    # exactly one line changed
    diffs = [
        (a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b
    ]
    assert len(diffs) == 1


@pytest.mark.unit
def test_takeover_unshares_the_description_label(target):
    _apply(target, {"waterwhip": WATER_WHIP})
    text = (target / "data/moves/descriptions.asm").read_text()
    # Own block now, with the new description...
    own = text.split("CrabhammerDescription:\n")[1]
    assert own.splitlines()[0].strip().startswith('text "')
    assert "flinch" in own.split("done")[0]
    # ...while the shared crit block keeps its text for the other labels.
    assert "Has a high criti-" in text
    shared = text.split('text "Has a high criti-"')[0]
    assert "SlashDescription:" in shared
    assert shared.count("CrabhammerDescription:") == 0


@pytest.mark.unit
def test_takeover_removes_host_from_crit_table(target):
    _apply(target, {"waterwhip": WATER_WHIP})
    crit = (target / "data/moves/critical_hit_moves.asm").read_text()
    assert "CRABHAMMER" not in crit


@pytest.mark.unit
def test_too_long_name_uses_aka_short_name_or_reports(target):
    punch = MoveDef(
        name="One-Inch Punch", chrooked_id="oneinchpunch", type="Fighting",
        category="physical", power=90, accuracy=100, pp=10, description="x",
        aka={"polishedcrystal": "CROSS_CHOP", "polishedcrystal_name": "1-Inch Punch"},
    )
    _, report = _apply(target, {"oneinchpunch": punch})
    names = (target / "data/moves/names.asm").read_text()
    assert '\tli "1-Inch Punch"' in names

    no_short = MoveDef(
        name="One-Inch Punch", chrooked_id="oneinchpunch", type="Fighting",
        category="physical", power=90, accuracy=100, pp=10, description="x",
        aka={"polishedcrystal": "CROSS_CHOP"},
    )
    _, report2 = _apply(target, {"oneinchpunch": no_short})
    assert report2.entries[0].status == "partial"
    assert "name" in report2.entries[0].partial_fields


@pytest.mark.unit
def test_accuracy_zero_maps_to_minus_one_and_crit_flag_keeps_table_entry(target):
    punch = MoveDef(
        name="One-Inch Punch", chrooked_id="oneinchpunch", type="Fighting",
        category="physical", power=90, accuracy=0, pp=10, description="x",
        aka={
            "polishedcrystal": "CROSS_CHOP",
            "polishedcrystal_name": "1-Inch Punch",
            "polishedcrystal_crit": True,
        },
    )
    _apply(target, {"oneinchpunch": punch})
    line = [
        l for l in (target / "data/moves/moves.asm").read_text().splitlines()
        if l.startswith("\tmove CROSS_CHOP,")
    ][0]
    assert " -1," in line          # accuracy 0 (Ruleset "can't miss") -> PC -1
    assert " 0," not in line.split("FIGHTING")[1].split(",")[1]
    crit = (target / "data/moves/critical_hit_moves.asm").read_text()
    assert "CROSS_CHOP" in crit    # crit flag keeps the table entry


@pytest.mark.unit
def test_symbol_splice_preserves_column_alignment(target):
    _apply(target, {"waterwhip": WATER_WHIP})
    line = [
        l for l in (target / "data/moves/moves.asm").read_text().splitlines()
        if l.startswith("\tmove CRABHAMMER,")
    ][0]
    # Effect symbol keeps the original field's padding instead of collapsing
    # to one space (EFFECT_FLINCH_HIT is the same length as EFFECT_NORMAL_HIT).
    assert "\tmove CRABHAMMER,      EFFECT_FLINCH_HIT," in line
