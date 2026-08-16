"""Milestone 5 — create Ruleset-owned moves/abilities the target lacks."""

from pathlib import Path

from chrooked_pokedex.appliers.pokeemerald.creation import create_owned_content
from chrooked_pokedex.appliers.pokeemerald.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.readers.pokeemerald import ability_parser, move_parser
from chrooked_pokedex.report import ApplyReport


def _target(tmp_path: Path) -> Path:
    target = tmp_path / "fork"
    (target / "include" / "constants").mkdir(parents=True)
    (target / "src" / "data").mkdir(parents=True)
    (target / "include" / "constants" / "moves.h").write_text(
        """\
#define MOVE_NONE 0
#define MOVE_POUND 1
#define MOVES_COUNT_GEN9 2
#define MOVES_COUNT MOVES_COUNT_GEN9
#define MOVE_BREAKNECK_BLITZ (MOVES_COUNT + 0)
""",
        encoding="utf-8",
    )
    (target / "src" / "data" / "moves_info.h").write_text(
        """\
const struct MoveInfo gMovesInfo[MOVES_COUNT] =
{
    [MOVE_POUND] =
    {
        .name = COMPOUND_STRING("Pound"),
        .type = TYPE_NORMAL,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },
};
""",
        encoding="utf-8",
    )
    (target / "include" / "constants" / "abilities.h").write_text(
        """\
#define ABILITY_NONE 0
#define ABILITY_STENCH 1
#define ABILITIES_COUNT_GEN9 2
#define ABILITIES_COUNT ABILITIES_COUNT_GEN9
""",
        encoding="utf-8",
    )
    (target / "src" / "data" / "abilities.h").write_text(
        """\
const struct AbilityInfo gAbilitiesInfo[ABILITIES_COUNT] =
{
    [ABILITY_STENCH] =
    {
        .name = _("Stench"),
        .description = COMPOUND_STRING("Repels."),
    },
};
""",
        encoding="utf-8",
    )
    return target


def _ruleset(tmp_path: Path) -> Ruleset:
    root = tmp_path / "ruleset"
    (root / "moves").mkdir(parents=True)
    (root / "abilities").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (root / "moves" / "excalibur.yaml").write_text(
        """\
name: Excalibur
chrooked_id: excalibur
aka: { pokeemerald: MOVE_EXCALIBUR }
type: Steel
category: physical
power: 90
accuracy: 100
pp: 10
description: A holy blade.
""",
        encoding="utf-8",
    )
    (root / "abilities" / "striker.yaml").write_text(
        """\
name: Striker
chrooked_id: striker
aka: { pokeemerald: ABILITY_STRIKER }
description: Boosts kicking moves.
""",
        encoding="utf-8",
    )
    return Ruleset.load(root)


def test_create_move_and_ability(tmp_path: Path) -> None:
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    create_owned_content(target, ruleset, resmap, report)

    # The new move now parses with the right fields.
    moves = move_parser.parse_moves(target)
    assert "MOVE_EXCALIBUR" in moves
    assert moves["MOVE_EXCALIBUR"].type == "TYPE_STEEL"
    assert moves["MOVE_EXCALIBUR"].power == 90
    # The constant count was bumped so the new id fits.
    moves_h = (target / "include/constants/moves.h").read_text()
    assert "#define MOVE_EXCALIBUR 2" in moves_h
    assert "#define MOVES_COUNT_GEN9 3" in moves_h

    # The new ability parses too.
    abilities = ability_parser.parse_ability_text(target)
    assert abilities["ABILITY_STRIKER"][0] == "Striker"

    # And the resolution map now resolves them.
    assert resmap.move("Excalibur") == "MOVE_EXCALIBUR"
    assert resmap.ability("Striker") == "ABILITY_STRIKER"
    assert report.counts()["applied"] == 2


