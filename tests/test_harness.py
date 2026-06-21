"""Hermetic tests for the Essentials log-oracle harness (issue #15, M1).

No game required: feed a captured log string through the parser + scorer.
"""

import pytest

from chrooked_pokedex.behavior.harness import parse_observations, score
from chrooked_pokedex.model.behavior_spec import BehaviorTestCase

pytestmark = pytest.mark.unit

# Three test_cases standing in for innerfocus's spec (order matters).
_CASES = (
    BehaviorTestCase(given="Inner Focus user uses Focus Blast at a foe with +6 evasion", expect="the move hits"),
    BehaviorTestCase(given="Inner Focus user uses Hydro Pump", expect="normal accuracy applies"),
    BehaviorTestCase(given="a Pokemon without Inner Focus uses Focus Blast", expect="normal 70% accuracy applies"),
)

_CHECKS = [
    {"select": {"move": "FOCUSBLAST", "if": "true"}, "expect": {"result": "ALWAYS_HIT"}},
    {"select": {"move": "HYDROPUMP", "if": "true"}, "expect": {"result": "NORMAL"}},
    {"select": {"move": "FOCUSBLAST", "if": "false"}, "expect": {"result": "NORMAL"}},
]

_GREEN_LOG = """\
[LOAD_ORDER_SHIM] active
[chrooked:innerfocus] installed on PokeBattle_Move
[chrooked:innerfocus] OBS move=FOCUSBLAST if=true result=ALWAYS_HIT
[chrooked:innerfocus] OBS move=HYDROPUMP if=true result=NORMAL
[chrooked:innerfocus] OBS move=FOCUSBLAST if=false result=NORMAL
"""


def test_parse_ignores_noise_and_other_mechanics():
    log = _GREEN_LOG + "[chrooked:kindle] OBS move=EMBER result=BOOSTED\n"
    obs = parse_observations(log, "innerfocus")
    assert len(obs) == 3
    assert obs[0] == {"move": "FOCUSBLAST", "if": "true", "result": "ALWAYS_HIT"}


def test_all_pass_when_log_matches_spec():
    results = score(parse_observations(_GREEN_LOG, "innerfocus"), _CHECKS, _CASES)
    assert [r["passed"] for r in results] == [True, True, True]
    assert results[0]["given"].startswith("Inner Focus user uses Focus Blast")


def test_fail_when_delta_leaks_to_other_move():
    # Bug: Hydro Pump got always-hit too.
    broken = _GREEN_LOG.replace("move=HYDROPUMP if=true result=NORMAL", "move=HYDROPUMP if=true result=ALWAYS_HIT")
    results = score(parse_observations(broken, "innerfocus"), _CHECKS, _CASES)
    assert [r["passed"] for r in results] == [True, False, True]
    assert "expected" in results[1]["reason"]


def test_fail_when_action_not_staged():
    # Case 3 never cast -> not observed.
    partial = "\n".join(_GREEN_LOG.splitlines()[:-1]) + "\n"
    results = score(parse_observations(partial, "innerfocus"), _CHECKS, _CASES)
    assert results[2]["passed"] is False
    assert "not observed" in results[2]["reason"]
