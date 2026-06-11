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
