"""A behavior spec may carry a `template:` block (mjolnir NV-8).

The block names a known port shape, its params, and one probe per test case, so the
dex can generate the engine port, the self-test case and the harness checks. These
tests cover the spec layer only: the loader's structural check and the YAML round
trip through the seed writer. Whether a shape and its params make sense is
`chrooked_pokedex.behavior.templates`' job; the web save is covered in
tests/test_web_crud.py.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from chrooked_pokedex.model.behavior_spec import BehaviorTemplate
from chrooked_pokedex.model.loader import load_behavior
from chrooked_pokedex.seed.writer import behavior_yaml

pytestmark = pytest.mark.unit

_SPEC = """\
name: Striker
chrooked_id: striker
applies_to: ability
effects:
  - summary: "Kicking moves deal 30% more damage."
    trigger: damage-calc
    effect: "multiply the move's damage by 1.3"
test_cases:
  - given: "Striker user uses High Jump Kick"
    expect: "damage is multiplied by 1.3"
  - given: "Striker user uses Tackle"
    expect: "no boost"
  - given: "a Pokemon without Striker uses High Jump Kick"
    expect: "no boost"
"""

_TEMPLATE = """\
template:
  shape: flag_boost
  params: {flags: [kicking], multiplier: 1.3}
  probes:
    - {move: High Jump Kick, result: boosted}
    - {move: Tackle, result: normal}
    - {move: High Jump Kick, result: normal, holder: false}
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "striker.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_template_block_loads_typed(tmp_path: Path) -> None:
    spec = load_behavior(_write(tmp_path, _SPEC + _TEMPLATE))

    assert spec.template == BehaviorTemplate(
        shape="flag_boost",
        params={"flags": ["kicking"], "multiplier": 1.3},
        probes=(
            {"move": "High Jump Kick", "result": "boosted"},
            {"move": "Tackle", "result": "normal"},
            {"move": "High Jump Kick", "result": "normal", "holder": False},
        ),
    )


_BLOCKS = """\
template:
  - shape: keeps
    params: {}
    effects: [1]
    cases: [3]
    probes:
      - {measure: status, status: poison}
  - shape: flag_boost
    params: {flags: [kicking], multiplier: 1.3}
    effects: [1]
    cases: [1, 2]
    probes:
      - {move: High Jump Kick, result: boosted}
      - {move: Tackle, result: normal}
"""


def test_template_blocks_load_and_round_trip(tmp_path: Path) -> None:
    """NV-18: a list of blocks, each naming its effects and the test cases it covers."""
    spec = load_behavior(_write(tmp_path, _SPEC + _BLOCKS))

    assert spec.template.shape == "blocks"
    keeps, boost = spec.template.blocks
    assert (keeps.shape, keeps.effects, keeps.cases) == ("keeps", (1,), (3,))
    assert boost.probes == ({"move": "High Jump Kick", "result": "boosted"}, {"move": "Tackle", "result": "normal"})
    assert behavior_yaml(spec).endswith(_BLOCKS)


@pytest.mark.parametrize(("blocks", "message"), [
    (_BLOCKS.replace("cases: [3]", "cases: [2]"), "cover each of the 3 test_cases exactly once"),
    (_BLOCKS.replace("cases: [3]", "cases: [4]"), "cases must number test_cases, 1 to 3"),
    (_BLOCKS.replace("    effects: [1]\n    cases: [3]", "    cases: [3]"), "name the effects"),
    (_BLOCKS.replace("cases: [1, 2]", "cases: [1]"), "2 probes for 1 test_cases"),
])
def test_template_blocks_must_cover_every_case_once(tmp_path: Path, blocks: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_behavior(_write(tmp_path, _SPEC + blocks))


def test_spec_without_a_template_loads_none_and_writes_no_block(tmp_path: Path) -> None:
    spec = load_behavior(_write(tmp_path, _SPEC))

    assert spec.template is None
    assert "template:" not in behavior_yaml(spec)


def test_template_round_trips_through_the_writer(tmp_path: Path) -> None:
    spec = load_behavior(_write(tmp_path, _SPEC + _TEMPLATE))

    text = behavior_yaml(spec)

    # The block is written exactly as a human would (append-only migrations rely on it).
    assert text.endswith(_TEMPLATE)
    assert load_behavior(_write(tmp_path, text)).template == spec.template


def test_writer_quotes_strings_yaml_would_misread(tmp_path: Path) -> None:
    spec = load_behavior(_write(tmp_path, _SPEC))
    tricky = BehaviorTemplate(
        shape="flag_boost",
        params={"label": "yes", "colon": "a: b", "number_text": "1.5", "hp": 0.25, "lead": " x"},
        probes=({"move": "King's Shield"}, {"move": "Null"}, {"move": "U-turn"}),
    )

    text = behavior_yaml(replace(spec, template=tricky))

    assert load_behavior(_write(tmp_path, text)).template == tricky


def test_probe_count_must_match_test_cases(tmp_path: Path) -> None:
    two_probes = _TEMPLATE.rsplit("    - ", 1)[0]

    with pytest.raises(ValueError, match="2 probes for 3 test_cases"):
        load_behavior(_write(tmp_path, _SPEC + two_probes))


@pytest.mark.parametrize(
    ("block", "message"),
    [
        ("template: [flag_boost]\n", "expected a mapping"),
        ("template:\n  params: {}\n", "missing required field 'shape'"),
        ("template:\n  shape: flag_boost\n  shapes: x\n", "shapes"),
        ("template:\n  shape: flag_boost\n  params: [1]\n", "'params' must be a mapping"),
        ("template:\n  shape: flag_boost\n  probes: [Tackle, Surf, Ember]\n", "'probes' must be a list of mappings"),
    ],
)
def test_malformed_template_block_is_refused(tmp_path: Path, block: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_behavior(_write(tmp_path, _SPEC + block))
