"""Milestone 2 — seed a Ruleset by diffing a fork against its base.

These use tiny hand-built base/fork repos so the diff logic is exercised
deterministically, without needing the real multi-hundred-megabyte forks.
"""

from pathlib import Path

from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.seed.extractor import seed_from_fork
from chrooked_pokedex.seed.writer import write_ruleset


def _write_species_info(repo: Path, body: str) -> None:
    d = repo / "src" / "data" / "pokemon"
    d.mkdir(parents=True, exist_ok=True)
    (d / "species_info.h").write_text(body, encoding="utf-8")


def _write_moves_info(repo: Path, body: str) -> None:
    d = repo / "src" / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "moves_info.h").write_text(body, encoding="utf-8")


_BASE_SPECIES = """\
    [SPECIES_GOODRA] =
    {
        .baseHP = 90,
        .baseSpeed = 80,
        .types = MON_TYPES(TYPE_DRAGON),
        .abilities = {ABILITY_SAP_SIPPER, ABILITY_HYDRATION, ABILITY_GOOEY},
    },
"""

_FORK_SPECIES = """\
    [SPECIES_GOODRA] =
    {
        .baseHP = 90,
        .baseSpeed = 90,
        .types = MON_TYPES(TYPE_WATER, TYPE_DRAGON),
        .abilities = {ABILITY_POISON_HEAL, ABILITY_HYDRATION, ABILITY_GOOEY},
    },
"""


def test_seed_captures_only_changed_species_fields(tmp_path: Path) -> None:
    base, fork = tmp_path / "base", tmp_path / "fork"
    _write_species_info(base, _BASE_SPECIES)
    _write_species_info(fork, _FORK_SPECIES)

    seed = seed_from_fork(fork, base)

    assert "goodra" in seed.species
    goodra = seed.species["goodra"]
    # type changed Dragon -> Water/Dragon
    assert goodra.types == ("Water", "Dragon")
    # only the changed ability slot (primary) is captured
    assert goodra.abilities.primary == "Poison Heal"
    assert goodra.abilities.secondary is None
    assert goodra.abilities.hidden is None
    # only the changed stat (speed) is captured; HP was unchanged
    assert goodra.stats == {"spe": 90}
    assert goodra.aka["pokeemerald"] == "SPECIES_GOODRA"


def test_seed_skips_unchanged_species(tmp_path: Path) -> None:
    base, fork = tmp_path / "base", tmp_path / "fork"
    _write_species_info(base, _BASE_SPECIES)
    _write_species_info(fork, _BASE_SPECIES)  # identical

    seed = seed_from_fork(fork, base)
    assert seed.species == {}


def test_seed_excludes_gmax_forms(tmp_path: Path) -> None:
    """Gigantamax forms are excluded even when the fork tuned them, so a re-seed
    never resurrects gmax entries Chris has removed from the Ruleset."""
    base, fork = tmp_path / "base", tmp_path / "fork"
    _write_species_info(
        base,
        """\
    [SPECIES_CHARIZARD_GMAX] =
    {
        .baseSpeed = 100,
        .abilities = {ABILITY_BLAZE, ABILITY_NONE, ABILITY_SOLAR_POWER},
    },
""",
    )
    _write_species_info(
        fork,
        """\
    [SPECIES_CHARIZARD_GMAX] =
    {
        .baseSpeed = 120,
        .abilities = {ABILITY_BLAZE, ABILITY_NONE, ABILITY_DROUGHT},
    },
""",
    )

    seed = seed_from_fork(fork, base)

    assert seed.species == {}  # the gmax change is dropped, not captured


def test_seed_owns_changed_and_new_moves(tmp_path: Path) -> None:
    base, fork = tmp_path / "base", tmp_path / "fork"
    _write_moves_info(
        base,
        """\
    [MOVE_POUND] =
    {
        .name = COMPOUND_STRING("Pound"),
        .type = TYPE_NORMAL,
        .power = 40,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },
""",
    )
    _write_moves_info(
        fork,
        """\
    [MOVE_POUND] =
    {
        .name = COMPOUND_STRING("Pound"),
        .type = TYPE_NORMAL,
        .power = 50,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },
    [MOVE_EXCALIBUR] =
    {
        .name = COMPOUND_STRING("Excalibur"),
        .type = TYPE_STEEL,
        .power = 90,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },
""",
    )

    seed = seed_from_fork(fork, base)

    assert "excalibur" in seed.moves
    assert seed.moves["excalibur"].type == "Steel"
    assert seed.moves["excalibur"].category == "physical"
    # Pound changed power -> owned too
    assert "pound" in seed.moves
    assert seed.moves["pound"].power == 50


def test_seed_round_trips_through_loader(tmp_path: Path) -> None:
    base, fork = tmp_path / "base", tmp_path / "fork"
    _write_species_info(base, _BASE_SPECIES)
    _write_species_info(fork, _FORK_SPECIES)

    seed = seed_from_fork(fork, base)
    out = tmp_path / "ruleset"
    (out).mkdir()
    (out / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    write_ruleset(seed, out)

    loaded = Ruleset.load(out)
    assert loaded.species["goodra"].types == ("Water", "Dragon")


def test_seed_writer_is_idempotent(tmp_path: Path) -> None:
    base, fork = tmp_path / "base", tmp_path / "fork"
    _write_species_info(base, _BASE_SPECIES)
    _write_species_info(fork, _FORK_SPECIES)
    seed = seed_from_fork(fork, base)

    out = tmp_path / "ruleset"
    out.mkdir()
    write_ruleset(seed, out)
    first = (out / "species" / "goodra.yaml").read_text()
    write_ruleset(seed, out)
    second = (out / "species" / "goodra.yaml").read_text()
    assert first == second
