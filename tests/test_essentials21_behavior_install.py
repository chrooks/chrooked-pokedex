"""Hermetic tests for the Essentials 21 behavior installer (mjolnir NV-5).

No game required: a temp dir stands in for the target, another for the port
source library. Mirrors tests/test_behavior_install.py (the 16.2 installer) and
adds what is new for v21: the install home is Data/Scripts/998_ChrookedMods/,
the dex owns that folder (stale ports are removed), and nothing else under
Data/Scripts/ is touched.
"""

import types
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.essentials.behavior_install import (
    MODS_DIR,
    has_plugin,
    has_port,
    install_behaviors,
)
from chrooked_pokedex.appliers.essentials.creation import create_owned_content
from chrooked_pokedex.appliers.essentials.resolution import build_resolution_map
from chrooked_pokedex.behavior.templates import render_essentials21
from chrooked_pokedex.cli import _ESSENTIALS_CATEGORIES, _apply_essentials
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.behavior_spec import (
    BehaviorEffect,
    BehaviorSpec,
    BehaviorTemplate,
    BehaviorTestCase,
)
from chrooked_pokedex.model.schema import AbilityDef
from chrooked_pokedex.report import ApplyReport

pytestmark = pytest.mark.unit

_REPO_PORTS = Path(__file__).resolve().parents[1] / "references" / "essentials21-harness"


def _ruleset(*ids):
    """Minimal stand-in: the installer only reads ruleset.behaviors (id -> spec)."""
    return types.SimpleNamespace(behaviors={i: types.SimpleNamespace(chrooked_id=i) for i in ids})


def _source(tmp_path, ports):
    src = tmp_path / "src"
    src.mkdir()
    for cid, contents in ports.items():
        (src / f"chrooked_{cid}.rb").write_text(contents)
    return src


def _target(tmp_path):
    tgt = tmp_path / "game"
    (tgt / "Data" / "Scripts" / "011_Battle").mkdir(parents=True)
    return tgt


def _mods(tgt):
    return tgt / MODS_DIR


def test_present_port_is_installed_into_998_chrookedmods(tmp_path):
    src = _source(tmp_path, {"kindle": "# chrooked:kindle\nputs 1\n"})
    tgt = _target(tmp_path)
    report = ApplyReport()

    changed = install_behaviors(tgt, _ruleset("kindle"), report, source_dir=src)

    dest = tgt / "Data" / "Scripts" / "998_ChrookedMods" / "chrooked_kindle.rb"
    assert dest.read_text().startswith("# chrooked:kindle")
    assert changed == {dest}
    entry = next(e for e in report.entries if e.chrooked_id == "kindle")
    assert entry.status == "applied"
    assert "installed" in entry.reason
    assert "998_ChrookedMods/chrooked_kindle.rb" in entry.reason


def test_missing_port_is_noop_and_creates_no_folder(tmp_path):
    src = _source(tmp_path, {})
    tgt = _target(tmp_path)
    report = ApplyReport()

    install_behaviors(tgt, _ruleset("someunported"), report, source_dir=src)

    assert not _mods(tgt).exists()
    assert report.entries == []


@pytest.mark.parametrize("contents", ["", "puts 'no tag here'\n"])
def test_empty_or_untagged_port_is_blocked_and_not_copied(tmp_path, contents):
    src = _source(tmp_path, {"broken": contents})
    tgt = _target(tmp_path)
    report = ApplyReport()

    install_behaviors(tgt, _ruleset("broken"), report, source_dir=src)

    assert not (_mods(tgt) / "chrooked_broken.rb").exists()
    assert next(e for e in report.entries if e.chrooked_id == "broken").status == "blocked"


def test_idempotent_rerun_is_no_churn(tmp_path):
    src = _source(tmp_path, {"kindle": "# chrooked:kindle\nv=1\n"})
    tgt = _target(tmp_path)
    install_behaviors(tgt, _ruleset("kindle"), ApplyReport(), source_dir=src)

    report2 = ApplyReport()
    changed = install_behaviors(tgt, _ruleset("kindle"), report2, source_dir=src)

    assert changed == set()
    assert report2.entries == []


