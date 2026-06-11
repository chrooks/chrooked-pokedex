"""Milestone 3 — apply species scalar Overrides into a target fork."""

from pathlib import Path

import pytest

from chrooked_pokedex.appliers.pokeemerald.resolution import build_resolution_map
from chrooked_pokedex.appliers.pokeemerald.species_apply import apply_species
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.readers.pokeemerald import species_parser
from chrooked_pokedex.report import ApplyReport


def _build_target(tmp_path: Path) -> Path:
    target = tmp_path / "fork"
    pokemon = target / "src" / "data" / "pokemon"
    pokemon.mkdir(parents=True)
    (pokemon / "species_info.h").write_text(
        """\
const struct SpeciesInfo gSpeciesInfo[] =
{
    [SPECIES_GOODRA] =
    {
        .baseHP = 90,
        .baseSpeed = 80,
        .types = MON_TYPES(TYPE_DRAGON),
        .abilities = {ABILITY_SAP_SIPPER, ABILITY_HYDRATION, ABILITY_GOOEY},
    },
};
""",
        encoding="utf-8",
    )
    # Minimal ability + type tables so the resolution map can resolve names.
    data = target / "src" / "data"
    (data / "abilities.h").write_text(
        """\
const struct AbilityInfo gAbilitiesInfo[ABILITIES_COUNT] =
{
    [ABILITY_POISON_HEAL] =
    {
        .name = _("Poison Heal"),
        .description = COMPOUND_STRING("Heals from poison."),
    },
};
""",
        encoding="utf-8",
    )
    (data / "types_info.h").write_text(
        """\
#define X UQ_4_12
#define ______ X(1.0)
const uq4_12_t gTypeEffectivenessTable[N][N] =
{
    [TYPE_WATER] = {______},
    [TYPE_DRAGON] = {______},
};
""",
        encoding="utf-8",
    )
    return target


def _ruleset(tmp_path: Path) -> Ruleset:
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (root / "species" / "goodra.yaml").write_text(
        """\
name: Goodra
chrooked_id: goodra
aka: { pokeemerald: SPECIES_GOODRA }
types: [Water, Dragon]
abilities:
  primary: Poison Heal
stats: { spe: 90 }
""",
        encoding="utf-8",
    )
    return Ruleset.load(root)


def test_apply_species_rewrites_types_abilities_stats(tmp_path: Path) -> None:
    target = _build_target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = apply_species(target, ruleset, resmap, report)

    assert changed  # a file was rewritten
    profiles = species_parser.parse_species_profiles(target)
    goodra = profiles["SPECIES_GOODRA"]
    # types now Water/Dragon
    assert "TYPE_WATER" in goodra.fields["types"]
    assert "TYPE_DRAGON" in goodra.fields["types"]
    # primary ability now Poison Heal, other slots preserved
    assert "ABILITY_POISON_HEAL" in goodra.fields["abilities"]
    assert "ABILITY_HYDRATION" in goodra.fields["abilities"]
    # stat applied
    assert goodra.fields["baseSpeed"] == "90"
    # report: applied
    assert report.counts()["applied"] == 1


def test_apply_species_is_idempotent(tmp_path: Path) -> None:
    target = _build_target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)

    apply_species(target, ruleset, resmap, ApplyReport())
    after_first = (target / "src/data/pokemon/species_info.h").read_text()
    second_changed = apply_species(target, ruleset, resmap, ApplyReport())
    after_second = (target / "src/data/pokemon/species_info.h").read_text()

    assert after_first == after_second
    assert second_changed == set()  # nothing changed on the re-run


def test_apply_blocks_missing_species(tmp_path: Path) -> None:
    target = _build_target(tmp_path)
    ruleset = _ruleset(tmp_path)
    # Point the override at a species the target lacks.
    object.__setattr__(
        ruleset.species["goodra"], "aka", {"pokeemerald": "SPECIES_NONEXISTENT"}
    )
    report = ApplyReport()

    apply_species(target, ruleset, resmap=build_resolution_map(target, ruleset), report=report)

    assert report.counts()["blocked"] == 1


def test_apply_edits_all_preprocessor_gated_field_branches(tmp_path: Path) -> None:
    """A species entry can carry the same field once per #if/#else branch. Every
    branch must be edited, or apply silently under-applies and the parser (which
    reads the last branch) disagrees with what landed."""
    target = _build_target(tmp_path)
    # Replace the flat species entry with one that gates abilities + a stat.
    (target / "src/data/pokemon/species_info.h").write_text(
        """\
const struct SpeciesInfo gSpeciesInfo[] =
{
    [SPECIES_GOODRA] =
    {
    #if P_UPDATED_ABILITIES >= GEN_4
        .baseSpeed = 80,
        .types = MON_TYPES(TYPE_DRAGON),
        .abilities = {ABILITY_SAP_SIPPER, ABILITY_HYDRATION, ABILITY_GOOEY},
    #else
        .baseSpeed = 70,
        .types = MON_TYPES(TYPE_DRAGON),
        .abilities = {ABILITY_SAP_SIPPER, ABILITY_NONE, ABILITY_GOOEY},
    #endif
    },
};
""",
        encoding="utf-8",
    )
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)

    apply_species(target, ruleset, resmap, ApplyReport())

    text = (target / "src/data/pokemon/species_info.h").read_text()
    # Both ability branches got the primary overlaid; neither still says Sap Sipper primary.
    assert text.count("ABILITY_POISON_HEAL") == 2
    # Each branch kept its own second slot (Hydration vs NONE).
    assert "{ABILITY_POISON_HEAL, ABILITY_HYDRATION, ABILITY_GOOEY}" in text
    assert "{ABILITY_POISON_HEAL, ABILITY_NONE, ABILITY_GOOEY}" in text
    # Both stat branches now hold the override value.
    assert text.count(".baseSpeed = 90,") == 2


def test_apply_partial_when_ability_unresolved(tmp_path: Path) -> None:
    target = _build_target(tmp_path)
    # Remove the ability table so "Poison Heal" cannot resolve.
    (target / "src/data/abilities.h").write_text("// empty\n", encoding="utf-8")
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_species(target, ruleset, resmap, report)

    assert report.counts()["partial"] == 1
    # types and stats still landed even though the ability did not
    profiles = species_parser.parse_species_profiles(target)
    assert profiles["SPECIES_GOODRA"].fields["baseSpeed"] == "90"
