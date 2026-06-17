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

    def __init__(self, species=None, moves=None, type_chart=None):
        self.species = species or {}
        self.moves = moves or {}
        self.type_chart = type_chart or []

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
    ruleset = _Ruleset(species={
        "ivysaur": SpeciesOverride(
            name="Ivysaur", chrooked_id="ivysaur", aka={"essentials": "IVYSAUR"},
            evolution=EvolutionOverride(from_species="Bulbasaur", method={"level": 16}),
        ),
        "happymon": SpeciesOverride(
            name="Happymon", chrooked_id="happymon", aka={"essentials": "HAPPYMON"},
            evolution=EvolutionOverride(
                from_species="Bulbasaur", method={"essentials": "Happiness"}
            ),
        ),
    })
    resmap = resolution.build_resolution_map(target, ruleset)
    evolution_apply.apply_evolutions(target, ruleset, resmap, ApplyReport())
    tokens = _field(target, "BULBASAUR", "Evolutions").split(",")
    assert len(tokens) % 3 == 0, tokens  # every branch is an aligned triple
    triples = [tokens[i:i + 3] for i in range(0, len(tokens), 3)]
    assert ["HAPPYMON", "Happiness", ""] in triples  # param-less -> empty param token
    assert ["IVYSAUR", "Level", "16"] in triples


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
