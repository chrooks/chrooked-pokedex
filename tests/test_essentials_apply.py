"""The Essentials Applier tiers: species, learnset, and owned-content creation.

Each tier mirrors its pokeemerald counterpart's Contract — `(target, ruleset,
resmap, report) -> set[Path]`, whole-field replacement, nothing silently dropped —
but writes Essentials PBS text. Tests run against tiny synthetic PBS files, the
same shape the existing applier tests use, so no real Essentials project is needed.
"""

from pathlib import Path

from chrooked_pokedex.appliers.essentials.creation import create_owned_content
from chrooked_pokedex.appliers.essentials.learnset_apply import apply_learnsets
from chrooked_pokedex.appliers.essentials.resolution import build_resolution_map
from chrooked_pokedex.appliers.essentials.species_apply import apply_species
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.schema import (
    AbilitiesOverride,
    AbilityDef,
    AdditionalEffect,
    LearnsetMove,
    MoveDef,
    SpeciesOverride,
)
from chrooked_pokedex.report import ApplyReport

_POKEMON = """\
[BULBASAUR]
Name = Bulbasaur
Types = GRASS,POISON
BaseStats = 45,49,49,45,65,65
Abilities = OVERGROW
HiddenAbilities = CHLOROPHYLL
Moves = 1,TACKLE,1,GROWL,3,VINEWHIP
"""

_MOVES = "[TACKLE]\nName = Tackle\n[GROWL]\nName = Growl\n[VINEWHIP]\nName = Vine Whip\n"
_ABILITIES = "[OVERGROW]\nName = Overgrow\n[CHLOROPHYLL]\nName = Chlorophyll\n[BLAZE]\nName = Blaze\n"
_TYPES = "[GRASS]\nName = Grass\n[POISON]\nName = Poison\n[FIRE]\nName = Fire\n[FAIRY]\nName = Fairy\n"


def _make_target(tmp_path: Path, pokemon: str = _POKEMON) -> Path:
    target = tmp_path / "essentials"
    pbs = target / "PBS"
    pbs.mkdir(parents=True)
    (pbs / "pokemon.txt").write_text(pokemon, encoding="utf-8")
    (pbs / "moves.txt").write_text(_MOVES, encoding="utf-8")
    (pbs / "abilities.txt").write_text(_ABILITIES, encoding="utf-8")
    (pbs / "types.txt").write_text(_TYPES, encoding="utf-8")
    return target


def _ruleset(**kw) -> Ruleset:
    return Ruleset(**kw)


def _section(target: Path, fname: str, header: str) -> str:
    from chrooked_pokedex.appliers.essentials import pbs_edit
    text = (target / "PBS" / fname).read_text(encoding="utf-8")
    span = pbs_edit.find_section(text, header)
    return text[span[0]:span[1]] if span else ""


def _field(target: Path, fname: str, header: str, key: str) -> str | None:
    from chrooked_pokedex.appliers.essentials import pbs_edit
    return pbs_edit.get_field(_section(target, fname, header), key)


# --- species -------------------------------------------------------------------

def test_species_applies_types_stats_abilities(tmp_path):
    target = _make_target(tmp_path)
    override = SpeciesOverride(
        name="Bulbasaur", chrooked_id="bulbasaur",
        aka={"essentials": "BULBASAUR"},
        types=("Grass", "Fairy"),
        stats={"spe": 99, "spa": 120},
        abilities=AbilitiesOverride(primary="Blaze"),
    )
    ruleset = _ruleset(species={"bulbasaur": override})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = apply_species(target, ruleset, resmap, report)

    assert (target / "PBS" / "pokemon.txt") in changed
    assert _field(target, "pokemon.txt", "BULBASAUR", "Types") == "GRASS,FAIRY"
    # Essentials BaseStats order is HP,ATK,DEF,SPEED,SPATK,SPDEF.
    assert _field(target, "pokemon.txt", "BULBASAUR", "BaseStats") == "45,49,49,99,120,65"
    assert _field(target, "pokemon.txt", "BULBASAUR", "Abilities") == "BLAZE"
    assert report.counts()["applied"] == 1


def test_species_blocked_when_absent(tmp_path):
    target = _make_target(tmp_path)
    override = SpeciesOverride(
        name="Missingno", chrooked_id="missingno",
        aka={"essentials": "MISSINGNO"}, types=("Fire",),
    )
    ruleset = _ruleset(species={"missingno": override})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_species(target, ruleset, resmap, report)
    assert report.counts()["blocked"] == 1


def test_species_partial_when_basestats_absent(tmp_path):
    # A stat Override against a section with no BaseStats line must be reported, not
    # silently dropped — the applier never edits what it cannot find.
    pokemon = "[BULBASAUR]\nName = Bulbasaur\nTypes = GRASS,POISON\n"  # no BaseStats
    target = _make_target(tmp_path, pokemon=pokemon)
    override = SpeciesOverride(
        name="Bulbasaur", chrooked_id="bulbasaur", aka={"essentials": "BULBASAUR"},
        stats={"spe": 99},
    )
    ruleset = _ruleset(species={"bulbasaur": override})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_species(target, ruleset, resmap, report)
    assert report.counts()["partial"] == 1
    entry = report.entries[0]
    assert any("stat:" in f for f in entry.partial_fields)


