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
from chrooked_pokedex.behavior.harness_scenarios import SCENARIOS
from chrooked_pokedex.behavior.templates import harness_checks, render_essentials21, validate
from chrooked_pokedex.model import Ruleset

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[1]
_PORTS_DIR = _REPO / "references" / "essentials21-harness"
_RULESET = Ruleset.load(_REPO / "ruleset")
_TEMPLATED = sorted(cid for cid, spec in _RULESET.behaviors.items() if spec.template is not None)
_HAND = sorted(p.stem.removeprefix("chrooked_") for p in _PORTS_DIR.glob("chrooked_*.rb"))


class _DefaultNames:
    """Essentials' default INTERNAL spelling for every name, standing in for a game's PBS."""

    def move(self, name):
        return vocab.internal_name(name)

    type = ability = move


def _render(cid):
    return render_essentials21(_RULESET.behaviors[cid], _DefaultNames())


def test_the_proven_nova_ports_are_all_templated():
    assert len(_TEMPLATED) >= 22
    assert {"kindle", "overcharge", "chitinize", "wyvernize", "martialartist", "striker"} <= set(_TEMPLATED)


@pytest.mark.parametrize("cid", _TEMPLATED)
def test_template_validates_and_renders_a_registry_port(cid):
    spec = _RULESET.behaviors[cid]
    validate(spec.template, len(spec.test_cases), cid)
    text = _render(cid)
    assert text.startswith(f"# chrooked:{cid}\n")
    assert f".add(:{vocab.internal_name(spec.name)}," in text
    assert f'($chrooked_selftest_cases ||= {{}})["{cid}"] = {{' in text


@pytest.mark.parametrize("cid", _TEMPLATED)
def test_every_key_a_generated_check_reads_is_logged(cid):
    text = _render(cid)
    for check in harness_checks(_RULESET.behaviors[cid], _DefaultNames()):
        for key in {**check["select"], **check["expect"]}:
            assert f"{key}=" in text, f"{cid} never logs '{key}=' but its checks read it"


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


def test_every_hand_written_port_is_wired():
    for cid in _HAND:
        text = (_PORTS_DIR / f"chrooked_{cid}.rb").read_text(encoding="utf-8")
        spec = _RULESET.behaviors.get(cid)
        assert spec is not None, f"no behavior spec ruleset/behaviors/{cid}.yaml"
        assert has_plugin(cid), f"chrooked_{cid}.rb is empty or lacks its '# chrooked:{cid}' tag"
        assert "Battle::AbilityEffects::" in text and "PokeBattle_" not in text
        assert 'File.expand_path("chrooked-oracle.on")' in text  # marker-gated oracle
        assert f'($chrooked_selftest_cases ||= {{}})["{cid}"]' in text, \
            f"chrooked_{cid}.rb never registers its self-test case"
        assert cid in SCENARIOS and len(SCENARIOS[cid]) == len(spec.test_cases)
        logged = set(re.findall(r"\b([a-z_]+)=", text))
        for check in SCENARIOS[cid]:
            for key in {**check.get("select", {}), **check.get("expect", {})}:
                assert key in logged, f"{cid} never logs '{key}=' but its scenario reads it"
