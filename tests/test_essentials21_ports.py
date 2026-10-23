"""Every Essentials 21 port stays provable: generated from its spec, or wired by hand.

Since mjolnir NV-8 a port in a proven shape is generated from its spec's
`template:` block, together with its self-test case and its harness checks, so
those three can no longer drift apart. What can still go wrong, and is caught here:
a template that stops validating or rendering, a check reading a key the port never
logs, a spec with both a template and a hand-written port (the installer would
block it), and a hand-written port missing its spec, scenario or self-test
registration.

Names resolve here by Essentials' default spelling (`High Jump Kick` ->
HIGHJUMPKICK); the real game's names are resolved, and the ports proven, by
`scripts/nova_selftest.sh --all` against the lab copy.
"""

import re
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.essentials import vocab
from chrooked_pokedex.appliers.essentials.behavior_install import has_plugin
from chrooked_pokedex.behavior.harness_scenarios import SCENARIOS, SCENARIOS_ESSENTIALS21
from chrooked_pokedex.behavior import compose
from chrooked_pokedex.behavior.templates import harness_checks, render_essentials21, validate_spec
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.schema import is_composed

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[1]
_PORTS_DIR = _REPO / "references" / "essentials21-harness"
_RULESET = Ruleset.load(_REPO / "ruleset")
_TEMPLATED = sorted(cid for cid, spec in _RULESET.behaviors.items() if spec.template is not None)
_HAND = sorted(p.stem.removeprefix("chrooked_") for p in _PORTS_DIR.glob("chrooked_*.rb"))
_SELFTEST_KEYS = set(re.findall(r"\b([a-z_]+)=", (_PORTS_DIR / "lab" / "010_battle_selftest.rb").read_text(encoding="utf-8")))


class _DefaultNames:
    """Essentials' default INTERNAL spelling for every name, standing in for a game's PBS."""

    def move(self, name):
        return vocab.internal_name(name)

    type = ability = item = move


def _render(cid):
    return render_essentials21(_RULESET.behaviors[cid], _DefaultNames())


def test_the_proven_nova_ports_are_all_templated():
    assert len(_TEMPLATED) >= 22
    assert {"kindle", "overcharge", "chitinize", "wyvernize", "martialartist", "striker"} <= set(_TEMPLATED)


@pytest.mark.parametrize("cid", _TEMPLATED)
def test_template_validates_and_renders_a_registry_port(cid):
    spec = _RULESET.behaviors[cid]
    validate_spec(spec)  # the shape's own check, and one effect per template
    text = _render(cid)
    assert text.startswith(f"# chrooked:{cid}\n")
    ability = vocab.internal_name(spec.name)
    # A registry entry, or (stat_swap, NV-23) a method wrapper keyed on the holder's ability.
    assert f".add(:{ability}," in text or f"user.hasActiveAbility?(:{ability})" in text
    assert f'($chrooked_selftest_cases ||= {{}})["{cid}"] = {{' in text


@pytest.mark.parametrize("cid", _TEMPLATED)
def test_every_key_a_generated_check_reads_is_logged(cid):
    """By the port, or by the lab self-test for a check on its own line (a rate it measured)."""
    text = _render(cid)
    for check in harness_checks(_RULESET.behaviors[cid], _DefaultNames()):
        selftest = check["select"].get("source") == "selftest"
        for key in {**check["select"], **check["expect"]}:
            logged = key in _SELFTEST_KEYS if selftest else f"{key}=" in text
            assert logged, f"{cid} never logs '{key}=' but its checks read it"


_COMPOSED = sorted(cid for cid, ability in _RULESET.abilities.items()
                   if is_composed(ability) and compose.render_essentials21(ability, _RULESET, _DefaultNames()))


def test_the_proven_compositions_compose():
    assert {"apexpredator", "razoredge", "requiem", "serratedjaw",  # NV-15
            "witchinghour", "kickboxer", "gyroscope", "brawlersspirit", "compulsion",  # NV-16
            "iceskater", "heavilyarmored", "breadbasket"} <= set(_COMPOSED)  # NV-17