def test_changed_port_is_rewritten(tmp_path):
    src = _source(tmp_path, {"kindle": "# chrooked:kindle\nv=1\n"})
    tgt = _target(tmp_path)
    install_behaviors(tgt, _ruleset("kindle"), ApplyReport(), source_dir=src)
    (src / "chrooked_kindle.rb").write_text("# chrooked:kindle\nv=2\n")

    report = ApplyReport()
    install_behaviors(tgt, _ruleset("kindle"), report, source_dir=src)

    assert (_mods(tgt) / "chrooked_kindle.rb").read_text() == "# chrooked:kindle\nv=2\n"
    assert next(e for e in report.entries if e.chrooked_id == "kindle").status == "applied"


def test_stale_port_is_removed_and_reported(tmp_path):
    # The dex owns 998_ChrookedMods: a port it no longer installs must not linger,
    # or a deploy that mirrors the folder would ship a dead mechanic.
    src = _source(tmp_path, {"kindle": "# chrooked:kindle\n"})
    tgt = _target(tmp_path)
    _mods(tgt).mkdir(parents=True)
    (_mods(tgt) / "chrooked_retired.rb").write_text("# chrooked:retired\n")
    report = ApplyReport()

    changed = install_behaviors(tgt, _ruleset("kindle"), report, source_dir=src)

    assert not (_mods(tgt) / "chrooked_retired.rb").exists()
    assert _mods(tgt) / "chrooked_retired.rb" in changed
    entry = next(e for e in report.entries if e.chrooked_id == "retired")
    assert entry.status == "applied"
    assert "uninstalled" in entry.reason


def test_installed_port_whose_source_turns_invalid_is_blocked_and_removed(tmp_path):
    src = _source(tmp_path, {"kindle": "# chrooked:kindle\n"})
    tgt = _target(tmp_path)
    install_behaviors(tgt, _ruleset("kindle"), ApplyReport(), source_dir=src)
    (src / "chrooked_kindle.rb").write_text("")
    report = ApplyReport()

    install_behaviors(tgt, _ruleset("kindle"), report, source_dir=src)

    assert not (_mods(tgt) / "chrooked_kindle.rb").exists()
    statuses = sorted(e.status for e in report.entries if e.chrooked_id == "kindle")
    assert statuses == ["applied", "blocked"]  # blocked source, then the uninstall


def test_other_script_folders_and_files_are_never_touched(tmp_path):
    # thor's controls shim and the lab's own scripts live beside the dex's folder.
    src = _source(tmp_path, {})
    tgt = _target(tmp_path)
    kirin = tgt / "Data" / "Scripts" / "998_ChrookedKirin" / "001_chrooked_kirin_controls.rb"
    lab = tgt / "Data" / "Scripts" / "998_ChrookedDexLab" / "chrooked_lab_note.rb"
    for path in (kirin, lab):
        path.parent.mkdir(parents=True)
        path.write_text("# keep me\n")
    _mods(tgt).mkdir(parents=True)
    note = _mods(tgt) / "README.txt"
    note.write_text("not a port\n")

    install_behaviors(tgt, _ruleset(), ApplyReport(), source_dir=src)

    assert kirin.read_text() == "# keep me\n"
    assert lab.read_text() == "# keep me\n"
    assert note.read_text() == "not a port\n"


def test_has_plugin_requires_a_valid_port(tmp_path):
    src = _source(tmp_path, {"kindle": "# chrooked:kindle\n", "empty": "", "wrong": "no tag\n"})
    assert has_plugin("kindle", source_dir=src) is True
    assert has_plugin("notported", source_dir=src) is False
    assert has_plugin("empty", source_dir=src) is False
    assert has_plugin("wrong", source_dir=src) is False


