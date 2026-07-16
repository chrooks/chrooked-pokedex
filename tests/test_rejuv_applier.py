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
    # No additional effects -> a plain 0x000 damage move is complete, no DATA ONLY.
    entry = next(e for e in report.entries if e.chrooked_id == "madeup")
    assert entry.status == "applied" and not entry.reason


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
    assert ":function => 0x00F" in drop  # flinch real; stat drop stays honest
    reasons = {e.chrooked_id: (e.reason or "") for e in report.entries if e.category == "move"}
    assert "DATA ONLY" not in reasons["fangy"]
    assert "DATA ONLY" not in reasons["frostfang"]
    assert "def_minus_1" in reasons["dropfang"]  # remaining gap named


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
    # burn@10 + flinch@30 cannot ride one combo code chance — fall back to 0x00F
    # (flinch real at its own chance) and name burn as the honest leftover.
    from chrooked_pokedex.model.schema import AdditionalEffect
    r = Ruleset(moves={"oddfang": MoveDef(
        name="Odd Fang", chrooked_id="oddfang", type="Fire", category="physical",
        power=80, accuracy=95, pp=15,
        additional_effects=(AdditionalEffect("burn", 10), AdditionalEffect("flinch", 30)),
    )})
    report, target = _apply(r, tmp_path)
    line = next(l for l in (target / "patch" / "Definitions" / "movetext.rb")
                .read_text().splitlines() if ":ODDFANG]" in l)
    assert ":function => 0x00F" in line and ":effect => 30" in line
    reason = next(e.reason for e in report.entries if e.chrooked_id == "oddfang")
    assert "burn" in reason


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
