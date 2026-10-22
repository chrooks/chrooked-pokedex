"""Every Essentials 21 port stays wired to its spec, scenario and self-test case.

A port in references/essentials21-harness/ is only provable if the harness can
score it: the Ruleset has its behavior spec, harness_scenarios.py has one check
per spec test_case, the lab self-test has a CASES entry that produces the OBS
lines, and the port logs every key the scenario selects on. These tests catch a
port added without one of those pieces.
"""

import re
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.essentials.behavior_install import has_plugin
from chrooked_pokedex.behavior.harness_scenarios import SCENARIOS
from chrooked_pokedex.model import Ruleset

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[1]
_PORTS_DIR = _REPO / "references" / "essentials21-harness"
_SELFTEST = (_PORTS_DIR / "lab" / "010_battle_selftest.rb").read_text(encoding="utf-8")
_PORTS = sorted(p.stem.removeprefix("chrooked_") for p in _PORTS_DIR.glob("chrooked_*.rb"))
_RULESET = Ruleset.load(_REPO / "ruleset")


def _text(cid):
    return (_PORTS_DIR / f"chrooked_{cid}.rb").read_text(encoding="utf-8")


def test_the_first_batch_is_present():
    assert len(_PORTS) >= 17
    assert {"kindle", "bloom", "overcharge", "chitinize", "wyvernize"} <= set(_PORTS)


@pytest.mark.parametrize("cid", _PORTS)
def test_port_is_a_valid_v21_registry_entry(cid):
    text = _text(cid)
    assert has_plugin(cid) is True
    assert f"Battle::AbilityEffects::" in text
    assert f".add(:{cid.upper()}" in text
    assert 'File.expand_path("chrooked-oracle.on")' in text  # marker-gated oracle
    assert "PokeBattle_" not in text                          # no 16.2 class names


@pytest.mark.parametrize("cid", _PORTS)
def test_port_has_spec_scenario_and_selftest_case(cid):
    spec = _RULESET.behaviors.get(cid)
    assert spec is not None, f"no behavior spec ruleset/behaviors/{cid}.yaml"
    assert cid in SCENARIOS, f"no harness scenario for {cid}"
    assert len(SCENARIOS[cid]) == len(spec.test_cases)
    assert f'"{cid}" =>' in _SELFTEST, f"no CASES entry for {cid} in the lab self-test"


@pytest.mark.parametrize("cid", _PORTS)
def test_port_logs_every_key_its_scenario_reads(cid):
    logged = set(re.findall(r"\b([a-z_]+)=", _text(cid)))
    for check in SCENARIOS[cid]:
        for key in {**check.get("select", {}), **check.get("expect", {})}:
            assert key in logged, f"{cid} never logs '{key}=' but its scenario reads it"


@pytest.mark.parametrize("cid", _PORTS)
def test_selftest_measures_every_move_its_scenario_selects(cid):
    entry = re.search(rf'"{cid}" => \{{(.*?)\n    \}}', _SELFTEST, re.S).group(1)
    calc = re.search(r"calc: \[(.*)\]", entry).group(1)
    without = (re.search(r"without: \[(.*)\]", entry) or [None, ""])[1]
    for check in SCENARIOS[cid]:
        select = check.get("select", {})
        move = select.get("move")
        if not move:
            continue
        names = move if isinstance(move, list) else [move]
        # A case about a Pokemon WITHOUT the ability is measured by `without`, not CALC.
        pool = without if select.get("ability") == "false" else calc
        assert any(f":{n}" in pool for n in names), \
            f"{cid}: scenario selects {move} (ability={select.get('ability')}), the self-test never measures it"