def test_lab_scripts_are_harvested_beside_the_ports():
    lab = _REPO_PORTS / "lab"
    names = sorted(p.name for p in lab.glob("*.rb"))
    assert names == ["001_register_black_weather.rb", "002_lab_save_dir.rb", "010_battle_selftest.rb"]
    selftest = (lab / "010_battle_selftest.rb").read_text(encoding="utf-8")
    # Cases come from the installed ports (NV-8), never from a table kept here.
    assert "cases = $chrooked_selftest_cases || {}" in selftest
    assert "CASES" not in selftest
    # Safe to arm briefly on a played copy (runbook 31): scratch save dir, globals
    # restored, run once per process, title-screen fallback, absolute log path.
    assert "swap_save_dir(SAVE_SCRATCH)" in selftest
    assert "$player, $bag, $stats, $game_switches, $game_variables, $PokemonSystem = old" in selftest
    assert "$chrooked_selftest_ran = true" in selftest
    assert "class Scene_Intro" in selftest
    assert 'LOG          = File.expand_path("chrooked_load.log")' in selftest
    assert "load_new_game_values" not in selftest  # would mark save values loaded for real


# --- the create path's honesty line ------------------------------------------

_POKEMON = "[NUMEL]\nName = Numel\nTypes = FIRE,GROUND\nBaseStats = 60,60,40,35,65,45\nAbilities = OBLIVIOUS\nMoves = 1,TACKLE\n"


_MOVES = "".join(f"[{m.upper()}]\nName = {m}\n" for m in ("Tackle", "Flamethrower", "Surf", "Ember"))


def _pbs_target(tmp_path, extra_abilities=""):
    target = tmp_path / "essentials"
    pbs = target / "PBS"
    pbs.mkdir(parents=True)
    (pbs / "pokemon.txt").write_text(_POKEMON, encoding="utf-8")
    (pbs / "moves.txt").write_text(_MOVES, encoding="utf-8")
    (pbs / "abilities.txt").write_text("[OBLIVIOUS]\nName = Oblivious\n" + extra_abilities, encoding="utf-8")
    (pbs / "types.txt").write_text("[FIRE]\nName = Fire\n[GROUND]\nName = Ground\n", encoding="utf-8")
    return target


# A made-up ability, so these tests never depend on which Ruleset mechanics are
# templated or hand-ported in the repo today.
_CINDERGLOW_PROBES = (
    {"move": "Flamethrower", "result": "boosted"},
    {"move": "Surf", "result": "normal"},
    {"move": "Ember", "result": "boosted"},
)


def _cinderglow(probes=_CINDERGLOW_PROBES):
    return BehaviorSpec(
        name="Cinderglow", chrooked_id="cinderglow", applies_to="ability",
        effects=(BehaviorEffect(summary="Fire-type moves deal 50% more damage.",
                                trigger="damage-calc", effect="multiply by 1.5"),),
        test_cases=tuple(BehaviorTestCase(given=f"case {i}", expect="x") for i in range(1, len(probes) + 1)),
        template=BehaviorTemplate(shape="type_boost",
                                  params={"type": "Fire", "multiplier": 1.5, "control": "BLAZE"},
                                  probes=tuple(probes)),
    )


def _cinderglow_ruleset(spec=None, extra_ability=None):
    abilities = {"cinderglow": AbilityDef(name="Cinderglow", chrooked_id="cinderglow",
                                          description="Fire-type moves are boosted by 50%.",
                                          aka={"essentials": "CINDERGLOW"})}
    behaviors = {"cinderglow": spec or _cinderglow()}
    if extra_ability:
        cid, name = extra_ability
        abilities[cid] = AbilityDef(name=name, chrooked_id=cid, aka={"essentials": name.upper()})
        behaviors[cid] = BehaviorSpec(name=name, chrooked_id=cid, applies_to="ability")
    return Ruleset(abilities=abilities, behaviors=behaviors)


def test_created_ability_with_a_port_says_installed_not_data_only(tmp_path):
    target = _pbs_target(tmp_path)
    ruleset = _cinderglow_ruleset(extra_ability=("unportedthing", "Unportedthing"))
    report = ApplyReport()

    create_owned_content(target, ruleset, build_resolution_map(target, ruleset), report)

    created = next(e for e in report.entries if e.chrooked_id == "cinderglow")
    assert "DATA ONLY" not in created.reason
    assert "998_ChrookedMods/chrooked_cinderglow.rb" in created.reason
    unported = next(e for e in report.entries if e.chrooked_id == "unportedthing")
    assert "DATA ONLY" in unported.reason


