"""Integration: essentials162 honors per-Target holds and additive learnset edits.

Drives the real `apply_species` / `apply_learnsets` over the committed 16.2 PBS
fixtures, so a hold genuinely suppresses a write and an additive edit genuinely
appends a move. Kept hermetic (`unit`) — the fixtures are copied into a tmp PBS dir.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.essentials162 import (
    learnset_apply,
    pbs_io,
    resolution,
    section_edit,
    species_apply,
)
from chrooked_pokedex.model.holds import HoldSet
from chrooked_pokedex.model.schema import LearnsetMove, SpeciesOverride
from chrooked_pokedex.model.target_edits import LearnsetAddition, TargetEdits
from chrooked_pokedex.report import ApplyReport

_FIXTURES = Path(__file__).parent / "fixtures" / "essentials162"


class _Ruleset:
    def __init__(self, species=None, moves=None, abilities=None):
        self.species = species or {}
        self.moves = moves or {}
        self.type_chart = []
        self.abilities = abilities or {}

    def owned_move(self, name):
        for move in self.moves.values():
            if move.name == name:
                return move
        return None


def _target(tmp_path: Path) -> Path:
    pbs = tmp_path / "PBS"
    pbs.mkdir()
    for name in ("pokemon.txt", "moves.txt", "types.txt", "abilities.txt"):
        shutil.copy(_FIXTURES / name, pbs / name)
    return tmp_path


def _moves_line(target: Path) -> str:
    text, _ = pbs_io.read(target / "PBS" / "pokemon.txt")
    span = section_edit.find_section_by_internalname(text, "BULBASAUR")
    assert span is not None
    return section_edit.get_field(text[span[0]:span[1]], "Moves") or ""


def _type1(target: Path) -> str | None:
    text, _ = pbs_io.read(target / "PBS" / "pokemon.txt")
    span = section_edit.find_section_by_internalname(text, "BULBASAUR")
    return section_edit.get_field(text[span[0]:span[1]], "Type1")


def _bulbasaur(**kw) -> dict:
    return {
        "bulbasaur": SpeciesOverride(
            name="Bulbasaur", chrooked_id="bulbasaur",
            aka={"essentials": "BULBASAUR"}, **kw,
        )
    }


@pytest.mark.unit
def test_species_hold_keeps_target_data_and_reports_held(tmp_path: Path) -> None:
    target = _target(tmp_path)
    before_type1 = _type1(target)
    ruleset = _Ruleset(species=_bulbasaur(types=("Fire", "Flying")))
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()

    holds = HoldSet(held={"bulbasaur": frozenset({"species"})})
    changed = species_apply.apply_species(target, ruleset, resmap, report, holds=holds)

    assert changed == set()  # nothing written
    assert _type1(target) == before_type1  # target's typing intact
    held = [e for e in report.entries if e.status == "held"]
    assert [(e.category, e.chrooked_id) for e in held] == [("species", "bulbasaur")]


@pytest.mark.unit
def test_learnset_hold_keeps_target_moves(tmp_path: Path) -> None:
    target = _target(tmp_path)
    before = _moves_line(target)
    # A canon learnset that WOULD replace the whole list if not held.
    ruleset = _Ruleset(species=_bulbasaur(learnset=(LearnsetMove(level=1, move="TACKLE"),)))
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()

    holds = HoldSet(held={"bulbasaur": frozenset({"learnset"})})
    learnset_apply.apply_learnsets(target, ruleset, resmap, report, holds=holds)

    assert _moves_line(target) == before  # regional learnset untouched
    assert any(e.status == "held" and e.category == "learnset" for e in report.entries)


@pytest.mark.unit
def test_additive_edit_appends_move(tmp_path: Path) -> None:
    target = _target(tmp_path)
    before = _moves_line(target)
    assert "MEGAHORN" not in before
    ruleset = _Ruleset(species=_bulbasaur())  # no canon learnset
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()

    edits = TargetEdits(
        learnset_add={"bulbasaur": (LearnsetAddition(level=1, move="MEGAHORN"),)}
    )
    learnset_apply.apply_learnsets(
        target, ruleset, resmap, report, target_edits=edits
    )

    after = _moves_line(target)
    assert after == before + ",1,MEGAHORN"  # kept-and-appended
    applied = [e for e in report.entries if "target-edit" in e.reason]
    assert applied and applied[0].status == "applied"
    assert "+MEGAHORN" in applied[0].reason


@pytest.mark.unit
def test_hold_and_additive_compose(tmp_path: Path) -> None:
    target = _target(tmp_path)
    before = _moves_line(target)
    ruleset = _Ruleset(species=_bulbasaur(learnset=(LearnsetMove(level=1, move="TACKLE"),)))
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()

    holds = HoldSet(held={"bulbasaur": frozenset({"learnset"})})
    edits = TargetEdits(
        learnset_add={"bulbasaur": (LearnsetAddition(level=1, move="MEGAHORN"),)}
    )
    learnset_apply.apply_learnsets(
        target, ruleset, resmap, report, holds=holds, target_edits=edits
    )

    after = _moves_line(target)
    # Canon TACKLE-only replace was suppressed; target's own list kept, MEGAHORN added.
    assert after == before + ",1,MEGAHORN"
    assert "LEECHSEED" in after  # a fixture move, proving the canon replace did NOT run


@pytest.mark.unit
def test_additive_edit_is_idempotent(tmp_path: Path) -> None:
    target = _target(tmp_path)
    ruleset = _Ruleset(species=_bulbasaur())
    resmap = resolution.build_resolution_map(target, ruleset)
    edits = TargetEdits(
        learnset_add={"bulbasaur": (LearnsetAddition(level=1, move="MEGAHORN"),)}
    )
    learnset_apply.apply_learnsets(target, ruleset, resmap, ApplyReport(), target_edits=edits)
    once = _moves_line(target)
    learnset_apply.apply_learnsets(target, ruleset, resmap, ApplyReport(), target_edits=edits)
    twice = _moves_line(target)
    assert once == twice  # second apply adds nothing new
    assert once.count("MEGAHORN") == 1
