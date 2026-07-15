"""Abilities category for the polishedcrystal Applier (AC3, AC4).

Per-species slot reassignment edits only the `abilities_for` line in the
species' base_stats file (the non-faithful line when FAITHFUL-wrapped); a
None slot keeps the target's value. AbilityDef name/description overrides
edit data/abilities/names.asm / descriptions.asm. Anything the target lacks
is blocked.
"""

import shutil
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.polishedcrystal.ability_apply import apply_abilities
from chrooked_pokedex.appliers.polishedcrystal.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.schema import AbilitiesOverride, AbilityDef, SpeciesOverride
from chrooked_pokedex.report import ApplyReport

FIXTURE = Path(__file__).parent / "fixtures" / "polishedcrystal"


@pytest.fixture()
def target(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "pc")
    return tmp_path / "pc"


def _apply(target, species=None, abilities=None):
    ruleset = Ruleset(species=species or {}, abilities=abilities or {})
    report = ApplyReport()
    resmap = build_resolution_map(target)
    changed = apply_abilities(target, ruleset, resmap, report)
    return changed, report


def _override(chrooked_id, slots, aka=None):
    return SpeciesOverride(
        name=chrooked_id.title(), chrooked_id=chrooked_id, aka=aka or {},
        abilities=AbilitiesOverride(**slots),
    )


@pytest.mark.unit
def test_hidden_slot_reassigned_single_line_diff(target):
    path = target / "data/pokemon/base_stats/bulbasaur.asm"
    before = path.read_text().splitlines()
    changed, report = _apply(target, species={"bulbasaur": _override("bulbasaur", {"hidden": "solar-power"})})
    after = path.read_text().splitlines()

    assert changed == [path]
    assert report.entries[0].status == "applied"
    diffs = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(diffs) == 1
    assert after[diffs[0]].startswith("\tabilities_for BULBASAUR, OVERGROW, CHLOROPHYLL, SOLAR_POWER")


@pytest.mark.unit
def test_faithful_wrapped_abilities_edit_nonfaithful_line(target):
    path = target / "data/pokemon/base_stats/skiploom.asm"
    before = path.read_text().splitlines()
    changed, report = _apply(target, species={"skiploom": _override("skiploom", {"secondary": "infiltrator"})})
    after = path.read_text().splitlines()

    diffs = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(diffs) == 1
    # The faithful branch keeps LEAF_GUARD; only the else branch changed.
    assert "LEAF_GUARD" in "\n".join(after)
    assert "INFILTRATOR" in after[diffs[0]]
    assert report.entries[0].status == "applied"


@pytest.mark.unit
def test_unresolvable_ability_blocks_species(target):
    path = target / "data/pokemon/base_stats/bulbasaur.asm"
    before = path.read_bytes()
    changed, report = _apply(target, species={"bulbasaur": _override("bulbasaur", {"primary": "chrooked-aura"})})
    assert changed == []
    assert path.read_bytes() == before
    assert report.entries[0].status == "blocked"


@pytest.mark.unit
def test_missing_species_file_blocks(target):
    changed, report = _apply(target, species={"mewthree": _override("mewthree", {"primary": "overgrow"})})
    assert changed == []
    assert report.entries[0].status == "blocked"


@pytest.mark.unit
def test_ability_name_and_description_override(target):
    abilities = {
        "stench": AbilityDef(
            name="Reek", chrooked_id="stench",
            description="Foe may flinch from the awful smell.",
        )
    }
    changed, report = _apply(target, abilities=abilities)
    names = (target / "data/abilities/names.asm").read_text()
    descs = (target / "data/abilities/descriptions.asm").read_text()

    assert report.entries[0].status == "applied"
    assert 'rawchar "Reek@"' in names
    assert 'rawchar "Stench@"' not in names
    block = descs.split("StenchDescription:\n")[1]
    assert block.splitlines()[0].strip().startswith('text "')
    assert block.split("done")[0].count('"') % 2 == 0
    assert "smell." in block.split("done")[0]


@pytest.mark.unit
def test_new_ability_def_blocks(target):
    abilities = {"chrooked-aura": AbilityDef(name="Chrooked Aura", chrooked_id="chrooked-aura", description="x")}
    changed, report = _apply(target, abilities=abilities)
    assert changed == []
    assert report.entries[0].status == "blocked"


@pytest.mark.unit
def test_ability_def_with_missing_label_reports_partial_not_applied(target):
    # STEADFAST resolves in constants, but the fixture names.asm/descriptions.asm
    # excerpts carry no Steadfast label — claiming "applied" would be a lie.
    abilities = {
        "steadfast": AbilityDef(name="Steadfast+", chrooked_id="steadfast", description="x")
    }
    changed, report = _apply(target, abilities=abilities)
    assert changed == []
    entry = report.entries[0]
    assert entry.status == "partial"
    assert "label" in entry.reason


@pytest.mark.unit
def test_changed_paths_are_deduplicated(target):
    abilities = {
        "stench": AbilityDef(name="Reek", chrooked_id="stench", description="Smelly."),
        "drizzle": AbilityDef(name="Drencher", chrooked_id="drizzle", description=""),
    }
    changed, _ = _apply(target, abilities=abilities)
    assert len(changed) == len(set(changed))
