"""Tier-applier tests for the Essentials 16.2 dialect (issue #21).

These cover the five acceptance criteria of the 16.2 data tier:

  ac1  applying a Ruleset (species stat+type+ability, a move scalar, a type-chart
       override) to a 16.2 fixture writes the correct fields, routed through
       `_apply_essentials162`.
  ac2  parity: BaseStats Speed-is-index-3 (HP,Atk,Def,Spe,SpA,SpD) and the moves.txt
       scalar column indices (power=4, type=5, category=6, accuracy=7, pp=8, priority=11).
  ac3  mono-type species emit only Type1 (Type2 dropped); HiddenAbility is singular.
  ac4  brand-new rows (a new move / species) are appended, not silently dropped.
  ac5  type-chart edits land on the DEFENDER section's buckets.

Each test copies the committed byte-faithful fixtures into a tmp PBS dir so the
appliers read/write real files, mirroring how the v21 appliers are exercised.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from chrooked_pokedex.appliers.essentials162 import (
    ability_apply,
    csv_io,
    evolution_apply,
    learnset_apply,
    move_apply,
    pbs_io,
    resolution,
    section_edit,
    section_read,
    species_apply,
    type_chart_apply,
)
from chrooked_pokedex.model.schema import (
    AbilitiesOverride,
    AbilityDef,
    AdditionalEffect,
    EvolutionOverride,
    LearnsetMove,
    MoveDef,
    SpeciesOverride,
    TypeChartOverride,
)
from chrooked_pokedex.report import ApplyReport

_FIXTURES = Path(__file__).parent / "fixtures" / "essentials162"


# --- helpers ----------------------------------------------------------------------


class _Ruleset:
    """A minimal stand-in for the neutral Ruleset the appliers consume.

    The real Ruleset is loaded from YAML; for these unit tests we just need the
    attribute surface the appliers touch: `.species`, `.moves`, `.type_chart`,
    `owned_move`, `owned_species`.
    """

    def __init__(self, species=None, moves=None, type_chart=None, abilities=None):
        self.species = species or {}
        self.moves = moves or {}
        self.type_chart = type_chart or []
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


def _species_block(target: Path, internal: str) -> str:
    text, _ = pbs_io.read(target / "PBS" / "pokemon.txt")
    span = section_edit.find_section_by_internalname(text, internal)
    assert span is not None
    return text[span[0]:span[1]]


def _field(target: Path, internal: str, key: str) -> str | None:
    return section_edit.get_field(_species_block(target, internal), key)


def _move_col(target: Path, internal: str, index: int) -> str | None:
    text, _ = pbs_io.read(target / "PBS" / "moves.txt")
    return csv_io.get_column(text, internal, index)


def _type_block(target: Path, internal: str) -> str:
    text, _ = pbs_io.read(target / "PBS" / "types.txt")
    span = section_edit.find_section_by_internalname(text, internal)
    assert span is not None
    return text[span[0]:span[1]]


# --- ac1: species scalars write correct fields ------------------------------------


def test_species_writes_types_stats_abilities(tmp_path):
    target = _target(tmp_path)
    ruleset = _Ruleset(species={
        "bulbasaur": SpeciesOverride(
            name="Bulbasaur", chrooked_id="bulbasaur",
            aka={"essentials": "BULBASAUR"},
            types=("Fire", "Flying"),
            stats={"spe": 99, "atk": 88},
            abilities=AbilitiesOverride(primary="Stench", hidden="Drizzle"),
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = species_apply.apply_species(target, ruleset, resmap, report)

    assert changed
    assert _field(target, "BULBASAUR", "Type1") == "FIRE"
    assert _field(target, "BULBASAUR", "Type2") == "FLYING"
    # BaseStats parity: HP,Atk,Def,Spe,SpA,SpD -> spe@3, atk@1
    assert _field(target, "BULBASAUR", "BaseStats") == "45,88,49,99,65,65"
    assert _field(target, "BULBASAUR", "Abilities") == "STENCH"
    assert _field(target, "BULBASAUR", "HiddenAbility") == "DRIZZLE"


# --- ac2: BaseStats Speed-is-index-3 parity ---------------------------------------


def test_basestats_speed_is_index_3(tmp_path):
    target = _target(tmp_path)
    ruleset = _Ruleset(species={
        "bulbasaur": SpeciesOverride(
            name="Bulbasaur", chrooked_id="bulbasaur",
            aka={"essentials": "BULBASAUR"},
            stats={"spe": 7},
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    species_apply.apply_species(target, ruleset, resmap, ApplyReport())
    # original 45,49,49,45,65,65 -> index 3 (was 45) becomes 7
    parts = _field(target, "BULBASAUR", "BaseStats").split(",")
    assert parts[3] == "7"
    assert parts == ["45", "49", "49", "7", "65", "65"]


def test_species_stat_index_map_is_canonical():
    # Explicit parity assertion on the index map the applier uses.
    assert species_apply._STAT_KEY_TO_INDEX == {
        "hp": 0, "atk": 1, "def": 2, "spe": 3, "spa": 4, "spd": 5
    }


# --- ac2: moves.txt scalar column indices -----------------------------------------


def test_move_scalar_column_indices(tmp_path):
    target = _target(tmp_path)
    ruleset = _Ruleset(moves={
        "megahorn": MoveDef(
            name="Megahorn", chrooked_id="megahorn", type="Fire",
            category="special", power=130, accuracy=90, pp=8, priority=2,
            aka={"essentials": "MEGAHORN"},
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = move_apply.apply_moves(target, ruleset, resmap, report)

    assert changed
    assert _move_col(target, "MEGAHORN", 4) == "130"      # power
    assert _move_col(target, "MEGAHORN", 5) == "FIRE"     # type
    assert _move_col(target, "MEGAHORN", 6) == "Special"  # category
    assert _move_col(target, "MEGAHORN", 7) == "90"       # accuracy
    assert _move_col(target, "MEGAHORN", 8) == "8"        # pp
    assert _move_col(target, "MEGAHORN", 11) == "2"       # priority


def test_move_column_map_is_canonical():
    assert move_apply._COLUMN == {
        "power": 4, "type": 5, "category": 6, "accuracy": 7, "pp": 8, "priority": 11
    }


def test_move_leaves_untouched_columns_intact(tmp_path):
    target = _target(tmp_path)
    before_desc = _move_col(target, "MEGAHORN", 13)
    before_func = _move_col(target, "MEGAHORN", 3)
    before_flags = _move_col(target, "MEGAHORN", 12)
    ruleset = _Ruleset(moves={
        "megahorn": MoveDef(
            name="Megahorn", chrooked_id="megahorn", type="Bug",
            category="physical", power=130, aka={"essentials": "MEGAHORN"},
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    move_apply.apply_moves(target, ruleset, resmap, ApplyReport())
    # funccode(3), flags(12), desc(13) are #22's job — untouched here.
    assert _move_col(target, "MEGAHORN", 13) == before_desc
    assert _move_col(target, "MEGAHORN", 3) == before_func
    assert _move_col(target, "MEGAHORN", 12) == before_flags


# --- ac3: mono-type drops Type2; HiddenAbility singular ----------------------------


def test_monotype_drops_type2(tmp_path):
    target = _target(tmp_path)
    assert _field(target, "BULBASAUR", "Type2") == "POISON"  # starts dual
    ruleset = _Ruleset(species={
        "bulbasaur": SpeciesOverride(
            name="Bulbasaur", chrooked_id="bulbasaur",
            aka={"essentials": "BULBASAUR"},
            types=("Fire",),
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    species_apply.apply_species(target, ruleset, resmap, ApplyReport())
    assert _field(target, "BULBASAUR", "Type1") == "FIRE"
    assert _field(target, "BULBASAUR", "Type2") is None  # dropped, not blank


def test_hidden_ability_is_single_value(tmp_path):
    target = _target(tmp_path)
    ruleset = _Ruleset(species={
        "bulbasaur": SpeciesOverride(
            name="Bulbasaur", chrooked_id="bulbasaur",
            aka={"essentials": "BULBASAUR"},
            abilities=AbilitiesOverride(hidden="Chlorophyll"),
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    species_apply.apply_species(target, ruleset, resmap, ApplyReport())
    hidden = _field(target, "BULBASAUR", "HiddenAbility")
    assert hidden == "CHLOROPHYLL"
    assert "," not in hidden  # never a comma list


def test_remove_section_field_helper(tmp_path):
    target = _target(tmp_path)
    text, _ = pbs_io.read(target / "PBS" / "pokemon.txt")
    new, removed = section_edit.remove_section_field(text, "BULBASAUR", "Type2")
    assert removed is True
    span = section_edit.find_section_by_internalname(new, "BULBASAUR")
    assert section_edit.get_field(new[span[0]:span[1]], "Type2") is None
    # neighbor section untouched
    ivy_b = section_edit.find_section_by_internalname(text, "IVYSAUR")
    ivy_a = section_edit.find_section_by_internalname(new, "IVYSAUR")
    assert text[ivy_b[0]:ivy_b[1]] == new[ivy_a[0]:ivy_a[1]]


# --- ac4: brand-new rows are created ----------------------------------------------


def test_new_move_appends_row(tmp_path):
    target = _target(tmp_path)
    before_max = csv_io.max_index((tmp_path / "PBS" / "moves.txt").read_text(encoding="utf-8"))
    ruleset = _Ruleset(moves={
        "excalibur": MoveDef(
            name="Excalibur", chrooked_id="excalibur", type="Steel",
            category="physical", power=120, accuracy=100, pp=5, priority=0,
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = move_apply.apply_moves(target, ruleset, resmap, report)

    assert changed
    text, _ = pbs_io.read(target / "PBS" / "moves.txt")
    assert csv_io.find_row(text, "EXCALIBUR") is not None
    assert csv_io.max_index(text) == before_max + 1
    assert csv_io.get_column(text, "EXCALIBUR", 4) == "120"
    assert csv_io.get_column(text, "EXCALIBUR", 5) == "STEEL"


def test_new_species_appends_section(tmp_path):
    target = _target(tmp_path)
    text, _ = pbs_io.read(target / "PBS" / "pokemon.txt")
    before_max = section_read.max_index(text)
    ruleset = _Ruleset(species={
        "faketron": SpeciesOverride(
            name="Faketron", chrooked_id="faketron",
            types=("Normal",),
            stats={"hp": 50, "atk": 50, "def": 50, "spe": 50, "spa": 50, "spd": 50},
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = species_apply.apply_species(target, ruleset, resmap, report)

    assert changed
    text, _ = pbs_io.read(target / "PBS" / "pokemon.txt")
    assert section_read.max_index(text) == before_max + 1
    assert _field(target, "FAKETRON", "Type1") == "NORMAL"
    assert _field(target, "FAKETRON", "Type2") is None  # mono-type new species
    assert _field(target, "FAKETRON", "BaseStats") == "50,50,50,50,50,50"


# --- ac5: type-chart edits land on the defender -----------------------------------


def test_type_chart_writes_defender_bucket(tmp_path):
    target = _target(tmp_path)
    # Fairy->Bug = super effective (2x). In 16.2 this lands on BUG's Weaknesses bucket;
    # but our fixture types are NORMAL/FIGHTING/FLYING. Use FLYING as defender.
    ruleset = _Ruleset(type_chart=[
        TypeChartOverride(attacker="Fighting", defender="Flying", multiplier=2.0),
    ])
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = type_chart_apply.apply_type_chart(target, ruleset, resmap, report)

    assert changed
    block = _type_block(target, "FLYING")  # edit lands on the DEFENDER
    weaknesses = section_edit.get_field(block, "Weaknesses")
    assert "FIGHTING" in weaknesses.split(",")


def test_type_chart_neutral_clears_all_buckets(tmp_path):
    target = _target(tmp_path)
    # FLYING resists FIGHTING by default; a neutral override should clear it.
    ruleset = _Ruleset(type_chart=[
        TypeChartOverride(attacker="Fighting", defender="Flying", multiplier=1.0),
    ])
    resmap = resolution.build_resolution_map(target, ruleset)
    type_chart_apply.apply_type_chart(target, ruleset, resmap, ApplyReport())
    block = _type_block(target, "FLYING")
    resistances = section_edit.get_field(block, "Resistances") or ""
    assert "FIGHTING" not in resistances.split(",")


# --- learnset + evolution (16.2 flat lines) ---------------------------------------


def test_learnset_rewrites_flat_moves_line(tmp_path):
    target = _target(tmp_path)
    ruleset = _Ruleset(species={
        "bulbasaur": SpeciesOverride(
            name="Bulbasaur", chrooked_id="bulbasaur",
            aka={"essentials": "BULBASAUR"},
            learnset=(LearnsetMove(level=1, move="Megahorn"),
                      LearnsetMove(level=5, move="Bugbuzz")),
        )
    })
    # Move names resolve by INTERNAL name (lowercased): MEGAHORN, BUGBUZZ in the fixture.
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = learnset_apply.apply_learnsets(target, ruleset, resmap, report)
    assert changed
    moves_line = _field(target, "BULBASAUR", "Moves")
    assert moves_line == "1,MEGAHORN,5,BUGBUZZ"


def test_evolution_writes_flat_triples_on_preevo(tmp_path):
    target = _target(tmp_path)
    # IVYSAUR evolves from BULBASAUR by level 16 -> lands on BULBASAUR's Evolutions line.
    ruleset = _Ruleset(species={
        "ivysaur": SpeciesOverride(
            name="Ivysaur", chrooked_id="ivysaur",
            aka={"essentials": "IVYSAUR"},
            evolution=EvolutionOverride(
                from_species="Bulbasaur", method={"level": 18}
            ),
        ),
        "bulbasaur": SpeciesOverride(
            name="Bulbasaur", chrooked_id="bulbasaur",
            aka={"essentials": "BULBASAUR"},
        ),
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = evolution_apply.apply_evolutions(target, ruleset, resmap, report)
    assert changed
    evo_line = _field(target, "BULBASAUR", "Evolutions")
    assert evo_line == "IVYSAUR,Level,18"


# --- unresolved reporting (honesty) -----------------------------------------------


# --- ac1: end-to-end routing through _apply_essentials162 -------------------------


def test_apply_routes_through_essentials162(tmp_path):
    """A mixed Ruleset (species stat+type+ability, move scalar, type-chart) applied via
    the cli entry writes all three files and routes through `_apply_essentials162`."""
    from chrooked_pokedex.cli import _apply_essentials162
    from chrooked_pokedex.model import Ruleset

    target = _target(tmp_path)
    ruleset = Ruleset(
        species={
            "bulbasaur": SpeciesOverride(
                name="Bulbasaur", chrooked_id="bulbasaur",
                aka={"essentials": "BULBASAUR"},
                types=("Fire",),
                stats={"spe": 120},
                abilities=AbilitiesOverride(primary="Stench", hidden="Drizzle"),
            )
        },
        moves={
            "megahorn": MoveDef(
                name="Megahorn", chrooked_id="megahorn", type="Steel",
                category="physical", power=130, accuracy=95, pp=8,
                aka={"essentials": "MEGAHORN"},
            )
        },
        type_chart=(
            TypeChartOverride(attacker="Fighting", defender="Flying", multiplier=2.0),
        ),
    )
    report = ApplyReport()
    _apply_essentials162(target, "all", ruleset, report)

    # species
    assert _field(target, "BULBASAUR", "Type1") == "FIRE"
    assert _field(target, "BULBASAUR", "Type2") is None  # mono-type Type2 dropped
    assert _field(target, "BULBASAUR", "BaseStats").split(",")[3] == "120"
    assert _field(target, "BULBASAUR", "HiddenAbility") == "DRIZZLE"
    # move scalars
    assert _move_col(target, "MEGAHORN", 4) == "130"
    assert _move_col(target, "MEGAHORN", 5) == "STEEL"
    # type chart on defender
    block = _type_block(target, "FLYING")
    assert "FIGHTING" in (section_edit.get_field(block, "Weaknesses") or "").split(",")
    # the run produced applied entries (proves the tiers, not the no-op, ran)
    assert report.counts()["applied"] >= 1


def test_missing_species_reported_blocked(tmp_path):
    target = _target(tmp_path)
    ruleset = _Ruleset(species={
        "missingmon": SpeciesOverride(
            name="Missingmon", chrooked_id="missingmon",
            aka={"essentials": "MISSINGMON"},
            stats={"hp": 1},
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    species_apply.apply_species(target, ruleset, resmap, report)
    # No aka match and not creating (it has only a stat override on absent species)
    statuses = [(e.category, e.status) for e in report.entries]
    assert ("species", "blocked") in statuses


# --- review-fanout regression: 2 HIGH findings (issue #21) ------------------------


def test_evolution_paramless_method_emits_aligned_triple(tmp_path):
    """A multi-branch source with one param-less `essentials` method must still emit
    3-token-aligned triples (empty param), not a 2-token branch that misaligns the
    whole Evolutions= line. Matches the real 16.2 shape `BRAMBLEGHAST,Happiness,`."""
    target = _target(tmp_path)
    # IVYSAUR exists in the fixture, so the branch is kept; a param-less essentials
    # method must still produce a 3-token triple with an empty param token.
    ruleset = _Ruleset(species={
        "ivysaur": SpeciesOverride(
            name="Ivysaur", chrooked_id="ivysaur", aka={"essentials": "IVYSAUR"},
            evolution=EvolutionOverride(
                from_species="Bulbasaur", method={"essentials": "Happiness"}
            ),
        ),
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    evolution_apply.apply_evolutions(target, ruleset, resmap, ApplyReport())
    tokens = _field(target, "BULBASAUR", "Evolutions").split(",")
    assert len(tokens) % 3 == 0, tokens  # aligned triple, not a 2-token branch
    assert tokens[:3] == ["IVYSAUR", "Happiness", ""]  # param-less -> empty param token


def test_new_species_blocked_when_a_type_is_unresolved(tmp_path):
    """A brand-new dual-type species whose 2nd type does not exist in the target must
    be BLOCKED — never created mono-typed (which would silently mis-type it)."""
    target = _target(tmp_path)
    text, _ = pbs_io.read(target / "PBS" / "pokemon.txt")
    before_max = section_read.max_index(text)
    ruleset = _Ruleset(species={
        "faketron": SpeciesOverride(
            name="Faketron", chrooked_id="faketron",
            types=("Normal", "Galaxy"),  # Galaxy is not a type in the fixture
            stats={"hp": 50, "atk": 50, "def": 50, "spe": 50, "spa": 50, "spd": 50},
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    species_apply.apply_species(target, ruleset, resmap, report)

    text, _ = pbs_io.read(target / "PBS" / "pokemon.txt")
    assert section_read.max_index(text) == before_max  # NOT created
    assert section_edit.find_section_by_internalname(text, "FAKETRON") is None
    statuses = [(e.category, e.status) for e in report.entries]
    assert ("species", "blocked") in statuses


# --- review-fanout regression: 2 MED findings (issue #21) -------------------------


def test_move_present_under_unindexed_name_is_edited_not_duplicated(tmp_path):
    """A move present in the file but cited by a display name the ResolutionMap does
    not index (resolved instead via aka/name-derived internal) must be EDITED in
    place, never appended as a duplicate row."""
    target = _target(tmp_path)
    text, _ = pbs_io.read(target / "PBS" / "moves.txt")
    before_max = csv_io.max_index(text)
    ruleset = _Ruleset(moves={
        "bugbuzz": MoveDef(
            name="Bug Buzz", chrooked_id="bugbuzz", aka={"essentials": "BUGBUZZ"},
            type="Bug", category="special", power=99, accuracy=100, pp=10,
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    move_apply.apply_moves(target, ruleset, resmap, ApplyReport())

    text, _ = pbs_io.read(target / "PBS" / "moves.txt")
    assert csv_io.max_index(text) == before_max  # edited in place — no new/duplicate row
    assert _move_col(target, "BUGBUZZ", 4) == "99"  # power column was edited


def test_type_chart_noop_is_reported(tmp_path):
    """An already-correct type-chart override is reported (status applied, 'already in
    desired state'), not silently dropped."""
    target = _target(tmp_path)
    # FLYING already resists FIGHTING in the fixture, so a 0.5x override is a no-op.
    ruleset = _Ruleset(type_chart=[
        TypeChartOverride(attacker="Fighting", defender="Flying", multiplier=0.5),
    ])
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    type_chart_apply.apply_type_chart(target, ruleset, resmap, report)

    entries = [e for e in report.entries if e.category == "type-chart"]
    assert entries and entries[0].status == "applied"
    assert "already" in (entries[0].reason or "")


def test_unresolved_custom_ability_is_not_written(tmp_path):
    """An ability not defined in the target's abilities.txt (a custom ability like
    Chloroplast) must NOT be written as an undefined reference — Essentials would
    refuse to compile it. It is skipped and reported partial; #23 will define it."""
    target = _target(tmp_path)
    before = _field(target, "BULBASAUR", "Abilities")
    ruleset = _Ruleset(species={
        "bulbasaur": SpeciesOverride(
            name="Bulbasaur", chrooked_id="bulbasaur", aka={"essentials": "BULBASAUR"},
            abilities=AbilitiesOverride(primary="Chloroplast", hidden="Chloroplast"),
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    species_apply.apply_species(target, ruleset, resmap, report)

    assert "CHLOROPLAST" not in (_field(target, "BULBASAUR", "Abilities") or "")
    assert "CHLOROPLAST" not in (_field(target, "BULBASAUR", "HiddenAbility") or "")
    assert (_field(target, "BULBASAUR", "Abilities") or "") == (before or "")  # untouched
    species_entries = [e for e in report.entries if e.category == "species"]
    assert any(e.status == "partial" for e in species_entries)


def test_evolution_to_absent_species_is_dropped(tmp_path):
    """An evolution whose TARGET species is not in the target game (e.g. a Galarian
    form like WEEZINGGALAR) must NOT be written — it would reference an undefined
    PBSpecies and break compilation. The branch is dropped and reported."""
    target = _target(tmp_path)
    ruleset = _Ruleset(species={
        "galarmon": SpeciesOverride(
            name="Galarmon", chrooked_id="galarmon", aka={"essentials": "WEEZINGGALAR"},
            evolution=EvolutionOverride(from_species="Bulbasaur", method={"level": 30}),
        ),
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    evolution_apply.apply_evolutions(target, ruleset, resmap, report)

    evo_line = _field(target, "BULBASAUR", "Evolutions") or ""
    assert "WEEZINGGALAR" not in evo_line  # absent target species not written
    assert any(e.category == "evolution" and e.status == "partial" for e in report.entries)


def test_evolution_item_present_written_absent_dropped(tmp_path):
    """An Item-method branch is written when the target's items.txt has the item, and
    dropped + reported partial when it does not — writing an undefined PBItem (e.g. a
    Hisui BLACKAUGURITE) breaks compilation."""
    target = _target(tmp_path)
    # The fixture has no items.txt; supply one with METALCOAT present, BLACKAUGURITE absent.
    (target / "PBS" / "items.txt").write_text(
        "1,METALCOAT,Metal Coat,Metal Coats,1,2000,\"Boosts steel moves.\",2,0,0,\n",
        encoding="utf-8",
    )
    ruleset = _Ruleset(species={
        "scizor": SpeciesOverride(
            name="Scizor", chrooked_id="scizor", aka={"essentials": "IVYSAUR"},
            evolution=EvolutionOverride(
                from_species="Bulbasaur", method={"item": "Metal Coat"}
            ),
        ),
        "kleavor": SpeciesOverride(
            name="Kleavor", chrooked_id="kleavor", aka={"essentials": "VENUSAUR"},
            evolution=EvolutionOverride(
                from_species="Bulbasaur", method={"item": "Black Augurite"}
            ),
        ),
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    evolution_apply.apply_evolutions(target, ruleset, resmap, report)

    evo_line = _field(target, "BULBASAUR", "Evolutions") or ""
    assert "METALCOAT" in evo_line  # present item written
    assert "BLACKAUGURITE" not in evo_line  # absent item dropped
    assert any(e.category == "evolution" and e.status == "partial" for e in report.entries)


# --- helpers for ability tests ----------------------------------------------------


def _ability_col(target: Path, internal: str, index: int) -> str | None:
    text, _ = pbs_io.read(target / "PBS" / "abilities.txt")
    return csv_io.get_column(text, internal, index)


def _ability_row_count(target: Path, internal: str) -> int:
    """Count how many rows exist for a given internal name (should always be 0 or 1)."""
    text, _ = pbs_io.read(target / "PBS" / "abilities.txt")
    count = 0
    import re
    for match in re.finditer(r"^[^\r\n]*", text, re.MULTILINE):
        line = match.group(0)
        if not line:
            continue
        cols = csv_io.split_columns(line)
        if len(cols) > 1 and cols[1].strip() == internal:
            count += 1
    return count


def _ability_ruleset(abilities: dict) -> "_Ruleset":
    """Build a _Ruleset stand-in that also exposes `.abilities`."""
    rs = _Ruleset()
    rs.abilities = abilities
    return rs


# --- ac1: a new ability is written as a correct 16.2 row --------------------------


def test_new_ability_appends_correct_row(tmp_path):
    """A Ruleset ability absent from the fixture is appended with the next index,
    INTERNAL in col 1, display Name in col 2, quoted description in col 3. BOM/CRLF
    are preserved."""
    target = _target(tmp_path)
    text_before, had_bom = pbs_io.read(target / "PBS" / "abilities.txt")
    before_max = csv_io.max_index(text_before)

    ruleset = _ability_ruleset({
        "chloroplast": AbilityDef(
            name="Chloroplast",
            chrooked_id="chloroplast",
            description="Doubles Speed in sunlight.",
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = ability_apply.apply_abilities(target, ruleset, resmap, report)

    assert changed  # file was written

    raw = (target / "PBS" / "abilities.txt").read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf"  # BOM preserved
    assert b"\r\n" in raw              # CRLF preserved

    text, _ = pbs_io.read(target / "PBS" / "abilities.txt")
    span = csv_io.find_row(text, "CHLOROPLAST")
    assert span is not None, "row for CHLOROPLAST not found"

    assert csv_io.max_index(text) == before_max + 1          # next index
    assert _ability_col(target, "CHLOROPLAST", 0) == str(before_max + 1)  # col 0: idx
    assert _ability_col(target, "CHLOROPLAST", 1) == "CHLOROPLAST"         # col 1: INTERNAL
    assert _ability_col(target, "CHLOROPLAST", 2) == "Chloroplast"         # col 2: name
    assert _ability_col(target, "CHLOROPLAST", 3) == '"Doubles Speed in sunlight."'  # col 3: quoted desc

    entries = [e for e in report.entries if e.category == "ability"]
    assert entries and entries[0].status == "applied"


def test_new_ability_aka_hint_used_as_internal(tmp_path):
    """When an ability has an `aka.essentials` hint, that hint is used as the INTERNAL
    name rather than the vocab-derived one."""
    target = _target(tmp_path)
    ruleset = _ability_ruleset({
        "ice_scales": AbilityDef(
            name="Ice Scales",
            chrooked_id="ice_scales",
            description="Halves special damage.",
            aka={"essentials": "ICESCALES"},
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    ability_apply.apply_abilities(target, ruleset, resmap, ApplyReport())

    assert _ability_col(target, "ICESCALES", 1) == "ICESCALES"


# --- ac3: edit-vs-create dedupe and no-op -----------------------------------------


def test_existing_ability_edited_not_duplicated(tmp_path):
    """Applying an ability already in the fixture (STENCH) with a changed description
    edits col 3 in place — one row, no duplicate appended."""
    target = _target(tmp_path)
    text_before, _ = pbs_io.read(target / "PBS" / "abilities.txt")
    before_max = csv_io.max_index(text_before)

    ruleset = _ability_ruleset({
        "stench": AbilityDef(
            name="Stench",
            chrooked_id="stench",
            description="Updated stench description.",
            aka={"essentials": "STENCH"},
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = ability_apply.apply_abilities(target, ruleset, resmap, report)

    assert changed  # description was updated

    text, _ = pbs_io.read(target / "PBS" / "abilities.txt")
    assert csv_io.max_index(text) == before_max          # no new row appended
    assert _ability_row_count(target, "STENCH") == 1     # still exactly one row

    new_desc = _ability_col(target, "STENCH", 3)
    assert new_desc == '"Updated stench description."'

    entries = [e for e in report.entries if e.category == "ability"]
    assert entries and entries[0].status == "applied"
    assert "description" in entries[0].reason


def test_identical_apply_is_noop(tmp_path):
    """A second identical apply (same name, same description) makes no change and emits
    no report lines — pure idempotence."""
    target = _target(tmp_path)
    # Read what the fixture already has for STENCH
    orig_desc = _ability_col(target, "STENCH", 3)   # e.g. '"Debido al mal olor..."'
    orig_name = _ability_col(target, "STENCH", 2)   # e.g. "Hedor"

    ruleset = _ability_ruleset({
        "stench": AbilityDef(
            name=orig_name,
            chrooked_id="stench",
            description=orig_desc.strip('"'),   # strip the existing quotes for the model field
            aka={"essentials": "STENCH"},
        )
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = ability_apply.apply_abilities(target, ruleset, resmap, report)

    assert not changed  # file unchanged
    ability_entries = [e for e in report.entries if e.category == "ability"]
    assert ability_entries == []  # no churn, no report line


# --- ac2: ability registers so species slot resolves --------------------------------


def test_brand_new_ability_resolves_species_slot(tmp_path):
    """Full apply: a species cites a brand-new Ruleset ability. The abilities tier runs
    first, writes the row, registers it in resmap, and the species tier then resolves
    the slot. Report shows applied, not partial with 'ability:NAME'."""
    from chrooked_pokedex.cli import _apply_essentials162
    from chrooked_pokedex.model import Ruleset

    target = _target(tmp_path)
    ruleset = Ruleset(
        abilities={
            "chloroplast": AbilityDef(
                name="Chloroplast",
                chrooked_id="chloroplast",
                description="Doubles Speed in sunlight.",
            )
        },
        species={
            "bulbasaur": SpeciesOverride(
                name="Bulbasaur", chrooked_id="bulbasaur",
                aka={"essentials": "BULBASAUR"},
                abilities=AbilitiesOverride(primary="Chloroplast"),
            )
        },
    )
    report = ApplyReport()
    _apply_essentials162(target, "all", ruleset, report)

    # The Abilities= field must have CHLOROPLAST (not empty / not the old value).
    abilities_field = _field(target, "BULBASAUR", "Abilities")
    assert abilities_field is not None
    assert "CHLOROPLAST" in abilities_field.split(",")

    # The species entry must be applied, not partial with 'ability:Chloroplast'.
    species_entries = [e for e in report.entries if e.category == "species"]
    assert species_entries, "no species report entries found"
    assert all(e.status == "applied" for e in species_entries), (
        f"expected all applied, got: {[(e.status, e.partial_fields) for e in species_entries]}"
    )


# --- issue #22: effect-resolution tables ------------------------------------------
#
# ac1  representative effect/secondary -> funccode mappings (cribbed from the game).
# ac2  flag-letter + target-hex legends render to the right columns.
# ac3  standard-pattern moves write all four behavior columns (not placeholders).
# ac4  an unmappable effect -> unresolved/partial, funccode stays 000 (nothing faked).


def _new_move_ruleset(move: MoveDef) -> "_Ruleset":
    return _Ruleset(moves={move.chrooked_id: move})


# --- ac1: the cribbed funccode tables ---------------------------------------------


def test_effect_to_funccode_representative_mappings():
    from chrooked_pokedex.appliers.essentials162 import effect_tables as et

    assert et.EFFECT_TO_FUNCCODE["multi_hit"] == "0C0"
    assert et.EFFECT_TO_FUNCCODE["ohko"] == "070"
    assert et.EFFECT_TO_FUNCCODE["absorb"] == "0DD"
    assert et.EFFECT_TO_FUNCCODE["roar"] == "0EB"
    assert et.EFFECT_TO_FUNCCODE["triple_kick"] == "0BF"


def test_secondary_to_funccode_representative_mappings():
    from chrooked_pokedex.appliers.essentials162 import effect_tables as et

    assert et.SECONDARY_TO_FUNCCODE["burn"] == "00A"
    assert et.SECONDARY_TO_FUNCCODE["paralysis"] == "007"
    assert et.SECONDARY_TO_FUNCCODE["flinch"] == "00F"
    assert et.SECONDARY_TO_FUNCCODE["spd_minus_1"] == "044"  # Speed, not SpAtk
    assert et.SECONDARY_TO_FUNCCODE["sp_atk_minus_1"] == "045"  # distinct from SpDef 046
    assert et.SECONDARY_TO_FUNCCODE["sp_def_minus_1"] == "046"


# --- ac2: flag-letter + target-hex legends ----------------------------------------


def test_flag_and_target_legends_render():
    from chrooked_pokedex.appliers.essentials162 import effect_tables as et

    # contact -> a, but slicing has no 16.2 letter in this engine -> dropped + noted.
    move = MoveDef(
        name="Pixie Slash", chrooked_id="pixieslash", type="Fairy",
        category="physical", power=80, flags=("contact", "slicing"), target="selected",
    )
    behavior = et.resolve_behavior(move)
    assert behavior is not None
    assert behavior.flags == "a"               # contact -> a; slicing dropped
    assert behavior.target == "00"             # selected -> 00
    assert et.dropped_flags(move) == ["slicing"]

    # A non-default target renders its hex.
    both = MoveDef(
        name="Overdrive", chrooked_id="overdrive", type="Electric",
        category="special", power=100, flags=("sound",), target="both",
    )
    both_behavior = et.resolve_behavior(both)
    assert both_behavior is not None
    assert both_behavior.target == "04"        # both -> 04 (all foes)
    assert both_behavior.flags == "k"          # sound -> k


# --- ac3: standard-pattern moves write all four behavior columns ------------------


def test_burn_on_hit_writes_all_behavior_columns(tmp_path):
    """Ember (hit + 10% burn) -> funccode 00A, chance 10, target 00 — a created row."""
    target = _target(tmp_path)
    move = MoveDef(
        name="Ember", chrooked_id="ember", type="Fire", category="special",
        power=45, accuracy=100, pp=25, aka={"essentials": "EMBER"},
        additional_effects=(AdditionalEffect(effect="burn", chance=10),),
    )
    resmap = resolution.build_resolution_map(target, _new_move_ruleset(move))
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, ApplyReport())
    assert _move_col(target, "EMBER", 3) == "00A"   # funccode (not 000)
    assert _move_col(target, "EMBER", 9) == "10"    # effectchance
    assert _move_col(target, "EMBER", 10) == "00"   # target


def test_stat_drop_on_hit_writes_funccode_and_chance(tmp_path):
    """A SpDef-drop secondary -> funccode 046 + its chance."""
    target = _target(tmp_path)
    move = MoveDef(
        name="Bug Buzz", chrooked_id="bugbuzz", type="Bug", category="special",
        power=90, accuracy=100, pp=10, aka={"essentials": "BUGBUZZ"},
        additional_effects=(AdditionalEffect(effect="sp_def_minus_1", chance=10),),
    )
    # BUGBUZZ exists in the fixture (func 046, chance 10) — this edits in place.
    resmap = resolution.build_resolution_map(target, _new_move_ruleset(move))
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, ApplyReport())
    assert _move_col(target, "BUGBUZZ", 3) == "046"
    assert _move_col(target, "BUGBUZZ", 9) == "10"


def test_flinch_with_both_target_writes_columns(tmp_path):
    """Twister (hit + 20% flinch, target both) -> 00F / 20 / 04 + wind dropped."""
    target = _target(tmp_path)
    move = MoveDef(
        name="Twister", chrooked_id="twister", type="Dragon", category="special",
        power=60, accuracy=100, pp=20, aka={"essentials": "TWISTER"},
        additional_effects=(AdditionalEffect(effect="flinch", chance=20),),
        flags=("wind",), target="both",
    )
    resmap = resolution.build_resolution_map(target, _new_move_ruleset(move))
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, ApplyReport())
    assert _move_col(target, "TWISTER", 3) == "00F"
    assert _move_col(target, "TWISTER", 9) == "20"
    assert _move_col(target, "TWISTER", 10) == "04"
    assert _move_col(target, "TWISTER", 12) == ""   # wind has no 16.2 letter -> dropped


def test_ohko_primary_writes_funccode(tmp_path):
    target = _target(tmp_path)
    move = MoveDef(
        name="Fissure", chrooked_id="fissure", type="Ground", category="physical",
        power=1, accuracy=30, pp=5, aka={"essentials": "FISSURE"}, effect="ohko",
    )
    resmap = resolution.build_resolution_map(target, _new_move_ruleset(move))
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, ApplyReport())
    assert _move_col(target, "FISSURE", 3) == "070"


def test_multi_hit_primary_writes_funccode(tmp_path):
    target = _target(tmp_path)
    move = MoveDef(
        name="Triple Hit", chrooked_id="triplehit", type="Normal", category="physical",
        power=20, accuracy=90, pp=10, aka={"essentials": "TRIPLEHIT"}, effect="multi_hit",
    )
    resmap = resolution.build_resolution_map(target, _new_move_ruleset(move))
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, ApplyReport())
    assert _move_col(target, "TRIPLEHIT", 3) == "0C0"


def test_semi_invulnerable_disambiguated_by_internal(tmp_path):
    """Fly resolves to its own per-move code 0C9 via the engine internal name."""
    target = _target(tmp_path)
    move = MoveDef(
        name="Fly", chrooked_id="fly", type="Flying", category="physical",
        accuracy=100, pp=15, aka={"essentials": "FLY"}, effect="semi_invulnerable",
        flags=("contact",),
    )
    resmap = resolution.build_resolution_map(target, _new_move_ruleset(move))
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, ApplyReport())
    assert _move_col(target, "FLY", 3) == "0C9"
    assert _move_col(target, "FLY", 12) == "a"  # contact -> a


# --- ac4: unmappable effect -> unresolved/partial, funccode stays 000 -------------


def test_super_effective_on_arg_is_unresolved(tmp_path):
    """Excalibur (super_effective_on_arg{Dragon}) has no generic 16.2 funccode — it is
    reported partial and the created row keeps funccode 000 (nothing fabricated)."""
    target = _target(tmp_path)
    move = MoveDef(
        name="Excalibur", chrooked_id="excalibur", type="Steel", category="physical",
        power=120, accuracy=80, pp=5, effect="super_effective_on_arg",
        argument={"type": "Dragon"}, flags=("contact", "slicing"),
    )
    resmap = resolution.build_resolution_map(target, _new_move_ruleset(move))
    report = ApplyReport()
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, report)

    assert _move_col(target, "EXCALIBUR", 3) == "000"  # plain-hit default kept
    entries = [e for e in report.entries if e.category == "move"]
    assert entries and entries[0].status == "partial"
    assert any("funccode" in (f or "") for f in entries[0].partial_fields)


def test_two_secondary_combo_without_bundled_code_is_unresolved(tmp_path):
    """A two-secondary combo with NO bundled 16.2 funccode and NO flinch-defer path stays
    unresolved — funccode stays 000, never approximated by dropping a secondary. (Two
    statuses with no flinch is not a fang combo and has no single code.)"""
    target = _target(tmp_path)
    move = MoveDef(
        name="Toxic Burn", chrooked_id="toxicburn", type="Fire", category="physical",
        power=65, accuracy=95, pp=15, aka={"essentials": "TOXICBURNCUSTOM"},
        additional_effects=(
            AdditionalEffect(effect="burn", chance=10),
            AdditionalEffect(effect="poison", chance=10),
        ),
        flags=("contact",),
    )
    resmap = resolution.build_resolution_map(target, _new_move_ruleset(move))
    report = ApplyReport()
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, report)

    assert _move_col(target, "TOXICBURNCUSTOM", 3) == "000"  # nothing fabricated
    entries = [e for e in report.entries if e.category == "move"]
    assert entries and entries[0].status == "partial"


def test_unmapped_secondary_is_unresolved(tmp_path):
    """freeze_or_frostbite has no 16.2 funccode in this engine -> unresolved (not faked
    as plain freeze, which would silently drop the frostbite half)."""
    target = _target(tmp_path)
    move = MoveDef(
        name="Glacial Crush", chrooked_id="glacialcrush", type="Ice", category="physical",
        power=80, accuracy=95, pp=10, aka={"essentials": "GLACIALCRUSHX"},
        additional_effects=(AdditionalEffect(effect="freeze_or_frostbite", chance=10),),
    )
    resmap = resolution.build_resolution_map(target, _new_move_ruleset(move))
    report = ApplyReport()
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, report)

    assert _move_col(target, "GLACIALCRUSHX", 3) == "000"
    entries = [e for e in report.entries if e.category == "move"]
    assert entries and entries[0].status == "partial"


# --- named-target PBS variant (Infinite Fusion 2) ---------------------------------
# IF2 spells col 10 as a NAME (NearOther) and carries engine-default flag letters
# (bef = protect/mirror/flinch). The hex-format applier was writing `00` into the
# named column and wiping those flags; these lock the named-aware behavior.


def test_resolve_behavior_named_targets():
    from chrooked_pokedex.appliers.essentials162 import effect_tables as et

    selected = MoveDef(
        name="Slash", chrooked_id="slash", type="Normal", category="physical",
        power=70, flags=("contact",), target="selected",
    )
    both = MoveDef(
        name="Gust Storm", chrooked_id="guststorm", type="Flying", category="special",
        power=60, flags=("sound",), target="both",
    )
    assert et.resolve_behavior(selected, named=True).target == "NearOther"
    assert et.resolve_behavior(both, named=True).target == "AllNearFoes"
    # hex format unchanged (default named=False).
    assert et.resolve_behavior(selected).target == "00"
    assert et.resolve_behavior(both).target == "04"


def test_merge_flags_is_additive_union():
    from chrooked_pokedex.appliers.essentials162 import effect_tables as et

    assert et.merge_flags("bef", "") == "bef"          # nothing added -> preserved
    assert et.merge_flags("bef", "a") == "abef"        # contact added, defaults kept
    assert et.merge_flags("abef", "j") == "abefj"      # punching added
    assert et.merge_flags("", "a") == "a"              # created row: no existing


def _named_target(tmp_path: Path) -> Path:
    """A target whose moves.txt uses NAMED targets + engine-default flags (IF2 shape)."""
    pbs = tmp_path / "PBS"
    pbs.mkdir()
    for name in ("pokemon.txt", "types.txt", "abilities.txt"):
        shutil.copy(_FIXTURES / name, pbs / name)
    (pbs / "moves.txt").write_text(
        "﻿1,ABSORB,Absorber,0DD,20,GRASS,Special,100,25,0,NearOther,0,bef,"
        '"Drena PS."\r\n'
        "2,TWISTER,Tornado,00F,40,DRAGON,Special,100,20,20,AllNearFoes,0,bef,"
        '"Tornado."\r\n'
        "3,BRAVEBIRD,Pájaro Osado,0FB,120,FLYING,Physical,100,15,0,NearOther,0,abef,"
        '"Carga con retroceso."\r\n',
        encoding="utf-8",
    )
    return tmp_path


def test_named_edit_preserves_target_and_flags(tmp_path):
    """Retuning a default-target move on a named-format file must NOT write `00` into
    col 10 and must NOT wipe the row's engine-default flags."""
    target = _named_target(tmp_path)
    move = MoveDef(
        name="Absorb", chrooked_id="absorb", type="Grass", category="special",
        power=20, accuracy=100, pp=25, effect="absorb", target="selected",
        aka={"essentials": "ABSORB"},
    )
    resmap = resolution.ResolutionMap(
        type_by_name={"grass": "GRASS"}, move_by_name={"absorb": "ABSORB"}
    )
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, ApplyReport())

    assert _move_col(target, "ABSORB", 10) == "NearOther"  # not 00
    assert _move_col(target, "ABSORB", 12) == "bef"        # flags preserved, not wiped
    assert _move_col(target, "ABSORB", 3) == "0DD"         # absorb funccode written


def test_named_edit_writes_named_multitarget(tmp_path):
    """A `both`-target retune writes the NAMED multi-foe constant, not hex 04."""
    target = _named_target(tmp_path)
    move = MoveDef(
        name="Twister", chrooked_id="twister", type="Dragon", category="special",
        power=40, accuracy=100, pp=20, target="both",
        additional_effects=(AdditionalEffect(effect="flinch", chance=20),),
        aka={"essentials": "TWISTER"},
    )
    resmap = resolution.ResolutionMap(
        type_by_name={"dragon": "DRAGON"}, move_by_name={"twister": "TWISTER"}
    )
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, ApplyReport())
    assert _move_col(target, "TWISTER", 10) == "AllNearFoes"  # not 04
    assert _move_col(target, "TWISTER", 12) == "bef"          # preserved


def test_named_create_uses_named_default_target(tmp_path):
    """A move IF2 lacks is created with a NAMED default target, never hex 00."""
    target = _named_target(tmp_path)
    move = MoveDef(
        name="Astral Hand", chrooked_id="astralhand", type="Ghost", category="special",
        power=70, accuracy=100, pp=10, target="selected",
        aka={"essentials": "ASTRALHAND"},
    )
    resmap = resolution.ResolutionMap(type_by_name={"ghost": "GHOST"})
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, ApplyReport())
    assert _move_col(target, "ASTRALHAND", 10) == "NearOther"


def test_specifies_effect_distinguishes_effect_from_flag_only():
    from chrooked_pokedex.appliers.essentials162 import effect_tables as et

    flags_only = MoveDef(
        name="Brave Bird", chrooked_id="bravebird", type="Flying", category="physical",
        power=120, flags=("contact",), target="selected",
    )
    has_effect = MoveDef(
        name="Absorb", chrooked_id="absorb", type="Grass", category="special",
        power=20, effect="absorb",
    )
    has_secondary = MoveDef(
        name="Ember", chrooked_id="ember", type="Fire", category="special", power=40,
        additional_effects=(AdditionalEffect(effect="burn", chance=10),),
    )
    assert et.specifies_effect(flags_only) is False
    assert et.specifies_effect(has_effect) is True
    assert et.specifies_effect(has_secondary) is True


def test_edit_without_effect_intent_preserves_funccode(tmp_path):
    """#22 AC4 — never silently wrong: a move the Ruleset only retunes for stats/flags
    must keep its existing funccode, never flattened to plain 000 (Brave Bird keeps its
    recoil code 0FB)."""
    target = _named_target(tmp_path)
    move = MoveDef(
        name="Brave Bird", chrooked_id="bravebird", type="Flying", category="physical",
        power=120, accuracy=100, pp=15, flags=("contact",), target="selected",
        aka={"essentials": "BRAVEBIRD"},
    )
    resmap = resolution.ResolutionMap(
        type_by_name={"flying": "FLYING"}, move_by_name={"bravebird": "BRAVEBIRD"}
    )
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, ApplyReport())
    assert _move_col(target, "BRAVEBIRD", 3) == "0FB"   # recoil code preserved, not 000
    assert _move_col(target, "BRAVEBIRD", 12) == "abef"  # flags intact


def test_edit_with_mapped_effect_still_writes_funccode(tmp_path):
    """The guard only spares unspecified effects — a move that DOES name a mapped effect
    still has its funccode written (Absorb -> 0DD)."""
    target = _named_target(tmp_path)
    move = MoveDef(
        name="Absorb", chrooked_id="absorb", type="Grass", category="special",
        power=20, accuracy=100, pp=25, effect="absorb", target="selected",
        aka={"essentials": "ABSORB"},
    )
    resmap = resolution.ResolutionMap(
        type_by_name={"grass": "GRASS"}, move_by_name={"absorb": "ABSORB"}
    )
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, ApplyReport())
    assert _move_col(target, "ABSORB", 3) == "0DD"


def test_absorb_percentage_selects_drain_funccode():
    """Drain is fraction-specific: 50% -> 0DD, 75% -> 14F. Default (no argument) is 50%;
    an unmapped fraction stays unresolved rather than draining the wrong amount (#22)."""
    from chrooked_pokedex.appliers.essentials162 import effect_tables as et

    def absorb(pct):
        arg = {"absorb_percentage": pct} if pct is not None else None
        return MoveDef(
            name="Drain", chrooked_id="drain", type="Grass", category="special",
            power=60, effect="absorb", argument=arg,
        )

    assert et.resolve_behavior(absorb(50)).funccode == "0DD"
    assert et.resolve_behavior(absorb(75)).funccode == "14F"
    assert et.resolve_behavior(absorb(None)).funccode == "0DD"   # default 50%
    assert et.resolve_behavior(absorb(25)) is None               # unmapped -> unresolved


# --- #22 effect-coverage expansion: cribbed singles + bundled combos ---------------


def test_new_primary_effect_table_rows():
    """Single-effect moves whose code sits in IF2's own file, now cribbed in."""
    from chrooked_pokedex.appliers.essentials162 import effect_tables as et

    def primary(effect):
        return MoveDef(
            name=effect, chrooked_id=effect, type="Normal", category="status",
            effect=effect,
        )
    assert et.resolve_behavior(primary("curse")).funccode == "10D"
    assert et.resolve_behavior(primary("moonlight")).funccode == "0D8"
    assert et.resolve_behavior(primary("attack_down_2")).funccode == "04B"


def test_semi_invulnerable_resolves_with_bundled_secondary():
    """Bounce's per-move code (0CC) already bundles its paralysis, so the secondary no
    longer blocks resolution; the secondary's chance carries to col 9."""
    from chrooked_pokedex.appliers.essentials162 import effect_tables as et

    bounce = MoveDef(
        name="Bounce", chrooked_id="bounce", type="Flying", category="physical",
        power=85, effect="semi_invulnerable", aka={"essentials": "BOUNCE"},
        additional_effects=(AdditionalEffect(effect="paralysis", chance=30),),
    )
    b = et.resolve_behavior(bounce)
    assert b.funccode == "0CC"
    assert b.effectchance == "30"


def test_status_plus_flinch_fang_combo():
    """A biting status+flinch move collapses to its bundled fang code; a biting
    stat-drop+flinch move emits the stat-drop code and defers flinch to the plugin."""
    from chrooked_pokedex.appliers.essentials162 import effect_tables as et

    def fang(status, chance=10, flags=("contact", "biting")):
        return MoveDef(
            name="Fang", chrooked_id="fang", type="Fire", category="physical", power=65,
            flags=flags,
            additional_effects=(
                AdditionalEffect(effect=status, chance=chance),
                AdditionalEffect(effect="flinch", chance=10),
            ),
        )
    fire = et.resolve_behavior(fang("burn"))
    assert fire.funccode == "00B" and fire.effectchance == "10"
    assert et.resolve_behavior(fang("paralysis")).funccode == "009"
    assert et.resolve_behavior(fang("freeze")).funccode == "00E"  # plain freeze, Ice Fang
    # stat-drop+flinch: engine does the drop (042), plugin adds flinch (reported deferred)
    drac = et.resolve_behavior(fang("atk_minus_1"))
    assert drac.funccode == "042" and drac.effectchance == "10"
    assert et.deferred_effects(fang("atk_minus_1")) == ["flinch -> chrooked_fangflinch plugin"]
    # a non-plain primary never resolves to a stat-drop code, so no deferred note either
    # (deferred_effects must mirror _resolve_funccode's is_plain gate).
    non_plain = MoveDef(
        name="Odd Fang", chrooked_id="oddfang", type="Dragon", category="physical", power=80,
        effect="ohko", flags=("contact", "biting"),
        additional_effects=(
            AdditionalEffect(effect="atk_minus_1", chance=10),
            AdditionalEffect(effect="flinch", chance=10),
        ),
    )
    assert et.resolve_behavior(non_plain) is None
    assert et.deferred_effects(non_plain) == []
    # frostbite naming has no clean code, and a status+flinch with no fang code -> None
    assert et.resolve_behavior(fang("freeze_or_frostbite")) is None
    # the fang code is gated on the biting flag: a non-biting burn+flinch move stays
    # unresolved rather than borrowing Fire Fang's code.
    assert et.resolve_behavior(fang("burn", flags=("contact",))) is None
    assert et.deferred_effects(fang("atk_minus_1", flags=("contact",))) == []


def test_created_damaging_move_without_power_is_flagged(tmp_path):
    """A created physical/special move with no power lands as 0 (engine demotes to Status);
    the applier must surface that as partial, not ship a silent dud."""
    target = _target(tmp_path)
    move = MoveDef(
        name="Ghost Wing", chrooked_id="ghostwing", type="Psychic", category="special",
        accuracy=100, pp=10, aka={"essentials": "GHOSTWINGCUSTOM"},
    )
    report = ApplyReport()
    resmap = resolution.build_resolution_map(target, _new_move_ruleset(move))
    move_apply.apply_moves(target, _new_move_ruleset(move), resmap, report)
    entry = [e for e in report.entries if e.category == "move"][0]
    assert entry.status == "partial"
    assert any("power 0" in f for f in entry.partial_fields)
