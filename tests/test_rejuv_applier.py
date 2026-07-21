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
    EvolutionOverride,
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
    # No additional effects -> a plain 0x000 damage move is complete, no DATA ONLY.
    # reason must be exactly "" (str Contract) — a None here crashed the web
    # apply summary's reason.startswith().
    entry = next(e for e in report.entries if e.chrooked_id == "madeup")
    assert entry.status == "applied" and entry.reason == ""


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


# --- behavior installer (phase 3, M1) ----------------------------------------

def _harness(tmp: Path, files: dict[str, str]) -> Path:
    src = tmp / "harness"
    src.mkdir()
    for name, text in files.items():
        (src / name).write_text(text)
    return src


_CORE = "# chrooked:core\nCHROOKED_DAMAGE_MODS = {}\n"


def test_installer_copies_core_and_behavior(tmp_path):
    from chrooked_pokedex.appliers.rejuv.behavior_install import install_behaviors
    src = _harness(tmp_path, {
        "chrooked_00_core.rb": _CORE,
        "chrooked_sledgehammer.rb": "# chrooked:sledgehammer\nCHROOKED_DAMAGE_MODS[:SLEDGEHAMMER] = 1\n",
    })
    target = tmp_path / "game"
    shutil.copytree(FIXTURE, target)
    r = Ruleset(behaviors={"sledgehammer": BehaviorSpec(
        name="Sledgehammer", chrooked_id="sledgehammer", applies_to="ability")})
    report = ApplyReport()
    install_behaviors(target, r, report, source_dir=src)
    mods = target / "patch" / "Mods"
    assert (mods / "chrooked_00_core.rb").exists()
    assert (mods / "chrooked_sledgehammer.rb").exists()
    assert any(e.status == "applied" and e.chrooked_id == "sledgehammer"
               and "installed" in (e.reason or "") for e in report.entries)


def test_installer_absent_implementation_is_silent(tmp_path):
    from chrooked_pokedex.appliers.rejuv.behavior_install import install_behaviors
    src = _harness(tmp_path, {"chrooked_00_core.rb": _CORE})
    target = tmp_path / "game"
    shutil.copytree(FIXTURE, target)
    r = Ruleset(behaviors={"newab": BehaviorSpec(
        name="Newab", chrooked_id="newab", applies_to="ability")})
    report = ApplyReport()
    written = install_behaviors(target, r, report, source_dir=src)
    assert written == set()
    assert not (target / "patch" / "Mods").exists()
    assert not any(e.category == "behavior" for e in report.entries)


def test_installer_untagged_implementation_blocks(tmp_path):
    from chrooked_pokedex.appliers.rejuv.behavior_install import install_behaviors
    src = _harness(tmp_path, {
        "chrooked_00_core.rb": _CORE,
        "chrooked_badone.rb": "CHROOKED_DAMAGE_MODS[:BADONE] = 1\n",  # no tag
    })
    target = tmp_path / "game"
    shutil.copytree(FIXTURE, target)
    r = Ruleset(behaviors={"badone": BehaviorSpec(
        name="Badone", chrooked_id="badone", applies_to="ability")})
    report = ApplyReport()
    written = install_behaviors(target, r, report, source_dir=src)
    assert written == set()
    assert not (target / "patch" / "Mods").exists()
    assert any(e.status == "blocked" and e.chrooked_id == "badone" for e in report.entries)