def test_create_ability_with_newline_description_round_trips(tmp_path: Path) -> None:
    """A multi-line description must emit a single-line C string (\\n escaped),
    or the C is invalid and the ability cannot be re-resolved (re-created forever)."""
    target = _target(tmp_path)
    root = tmp_path / "ruleset"
    (root / "abilities").mkdir(parents=True, exist_ok=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (root / "abilities" / "blitz.yaml").write_text(
        'name: Blitz\nchrooked_id: blitz\naka: { pokeemerald: ABILITY_BLITZ }\n'
        'description: "Turn 1: Speed +50%,\\nAttack +30%."\n',
        encoding="utf-8",
    )
    ruleset = Ruleset.load(root)
    resmap = build_resolution_map(target, ruleset)

    create_owned_content(target, ruleset, resmap, ApplyReport())

    # The textbox control code is flattened, NOT emitted as a backslash: a literal
    # backslash would break the GBA charmap preprocessor and fail the build.
    data = (target / "src/data/abilities.h").read_text()
    assert "\\" not in data.split("[ABILITY_BLITZ]")[1].split("},")[0]
    assert "+50%, Attack +30%." in data
    # And the ability still round-trips so a re-resolve finds it.
    resmap2 = build_resolution_map(target, ruleset)
    assert resmap2.ability("Blitz") == "ABILITY_BLITZ"


def test_creation_is_idempotent(tmp_path: Path) -> None:
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path)

    resmap = build_resolution_map(target, ruleset)
    create_owned_content(target, ruleset, resmap, ApplyReport())
    first = (target / "include/constants/moves.h").read_text()

    # Rebuild the map (Excalibur now resolves) and re-run: nothing should change.
    resmap2 = build_resolution_map(target, ruleset)
    changed = create_owned_content(target, ruleset, resmap2, ApplyReport())
    second = (target / "include/constants/moves.h").read_text()

    assert first == second
    assert changed == set()


def _enum_target(tmp_path: Path) -> Path:
    """Expansion >= 1.14 dialect: constants are enum members, not #defines."""
    target = tmp_path / "fork"
    (target / "include" / "constants").mkdir(parents=True)
    (target / "src" / "data").mkdir(parents=True)
    (target / "include" / "constants" / "moves.h").write_text(
        """\
enum MoveId
{
    MOVE_NONE = 0,
    MOVE_POUND = 1,
    MOVES_COUNT,
    FIRST_Z_MOVE = MOVES_COUNT,
    MOVES_COUNT_ALL,
};
""",
        encoding="utf-8",
    )
    (target / "src" / "data" / "moves_info.h").write_text(
        """\
const struct MoveInfo gMovesInfo[MOVES_COUNT_ALL] =
{
    [MOVE_POUND] =
    {
        .name = COMPOUND_STRING("Pound"),
        .type = TYPE_NORMAL,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },
};
""",
        encoding="utf-8",
    )
    (target / "include" / "constants" / "abilities.h").write_text(
        """\
enum __attribute__((packed)) Ability
{
    ABILITY_NONE = 0,
    ABILITY_STENCH = 1,
    ABILITIES_COUNT_GEN9,
    ABILITIES_COUNT = ABILITIES_COUNT_GEN9,
};
""",
        encoding="utf-8",
    )
    (target / "src" / "data" / "abilities.h").write_text(
        """\
const struct AbilityInfo gAbilitiesInfo[ABILITIES_COUNT] =
{
    [ABILITY_STENCH] =
    {
        .name = _("Stench"),
        .description = COMPOUND_STRING("Repels."),
    },
};
""",
        encoding="utf-8",
    )
    return target


def test_create_into_enum_constants(tmp_path: Path) -> None:
    target = _enum_target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = create_owned_content(target, ruleset, resmap, report)

    assert changed
    moves_h = (target / "include" / "constants" / "moves.h").read_text()
    abilities_h = (target / "include" / "constants" / "abilities.h").read_text()
    # New members sit immediately before their sentinel, keeping Z-moves shifted.
    assert "    MOVE_EXCALIBUR,\n    MOVES_COUNT,\n" in moves_h
    assert "    ABILITY_STRIKER,\n    ABILITIES_COUNT_GEN9,\n" in abilities_h
    # Data entries landed too.
    assert "MOVE_EXCALIBUR" in (target / "src" / "data" / "moves_info.h").read_text()
    assert "ABILITY_STRIKER" in (target / "src" / "data" / "abilities.h").read_text()
    assert report.counts()["blocked"] == 0


def test_create_into_enum_constants_is_idempotent(tmp_path: Path) -> None:
    target = _enum_target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    create_owned_content(target, ruleset, resmap, ApplyReport())
    before = (target / "include" / "constants" / "moves.h").read_text()

    create_owned_content(target, ruleset, build_resolution_map(target, ruleset), ApplyReport())

    assert (target / "include" / "constants" / "moves.h").read_text() == before
