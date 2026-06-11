"""Seeding evolutions: a changed pre-evolution's whole list becomes backward
`from` pointers on its targets, with source identity stubs."""

from pathlib import Path

from chrooked_pokedex.seed.extractor import seed_from_fork


def _write(repo: Path, body: str) -> None:
    d = repo / "src" / "data" / "pokemon"
    d.mkdir(parents=True, exist_ok=True)
    (d / "species_info.h").write_text(body, encoding="utf-8")


def test_seed_emits_backward_evolution_and_source_stub(tmp_path: Path) -> None:
    base, fork = tmp_path / "base", tmp_path / "fork"
    # Base: Cubone -> Marowak only. Fork: Cubone branches to Marowak + Marowak-Alola.
    _write(base, """\
    [SPECIES_CUBONE] = { .baseHP = 50, .evolutions = EVOLUTION({EVO_LEVEL, 28, SPECIES_MAROWAK}), },
""")
    _write(fork, """\
    [SPECIES_CUBONE] =
    {
        .baseHP = 50,
        .evolutions = EVOLUTION({EVO_LEVEL, 28, SPECIES_MAROWAK}, {EVO_ITEM, ITEM_THICK_CLUB, SPECIES_MAROWAK_ALOLA}),
    },
""")

    seed = seed_from_fork(fork, base)

    # Both targets carry a backward pointer to Cubone.
    assert seed.species["marowak"].evolution.from_species == "Cubone"
    assert seed.species["marowak"].evolution.method == {"level": 28}
    assert seed.species["marowakalola"].evolution.from_species == "Cubone"
    assert seed.species["marowakalola"].evolution.method == {"item": "Thick Club"}
    # Cubone got an identity stub so the applier can resolve the pre-evolution.
    assert "cubone" in seed.species
    assert seed.species["cubone"].aka["pokeemerald"] == "SPECIES_CUBONE"


def test_seed_skips_unchanged_evolutions(tmp_path: Path) -> None:
    base, fork = tmp_path / "base", tmp_path / "fork"
    body = """\
    [SPECIES_CUBONE] = { .baseHP = 50, .evolutions = EVOLUTION({EVO_LEVEL, 28, SPECIES_MAROWAK}), },
"""
    _write(base, body)
    _write(fork, body)

    seed = seed_from_fork(fork, base)
    assert all(s.evolution is None for s in seed.species.values())