def test_abiltext_drops_data_only_when_implemented(tmp_path):
    src = _harness(tmp_path, {
        "chrooked_00_core.rb": _CORE,
        "chrooked_sledgehammer.rb": "# chrooked:sledgehammer\nX = 1\n",
    })
    r = Ruleset(
        abilities={
            "sledgehammer": AbilityDef(name="Sledgehammer", chrooked_id="sledgehammer"),
            "newab": AbilityDef(name="Newab", chrooked_id="newab"),
        },
        behaviors={"sledgehammer": BehaviorSpec(
            name="Sledgehammer", chrooked_id="sledgehammer", applies_to="ability")},
    )
    target = tmp_path / "game"
    shutil.copytree(FIXTURE, target)
    report = ApplyReport()
    apply_rejuv(target, r, report, behavior_source_dir=src)
    sledge = next(e for e in report.entries if e.chrooked_id == "sledgehammer" and e.category == "ability")
    newab = next(e for e in report.entries if e.chrooked_id == "newab" and e.category == "ability")
    assert "DATA ONLY" not in (sledge.reason or "")
    assert "DATA ONLY" in (newab.reason or "")
    assert (target / "patch" / "Mods" / "chrooked_sledgehammer.rb").exists()


def test_new_move_primary_effect_uturn_gets_function_code(tmp_path):
    """A new move's primary `effect:` must render, not silently drop.

    Regression: Bail Out (effect: u-turn) shipped as :function 0x000 — a plain
    damage move that never switched the attacker — reported applied, no reason.
    """
    r = Ruleset(moves={"bailout": MoveDef(
        name="Bail Out", chrooked_id="bailout", type="Normal", category="physical",
        power=60, accuracy=100, pp=24, effect="u-turn", flags=("contact",),
    )})
    report, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "movetext.rb").read_text()
    assert "MOVEHASH[:BAILOUT] = {" in text
    assert ":function => 0x0EE" in text
    entry = next(e for e in report.entries if e.chrooked_id == "bailout")
    assert "0x0EE" in entry.reason


def test_new_move_primary_effect_triple_kick_gets_function_code(tmp_path):
    r = Ruleset(moves={"triplehit": MoveDef(
        name="Triple Hit", chrooked_id="triplehit", type="Normal", category="physical",
        power=15, accuracy=100, pp=10, effect="triple_kick", flags=("contact",),
    )})
    _, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "movetext.rb").read_text()
    assert ":function => 0x0BF" in text


def test_new_move_unmapped_primary_effect_reports_data_only(tmp_path):
    r = Ruleset(moves={"weird": MoveDef(
        name="Weird", chrooked_id="weird", type="Normal", category="physical",
        power=60, accuracy=100, pp=10, effect="no_such_mechanic",
    )})
    report, _ = _apply(r, tmp_path)
    entry = next(e for e in report.entries if e.chrooked_id == "weird")
    assert "no_such_mechanic" in entry.reason and "DATA ONLY" in entry.reason


def test_new_move_flinch_gets_function_code(tmp_path):
    from chrooked_pokedex.model.schema import AdditionalEffect
    r = Ruleset(moves={
        "fangy": MoveDef(name="Fangy", chrooked_id="fangy", type="Dark",
                         category="physical", power=80, accuracy=95, pp=15,
                         additional_effects=(AdditionalEffect("flinch", 30),),
                         flags=("contact", "biting")),
        "frostfang": MoveDef(name="Frost Fang", chrooked_id="frostfang", type="Ice",
                             category="physical", power=80, accuracy=95, pp=15,
                             additional_effects=(AdditionalEffect("freeze", 10),
                                                 AdditionalEffect("flinch", 10)),
                             flags=("contact", "biting")),
        "dropfang": MoveDef(name="Drop Fang", chrooked_id="dropfang", type="Rock",
                            category="physical", power=80, accuracy=95, pp=15,
                            additional_effects=(AdditionalEffect("def_minus_1", 10),
                                                AdditionalEffect("flinch", 10)),
                            flags=("contact", "biting")),
    })
    report, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "movetext.rb").read_text()
    fangy = next(l for l in text.splitlines() if ":FANGY]" in l)
    assert ":function => 0x00F" in fangy and ":effect => 30" in fangy
    frost = next(l for l in text.splitlines() if ":FROSTFANG]" in l)
    assert ":function => 0x00E" in frost and ":effect => 10" in frost
    drop = next(l for l in text.splitlines() if ":DROPFANG]" in l)
    # stat drop rides the native code; the flinch leftover is fangflinch's job
    assert ":function => 0x043" in drop and ":effect => 10" in drop
    reasons = {e.chrooked_id: (e.reason or "") for e in report.entries if e.category == "move"}
    assert "DATA ONLY" not in reasons["fangy"]
    assert "DATA ONLY" not in reasons["frostfang"]
    assert "flinch" in reasons["dropfang"]  # remaining gap named


