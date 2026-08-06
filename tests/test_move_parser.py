from pathlib import Path

from chrooked_pokedex.readers.pokeemerald.move_parser import MoveInfo, parse_moves


def test_parse_moves_reads_fields(tmp_path: Path) -> None:
    """Parse a moves_info.h entry into a MoveInfo with all scalar fields."""
    repo = tmp_path / "repo"
    _write_moves_info(repo)

    moves = parse_moves(repo)

    assert "MOVE_POUND" in moves
    pound = moves["MOVE_POUND"]
    assert pound == MoveInfo(
        constant="MOVE_POUND",
        name="Pound",
        type="TYPE_NORMAL",
        category="PHYSICAL",
        power=40,
        accuracy=100,
        pp=35,
        description="Pounds with forelegs or tail.",
    )


def test_parse_moves_skips_sentinels(tmp_path: Path) -> None:
    """MOVE_NONE and similar sentinel entries are skipped."""
    repo = tmp_path / "repo"
    _write_moves_info(repo)

    moves = parse_moves(repo)

    assert "MOVE_NONE" not in moves


def test_parse_moves_missing_file_returns_empty(tmp_path: Path) -> None:
    """A repo with no moves_info.h returns an empty mapping."""
    assert parse_moves(tmp_path / "repo") == {}


def test_parse_moves_reads_gen_conditional_numbers(tmp_path: Path) -> None:
    """A generation-gated ternary yields the branch a default build ships.

    The expansion writes every gen-dependent number this way. Reading only a
    bare literal left 104 damaging moves with no power at all.
    """
    repo = tmp_path / "repo"
    _write_gen_conditional_moves(repo)

    moves = parse_moves(repo)

    # Both gating macros default to GEN_LATEST, so the `>=` test holds and the
    # first branch is the shipped value.
    assert moves["MOVE_FLAMETHROWER"].power == 90
    assert moves["MOVE_DRAGON_PULSE"].power == 85
    # Parenthesized condition, and a second gating macro.
    assert moves["MOVE_DRAGON_PULSE"].accuracy == 100
    assert moves["MOVE_HIDDEN_POWER"].power == 60
    # PP and a negative priority branch.
    assert moves["MOVE_FLAMETHROWER"].pp == 15
    assert moves["MOVE_TELEPORT"].priority == 0


def test_parse_moves_unreadable_number_is_absent_not_wrong(tmp_path: Path) -> None:
    """An expression we cannot resolve reads as absent, never as a wrong number."""
    repo = tmp_path / "repo"
    _write_gen_conditional_moves(repo)

    moves = parse_moves(repo)

    assert moves["MOVE_MYSTERY"].power is None
    # Priority has no "absent" state in the model, so it falls back to 0.
    assert moves["MOVE_MYSTERY"].priority == 0


def _write_gen_conditional_moves(repo: Path) -> None:
    data_dir = repo / "src" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "moves_info.h").write_text(
        """\
const struct MoveInfo gMovesInfo[MOVES_COUNT] =
{
    [MOVE_FLAMETHROWER] =
    {
        .name = COMPOUND_STRING("Flamethrower"),
        .type = TYPE_FIRE,
        .power = B_UPDATED_MOVE_DATA >= GEN_6 ? 90 : 95,
        .accuracy = 100,
        .pp = B_UPDATED_MOVE_DATA >= GEN_6 ? 15 : 10,
        .category = DAMAGE_CATEGORY_SPECIAL,
    },
    [MOVE_DRAGON_PULSE] =
    {
        .name = COMPOUND_STRING("Dragon Pulse"),
        .type = TYPE_DRAGON,
        .power = B_UPDATED_MOVE_DATA >= GEN_6 ? 85 : 90,
        .accuracy = (B_UPDATED_MOVE_DATA >= GEN_9) ? 100 : 95,
        .pp = 10,
        .category = DAMAGE_CATEGORY_SPECIAL,
    },
    [MOVE_HIDDEN_POWER] =
    {
        .name = COMPOUND_STRING("Hidden Power"),
        .type = TYPE_NORMAL,
        .power = B_HIDDEN_POWER_DMG >= GEN_6 ? 60 : 1,
        .accuracy = 100,
        .pp = 15,
        .category = DAMAGE_CATEGORY_SPECIAL,
    },
    [MOVE_TELEPORT] =
    {
        .name = COMPOUND_STRING("Teleport"),
        .type = TYPE_PSYCHIC,
        .power = 0,
        .accuracy = 0,
        .pp = 20,
        .priority = B_UPDATED_MOVE_DATA >= GEN_6 ? 0 : -7,
        .category = DAMAGE_CATEGORY_STATUS,
    },
    [MOVE_MYSTERY] =
    {
        .name = COMPOUND_STRING("Mystery"),
        .type = TYPE_NORMAL,
        .power = SOME_UNPARSEABLE_MACRO(3),
        .accuracy = 100,
        .pp = 5,
        .priority = ALSO_UNPARSEABLE,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },
};
""",
        encoding="utf-8",
    )


def _write_moves_info(repo: Path) -> None:
    data_dir = repo / "src" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "moves_info.h").write_text(
        """\
const struct MoveInfo gMovesInfo[MOVES_COUNT] =
{
    [MOVE_NONE] =
    {
        .name = COMPOUND_STRING("-"),
    },
    [MOVE_POUND] =
    {
        .name = COMPOUND_STRING("Pound"),
        .description = COMPOUND_STRING("Pounds with forelegs or tail."),
        .type = TYPE_NORMAL,
        .power = 40,
        .accuracy = 100,
        .pp = 35,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },
};
""",
        encoding="utf-8",
    )
