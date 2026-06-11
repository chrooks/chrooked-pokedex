from pathlib import Path

from chrooked_pokedex.readers.pokeemerald.learnset_parser import LearnsetEntry, parse_learnsets


def test_parse_learnsets_split_struct_format(tmp_path: Path) -> None:
    """Parse split/struct format learnsets (Pokeemerald/Target Fork layout)."""
    repo = tmp_path / "repo"
    _write_split_learnsets(repo)
    _write_species_info_with_learnset_refs(repo)

    learnsets = parse_learnsets(repo)

    assert "SPECIES_BULBASAUR" in learnsets
    bulbasaur = learnsets["SPECIES_BULBASAUR"]
    assert LearnsetEntry("MOVE_TACKLE", 1) in bulbasaur
    assert LearnsetEntry("MOVE_GROWL", 1) in bulbasaur
    assert LearnsetEntry("MOVE_VINE_WHIP", 13) in bulbasaur
    assert len(bulbasaur) == 4

    assert "SPECIES_CHARMANDER" in learnsets
    charmander = learnsets["SPECIES_CHARMANDER"]
    assert LearnsetEntry("MOVE_SCRATCH", 1) in charmander
    assert LearnsetEntry("MOVE_EMBER", 7) in charmander
    assert len(charmander) == 2


def test_parse_learnsets_flat_packed_u16_format(tmp_path: Path) -> None:
    """Parse flat/packed u16 format learnsets (Chrooked layout with pointer table)."""
    repo = tmp_path / "repo"
    _write_flat_learnsets(repo)
    _write_pointer_table(repo)

    learnsets = parse_learnsets(repo)

    assert "SPECIES_BULBASAUR" in learnsets
    bulbasaur = learnsets["SPECIES_BULBASAUR"]
    assert LearnsetEntry("MOVE_TACKLE", 1) in bulbasaur
    assert LearnsetEntry("MOVE_GROWL", 4) in bulbasaur
    assert LearnsetEntry("MOVE_VINE_WHIP", 10) in bulbasaur
    assert len(bulbasaur) == 3


def test_parse_learnsets_pointer_table_takes_precedence(tmp_path: Path) -> None:
    """When both pointer table and species_info refs exist, pointer table wins."""
    repo = tmp_path / "repo"
    _write_flat_learnsets(repo)
    _write_pointer_table(repo)
    _write_species_info_with_learnset_refs(repo)

    learnsets = parse_learnsets(repo)

    # Should still work — pointer table provides the mapping
    assert "SPECIES_BULBASAUR" in learnsets
    # SPECIES_CHARMANDER is only in species_info refs, not pointer table
    assert "SPECIES_CHARMANDER" not in learnsets


def test_parse_learnsets_ignores_original_files(tmp_path: Path) -> None:
    """Parser ignores _original backup files like _old fields in Species Profile."""
    repo = tmp_path / "repo"
    _write_flat_learnsets(repo)
    _write_pointer_table(repo)

    # Write an _original file with different data — should be ignored
    pokemon_dir = repo / "src" / "data" / "pokemon"
    (pokemon_dir / "level_up_learnsets_original.h").write_text(
        _FLAT_LEARNSET_CONTENT.replace("MOVE_VINE_WHIP", "MOVE_SOLAR_BEAM"),
        encoding="utf-8",
    )

    learnsets = parse_learnsets(repo)
    bulbasaur = learnsets["SPECIES_BULBASAUR"]
    assert LearnsetEntry("MOVE_VINE_WHIP", 10) in bulbasaur
    assert LearnsetEntry("MOVE_SOLAR_BEAM", 10) not in bulbasaur


_SPLIT_GEN1_CONTENT = """\
static const struct LevelUpMove sBulbasaurLevelUpLearnset[] = {
    LEVEL_UP_MOVE( 1, MOVE_TACKLE),
    LEVEL_UP_MOVE( 1, MOVE_GROWL),
    LEVEL_UP_MOVE( 7, MOVE_LEECH_SEED),
    LEVEL_UP_MOVE(13, MOVE_VINE_WHIP),
    LEVEL_UP_END
};

static const struct LevelUpMove sCharmanderLevelUpLearnset[] = {
    LEVEL_UP_MOVE( 1, MOVE_SCRATCH),
    LEVEL_UP_MOVE( 7, MOVE_EMBER),
    LEVEL_UP_END
};
"""

_FLAT_LEARNSET_CONTENT = """\
static const u16 sBulbasaurLevelUpLearnset[] = {
    LEVEL_UP_MOVE(1, MOVE_TACKLE),
    LEVEL_UP_MOVE(4, MOVE_GROWL),
    LEVEL_UP_MOVE(10, MOVE_VINE_WHIP),
    LEVEL_UP_END};
"""


def _write_split_learnsets(repo: Path) -> None:
    learnset_dir = repo / "src" / "data" / "pokemon" / "level_up_learnsets"
    learnset_dir.mkdir(parents=True)
    (learnset_dir / "gen_1.h").write_text(_SPLIT_GEN1_CONTENT, encoding="utf-8")


def _write_flat_learnsets(repo: Path) -> None:
    pokemon_dir = repo / "src" / "data" / "pokemon"
    pokemon_dir.mkdir(parents=True, exist_ok=True)
    (pokemon_dir / "level_up_learnsets.h").write_text(
        _FLAT_LEARNSET_CONTENT, encoding="utf-8"
    )


def _write_species_info_with_learnset_refs(repo: Path) -> None:
    """Write species_info entries with .levelUpLearnset references."""
    pokemon_dir = repo / "src" / "data" / "pokemon"
    pokemon_dir.mkdir(parents=True, exist_ok=True)
    (pokemon_dir / "species_info.h").write_text(
        """\
    [SPECIES_BULBASAUR] =
    {
        .baseHP = 45,
        .levelUpLearnset = sBulbasaurLevelUpLearnset,
    },
    [SPECIES_CHARMANDER] =
    {
        .baseHP = 39,
        .levelUpLearnset = sCharmanderLevelUpLearnset,
    },
""",
        encoding="utf-8",
    )


def _write_pointer_table(repo: Path) -> None:
    """Write Chrooked-style pointer table."""
    pokemon_dir = repo / "src" / "data" / "pokemon"
    pokemon_dir.mkdir(parents=True, exist_ok=True)
    (pokemon_dir / "level_up_learnset_pointers.h").write_text(
        """\
const u16 *const gLevelUpLearnsets[NUM_SPECIES] =
{
    [SPECIES_BULBASAUR] = sBulbasaurLevelUpLearnset,
};
""",
        encoding="utf-8",
    )