def test_triage_notes_implemented_behaviors():
    res = RejuvResolution.build(FIXTURE)
    r = Ruleset(behaviors={
        "sledge": BehaviorSpec(name="Sledge", chrooked_id="sledge", applies_to="ability"),
        "newab": BehaviorSpec(name="Newab", chrooked_id="newab", applies_to="ability"),
    })
    rows = behavior_triage.triage(r, res, implemented={"sledge"})
    notes = {row.chrooked_id: row.note for row in rows}
    assert "implemented" in notes["sledge"]
    assert "implemented" not in notes["newab"]
    assert {row.bucket for row in rows} == {behavior_triage.BUCKET_CUSTOM_CODE}


def test_abiltext_keeps_data_only_when_behaviors_category_skipped(tmp_path):
    # `--category abilities` alone must NOT claim "mechanic implemented" — the
    # installer never runs, so nothing lands in patch/Mods this run.
    src = _harness(tmp_path, {
        "chrooked_00_core.rb": _CORE,
        "chrooked_sledgehammer.rb": "# chrooked:sledgehammer\nX = 1\n",
    })
    r = Ruleset(
        abilities={"sledgehammer": AbilityDef(name="Sledgehammer", chrooked_id="sledgehammer")},
        behaviors={"sledgehammer": BehaviorSpec(
            name="Sledgehammer", chrooked_id="sledgehammer", applies_to="ability")},
    )
    target = tmp_path / "game"
    shutil.copytree(FIXTURE, target)
    report = ApplyReport()
    apply_rejuv(target, r, report, category="abilities", behavior_source_dir=src)
    entry = next(e for e in report.entries if e.chrooked_id == "sledgehammer")
    assert "DATA ONLY" in (entry.reason or "")
    assert not (target / "patch" / "Mods").exists()


def test_flinch_combo_with_mismatched_chances_falls_back(tmp_path):
    # burn@10 + flinch@30 cannot ride one combo code chance — burn takes its
    # own single-effect code at its chance; flinch is the named leftover.
    from chrooked_pokedex.model.schema import AdditionalEffect
    r = Ruleset(moves={"oddfang": MoveDef(
        name="Odd Fang", chrooked_id="oddfang", type="Fire", category="physical",
        power=80, accuracy=95, pp=15,
        additional_effects=(AdditionalEffect("burn", 10), AdditionalEffect("flinch", 30)),
    )})
    report, target = _apply(r, tmp_path)
    line = next(l for l in (target / "patch" / "Definitions" / "movetext.rb")
                .read_text().splitlines() if ":ODDFANG]" in l)
    assert ":function => 0x00A" in line and ":effect => 10" in line
    reason = next(e.reason for e in report.entries if e.chrooked_id == "oddfang")
    assert "flinch" in reason


def test_installer_write_failure_reports_blocked(tmp_path, monkeypatch):
    from chrooked_pokedex.appliers.rejuv.behavior_install import install_behaviors
    src = _harness(tmp_path, {
        "chrooked_00_core.rb": _CORE,
        "chrooked_sledgehammer.rb": "# chrooked:sledgehammer\nX = 1\n",
    })
    target = tmp_path / "game"
    shutil.copytree(FIXTURE, target)
    real_write = Path.write_text

    def failing_write(self, *a, **kw):
        if self.parent.name == "Mods" and self.name == "chrooked_sledgehammer.rb":
            raise OSError("disk full")
        return real_write(self, *a, **kw)

    monkeypatch.setattr(Path, "write_text", failing_write)
    r = Ruleset(behaviors={"sledgehammer": BehaviorSpec(
        name="Sledgehammer", chrooked_id="sledgehammer", applies_to="ability")})
    report = ApplyReport()
    install_behaviors(target, r, report, source_dir=src)
    assert any(e.status == "blocked" and e.chrooked_id == "sledgehammer"
               and "copy failed" in (e.reason or "") for e in report.entries)