@pytest.mark.parametrize("cid", _COMPOSED)
def test_every_key_a_composition_check_reads_is_logged(cid):
    """NV-15: by a part's port (re-tagged, with part=), or by the lab self-test."""
    ability = _RULESET.abilities[cid]
    text = compose.render_essentials21(ability, _RULESET, _DefaultNames())
    ports = text + "".join(_render(part) for part in ability.behaviors if part in _RULESET.behaviors)
    checks, cases = compose.harness_checks(ability, _RULESET, _DefaultNames())
    assert len(checks) == len(cases)
    for check in checks:
        selftest = check["select"].get("source") == "selftest"
        for key in {**check["select"], **check["expect"]}:
            logged = key in _SELFTEST_KEYS if selftest else (key == "part" or f"{key}=" in ports)
            assert logged, f"{cid} never logs '{key}=' but its checks read it"


@pytest.mark.parametrize("cid", _TEMPLATED)
def test_a_templated_spec_has_no_hand_port_too(cid):
    assert not (_PORTS_DIR / f"chrooked_{cid}.rb").exists(), \
        f"{cid} has a template AND a hand-written port; the installer blocks that as ambiguous"


def test_the_two_probes_follow_the_spec_prose():
    """Chris, 2026-10-22 (NV-8): a probe is its test case's sentence made checkable,
    so where the old scenario measured a stand-in move, the probe names the spec's."""
    assert _RULESET.behaviors["kindle"].template.probes[1]["move"] == "Surf"
    assert _RULESET.behaviors["striker"].template.probes[2] == {
        "move": "High Jump Kick", "result": "normal", "holder": False}


def test_scenario_tables_have_no_duplicate_keys():
    """A dict literal silently keeps the LAST duplicate key: NV-11's Essentials 21
    Infernal Maw scenario was shadowed that way by the older Rejuvenation one."""
    import ast
    import collections

    source = (_REPO / "src" / "chrooked_pokedex" / "behavior" / "harness_scenarios.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Dict) and node.keys and all(isinstance(k, ast.Constant) for k in node.keys):
            keys = [k.value for k in node.keys]
            if len(keys) > 2 and all(isinstance(k, str) for k in keys):
                dupes = [k for k, n in collections.Counter(keys).items() if n > 1]
                assert not dupes, f"duplicate scenario keys (line {node.lineno}): {dupes}"


def test_every_hand_written_port_is_wired():
    for cid in _HAND:
        text = (_PORTS_DIR / f"chrooked_{cid}.rb").read_text(encoding="utf-8")
        spec = _RULESET.behaviors.get(cid)
        assert spec is not None, f"no behavior spec ruleset/behaviors/{cid}.yaml"
        assert has_plugin(cid), f"chrooked_{cid}.rb is empty or lacks its '# chrooked:{cid}' tag"
        # An ability port adds to a handler registry; a status port (frostbite)
        # wraps Battle methods. Either way it is Essentials 21 code, not 16.2's.
        assert "Battle::" in text and "PokeBattle_" not in text
        if spec.applies_to == "ability":
            assert "Battle::AbilityEffects::" in text
        assert 'File.expand_path("chrooked-oracle.on")' in text  # marker-gated oracle
        assert f'($chrooked_selftest_cases ||= {{}})["{cid}"]' in text, \
            f"chrooked_{cid}.rb never registers its self-test case"
        checks = SCENARIOS_ESSENTIALS21.get(cid) or SCENARIOS.get(cid)
        assert checks is not None and len(checks) == len(spec.test_cases), f"no aligned scenario for {cid}"
        logged = set(re.findall(r"\b([a-z_]+)=", text))
        for check in checks:
            # A case the self-test measures on the mechanic's behalf (source=selftest:
            # a Pokemon without the ability, an on-hit chance) is logged by the self-test,
            # or (NV-25, case=check) by the port's own check proc, which the self-test runs.
            pool = _SELFTEST_KEYS | logged if check.get("select", {}).get("source") == "selftest" else logged
            for key in {**check.get("select", {}), **check.get("expect", {})}:
                assert key in pool, f"{cid} never logs '{key}=' but its scenario reads it"
