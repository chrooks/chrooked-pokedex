from pathlib import Path

from chrooked_pokedex.readers.pokeemerald.type_chart_parser import parse_type_chart


def test_parse_type_chart_literals_and_sentinel(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_types_info(repo)

    chart = parse_type_chart(repo)

    # Column order equals row order: [Normal, Fire, Ice].
    # Regular effectiveness sentinel resolves to 1.0.
    assert chart[("Normal", "Normal")].value == 1.0
    # A literal X(0.5) cell resolves to 0.5 and keeps its raw token for diffing.
    fire_to_ice = chart[("Fire", "Ice")]
    assert fire_to_ice.value == 0.5
    assert fire_to_ice.raw == "X(0.5)"
    # An immunity X(0.0): Normal -> Fire (second column).
    assert chart[("Normal", "Fire")].value == 0.0


def test_parse_type_chart_resolves_conditional_macro(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_types_info(repo)

    chart = parse_type_chart(repo)

    # FIR_RS is `(COND >= GEN_2 ? X(0.5) : X(1.0))` -> modern branch 0.5,
    # but its raw token stays the macro name so diffs ignore build flags.
    # In the fixture it is the Ice -> Normal cell (first column of the Ice row).
    ice_to_normal = chart[("Ice", "Normal")]
    assert ice_to_normal.raw == "FIR_RS"
    assert ice_to_normal.value == 0.5


def _write_types_info(repo: Path) -> None:
    data_dir = repo / "src" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "types_info.h").write_text(
        """\
#define X UQ_4_12
#define ______ X(1.0)
#define FIR_RS (B_UPDATED_TYPE_MATCHUPS >= GEN_2 ? X(0.5) : X(1.0))

const uq4_12_t gTypeEffectivenessTable[NUMBER_OF_MON_TYPES][NUMBER_OF_MON_TYPES] =
{
    [TYPE_NORMAL] = {______, X(0.0), ______},
    [TYPE_FIRE]   = {______, ______, X(0.5)},
    [TYPE_ICE]    = {FIR_RS, ______, ______},
};
""",
        encoding="utf-8",
    )
    # Column order = row order = [Normal, Fire, Ice]:
    #   Normal->Normal=1.0, Normal->Fire=0.0(written as Ghost slot placeholder),
    # For clarity the test asserts only unambiguous cells.