# --- harness load-shape (real files, stubbed ruby eval) -----------------------

HARNESS = Path(__file__).parent.parent / "references" / "rejuv-harness"

_RUBY_STUB = """
class PokeBattle_Move
  def pbCalcDamage(a, o, h = 0, f = {}); 100; end
  def pbType(attacker, type = nil); :NORMAL; end
end
# Dream Eater's effect class — chrooked_daydreamer prepends onto it.
class PokeBattle_Move_0DE < PokeBattle_Move; end
# Rejuv's party-menu registry — the zz_* QoL mods register handlers on it.
module MenuHandlers
  def self.add(*args, &blk); end
end
def _INTL(s, *a); s; end
class PokeBattle_Battler; end
class PokeBattle_Battle; end
"""


@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby unavailable")
def test_harness_load_shape(tmp_path):
    """Core + every behavior file evals clean in load order; tables populate."""
    import subprocess
    files = sorted(HARNESS.glob("chrooked_*.rb"))
    assert files, "harness is empty"
    script = _RUBY_STUB + "".join(
        f'eval(File.read({str(f)!r}), TOPLEVEL_BINDING)\n' for f in files
    ) + (
        'raise "damage table empty" if CHROOKED_DAMAGE_MODS.empty?\n'
        'tables = CHROOKED_DAMAGE_MODS.values + CHROOKED_DEFENSE_MODS.values\n'
        'raise "lambda arity" unless tables.all? { |l| l.arity == 3 }\n'
        'puts "OK"\n'
    )
    proc = subprocess.run(["ruby", "-e", script], capture_output=True, text=True, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby unavailable")
def test_harness_lambda_behavior(tmp_path):
    """Every wave-1 lambda produces the spec'd multiplier against stub classes."""
    import subprocess
    script = Path(__file__).parent / "fixtures" / "rejuv-harness" / "lambda_checks.rb"
    proc = subprocess.run(
        ["ruby", str(script), str(HARNESS)], capture_output=True, text=True, cwd=tmp_path
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby unavailable")
def test_harness_event_hooks(tmp_path):
    """Wave-3 event hooks (KO, contact, switch-in, speed, priority, immunity,
    stat swap, move lock) behave per spec against stub battle classes."""
    import subprocess
    script = Path(__file__).parent / "fixtures" / "rejuv-harness" / "event_checks.rb"
    proc = subprocess.run(
        ["ruby", str(script), str(HARNESS)], capture_output=True, text=True, cwd=tmp_path
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --- type chart ----------------------------------------------------------------

def test_type_chart_overrides_emit_typetext(tmp_path):
    from chrooked_pokedex.model.schema import TypeChartOverride
    r = Ruleset(type_chart=(
        TypeChartOverride("Poison", "Water", 2),
        TypeChartOverride("Ice", "Water", 1),
    ))
    report, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "typetext.rb").read_text()
    # old membership scrubbed from every bucket, then re-added where it belongs
    assert "TYPEHASH[:WATER][k]&.delete(:POISON)" in text
    assert "(TYPEHASH[:WATER][:weaknesses] ||= []) << :POISON" in text
    assert "TYPEHASH[:WATER][k]&.delete(:ICE)" in text
    assert "<< :ICE" not in text  # neutral = removal only
    assert sum(1 for e in report.entries if e.category == "type-chart"
               and e.status == "applied") == 2
    # Init script recompiles types.dat
    init = (target / "patch" / "Init" / "chrooked_compile.rb").read_text()
    assert '"patch/Definitions/typetext.rb", "patch/Data/types.dat", :compileTypes' in init


def test_existing_move_patches_priority_and_effect_function(tmp_path):
    # Astonish: Fake Out clone — priority + first_turn_only ride the patch.
    r = Ruleset(moves={"astonish": MoveDef(
        name="Tackle", chrooked_id="astonish", type="Ghost", category="physical",
        power=40, accuracy=100, pp=10, effect="first_turn_only", priority=3,
    )})
    _, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "movetext.rb").read_text()
    assert "MOVEHASH[:TACKLE][:priority] = 3" in text
    assert "MOVEHASH[:TACKLE][:function] = 0x012" in text
    assert "MOVEHASH[:TACKLE][:effect] = 100" in text  # Fake Out flinch chance


def test_existing_move_default_priority_untouched(tmp_path):
    r = Ruleset(moves={"tackle": MoveDef(
        name="Tackle", chrooked_id="tackle", type="Normal", category="physical",
        power=50, accuracy=100, pp=35,
    )})
    _, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "movetext.rb").read_text()
    assert ":priority" not in text and ":function" not in text.split("MOVEHASH[:TACKLE]")[1]