def test_template_naming_a_move_the_target_lacks_stays_data_only_and_is_blocked(tmp_path):
    target = _pbs_target(tmp_path)
    probes = (_CINDERGLOW_PROBES[0], {"move": "Sludge Wave", "result": "normal"}, _CINDERGLOW_PROBES[2])
    ruleset = _cinderglow_ruleset(spec=_cinderglow(probes))
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    create_owned_content(target, ruleset, resmap, report)
    install_behaviors(target, ruleset, report, resmap=resmap, source_dir=_source(tmp_path, {}))

    created, blocked = [e for e in report.entries if e.chrooked_id == "cinderglow"]
    assert "DATA ONLY" in created.reason  # never promises a port the installer refuses
    assert blocked.status == "blocked"
    assert "Sludge Wave" in blocked.reason
    assert not (_mods(target) / "chrooked_cinderglow.rb").exists()


def test_cli_essentials_apply_generates_the_templated_port(tmp_path, capsys):
    assert _ESSENTIALS_CATEGORIES[-1] == "behaviors"
    target = _pbs_target(tmp_path, extra_abilities="[CINDERGLOW]\nName = Cinderglow\n")
    ruleset = _cinderglow_ruleset()
    report = ApplyReport()

    _apply_essentials(target, "behaviors", ruleset, report)

    installed = (_mods(target) / "chrooked_cinderglow.rb").read_text(encoding="utf-8")
    assert installed == render_essentials21(ruleset.behaviors["cinderglow"], build_resolution_map(target, ruleset))
    assert "chrooked_table.add(:CINDERGLOW," in installed
    assert "behaviors: 1 file(s) changed" in capsys.readouterr().out
    entry = next(e for e in report.entries if e.category == "behavior")
    assert entry.status == "applied" and "mechanic installed" in entry.reason


def test_generated_port_rerun_is_no_churn(tmp_path):
    target = _pbs_target(tmp_path, extra_abilities="[CINDERGLOW]\nName = Cinderglow\n")
    ruleset, src = _cinderglow_ruleset(), _source(tmp_path, {})
    install_behaviors(target, ruleset, ApplyReport(), source_dir=src)  # builds its own resmap
    report = ApplyReport()

    assert install_behaviors(target, ruleset, report, source_dir=src) == set()
    assert report.entries == []


def test_template_and_hand_port_together_is_ambiguous_and_blocked(tmp_path):
    target = _pbs_target(tmp_path, extra_abilities="[CINDERGLOW]\nName = Cinderglow\n")
    ruleset = _cinderglow_ruleset()
    src = _source(tmp_path, {"cinderglow": "# chrooked:cinderglow\nputs 'hand'\n"})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    install_behaviors(target, ruleset, report, resmap=resmap, source_dir=src)

    (entry,) = report.entries
    assert entry.status == "blocked" and "ambiguous" in entry.reason
    assert not (_mods(target) / "chrooked_cinderglow.rb").exists()
    assert has_port(ruleset.behaviors["cinderglow"], resmap, source_dir=src) is False


def test_resolution_reads_items_from_every_items_file(tmp_path):
    """Nova keeps its own items in items_nova.txt beside items.txt; Essentials 21
    loads both, so a probe's held item resolves from either."""
    target = _pbs_target(tmp_path)
    (target / "PBS" / "items.txt").write_text("[UTILITYUMBRELLA]\nName = Utility Umbrella\n", encoding="utf-8")
    (target / "PBS" / "items_nova.txt").write_text("[NOVACHARM]\nName = Nova Charm\n", encoding="utf-8")

    resmap = build_resolution_map(target, _cinderglow_ruleset())

    assert resmap.item("Utility Umbrella") == "UTILITYUMBRELLA"
    assert resmap.item("nova charm") == "NOVACHARM"
    assert resmap.item("Rain Hat") is None


