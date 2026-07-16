"""Learnsets category for the polishedcrystal Applier (AC2, AC4).

A Ruleset-owned learnset replaces the species' `learnset` lines in
data/pokemon/evos_attacks.asm outright — including flattening any embedded
FAITHFUL conditionals, because the Ruleset owns the whole list. `evo_data`
lines and every other species' block stay byte-identical. One unresolvable
move blocks that species' whole learnset (a partial list would corrupt intent).
"""

import shutil
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.polishedcrystal.learnset_apply import apply_learnsets
from chrooked_pokedex.appliers.polishedcrystal.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.schema import LearnsetMove, SpeciesOverride
from chrooked_pokedex.report import ApplyReport

FIXTURE = Path(__file__).parent / "fixtures" / "polishedcrystal"
EVOS = Path("data/pokemon/evos_attacks.asm")


@pytest.fixture()
def target(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "pc")
    return tmp_path / "pc"


def _apply(target, species):
    ruleset = Ruleset(species=species)
    report = ApplyReport()
    resmap = build_resolution_map(target)
    changed = apply_learnsets(target, ruleset, resmap, report)
    return changed, report


def _override(chrooked_id, learnset, aka=None):
    return SpeciesOverride(
        name=chrooked_id.title(), chrooked_id=chrooked_id,
        aka=aka or {}, learnset=tuple(LearnsetMove(lvl, mv) for lvl, mv in learnset),
    )


@pytest.mark.unit
def test_learnset_replaced_whole_preserving_evo_data(target):
    species = {"bulbasaur": _override("bulbasaur", [(1, "tackle"), (10, "razor-leaf"), (30, "seed-bomb")])}
    before = (target / EVOS).read_text()
    changed, report = _apply(target, species)
    after = (target / EVOS).read_text()

    assert changed == [target / EVOS]
    assert report.entries[0].status == "applied"
    # Bulbasaur's block: evo_data preserved, learnset replaced exactly.
    block = after.split("\tevos_attacks Bulbasaur\n")[1].split("\n\n")[0]
    assert block.splitlines()[0] == "\tevo_data EVOLVE_LEVEL, 16, IVYSAUR"
    assert block.splitlines()[1:] == [
        "\tlearnset 1, TACKLE",
        "\tlearnset 10, RAZOR_LEAF",
        "\tlearnset 30, SEED_BOMB",
    ]
    # Every other species' block is byte-identical.
    for label in ("Caterpie", "Metapod", "FarfetchDGalarian"):
        marker = f"\tevos_attacks {label}\n"
        assert before.split(marker)[1].split("\n\n")[0] == after.split(marker)[1].split("\n\n")[0]


@pytest.mark.unit
def test_embedded_faithful_conditionals_are_flattened(target):
    species = {
        "farfetchd-galarian": _override(
            "farfetchd-galarian", [(1, "peck"), (15, "reversal")],
            aka={"polishedcrystal": "FarfetchDGalarian"},
        )
    }
    changed, report = _apply(target, species)
    after = (target / EVOS).read_text()

    assert report.entries[0].status == "applied"
    block = after.split("\tevos_attacks FarfetchDGalarian\n")[1].split("\n\n")[0]
    assert "FAITHFUL" not in block and "else" not in block and "endc" not in block
    assert block.splitlines()[-2:] == ["\tlearnset 1, PECK", "\tlearnset 15, REVERSAL"]


@pytest.mark.unit
def test_unresolvable_move_drops_to_partial_with_report(target):
    # Relaxed rule (2026-07-15): write the resolvable moves, name the dropped
    # ones in a partial entry — a custom move missing from PC no longer holds
    # the whole species hostage.
    species = {"bulbasaur": _override("bulbasaur", [(1, "tackle"), (5, "chrooked-slam")])}
    changed, report = _apply(target, species)
    after = (target / EVOS).read_text()

    assert changed == [target / EVOS]
    block = after.split("\tevos_attacks Bulbasaur\n")[1].split("\n\n")[0]
    assert block.splitlines()[1:] == ["\tlearnset 1, TACKLE"]
    entry = report.entries[0]
    assert entry.status == "partial"
    assert "chrooked-slam" in entry.reason
    assert entry.partial_fields == ("chrooked-slam",)


