from pathlib import Path

from chrooked_pokedex.readers.pokeemerald.evolution_parser import EvolutionEntry, parse_evolutions


def test_parse_evolutions_table_format(tmp_path: Path) -> None:
    """Parse Chrooked's separate evolution.h table."""
    repo = tmp_path / "repo"
    _write_evolution_table(repo)

    evolutions = parse_evolutions(repo)

    assert "SPECIES_BULBASAUR" in evolutions
    assert evolutions["SPECIES_BULBASAUR"] == [
        EvolutionEntry("EVO_LEVEL", "16", "SPECIES_IVYSAUR"),
    ]

    assert "SPECIES_GLOOM" in evolutions
    gloom = evolutions["SPECIES_GLOOM"]
    assert len(gloom) == 2
    assert EvolutionEntry("EVO_ITEM", "ITEM_LEAF_STONE", "SPECIES_VILEPLUME") in gloom
    assert EvolutionEntry("EVO_ITEM", "ITEM_SUN_STONE", "SPECIES_BELLOSSOM") in gloom


def test_parse_evolutions_inline_format(tmp_path: Path) -> None:
    """Parse Pokeemerald/Target Fork inline .evolutions in species_info."""
    repo = tmp_path / "repo"
    _write_inline_evolutions(repo)

    evolutions = parse_evolutions(repo)

    assert "SPECIES_BULBASAUR" in evolutions
    assert evolutions["SPECIES_BULBASAUR"] == [
        EvolutionEntry("EVO_LEVEL", "16", "SPECIES_IVYSAUR"),
    ]

    assert "SPECIES_PIKACHU" in evolutions
    assert evolutions["SPECIES_PIKACHU"] == [
        EvolutionEntry("EVO_ITEM", "ITEM_THUNDER_STONE", "SPECIES_RAICHU"),
    ]


def test_parse_evolutions_multi_entry_inline(tmp_path: Path) -> None:
    """Parse multi-evolution inline format."""
    repo = tmp_path / "repo"
    _write_inline_evolutions_multi(repo)

    evolutions = parse_evolutions(repo)

    assert "SPECIES_GLOOM" in evolutions
    gloom = evolutions["SPECIES_GLOOM"]
    assert len(gloom) == 2
    assert EvolutionEntry("EVO_ITEM", "ITEM_LEAF_STONE", "SPECIES_VILEPLUME") in gloom
    assert EvolutionEntry("EVO_ITEM", "ITEM_SUN_STONE", "SPECIES_BELLOSSOM") in gloom


def test_parse_evolutions_species_without_evolutions_excluded(tmp_path: Path) -> None:
    """Species with no evolution data not in result."""
    repo = tmp_path / "repo"
    _write_inline_evolutions(repo)

    evolutions = parse_evolutions(repo)

    # SPECIES_VENUSAUR has no .evolutions field
    assert "SPECIES_VENUSAUR" not in evolutions


def test_parse_evolutions_prefers_table_over_inline(tmp_path: Path) -> None:
    """When evolution.h exists, use it instead of species_info inline."""
    repo = tmp_path / "repo"
    _write_evolution_table(repo)
    _write_inline_evolutions(repo)

    evolutions = parse_evolutions(repo)

    # Table has SPECIES_GLOOM, inline doesn't
    assert "SPECIES_GLOOM" in evolutions


_EVOLUTION_TABLE = """\
const struct Evolution gEvolutionTable[NUM_SPECIES][EVOS_PER_MON] =
{
    [SPECIES_BULBASAUR]  = {{EVO_LEVEL, 16, SPECIES_IVYSAUR}},
    [SPECIES_GLOOM]      = {{EVO_ITEM, ITEM_LEAF_STONE, SPECIES_VILEPLUME},
                            {EVO_ITEM, ITEM_SUN_STONE, SPECIES_BELLOSSOM}},
    [SPECIES_PIKACHU]    = {{EVO_ITEM, ITEM_THUNDER_STONE, SPECIES_RAICHU}},
};
"""

_INLINE_EVOLUTIONS = """\
    [SPECIES_BULBASAUR] =
    {
        .baseHP = 45,
        .evolutions = EVOLUTION({EVO_LEVEL, 16, SPECIES_IVYSAUR}),
    },
    [SPECIES_VENUSAUR] =
    {
        .baseHP = 80,
    },
    [SPECIES_PIKACHU] =
    {
        .baseHP = 35,
        .evolutions = EVOLUTION({EVO_ITEM, ITEM_THUNDER_STONE, SPECIES_RAICHU}),
    },
"""

_INLINE_EVOLUTIONS_MULTI = """\
    [SPECIES_GLOOM] =
    {
        .baseHP = 60,
        .evolutions = EVOLUTION({EVO_ITEM, ITEM_LEAF_STONE, SPECIES_VILEPLUME},
                                {EVO_ITEM, ITEM_SUN_STONE, SPECIES_BELLOSSOM}),
    },
"""


def _write_evolution_table(repo: Path) -> None:
    pokemon_dir = repo / "src" / "data" / "pokemon"
    pokemon_dir.mkdir(parents=True, exist_ok=True)
    (pokemon_dir / "evolution.h").write_text(_EVOLUTION_TABLE, encoding="utf-8")


def _write_inline_evolutions(repo: Path) -> None:
    pokemon_dir = repo / "src" / "data" / "pokemon"
    pokemon_dir.mkdir(parents=True, exist_ok=True)
    (pokemon_dir / "species_info.h").write_text(_INLINE_EVOLUTIONS, encoding="utf-8")


def _write_inline_evolutions_multi(repo: Path) -> None:
    pokemon_dir = repo / "src" / "data" / "pokemon"
    pokemon_dir.mkdir(parents=True, exist_ok=True)
    (pokemon_dir / "species_info.h").write_text(_INLINE_EVOLUTIONS_MULTI, encoding="utf-8")
