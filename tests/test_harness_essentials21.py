"""The log-oracle harness on an Essentials 21 target (mjolnir NV-5).

Same OBS lines and scenarios as 16.2; what differs is the layout: the log sits in
the game folder, ports write it only while chrooked-oracle.on exists, and AI
estimates are tagged EST so they are never scored as real hits.
"""

import shutil
from pathlib import Path

import pytest

from chrooked_pokedex.behavior import harness
from chrooked_pokedex.behavior.harness_scenarios import SCENARIOS
from chrooked_pokedex.model.behavior_spec import BehaviorTestCase

pytestmark = pytest.mark.unit

_FIXTURES = Path(__file__).parent / "fixtures" / "essentials_dialect"
_RULESET = Path(__file__).resolve().parents[1] / "ruleset"

# Shape of a real lab run (2026-10-22, Nova V3.0): load lines, AI estimates (EST),
# the self-test's own lines, and real hits (OBS).
_V21_LOG = """\
[chrooked:lab] save dir D:/Games/Pokemon FanGames/NovaV3.0-dexlab/Nova/LabSaves/
[chrooked:kindle] load ruby=3.1.3 platform=x64-mingw32 prior_handler=false
[chrooked:kindle] installed on Battle::AbilityEffects::DamageCalcFromUser
[chrooked:selftest] start mechanic=kindle ruby=3.1.3 platform=x64-mingw32
[chrooked:kindle] EST move=TACKLE type=NORMAL kindle=true result=BOOSTED
[chrooked:kindle] OBS move=FLAMETHROWER type=FIRE kindle=true result=BOOSTED
[chrooked:selftest] CALC move=FLAMETHROWER type=FIRE eff=1.0 with=54 none=36 BLAZE=36 ratio=1.500
[chrooked:kindle] OBS move=SURF type=WATER kindle=true result=NORMAL
[chrooked:kindle] OBS move=TACKLE type=NORMAL kindle=true result=NORMAL
[chrooked:kindle] OBS move=EMBER type=FIRE kindle=true result=BOOSTED
[chrooked:selftest] DONE
"""


def _copy(name, tmp_path):
    dest = tmp_path / name
    shutil.copytree(_FIXTURES / name, dest)
    return dest


def test_v21_log_lives_in_the_game_folder(tmp_path):
    v21 = _copy("modern_v21", tmp_path)
    old = _copy("english_162", tmp_path)
    assert harness.log_path(v21) == v21 / "chrooked_load.log"
    assert harness.log_path(old) == old / "Scripts" / "chrooked_load.log"


def test_est_lines_are_never_observations():
    obs = harness.parse_observations(_V21_LOG, "kindle")
    assert len(obs) == 4
    # The deliberately wrong EST line (Tackle "BOOSTED") must not be scored.
    assert {"move": "TACKLE", "type": "NORMAL", "kindle": "true", "result": "NORMAL"} in obs
    assert all(o.get("result") != "BOOSTED" or o["move"] != "TACKLE" for o in obs)


def test_kindle_scenario_scores_a_v21_log_unchanged():
    # The pre-NV-8 hand port's log, scored by the scenario 16.2 still uses.
    cases = tuple(BehaviorTestCase(given=f"case {i}", expect="") for i in range(1, 4))
    results = harness.score(harness.parse_observations(_V21_LOG, "kindle"), SCENARIOS["kindle"], cases)
    assert [r["passed"] for r in results] == [True, True, True]


def test_stage_on_v21_sets_the_oracle_marker_and_clears_the_log(tmp_path, capsys):
    v21, ruleset = _templated(tmp_path)
    (v21 / "chrooked_load.log").write_text("old session\n")

    assert harness.cmd_stage("cinderglow", ruleset, v21) == 0

    assert (v21 / "chrooked_load.log").read_text() == ""
    assert (v21 / harness.ORACLE_MARKER).exists()
    assert "nova_selftest.sh cinderglow" in capsys.readouterr().out


def test_stage_on_162_sets_no_marker(tmp_path):
    old = _copy("english_162", tmp_path)

    harness.cmd_stage("kindle", _RULESET, old)

    assert (old / "Scripts" / "chrooked_load.log").exists()
    assert not (old / harness.ORACLE_MARKER).exists()


def test_verify_on_v21_passes_and_reminds_about_the_marker(tmp_path, capsys):
    v21, ruleset = _templated(tmp_path)
    (v21 / "chrooked_load.log").write_text(_CINDERGLOW_LOG)
    (v21 / harness.ORACLE_MARKER).write_text("harness\n")

    assert harness.cmd_verify("cinderglow", ruleset, v21) == 0

    out = capsys.readouterr().out
    assert "3/3 passed" in out
    assert "still set" in out


