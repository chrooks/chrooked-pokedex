"""Milestone 5 — the create-then-cite tier: a Ruleset-owned move is created,
and a learnset that cites it lands as applied (not partial)."""

from pathlib import Path

from chrooked_pokedex.appliers.pokeemerald.creation import create_owned_content
from chrooked_pokedex.appliers.pokeemerald.learnset_apply import apply_learnsets
from chrooked_pokedex.appliers.pokeemerald.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.readers.pokeemerald.learnset_parser import parse_learnsets
from chrooked_pokedex.report import ApplyReport


def _target(tmp_path: Path) -> Path:
    target = tmp_path / "fork"
    pokemon = target / "src" / "data" / "pokemon"
    (pokemon / "level_up_learnsets").mkdir(parents=True)
    (target / "include" / "constants").mkdir(parents=True)
    # Aegislash cites a move the target does not have yet.
    (pokemon / "level_up_learnsets" / "gen_1.h").write_text(
        """\
static const struct LevelUpMove sAegislashLevelUpLearnset[] = {
    LEVEL_UP_MOVE(1, MOVE_TACKLE),
    LEVEL_UP_END
};
""",
        encoding="utf-8",
    )
    (pokemon / "species_info.h").write_text(
        """\
    [SPECIES_AEGISLASH] =
    {
        .baseHP = 60,
        .levelUpLearnset = sAegislashLevelUpLearnset,
    },
""",
        encoding="utf-8",
    )
    (target / "src" / "data" / "moves_info.h").write_text(
        """\
const struct MoveInfo gMovesInfo[MOVES_COUNT] =
{
    [MOVE_TACKLE] = { .name = COMPOUND_STRING("Tackle"), .type = TYPE_NORMAL, .category = DAMAGE_CATEGORY_PHYSICAL, },
};
""",
        encoding="utf-8",
    )
    (target / "include" / "constants" / "moves.h").write_text(
        """\
#define MOVE_NONE 0
#define MOVE_TACKLE 1
#define MOVES_COUNT_GEN9 2
#define MOVES_COUNT MOVES_COUNT_GEN9
""",
        encoding="utf-8",
    )
    return target


def _ruleset(tmp_path: Path) -> Ruleset:
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "moves").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (root / "species" / "aegislash.yaml").write_text(
        """\
name: Aegislash
chrooked_id: aegislash
aka: { pokeemerald: SPECIES_AEGISLASH }
learnset:
  - { level: 1, move: Tackle }
  - { level: 50, move: Excalibur }
""",
        encoding="utf-8",
    )
    (root / "moves" / "excalibur.yaml").write_text(
        """\
name: Excalibur
chrooked_id: excalibur
aka: { pokeemerald: MOVE_EXCALIBUR }
type: Steel
category: physical
power: 90
""",
        encoding="utf-8",
    )
    return Ruleset.load(root)


def test_creation_turns_partial_learnset_into_applied(tmp_path: Path) -> None:
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)

    # Before creation: Excalibur cannot resolve, so the learnset is partial.
    pre_report = ApplyReport()
    apply_learnsets(target, ruleset, resmap, pre_report)
    assert pre_report.counts()["partial"] == 1

    # Create owned content (updates the resolution map in place), then re-apply.
    create_owned_content(target, ruleset, resmap, ApplyReport())
    post_report = ApplyReport()
    apply_learnsets(target, ruleset, resmap, post_report)

    assert post_report.counts()["applied"] == 1
    assert post_report.counts()["partial"] == 0
    # Excalibur is now actually in Aegislash's learnset.
    aegislash = parse_learnsets(target)["SPECIES_AEGISLASH"]
    assert any(e.move == "MOVE_EXCALIBUR" for e in aegislash)
