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


def _build_brace_target(tmp_path: Path) -> Path:
    """A target whose species file uses the older brace-array .types form
    (no MON_TYPES macro anywhere) — e.g. pokeemerald-rogue-ex (expansion 1.7.4)."""
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
        .types = { TYPE_DRAGON, TYPE_DRAGON },
        .abilities = {ABILITY_SAP_SIPPER, ABILITY_HYDRATION, ABILITY_GOOEY},
    },
};
""",
        encoding="utf-8",
    )
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
    [TYPE_ROCK] = {______},
};
""",
        encoding="utf-8",
    )
    return target


def _build_split_dialect_target(tmp_path: Path) -> Path:
    """A split-layout target (species_info/*.h) where one file is brace-form
    and another is macro-form — a fork mid-migration between conventions."""
    target = tmp_path / "fork"
    split_dir = target / "src" / "data" / "pokemon" / "species_info"
    split_dir.mkdir(parents=True)
    (split_dir / "gen_a.h").write_text(
        """\
const struct SpeciesInfo gSpeciesInfoGenA[] =
{
    [SPECIES_GOODRA] =
    {
        .types = { TYPE_DRAGON, TYPE_DRAGON },
    },
};
""",
        encoding="utf-8",
    )
    (split_dir / "gen_b.h").write_text(
        """\
const struct SpeciesInfo gSpeciesInfoGenB[] =
{
    [SPECIES_SLIGGOO] =
    {
        .types = MON_TYPES(TYPE_DRAGON),
    },
};
""",
        encoding="utf-8",
    )
    data = target / "src" / "data"
    (data / "abilities.h").write_text("// empty\n", encoding="utf-8")
    (data / "types_info.h").write_text(
        """\
#define X UQ_4_12
#define ______ X(1.0)
const uq4_12_t gTypeEffectivenessTable[N][N] =
{
    [TYPE_WATER] = {______},
    [TYPE_DRAGON] = {______},
    [TYPE_ROCK] = {______},
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


def test_apply_species_rewrites_types_brace_form(tmp_path: Path) -> None:
    """A target with no MON_TYPES usage (e.g. pokeemerald-rogue-ex) gets its
    .types Override written as a plain brace array, matching its own convention."""
    target = _build_brace_target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = apply_species(target, ruleset, resmap, report)

    assert changed
    text = (target / "src/data/pokemon/species_info.h").read_text()
    assert "MON_TYPES" not in text
    profiles = species_parser.parse_species_profiles(target)
    goodra = profiles["SPECIES_GOODRA"]
    assert "TYPE_WATER" in goodra.fields["types"]
    assert "TYPE_DRAGON" in goodra.fields["types"]


def test_apply_species_brace_mono_type_duplicates(tmp_path: Path) -> None:
    """A single-type Override on a brace-form target duplicates the type into
    both slots, matching the target's own native mono-type convention."""
    target = _build_brace_target(tmp_path)
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (root / "species" / "goodra.yaml").write_text(
        """\
name: Goodra
chrooked_id: goodra
aka: { pokeemerald: SPECIES_GOODRA }
types: [Rock]
""",
        encoding="utf-8",
    )
    ruleset = Ruleset.load(root)
    resmap = build_resolution_map(target, ruleset)

    apply_species(target, ruleset, resmap, ApplyReport())

    text = (target / "src/data/pokemon/species_info.h").read_text()
    assert "{ TYPE_ROCK, TYPE_ROCK }" in text


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


def test_apply_species_detects_dialect_per_file(tmp_path: Path) -> None:
    """A split-layout target with genuinely mixed dialects across files must
    render each file in its OWN dialect, not a global winner-takes-all verdict."""
    target = _build_split_dialect_target(tmp_path)
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (root / "species" / "goodra.yaml").write_text(
        "name: Goodra\nchrooked_id: goodra\naka: { pokeemerald: SPECIES_GOODRA }\ntypes: [Water, Dragon]\n",
        encoding="utf-8",
    )
    (root / "species" / "sliggoo.yaml").write_text(
        "name: Sliggoo\nchrooked_id: sliggoo\naka: { pokeemerald: SPECIES_SLIGGOO }\ntypes: [Water, Rock]\n",
        encoding="utf-8",
    )
    ruleset = Ruleset.load(root)
    resmap = build_resolution_map(target, ruleset)

    apply_species(target, ruleset, resmap, ApplyReport())

    gen_a = (target / "src/data/pokemon/species_info/gen_a.h").read_text()
    gen_b = (target / "src/data/pokemon/species_info/gen_b.h").read_text()
    assert "{ TYPE_WATER, TYPE_DRAGON }" in gen_a
    assert "MON_TYPES" not in gen_a
    assert "MON_TYPES(TYPE_WATER, TYPE_ROCK)" in gen_b


def test_apply_species_brace_form_is_idempotent(tmp_path: Path) -> None:
    target = _build_brace_target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)

    apply_species(target, ruleset, resmap, ApplyReport())
    after_first = (target / "src/data/pokemon/species_info.h").read_text()
    second_changed = apply_species(target, ruleset, resmap, ApplyReport())
    after_second = (target / "src/data/pokemon/species_info.h").read_text()

    assert after_first == after_second
    assert second_changed == set()


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


def test_apply_skips_identity_stub_without_scalar_fields(tmp_path: Path) -> None:
    """An identity/evolution-only stub (no types/abilities/stats) is not the species
    tier's concern — it must be skipped silently, not reported blocked."""
    target = _build_target(tmp_path)
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    # A stub for a species the target lacks, with no scalar fields.
    (root / "species" / "missingno.yaml").write_text(
        "name: Missingno\nchrooked_id: missingno\naka: { pokeemerald: SPECIES_MISSINGNO }\n"
    )
    ruleset = Ruleset.load(root)
    report = ApplyReport()

    apply_species(target, ruleset, build_resolution_map(target, ruleset), report)

    assert report.counts()["blocked"] == 0
    assert report.counts()["applied"] == 0


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


def test_resolution_matches_form_symbols_without_aka(tmp_path: Path) -> None:
    """`diglettalola` (no aka hint) resolves to the target's real
    SPECIES_DIGLETT_ALOLA by underscore-insensitive match, not a constructed
    SPECIES_DIGLETTALOLA."""
    target = _build_target(tmp_path)
    pokemon = target / "src" / "data" / "pokemon"
    (pokemon / "species_info.h").write_text(
        (pokemon / "species_info.h").read_text().replace(
            "};",
            """    [SPECIES_DIGLETT_ALOLA] =
    {
        .baseHP = 10,
    },
};""",
        ),
        encoding="utf-8",
    )
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (root / "species" / "diglettalola.yaml").write_text(
        """\
name: Diglett (Alola)
chrooked_id: diglettalola
stats: { hp: 20 }
""",
        encoding="utf-8",
    )
    ruleset = Ruleset.load(root)

    resmap = build_resolution_map(target, ruleset)

    assert resmap.species("diglettalola", {}) == "SPECIES_DIGLETT_ALOLA"