# --- web snapshot (rejuv target) ----------------------------------------------

@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby unavailable")
def test_rejuv_web_snapshot_builds_from_fixture():
    from chrooked_pokedex.web.snapshot_rejuv import build_snapshot_rejuv
    snap = build_snapshot_rejuv(FIXTURE)
    assert snap["version"] == "rejuv"
    bulba = snap["species"]["bulbasaur"]
    assert bulba["name"] == "Bulbasaur"
    assert bulba["types"] == ["Grass", "Poison"]
    assert bulba["stats"] == {"hp": 45, "atk": 49, "def": 49, "spa": 65, "spd": 65, "spe": 45}
    assert bulba["abilities"]["primary"] == "OVERGROW"
    assert {"level": 3, "move": "Vine Whip", "move_id": "vinewhip"} in bulba["learnset"]
    assert snap["moves"]["tackle"]["name"] == "Tackle"
    assert snap["abilities"]["overgrow"]["chrooked_id"] == "overgrow"
    cells = {(c["attacker"], c["defender"]): c["multiplier"] for c in snap["type_chart"]}
    assert cells[("Grass", "Water")] == 2.0
    assert cells[("Fire", "Water")] == 0.5
    assert cells[("Ghost", "Normal")] == 0.0
    assert cells[("Fire", "Fire")] == 1.0


@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby unavailable")
def test_rejuv_web_snapshot_prefers_patch_delta(tmp_path):
    from chrooked_pokedex.web.snapshot_rejuv import build_snapshot_rejuv
    r = Ruleset(species={"bulbasaur": _species(cid="bulbasaur", stats={"atk": 99})})
    _, target = _apply(r, tmp_path)
    snap = build_snapshot_rejuv(target)
    assert snap["species"]["bulbasaur"]["stats"]["atk"] == 99  # patched value wins


def test_registry_accepts_rejuv_engine(tmp_path):
    from chrooked_pokedex.web.targets import TargetRegistry, TargetError
    registry = TargetRegistry(tmp_path / "targets.json")
    game = tmp_path / "game"
    shutil.copytree(FIXTURE, game)
    target = registry.add("Rejuv", str(game), "rejuv")
    assert target.engine == "rejuv"
    with pytest.raises(TargetError):
        registry.add("NotRejuv", str(tmp_path), "rejuv")  # no Scripts/Rejuv/Definitions


@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby unavailable")
def test_rejuv_web_snapshot_includes_all_forms():
    from chrooked_pokedex.web.snapshot_rejuv import build_snapshot_rejuv
    snap = build_snapshot_rejuv(FIXTURE)
    mega = snap["species"]["absol--megaform"]
    assert mega["name"] == "Absol (Mega Form)"
    assert snap["species"]["absol"]["name"] == "Absol"  # base keeps plain slug
    # Charizard fixture Mega X inherits BaseStats from the base form
    megax = snap["species"]["charizard--megaxform"]
    assert megax["stats"]["hp"] == snap["species"]["charizard"]["stats"]["hp"]