def _emberjaw_ruleset(parts=("cinderglow", "strongjaw")):
    ruleset = _cinderglow_ruleset()
    abilities = {**ruleset.abilities, "emberjaw": AbilityDef(name="Emberjaw", chrooked_id="emberjaw",
                                                             behaviors=tuple(parts))}
    return Ruleset(abilities=abilities, behaviors=ruleset.behaviors)


def _emberjaw_target(tmp_path, abilities="[CINDERGLOW]\nName = Cinderglow\n[STRONGJAW]\nName = Strong Jaw\n"):
    target = _pbs_target(tmp_path, extra_abilities=abilities)
    with (target / "PBS" / "moves.txt").open("a", encoding="utf-8") as moves:
        moves.write("[CRUNCH]\nName = Crunch\n")
    return target


def test_a_composed_ability_is_created_installed_and_says_so(tmp_path):
    """NV-15: a composition gets its own file, and its created line is not DATA ONLY."""
    target, ruleset = _emberjaw_target(tmp_path), _emberjaw_ruleset()
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    create_owned_content(target, ruleset, resmap, report)
    install_behaviors(target, ruleset, report, resmap=resmap, source_dir=_source(tmp_path, {}))

    created = next(e for e in report.entries if e.chrooked_id == "emberjaw" and e.status == "applied"
                   and "created" in e.reason)
    assert "DATA ONLY" not in created.reason and "chrooked_emberjaw.rb (composed)" in created.reason
    installed = (_mods(target) / "chrooked_emberjaw.rb").read_text(encoding="utf-8")
    assert 'ChrookedCompose.register(:EMBERJAW, "emberjaw", [[:CINDERGLOW, "cinderglow"], [:STRONGJAW, "strongjaw"]])' \
        in installed
    assert (_mods(target) / "chrooked_cinderglow.rb").exists()  # the part's own port, beside it


def test_a_composition_not_composable_yet_is_silent_and_stays_data_only(tmp_path):
    target, ruleset = _emberjaw_target(tmp_path), _emberjaw_ruleset(("cinderglow", "pickup"))
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    create_owned_content(target, ruleset, resmap, report)
    install_behaviors(target, ruleset, report, resmap=resmap, source_dir=_source(tmp_path, {}))

    assert "DATA ONLY" in next(e for e in report.entries if e.chrooked_id == "emberjaw").reason
    assert [e for e in report.entries if e.status == "blocked"] == []
    assert not (_mods(target) / "chrooked_emberjaw.rb").exists()


def test_a_composition_whose_target_lacks_a_vanilla_part_is_blocked(tmp_path):
    target = _emberjaw_target(tmp_path, abilities="[CINDERGLOW]\nName = Cinderglow\n[EMBERJAW]\nName = Emberjaw\n")
    ruleset = _emberjaw_ruleset()
    report = ApplyReport()

    install_behaviors(target, ruleset, report, source_dir=_source(tmp_path, {}))

    blocked = next(e for e in report.entries if e.chrooked_id == "emberjaw")
    assert blocked.status == "blocked" and "no ability 'Strong Jaw'" in blocked.reason
    assert not (_mods(target) / "chrooked_emberjaw.rb").exists()


def test_has_port_is_what_the_installer_would_install(tmp_path):
    target = _pbs_target(tmp_path, extra_abilities="[CINDERGLOW]\nName = Cinderglow\n")
    ruleset = _cinderglow_ruleset()
    resmap = build_resolution_map(target, ruleset)
    empty = _source(tmp_path, {})
    hand = tmp_path / "hand"
    hand.mkdir()
    (hand / "chrooked_handmade.rb").write_text("# chrooked:handmade\n", encoding="utf-8")
    handmade = BehaviorSpec(name="Handmade", chrooked_id="handmade", applies_to="ability")

    assert has_port(ruleset.behaviors["cinderglow"], resmap, source_dir=empty) is True
    assert has_port(handmade, resmap, source_dir=hand) is True
    assert has_port(handmade, resmap, source_dir=empty) is False
    assert has_port(_cinderglow((_CINDERGLOW_PROBES[0], {"move": "Hyper Beam", "result": "normal"},
                                 _CINDERGLOW_PROBES[2])), resmap, source_dir=empty) is False
