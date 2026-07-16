"""Unit tests for the Rejuvenation applier (hermetic, in-repo fixture tree)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.rejuv import behavior_triage, definitions_read
from chrooked_pokedex.appliers.rejuv.apply import apply_rejuv
from chrooked_pokedex.appliers.rejuv.emit import Sym, montext_delta, to_ruby
from chrooked_pokedex.appliers.rejuv.resolution import RejuvResolution
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.behavior_spec import BehaviorSpec
from chrooked_pokedex.model.schema import (
    AbilitiesOverride,
    AbilityDef,
    LearnsetMove,
    MoveDef,
    SpeciesOverride,
)
from chrooked_pokedex.report import ApplyReport

FIXTURE = Path(__file__).parent / "fixtures" / "rejuv"
DEFS = FIXTURE / "Scripts" / "Rejuv" / "Definitions"

pytestmark = pytest.mark.unit


# --- to_ruby -----------------------------------------------------------------

def test_to_ruby_scalars():
    assert to_ruby(None) == "nil"
    assert to_ruby(True) == "true"
    assert to_ruby(42) == "42"
    assert to_ruby(Sym("GRASS")) == ":GRASS"
    assert to_ruby("hi") == '"hi"'


def test_to_ruby_escapes_quotes_and_backslash():
    assert to_ruby('a "b" \\c') == '"a \\"b\\" \\\\c"'


def test_to_ruby_nested_moveset():
    assert to_ruby([[1, Sym("TACKLE")], [3, Sym("VINEWHIP")]]) == "[[1, :TACKLE], [3, :VINEWHIP]]"


# --- scanners ----------------------------------------------------------------

def test_scan_monhash_keys_and_forms():
    keys = definitions_read.scan_monhash_keys(DEFS / "montext.rb")
    assert keys["BULBASAUR"] == ["Normal Form"]
    assert keys["ABSOL"] == ["Normal Form", "Mega Form"]


def test_scan_symbol_keys():
    assert definitions_read.scan_symbol_keys(DEFS / "movetext.rb") == {"TACKLE", "VINEWHIP", "HIJUMPKICK"}
    assert definitions_read.scan_symbol_keys(DEFS / "abiltext.rb") == {"OVERGROW", "CHLOROPHYLL"}


def test_max_ability_id():
    assert definitions_read.max_ability_id(DEFS / "abiltext.rb") == 65


# --- resolution --------------------------------------------------------------

def test_resolution_species_default_form():
    res = RejuvResolution.build(FIXTURE)
    assert res.species("bulbasaur", {}) == ("BULBASAUR", "Normal Form")


def test_resolution_species_mega_heuristic():
    res = RejuvResolution.build(FIXTURE)
    assert res.species("absolmega", {}) == ("ABSOL", "Mega Form")


def test_resolution_form_matcher_unambiguous():
    res = RejuvResolution.build(FIXTURE)
    # "megax" matches only "Mega X Form"; "megay" only "Mega Y Form".
    assert res.species("charizardmegax", {}) == ("CHARIZARD", "Mega X Form")
    assert res.species("charizardmegay", {}) == ("CHARIZARD", "Mega Y Form")


def test_resolution_form_matcher_ambiguous_blocks():
    res = RejuvResolution.build(FIXTURE)
    # "mega" matches BOTH Mega X and Mega Y forms -> ambiguous -> blocked, not guessed.
    assert res.species("charizardmega", {}) is None


def test_resolution_species_unresolved_blocks():
    res = RejuvResolution.build(FIXTURE)
    assert res.species("fakemon", {}) is None


def test_resolution_species_aka_hint():
    res = RejuvResolution.build(FIXTURE)
    assert res.species("whatever", {"rejuv": "ABSOL::Mega Form"}) == ("ABSOL", "Mega Form")


def test_resolution_move_and_ability():
    res = RejuvResolution.build(FIXTURE)
    assert res.move("Vine Whip") == "VINEWHIP"
    assert res.move("Nonexistent") is None
    assert res.ability("Overgrow") == "OVERGROW"
    assert res.ability("Chloroplast") is None


def test_resolution_move_by_name_index():
    # Symbol :HIJUMPKICK differs from slug("High Jump Kick")="highjumpkick";
    # the :name index resolves it where the symbol slug cannot.
    res = RejuvResolution.build(FIXTURE)
    assert res.move("High Jump Kick") == "HIJUMPKICK"
    assert res.move_symbol("High Jump Kick") == "HIJUMPKICK"


# --- montext emit ------------------------------------------------------------

def _species(**kw):
    return SpeciesOverride(name=kw.pop("name", "X"), chrooked_id=kw.pop("cid", "x"), **kw)


def _apply(ruleset: Ruleset, tmp: Path) -> tuple[ApplyReport, Path]:
    target = tmp / "game"
    shutil.copytree(FIXTURE, target)
    report = ApplyReport()
    apply_rejuv(target, ruleset, report)
    return report, target


def test_species_stats_emit_per_index(tmp_path):
    r = Ruleset(species={"absol": _species(cid="absol", stats={"atk": 160, "spe": 130})})
    report, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "montext.rb").read_text()
    assert 'MONHASH[:ABSOL]["Normal Form"][:BaseStats][1] = 160' in text
    assert 'MONHASH[:ABSOL]["Normal Form"][:BaseStats][5] = 130' in text
    assert any(e.status == "applied" and e.chrooked_id == "absol" for e in report.entries)


def test_form_lacking_array_is_seeded_from_base(tmp_path):
    # Charizard "Mega X Form" in the fixture has no :BaseStats/:Abilities of its own.
    # A per-index assign must seed the array from the base form first (no nil[]=).
    r = Ruleset(species={"charizardmegax": _species(
        cid="charizardmegax", stats={"atk": 130},
        abilities=AbilitiesOverride(primary="Blaze"),
    )})
    _, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "montext.rb").read_text()
    assert 'MONHASH[:CHARIZARD]["Mega X Form"][:BaseStats] ||= MONHASH[:CHARIZARD]["Normal Form"][:BaseStats].dup' in text
    assert 'MONHASH[:CHARIZARD]["Mega X Form"][:Abilities] ||= MONHASH[:CHARIZARD]["Normal Form"][:Abilities].dup' in text
    assert 'MONHASH[:CHARIZARD]["Mega X Form"][:BaseStats][1] = 130' in text


def test_species_dig_guard_wraps(tmp_path):
    r = Ruleset(species={"bulbasaur": _species(cid="bulbasaur", stats={"hp": 50})})
    _, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "montext.rb").read_text()
    assert 'if MONHASH.dig(:BULBASAUR, "Normal Form")' in text
    assert "else" in text and "skipped BULBASAUR" in text


def test_species_types_mono_sets_type2_nil(tmp_path):
    r = Ruleset(species={"absol": _species(cid="absol", types=("Dark",))})
    _, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "montext.rb").read_text()
    assert '[:Type1] = :DARK' in text
    assert '[:Type2] = nil' in text


def test_species_learnset_whole_replace(tmp_path):
    r = Ruleset(species={"bulbasaur": _species(
        cid="bulbasaur",
        learnset=(LearnsetMove(1, "Tackle"), LearnsetMove(5, "Vine Whip")),
    )})
    _, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "montext.rb").read_text()
    assert '[:Moveset] = [[1, :TACKLE], [5, :VINEWHIP]]' in text


def test_species_unresolved_blocks(tmp_path):
    r = Ruleset(species={"fakemon": _species(cid="fakemon", stats={"hp": 1})})
    report, target = _apply(r, tmp_path)
    assert any(e.status == "blocked" and e.chrooked_id == "fakemon" for e in report.entries)
    text = (target / "patch" / "Definitions" / "montext.rb").read_text()
    assert "fakemon" not in text.lower()


def test_species_ability_slot_and_new_ability_reference(tmp_path):
    # Bulbasaur gains a NEW ability "Chloroplast" (not in base) — resolvable because
    # the Ruleset also owns the AbilityDef, so it will exist after abiltext compiles.
    r = Ruleset(
        species={"bulbasaur": _species(
            cid="bulbasaur", abilities=AbilitiesOverride(primary="Chloroplast"),
        )},
        abilities={"chloroplast": AbilityDef(
            name="Chloroplast", chrooked_id="chloroplast", description="Moves act as if in sun.",
        )},
    )
    report, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "montext.rb").read_text()
    assert '[:Abilities][0] = :CHLOROPLAST' in text


# --- movetext emit -----------------------------------------------------------

def test_move_scalars_emit(tmp_path):
    r = Ruleset(moves={"tackle": MoveDef(
        name="Tackle", chrooked_id="tackle", type="Normal", category="physical",
        power=50, accuracy=100, pp=35,
    )})
    _, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "movetext.rb").read_text()
    assert "MOVEHASH[:TACKLE][:basedamage] = 50" in text
    assert "MOVEHASH[:TACKLE][:category] = :physical" in text


def test_new_move_created_with_next_id(tmp_path):
    # Base fixture max move ID is 3 (Tackle=1, Vine Whip=2, HiJumpKick=3), so a new move gets 4.
    r = Ruleset(moves={"madeup": MoveDef(
        name="Made Up", chrooked_id="madeup", type="Fire", category="special",
        power=90, accuracy=95, pp=10, description="A made-up move.", flags=("contact", "sound"),
    )})
    report, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "movetext.rb").read_text()
    assert "MOVEHASH[:MADEUP] = {" in text
    assert ":ID => 4" in text
    assert ":function => 0x000" in text
    assert ":type => :FIRE" in text
    assert ":basedamage => 90" in text
    assert ":contact => true" in text and ":soundmove => true" in text
    assert any("DATA ONLY" in e.reason and e.chrooked_id == "madeup" for e in report.entries)


def test_new_move_resolves_in_learnset(tmp_path):
    # A species learning a brand-new Ruleset move keeps it (known_moves includes owned).
    r = Ruleset(
        species={"bulbasaur": _species(
            cid="bulbasaur", learnset=(LearnsetMove(1, "Made Up"),),
        )},
        moves={"madeup": MoveDef(
            name="Made Up", chrooked_id="madeup", type="Fire", category="special", power=90,
        )},
    )
    report, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "montext.rb").read_text()
    assert "[:Moveset] = [[1, :MADEUP]]" in text
    assert not any(e.status == "partial" and e.chrooked_id == "bulbasaur" for e in report.entries)


# --- abiltext emit -----------------------------------------------------------

def test_existing_ability_patches_text(tmp_path):
    r = Ruleset(abilities={"overgrow": AbilityDef(
        name="Overgrow", chrooked_id="overgrow", description="New desc.",
    )})
    _, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "abiltext.rb").read_text()
    assert 'ABILHASH[:OVERGROW][:desc] = "New desc."' in text
    assert "ABILHASH[:OVERGROW] = {" not in text  # not recreated


def test_new_ability_allocates_noncolliding_id(tmp_path):
    r = Ruleset(abilities={"chloroplast": AbilityDef(
        name="Chloroplast", chrooked_id="chloroplast", description="Sun moves.",
    )})
    report, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "abiltext.rb").read_text()
    # base max ID is 65, so the new one is 66.
    assert "ABILHASH[:CHLOROPLAST] = { :ID => 66," in text
    assert any("DATA ONLY" in e.reason for e in report.entries)


# --- init + write invariants -------------------------------------------------

def test_init_script_written_with_three_pairs(tmp_path):
    r = Ruleset()
    _, target = _apply(r, tmp_path)
    init = (target / "patch" / "Init" / "chrooked_compile.rb").read_text()
    assert "compileMons" in init and "compileMoves" in init and "compileAbilities" in init
    assert "File.mtime(defn) > File.mtime(dat)" in init
    assert 'Dir.mkdir("patch/Data")' in init


def test_patch_data_dir_created(tmp_path):
    _, target = _apply(Ruleset(), tmp_path)
    assert (target / "patch" / "Data").is_dir()


def test_writes_only_game_data_under_patch(tmp_path):
    r = Ruleset(species={"absol": _species(cid="absol", stats={"atk": 160})})
    _, target = _apply(r, tmp_path)
    # Every generated Ruby file lives under patch/; only .md report artifacts at root.
    for p in target.rglob("*.rb"):
        rel = p.relative_to(target)
        if rel.parts[0] in ("Scripts",):  # base fixture files, untouched
            continue
        assert rel.parts[0] == "patch", f"generated {rel} escaped patch/"


def test_no_silent_drops(tmp_path):
    # Every in-scope entry appears in the report as applied/partial/blocked.
    r = Ruleset(
        species={
            "absol": _species(cid="absol", stats={"atk": 160}),
            "fakemon": _species(cid="fakemon", stats={"hp": 1}),
        },
    )
    report, _ = _apply(r, tmp_path)
    ids = {e.chrooked_id for e in report.entries}
    assert {"absol", "fakemon"} <= ids


# --- triage ------------------------------------------------------------------

def test_triage_buckets_are_exclusive_and_complete():
    res = RejuvResolution.build(FIXTURE)
    r = Ruleset(behaviors={
        "overgrow": BehaviorSpec(name="Overgrow", chrooked_id="overgrow", applies_to="ability"),
        "newab": BehaviorSpec(name="Newab", chrooked_id="newab", applies_to="ability"),
        "somemove": BehaviorSpec(name="Somemove", chrooked_id="somemove", applies_to="move"),
    })
    rows = behavior_triage.triage(r, res)
    assert len(rows) == 3
    by_id = {row.chrooked_id: row.bucket for row in rows}
    assert by_id["overgrow"] == behavior_triage.BUCKET_DATA_ONLY      # exists in base
    assert by_id["newab"] == behavior_triage.BUCKET_CUSTOM_CODE       # new ability
    assert by_id["somemove"] == behavior_triage.BUCKET_FUNCTION_CODE  # move
    md = behavior_triage.render_markdown(rows)
    assert "Total behaviors: 3" in md