@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby unavailable")
def test_rejuv_web_snapshot_carries_sprite_hints():
    from chrooked_pokedex.web.snapshot_rejuv import build_snapshot_rejuv
    snap = build_snapshot_rejuv(FIXTURE)
    assert snap["species"]["absol"]["sprite"] == {"folder": "absol", "form": 0}
    assert snap["species"]["absol--megaform"]["sprite"] == {"folder": "absol", "form": 1}


@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby unavailable")
def test_rejuv_web_snapshot_evolution_edges(tmp_path):
    from chrooked_pokedex.web.snapshot_rejuv import build_snapshot_rejuv
    # Give the fixture a forward edge: Bulbasaur -> Absol at level 16 (nonsense
    # biologically, real structurally).
    game = tmp_path / "game"
    shutil.copytree(FIXTURE, game)
    mon = game / "Scripts" / "Rejuv" / "Definitions" / "montext.rb"
    text = mon.read_text().replace(
        ''':name => "Bulbasaur",''',
        ''':name => "Bulbasaur",
      :evolutions => [ { species: :ABSOL, method: :Level, parameter: 16 } ],''')
    mon.write_text(text)
    snap = build_snapshot_rejuv(game)
    bulba = snap["species"]["bulbasaur"]
    assert bulba["fully_evolved"] is False
    assert bulba["evolves_into"][0]["to"] == "absol"
    absol = snap["species"]["absol"]
    assert absol["evolution"]["from"] == "bulbasaur"
    assert snap["species"]["charizard"]["fully_evolved"] is True


@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby unavailable")
def test_rejuv_evolution_keeps_source_form(tmp_path):
    # Engine rule: an edge without form: keeps the evolving mon's form index —
    # Mega Absol (form 1) evolving into Charizard lands on Mega X (form 1).
    from chrooked_pokedex.web.snapshot_rejuv import build_snapshot_rejuv
    game = tmp_path / "game"
    shutil.copytree(FIXTURE, game)
    mon = game / "Scripts" / "Rejuv" / "Definitions" / "montext.rb"
    text = mon.read_text().replace(
        '''  :ABSOL => {
    "Normal Form" => {''',
        '''  :ABSOL => {
    "Normal Form" => {
      :evolutions => [ { species: :CHARIZARD, method: :Level, parameter: 30 } ],''')
    mon.write_text(text)
    snap = build_snapshot_rejuv(game)
    # Base Absol (form 0) -> base Charizard (form 0)
    assert snap["species"]["absol"]["evolves_into"][0]["to"] == "charizard"
    # Mega Absol (form 1) inherits the edge at compile; keeps form 1 -> Mega X
    mega_edges = snap["species"]["absol--megaform"]["evolves_into"]
    assert mega_edges and mega_edges[0]["to"] == "charizard--megaxform"


def test_static_mod_relearn_always_installed(tmp_path):
    # chrooked_zz_*.rb static mods install on every apply, even with an empty
    # Ruleset and no behaviors — they carry the "relearn freely" UI override.
    _, target = _apply(Ruleset(), tmp_path)
    mod = target / "patch" / "Mods" / "chrooked_zz_relearn.rb"
    assert mod.exists()
    assert "def canRelearnAll?" in mod.read_text()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "form_label", "expected"),
    [
        # Form 0 of a genuinely multi-form species must be labelled — this is the
        # case that regressed: Spring Deerling rendered bare beside its siblings.
        ("Deerling", "Spring Form", "Deerling (Spring Form)"),
        ("Sawsbuck", "Spring Form", "Sawsbuck (Spring Form)"),
        ("Cherrim", "Overcast Form", "Cherrim (Overcast Form)"),
        ("Deerling", "Winter Form", "Deerling (Winter Form)"),
        # Rejuv's placeholder label for single-form species stays invisible.
        ("Bulbasaur", "Normal Form", "Bulbasaur"),
        ("Tornadus", "Normal Forme", "Tornadus"),
        ("Ponyta", "", "Ponyta"),
        # A label echoing the species name adds nothing (Rotom's own form 0).
        ("Rotom", "Rotom", "Rotom"),
    ],
)
def test_display_name_labels_only_meaningful_forms(name, form_label, expected):
    from chrooked_pokedex.web.snapshot_rejuv import _display_name

    assert _display_name(name, form_label) == expected


