"""Behavior layer — load + validate engine-neutral mechanic specs, render packets,
and flag created abilities whose mechanic still needs implementing.

Behavior specs are human-owned and live in `ruleset/behaviors/`, apart from the
machine-owned data the seed regenerates.
"""

from pathlib import Path

import pytest

from chrooked_pokedex.appliers.pokeemerald.creation import create_owned_content
from chrooked_pokedex.appliers.pokeemerald.resolution import build_resolution_map
from chrooked_pokedex.behavior import render_manifest, render_packet
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.loader import load_behavior
from chrooked_pokedex.report import ApplyReport

_VALID = """\
name: Inner Focus
chrooked_id: innerfocus
applies_to: ability
aka: { pokeemerald: ABILITY_INNER_FOCUS }
effects:
  - summary: "Prevents flinching."
    trigger: status-apply
    effect: "this Pokemon cannot flinch"
  - summary: "Focus Blast never misses."
    trigger: accuracy-check
    when: "the move is Focus Blast"
    effect: "skip the accuracy roll"
test_cases:
  - given: "Inner Focus user uses Focus Blast"
    expect: "hits"
notes:
  - "Mold Breaker does not bypass it."
engine_hints:
  pokeemerald: "battle_util.c accuracy calc"
  essentials: "pbAccuracyCheck"
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "innerfocus.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_behavior_parses_effects_tests_hints(tmp_path: Path) -> None:
    spec = load_behavior(_write(tmp_path, _VALID))

    assert spec.name == "Inner Focus"
    assert spec.applies_to == "ability"
    assert spec.aka["pokeemerald"] == "ABILITY_INNER_FOCUS"
    assert len(spec.effects) == 2
    # The gated effect kept its condition.
    gated = spec.effects[1]
    assert gated.trigger == "accuracy-check"
    assert gated.when == "the move is Focus Blast"
    assert spec.test_cases[0].expect == "hits"
    assert spec.notes == ("Mold Breaker does not bypass it.",)
    assert spec.engine_hints["essentials"] == "pbAccuracyCheck"


def test_load_behavior_rejects_unknown_trigger(tmp_path: Path) -> None:
    bad = _VALID.replace("trigger: status-apply", "trigger: when-i-feel-like-it")
    with pytest.raises(ValueError, match="unknown trigger"):
        load_behavior(_write(tmp_path, bad))


def test_load_behavior_rejects_invalid_applies_to(tmp_path: Path) -> None:
    bad = _VALID.replace("applies_to: ability", "applies_to: pokemon")
    with pytest.raises(ValueError, match="invalid applies_to"):
        load_behavior(_write(tmp_path, bad))


def test_load_behavior_requires_at_least_one_effect(tmp_path: Path) -> None:
    body = "name: X\nchrooked_id: x\napplies_to: ability\neffects: []\n"
    with pytest.raises(ValueError, match="at least one effect"):
        load_behavior(_write(tmp_path, body))


def test_load_behavior_rejects_test_case_missing_expect(tmp_path: Path) -> None:
    bad = _VALID.replace('    expect: "hits"', "")
    with pytest.raises(ValueError, match="missing required field 'expect'"):
        load_behavior(_write(tmp_path, bad))


def test_load_behavior_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    bad = _VALID + "frobnicate: yes\n"
    with pytest.raises(ValueError, match="unknown field"):
        load_behavior(_write(tmp_path, bad))


def test_ruleset_loads_behaviors_and_resolves_by_name_or_id(tmp_path: Path) -> None:
    root = tmp_path / "ruleset"
    (root / "behaviors").mkdir(parents=True)
    (root / "behaviors" / "innerfocus.yaml").write_text(_VALID, encoding="utf-8")
    ruleset = Ruleset.load(root)

    assert "innerfocus" in ruleset.behaviors
    assert ruleset.behavior_for("Inner Focus") is not None
    assert ruleset.behavior_for("innerfocus").name == "Inner Focus"
    assert ruleset.behavior_for("nope") is None


def test_shipped_inner_focus_spec_loads() -> None:
    """The real spec shipped in the repo must stay valid."""
    repo_ruleset = Path(__file__).resolve().parent.parent / "ruleset"
    ruleset = Ruleset.load(repo_ruleset)
    spec = ruleset.behavior_for("innerfocus")
    assert spec is not None
    assert any("Focus Blast" in e.summary for e in spec.effects)
    # The real invariant: the spec is verifiable at all — it carries test cases, not an
    # exact count (adding/removing a case should not break this).
    assert spec.test_cases


def test_render_manifest_lists_each_mechanic(tmp_path: Path) -> None:
    root = tmp_path / "ruleset"
    (root / "behaviors").mkdir(parents=True)
    (root / "behaviors" / "innerfocus.yaml").write_text(_VALID, encoding="utf-8")
    ruleset = Ruleset.load(root)

    manifest = render_manifest(ruleset)
    assert "1 mechanic" in manifest
    assert "innerfocus" in manifest
    assert "Inner Focus" in manifest


def test_render_manifest_empty_when_no_specs(tmp_path: Path) -> None:
    ruleset = Ruleset.load(tmp_path / "ruleset")
    assert "Nothing custom" in render_manifest(ruleset)


def test_render_packet_is_self_contained(tmp_path: Path) -> None:
    spec = load_behavior(_write(tmp_path, _VALID))
    packet = render_packet(spec, engine="pokeemerald")

    # intent, the gated condition, the chosen engine hint, and every test case.
    assert "Focus Blast never misses." in packet
    assert "when the move is Focus Blast" in packet
    assert "battle_util.c accuracy calc" in packet
    assert "pbAccuracyCheck" not in packet  # only the requested engine's hint
    assert "Given Inner Focus user uses Focus Blast, expect: hits." in packet


def test_render_packet_lists_all_hints_when_engine_omitted(tmp_path: Path) -> None:
    spec = load_behavior(_write(tmp_path, _VALID))
    packet = render_packet(spec)
    assert "battle_util.c accuracy calc" in packet
    assert "pbAccuracyCheck" in packet


def test_created_ability_with_behavior_is_flagged_data_only(tmp_path: Path) -> None:
    """When the applier creates an ability that has a behavior spec, the Apply Report
    must say DATA ONLY so the silent-inert-ability trap stays visible."""
    target = tmp_path / "fork"
    (target / "include" / "constants").mkdir(parents=True)
    (target / "src" / "data").mkdir(parents=True)
    (target / "include" / "constants" / "abilities.h").write_text(
        "#define ABILITY_NONE 0\n#define ABILITY_STENCH 1\n"
        "#define ABILITIES_COUNT_GEN9 2\n#define ABILITIES_COUNT ABILITIES_COUNT_GEN9\n",
        encoding="utf-8",
    )
    (target / "src" / "data" / "abilities.h").write_text(
        "const struct AbilityInfo gAbilitiesInfo[ABILITIES_COUNT] =\n{\n"
        '    [ABILITY_STENCH] =\n    {\n        .name = _("Stench"),\n'
        '        .description = COMPOUND_STRING("Repels."),\n    },\n};\n',
        encoding="utf-8",
    )

    root = tmp_path / "ruleset"
    (root / "abilities").mkdir(parents=True)
    (root / "behaviors").mkdir(parents=True)
    (root / "abilities" / "blitz.yaml").write_text(
        "name: Blitz\nchrooked_id: blitz\naka: { pokeemerald: ABILITY_BLITZ }\n"
        "description: Fast start.\n",
        encoding="utf-8",
    )
    # A behavior spec exists for Blitz → its creation must be flagged.
    (root / "behaviors" / "blitz.yaml").write_text(
        "name: Blitz\nchrooked_id: blitz\napplies_to: ability\n"
        "aka: { pokeemerald: ABILITY_BLITZ }\n"
        "effects:\n  - summary: First turn priority.\n    trigger: turn-order\n"
        "    effect: user moves first on its first turn out\n",
        encoding="utf-8",
    )
    ruleset = Ruleset.load(root)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    create_owned_content(target, ruleset, resmap, report)

    entry = next(e for e in report.entries if e.chrooked_id == "blitz")
    assert "DATA ONLY" in entry.reason


def test_created_ability_without_behavior_is_plain_created(tmp_path: Path) -> None:
    target = tmp_path / "fork"
    (target / "include" / "constants").mkdir(parents=True)
    (target / "src" / "data").mkdir(parents=True)
    (target / "include" / "constants" / "abilities.h").write_text(
        "#define ABILITY_NONE 0\n#define ABILITY_STENCH 1\n"
        "#define ABILITIES_COUNT_GEN9 2\n#define ABILITIES_COUNT ABILITIES_COUNT_GEN9\n",
        encoding="utf-8",
    )
    (target / "src" / "data" / "abilities.h").write_text(
        "const struct AbilityInfo gAbilitiesInfo[ABILITIES_COUNT] =\n{\n"
        '    [ABILITY_STENCH] =\n    {\n        .name = _("Stench"),\n'
        '        .description = COMPOUND_STRING("Repels."),\n    },\n};\n',
        encoding="utf-8",
    )
    root = tmp_path / "ruleset"
    (root / "abilities").mkdir(parents=True)
    (root / "abilities" / "striker.yaml").write_text(
        "name: Striker\nchrooked_id: striker\naka: { pokeemerald: ABILITY_STRIKER }\n"
        "description: Boosts kicks.\n",
        encoding="utf-8",
    )
    ruleset = Ruleset.load(root)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    create_owned_content(target, ruleset, resmap, report)

    entry = next(e for e in report.entries if e.chrooked_id == "striker")
    assert entry.reason == "created"