@pytest.mark.unit
def test_fully_unresolvable_learnset_blocks(target):
    # An empty learnset would corrupt the species — all-dropped stays blocked.
    species = {"bulbasaur": _override("bulbasaur", [(1, "chrooked-slam"), (5, "void-fang")])}
    before = (target / EVOS).read_bytes()
    changed, report = _apply(target, species)

    assert changed == []
    assert (target / EVOS).read_bytes() == before
    assert report.entries[0].status == "blocked"


@pytest.mark.unit
def test_species_absent_from_target_blocks(target):
    species = {"mewthree": _override("mewthree", [(1, "tackle")])}
    changed, report = _apply(target, species)
    assert changed == []
    assert report.entries[0].status == "blocked"
    assert "Mewthree" in report.entries[0].reason


@pytest.mark.unit
def test_faithful_wrapped_evo_data_is_preserved_and_closed(target):
    # Flaaffy's evo_data is FAITHFUL-wrapped (real PC pattern). Replacing the
    # learnset must not swallow the conditional's endc or leave it unclosed.
    species = {"flaaffy": _override("flaaffy", [(1, "tackle"), (16, "spark")])}
    changed, report = _apply(target, species)
    after = (target / EVOS).read_text()

    assert report.entries[0].status == "applied"
    block = after.split("\tevos_attacks Flaaffy\n")[1].split("\n\n")[0]
    lines = block.splitlines()
    # The whole evo_data conditional survives intact and balanced.
    assert lines[0] == "if DEF(FAITHFUL)"
    assert lines[1] == "\tevo_data EVOLVE_LEVEL, 30, AMPHAROS"
    assert lines[2] == "else"
    assert lines[3] == "\tevo_data EVOLVE_LEVEL, 36, AMPHAROS"
    assert lines[4] == "endc"
    assert lines[5:] == ["\tlearnset 1, TACKLE", "\tlearnset 16, SPARK"]


@pytest.mark.unit
def test_plain_form_suffix_fallback_finds_evos_block(target):
    # Farfetch'd's default form block is labeled FarfetchDPlain.
    species = {"farfetchd": SpeciesOverride(
        name="Farfetch'd", chrooked_id="farfetchd",
        learnset=(LearnsetMove(1, "peck"),),
    )}
    changed, report = _apply(target, species)
    assert report.entries[0].status == "applied"
    after = (target / EVOS).read_text()
    block = after.split("\tevos_attacks FarfetchDPlain\n")[1].split("\n\n")[0]
    assert block.splitlines()[-1] == "\tlearnset 1, PECK"


@pytest.mark.unit
def test_standin_resolves_learnset_reference_without_touching_the_move(target):
    # meta standins: a move PC lacks resolves to Chris's chosen stand-in for
    # learnset references only — the stand-in move itself is never rewritten.
    standins = {"Tail Whip": "LEER", "Bogus Move": "NOT_A_SYMBOL"}
    resmap = build_resolution_map(target, standins=standins)
    ruleset = Ruleset(
        species={"bulbasaur": _override("bulbasaur", [(1, "tackle"), (3, "Tail Whip")])}
    )
    report = ApplyReport()
    moves_before = (target / "data/moves/moves.asm").read_bytes()
    apply_learnsets(target, ruleset, resmap, report)

    assert report.entries[0].status == "applied"
    block = (target / EVOS).read_text().split("\tevos_attacks Bulbasaur\n")[1].split("\n\n")[0]
    assert "\tlearnset 3, LEER" in block.splitlines()
    assert (target / "data/moves/moves.asm").read_bytes() == moves_before
    # An unverifiable stand-in target is ignored, not written.
    assert resmap.move_reference("Bogus Move") is None