# --- evolutions --------------------------------------------------------------

def test_evolution_level_writes_onto_the_pre_evolution(tmp_path):
    """A backward `evolution.from` lands as a forward `:evolutions` entry on the source.

    Regression: the Rejuv applier emitted no `:evolutions` at all, so all 88
    evolution Overrides in the Ruleset were silently dropped -- Goldeen kept its
    base evolution level in game while the Ruleset said 30.
    """
    r = Ruleset(species={
        "charizard": _species(
            cid="charizard", name="Charizard",
            evolution=EvolutionOverride(from_species="Absol", method={"level": 30}),
        )
    })
    report, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "montext.rb").read_text()
    # written onto ABSOL (the pre-evolution), not CHARIZARD
    assert 'MONHASH[:ABSOL]["Normal Form"][:evolutions]' in text
    assert "species: :CHARIZARD, form: 0, method: :Level, parameter: 30" in text
    assert any(e.category == "evolution" and e.status == "applied" for e in report.entries)


def test_evolution_item_makes_item_bag_usable(tmp_path):
    """An Item-method evolution must also make the item usable from the bag.

    Regression: Sachet kept its base :noUse flag and was absent from EVOSTONES,
    so the bag only offered Give — the applied evolution was unreachable.
    """
    r = Ruleset(species={
        "charizard": _species(
            cid="charizard", name="Charizard",
            evolution=EvolutionOverride(from_species="Absol", method={"item": "SACHET"}),
        )
    })
    _, target = _apply(r, tmp_path)
    itemtext = (target / "patch" / "Definitions" / "itemtext.rb").read_text()
    assert "ITEMHASH[:SACHET].delete(:noUse) if ITEMHASH[:SACHET]" in itemtext
    mod = (target / "patch" / "Mods" / "chrooked_zz_evoitems.rb").read_text()
    assert "[:SACHET].each" in mod
    assert "EVOSTONES.push(item)" in mod
    assert "ItemHandlers::UseOnPokemon.copy(:FIRESTONE, item)" in mod
    # items.dat compiles from the mod, NOT the Init script: compileItems needs
    # PBStats, which the game defines after Init but before Mods.
    assert "compileItems" in mod
    init = (target / "patch" / "Init" / "chrooked_compile.rb").read_text()
    assert '"patch/Definitions/itemtext.rb"' not in init


def test_no_item_evolution_writes_empty_item_patch(tmp_path):
    """No item evolutions -> both files still written, as self-healing no-ops."""
    r = Ruleset(species={"bulbasaur": _species(cid="bulbasaur", stats={"hp": 50})})
    _, target = _apply(r, tmp_path)
    itemtext = (target / "patch" / "Definitions" / "itemtext.rb").read_text()
    assert "ITEMHASH" not in itemtext.replace(
        'eval(File.read("Scripts/Rejuv/Definitions/itemtext.rb"), TOPLEVEL_BINDING)', ""
    )
    mod = (target / "patch" / "Mods" / "chrooked_zz_evoitems.rb").read_text()
    assert "[].each" in mod


def test_evolution_preserves_unrelated_base_branches(tmp_path):
    """Writing one branch must not wipe a base branch the Ruleset never mentions."""
    r = Ruleset(species={
        "charizard": _species(
            cid="charizard", name="Charizard",
            evolution=EvolutionOverride(from_species="Absol", method={"level": 30}),
        )
    })
    _, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "montext.rb").read_text()
    # The emitted statement must merge with whatever the base already had,
    # replacing only the branch pointing at our target.
    assert ".reject" in text, "evolution write replaces the whole array"


