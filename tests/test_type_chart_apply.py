"""Milestone 5 — apply type-chart multiplier overrides into types_info.h."""

from pathlib import Path

from chrooked_pokedex.appliers.pokeemerald.type_chart_apply import apply_type_chart
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.readers.pokeemerald.type_chart_parser import parse_type_chart
from chrooked_pokedex.report import ApplyReport


def _target(tmp_path: Path) -> Path:
    target = tmp_path / "fork"
    (target / "src" / "data").mkdir(parents=True)
    (target / "src" / "data" / "types_info.h").write_text(
        """\
#define X UQ_4_12
#define ______ X(1.0)
const uq4_12_t gTypeEffectivenessTable[N][N] =
{
    [TYPE_FLYING] = {______, ______, ______},
    [TYPE_GRASS]  = {______, ______, ______},
    [TYPE_ICE]    = {______, ______, ______},
};
""",
        encoding="utf-8",
    )
    return target


def _ruleset(tmp_path: Path) -> Ruleset:
    root = tmp_path / "ruleset"
    (root / "type-chart").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (root / "type-chart" / "overrides.yaml").write_text(
        """\
overrides:
  - { attacker: Flying, defender: Ice, multiplier: 0.5 }
""",
        encoding="utf-8",
    )
    return Ruleset.load(root)


def test_apply_type_chart_sets_cell(tmp_path: Path) -> None:
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path)
    report = ApplyReport()

    changed = apply_type_chart(target, ruleset, report)

    assert changed
    chart = parse_type_chart(target)
    # Flying -> Ice now does half damage.
    assert chart[("Flying", "Ice")].value == 0.5
    # An untouched cell stays neutral.
    assert chart[("Flying", "Flying")].value == 1.0
    assert report.counts()["applied"] == 1

    # The literal token is in the file.
    text = (target / "src/data/types_info.h").read_text()
    assert "X(0.5)" in text


def test_apply_type_chart_is_idempotent(tmp_path: Path) -> None:
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path)

    apply_type_chart(target, ruleset, ApplyReport())
    first = (target / "src/data/types_info.h").read_text()
    changed = apply_type_chart(target, ruleset, ApplyReport())
    second = (target / "src/data/types_info.h").read_text()

    assert first == second
    assert changed == set()