def test_species_partial_on_unresolved_ability(tmp_path):
    target = _make_target(tmp_path)
    override = SpeciesOverride(
        name="Bulbasaur", chrooked_id="bulbasaur", aka={"essentials": "BULBASAUR"},
        abilities=AbilitiesOverride(primary="Nonexistent Ability"),
    )
    ruleset = _ruleset(species={"bulbasaur": override})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_species(target, ruleset, resmap, report)
    assert report.counts()["partial"] == 1


# --- learnset ------------------------------------------------------------------

def test_learnset_replaces_moves_line(tmp_path):
    target = _make_target(tmp_path)
    override = SpeciesOverride(
        name="Bulbasaur", chrooked_id="bulbasaur", aka={"essentials": "BULBASAUR"},
        learnset=(LearnsetMove(level=1, move="Tackle"), LearnsetMove(level=7, move="Growl")),
    )
    ruleset = _ruleset(species={"bulbasaur": override})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_learnsets(target, ruleset, resmap, report)
    assert _field(target, "pokemon.txt", "BULBASAUR", "Moves") == "1,TACKLE,7,GROWL"
    assert report.counts()["applied"] == 1


def test_learnset_partial_when_move_missing(tmp_path):
    target = _make_target(tmp_path)
    override = SpeciesOverride(
        name="Bulbasaur", chrooked_id="bulbasaur", aka={"essentials": "BULBASAUR"},
        learnset=(LearnsetMove(level=1, move="Tackle"), LearnsetMove(level=5, move="Excalibur")),
    )
    ruleset = _ruleset(species={"bulbasaur": override})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_learnsets(target, ruleset, resmap, report)
    assert _field(target, "pokemon.txt", "BULBASAUR", "Moves") == "1,TACKLE"
    assert report.counts()["partial"] == 1


# --- creation ------------------------------------------------------------------

def test_create_owned_ability_appends_section(tmp_path):
    target = _make_target(tmp_path)
    ability = AbilityDef(name="Striker", chrooked_id="striker",
                         description="Boosts kicking moves.", aka={"essentials": "STRIKER"})
    ruleset = _ruleset(abilities={"striker": ability})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = create_owned_content(target, ruleset, resmap, report)
    assert (target / "PBS" / "abilities.txt") in changed
    assert _field(target, "abilities.txt", "STRIKER", "Name") == "Striker"
    assert _field(target, "abilities.txt", "STRIKER", "Description") == "Boosts kicking moves."
    # idempotent: a second run does not duplicate the section.
    create_owned_content(target, ruleset, resmap, ApplyReport())
    text = (target / "PBS" / "abilities.txt").read_text(encoding="utf-8")
    assert text.count("[STRIKER]") == 1


def test_create_owned_move_writes_fields_and_secondary(tmp_path):
    target = _make_target(tmp_path)
    move = MoveDef(
        name="Cinder Smash", chrooked_id="cindersmash", type="Fire", category="physical",
        power=90, accuracy=100, pp=10, description="A fiery smash.",
        aka={"essentials": "CINDERSMASH"},
        flags=("contact",),
        additional_effects=(AdditionalEffect(effect="burn", chance=10),),
        target="selected",
    )
    ruleset = _ruleset(moves={"cindersmash": move})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    create_owned_content(target, ruleset, resmap, report)
    assert _field(target, "moves.txt", "CINDERSMASH", "Type") == "FIRE"
    assert _field(target, "moves.txt", "CINDERSMASH", "Category") == "Physical"
    assert _field(target, "moves.txt", "CINDERSMASH", "Power") == "90"
    assert _field(target, "moves.txt", "CINDERSMASH", "Target") == "NearOther"
    assert _field(target, "moves.txt", "CINDERSMASH", "Flags") == "Contact"
    # the burn secondary becomes a FunctionCode + EffectChance.
    assert _field(target, "moves.txt", "CINDERSMASH", "FunctionCode") == "BurnTarget"
    assert _field(target, "moves.txt", "CINDERSMASH", "EffectChance") == "10"


def test_create_owned_move_marks_unmappable_flag_partial(tmp_path):
    target = _make_target(tmp_path)
    move = MoveDef(
        name="Bone Rush", chrooked_id="bonerush", type="Ground", category="physical",
        power=25, aka={"essentials": "BONERUSH"}, flags=("bone",),  # no Essentials flag
    )
    ruleset = _ruleset(moves={"bonerush": move})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    create_owned_content(target, ruleset, resmap, report)
    partial = [e for e in report.entries if e.status == "partial"]
    assert partial and any("flag" in f for e in partial for f in e.partial_fields)


def test_created_ability_with_behavior_spec_is_data_only(tmp_path):
    from chrooked_pokedex.model.behavior_spec import (
        BehaviorEffect, BehaviorSpec,
    )
    target = _make_target(tmp_path)
    ability = AbilityDef(name="Striker", chrooked_id="striker", aka={"essentials": "STRIKER"})
    spec = BehaviorSpec(
        name="Striker", chrooked_id="striker", applies_to="ability",
        effects=(BehaviorEffect(summary="boost kicks", trigger="damage-calc",
                                effect="multiply kicking move power by 1.3"),),
    )
    ruleset = _ruleset(abilities={"striker": ability}, behaviors={"striker": spec})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    create_owned_content(target, ruleset, resmap, report)
    striker = [e for e in report.entries if e.chrooked_id == "striker"][0]
    assert "DATA ONLY" in striker.reason