# --- a templated spec (mjolnir NV-8): checks generated from its probes ---------
# A made-up ability, so these tests never depend on what the repo's Ruleset has
# templated today.

_CINDERGLOW_SPEC = """\
name: Cinderglow
chrooked_id: cinderglow
applies_to: ability
effects:
  - summary: "Fire-type moves deal 50% more damage."
    trigger: damage-calc
    effect: "multiply the move's damage by 1.5"
test_cases:
  - given: "a Cinderglow user uses Flamethrower"
    expect: "damage is 1.5x"
  - given: "a Cinderglow user uses Surf"
    expect: "no boost"
  - given: "a Pokemon without Cinderglow uses Flamethrower"
    expect: "no boost"
template:
  shape: type_boost
  params: {type: Fire, multiplier: 1.5}
  probes:
    - {move: Flamethrower, result: boosted}
    - {move: Surf, result: normal}
    - {move: Flamethrower, result: normal, holder: false}
"""

# What the generated port and the self-test log for it in one lab boot.
_CINDERGLOW_LOG = """\
[chrooked:cinderglow] load prior_handler=false
[chrooked:cinderglow] EST move=SURF type=WATER ability=true result=BOOSTED
[chrooked:cinderglow] OBS move=FLAMETHROWER type=FIRE ability=true result=BOOSTED
[chrooked:cinderglow] OBS move=SURF type=WATER ability=true result=NORMAL
[chrooked:cinderglow] OBS move=FLAMETHROWER ability=false result=NORMAL source=selftest holder=54 STENCH=36 none=36
[chrooked:selftest] DONE
"""


def _templated(tmp_path):
    """A v21 game whose PBS knows the probes' moves and the ability, plus a Ruleset
    holding the one templated spec."""
    v21 = _copy("modern_v21", tmp_path)
    with (v21 / "PBS" / "moves.txt").open("a", encoding="utf-8") as moves:
        moves.write("\n[FLAMETHROWER]\nName = Flamethrower\nType = FIRE\n\n[SURF]\nName = Surf\nType = WATER\n")
    (v21 / "PBS" / "abilities.txt").write_text("[CINDERGLOW]\nName = Cinderglow\n", encoding="utf-8")
    ruleset = tmp_path / "ruleset"
    (ruleset / "behaviors").mkdir(parents=True)
    (ruleset / "behaviors" / "cinderglow.yaml").write_text(_CINDERGLOW_SPEC, encoding="utf-8")
    return v21, ruleset


def test_templated_spec_on_v21_is_scored_by_checks_from_its_probes(tmp_path, capsys):
    v21, ruleset = _templated(tmp_path)
    (v21 / "chrooked_load.log").write_text(_CINDERGLOW_LOG)

    assert harness.cmd_verify("cinderglow", ruleset, v21) == 0
    assert "3/3 passed" in capsys.readouterr().out


def test_generated_checks_catch_a_misbehaving_port(tmp_path, capsys):
    v21, ruleset = _templated(tmp_path)
    wrong = _CINDERGLOW_LOG.replace("OBS move=SURF type=WATER ability=true result=NORMAL",
                                    "OBS move=SURF type=WATER ability=true result=BOOSTED")
    (v21 / "chrooked_load.log").write_text(wrong)

    assert harness.cmd_verify("cinderglow", ruleset, v21) == 1
    out = capsys.readouterr().out
    assert "2/3 passed" in out
    assert "FAIL cinderglow :: a Cinderglow user uses Surf" in out


def test_stage_prints_the_generated_actions(tmp_path, capsys):
    v21, ruleset = _templated(tmp_path)

    assert harness.cmd_stage("cinderglow", ruleset, v21) == 0

    out = capsys.readouterr().out
    assert "1. With your Cinderglow user, use Flamethrower on the foe." in out
    assert "3. With a Pokemon WITHOUT Cinderglow, use Flamethrower on the foe." in out
    assert (v21 / harness.ORACLE_MARKER).exists()


def test_templated_spec_on_162_still_needs_a_scenario(tmp_path):
    _, ruleset = _templated(tmp_path)
    old = _copy("english_162", tmp_path)

    with pytest.raises(SystemExit, match="no harness scenario for 'cinderglow'"):
        harness.cmd_verify("cinderglow", ruleset, old)


def test_template_the_game_cannot_resolve_fails_loudly(tmp_path):
    v21, ruleset = _templated(tmp_path)
    (v21 / "PBS" / "abilities.txt").write_text("", encoding="utf-8")

    with pytest.raises(SystemExit, match="cannot generate checks for 'cinderglow'.*ability 'Cinderglow'"):
        harness.cmd_verify("cinderglow", ruleset, v21)