def test_evolution_unrenderable_method_is_reported_not_dropped(tmp_path):
    """A method with only a pokeemerald hint can't render for Rejuv -- it must report."""
    r = Ruleset(species={
        "charizard": _species(
            cid="charizard", name="Charizard",
            evolution=EvolutionOverride(
                from_species="Absol", method={"pokeemerald": "EVO_LEVEL_FOG", "param": 35},
            ),
        )
    })
    report, _ = _apply(r, tmp_path)
    assert any(
        e.category == "evolution" and e.status in ("blocked", "partial")
        for e in report.entries
    ), "unrenderable evolution vanished from the report"


def test_evolution_unresolved_pre_evolution_is_blocked(tmp_path):
    r = Ruleset(species={
        "charizard": _species(
            cid="charizard", name="Charizard",
            evolution=EvolutionOverride(from_species="Nonexistent", method={"level": 5}),
        )
    })
    report, _ = _apply(r, tmp_path)
    assert any(
        e.category == "evolution" and e.status == "blocked" for e in report.entries
    )


def test_evolution_reject_is_form_aware(tmp_path):
    """Rewriting one branch must not delete sibling branches to OTHER forms.

    Rejuv keys branches by (species, form): Rockruff carries three separate
    edges to LYCANROC forms 0/1/2, and Petilil carries two to LILLIGANT 0/1.
    A reject on the species symbol alone would collapse all of them into one.
    """
    r = Ruleset(species={
        "charizard": _species(
            cid="charizard", name="Charizard",
            evolution=EvolutionOverride(from_species="Absol", method={"level": 30}),
        )
    })
    _, target = _apply(r, tmp_path)
    text = (target / "patch" / "Definitions" / "montext.rb").read_text()
    line = next(ln for ln in text.splitlines() if "[:evolutions]" in ln)
    assert "e[:form]" in line, f"reject ignores form, will eat sibling branches: {line}"
    assert "form:" in line.split(".reject")[1], "appended branch does not pin its form"


def test_resolution_species_falls_back_to_essentials_aka():
    """Rejuv is Essentials-derived, so an `essentials:` aka names a real MONHASH key.

    Regression: Rejuv keys are not always uppercase (`:NIDORANfE`, `:NIDORANmA`),
    so `slug(id).upper()` can never match them and the form matcher can't either.
    The Ruleset already carries the exact symbol under `essentials:`; without this
    fallback the Nidoran family's evolutions were blocked with no way to rescue
    them short of hand-adding a duplicate `rejuv:` hint to every such species.
    """
    res = RejuvResolution.build(FIXTURE)
    assert res.species("whatever", {"essentials": "ABSOL"}) == ("ABSOL", "Normal Form")
    # an explicit rejuv hint still wins over the essentials one
    assert res.species("x", {"rejuv": "ABSOL::Mega Form", "essentials": "BULBASAUR"}) == (
        "ABSOL", "Mega Form"
    )
    # a bogus essentials symbol resolves to nothing rather than being fabricated
    assert res.species("x", {"essentials": "NOPE"}) is None


def test_scan_monhash_keys_accepts_mixed_case_symbols(tmp_path):
    """Rejuv MONHASH keys are not all uppercase -- `:NIDORANfE`, `:NIDORANmA`.

    Regression: the key regex was `[A-Z0-9_]+`, so those species never entered
    the resolution map at all. Every Override on them -- stats, types, abilities,
    learnset, evolution -- was reported blocked and silently skipped.
    """
    from chrooked_pokedex.appliers.rejuv import definitions_read as dr

    path = tmp_path / "montext.rb"
    path.write_text(
        'MONHASH = {\n'
        '  :NIDORANfE => {\n'
        '    "Normal Form" => {\n'
        '      :name => "Nidoran",\n'
        '    },\n'
        '  },\n'
        '  :BULBASAUR => {\n'
        '    "Normal Form" => {\n'
        '    },\n'
        '  },\n'
        '}\n',
        encoding="utf-8",
    )
    keys = dr.scan_monhash_keys(path)
    assert keys["NIDORANfE"] == ["Normal Form"]
    assert keys["BULBASAUR"] == ["Normal Form"]
