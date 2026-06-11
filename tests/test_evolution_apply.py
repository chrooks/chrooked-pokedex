"""Milestone 5 — evolution Overrides rewrite the pre-evolution's .evolutions."""

from pathlib import Path

from chrooked_pokedex.appliers.pokeemerald.evolution_apply import apply_evolutions
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.readers.pokeemerald.evolution_parser import (
    EvolutionEntry,
    parse_evolutions,
)
from chrooked_pokedex.report import ApplyReport


def _target(tmp_path: Path) -> Path:
    target = tmp_path / "fork"
    pokemon = target / "src" / "data" / "pokemon"
    pokemon.mkdir(parents=True)
    (pokemon / "species_info.h").write_text(
        """\
    [SPECIES_SLIGGOO] =
    {
        .baseHP = 68,
        .evolutions = EVOLUTION({EVO_LEVEL, 40, SPECIES_GOODRA}),
    },
    [SPECIES_GOODRA] =
    {
        .baseHP = 90,
    },
""",
        encoding="utf-8",
    )
    return target


def _ruleset(tmp_path: Path) -> Ruleset:
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (root / "species" / "goodra.yaml").write_text(
        """\
name: Goodra
chrooked_id: goodra
aka: { pokeemerald: SPECIES_GOODRA }
evolution: { from: Sliggoo, method: { level: 50 } }
""",
        encoding="utf-8",
    )
    return Ruleset.load(root)


def test_apply_evolution_rewrites_pre_evolution(tmp_path: Path) -> None:
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path)
    report = ApplyReport()

    apply_evolutions(target, ruleset, report)

    evolutions = parse_evolutions(target)
    # Sliggoo now evolves into Goodra at level 50, not 40.
    assert evolutions["SPECIES_SLIGGOO"] == [
        EvolutionEntry("EVO_LEVEL", "50", "SPECIES_GOODRA"),
    ]
    assert report.counts()["applied"] == 1
