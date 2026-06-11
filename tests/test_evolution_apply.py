"""Evolution Overrides rewrite the pre-evolution's whole `.evolutions` list."""

from pathlib import Path

from chrooked_pokedex.appliers.pokeemerald.evolution_apply import apply_evolutions
from chrooked_pokedex.appliers.pokeemerald.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.readers.pokeemerald.evolution_parser import (
    EvolutionEntry,
    parse_evolutions,
)
from chrooked_pokedex.report import ApplyReport


def _target(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "fork"
    pokemon = target / "src" / "data" / "pokemon"
    pokemon.mkdir(parents=True)
    (pokemon / "species_info.h").write_text(body, encoding="utf-8")
    return target


def _ruleset(tmp_path: Path, files: dict[str, str]) -> Ruleset:
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    for name, content in files.items():
        (root / "species" / f"{name}.yaml").write_text(content, encoding="utf-8")
    return Ruleset.load(root)


def test_apply_evolution_rewrites_pre_evolution(tmp_path: Path) -> None:
    target = _target(
        tmp_path,
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
    )
    ruleset = _ruleset(tmp_path, {
        # the pre-evolution needs an identity entry so its symbol resolves
        "sliggoo": "name: Sliggoo\nchrooked_id: sliggoo\naka: { pokeemerald: SPECIES_SLIGGOO }\n",
        "goodra": (
            "name: Goodra\nchrooked_id: goodra\naka: { pokeemerald: SPECIES_GOODRA }\n"
            "evolution: { from: Sliggoo, method: { level: 50 } }\n"
        ),
    })
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_evolutions(target, ruleset, resmap, report)

    evolutions = parse_evolutions(target)
    assert evolutions["SPECIES_SLIGGOO"] == [
        EvolutionEntry("EVO_LEVEL", "50", "SPECIES_GOODRA"),
    ]
    assert report.counts()["applied"] == 1


def test_branching_evolution_keeps_all_targets(tmp_path: Path) -> None:
    """A pre-evolution that branches must keep every target — whole-list replace,
    not one-target-at-a-time clobbering."""
    target = _target(
        tmp_path,
        """\
    [SPECIES_CUBONE] =
    {
        .baseHP = 50,
        .evolutions = EVOLUTION({EVO_LEVEL, 28, SPECIES_MAROWAK}),
    },
    [SPECIES_MAROWAK] = { .baseHP = 60, },
    [SPECIES_MAROWAK_ALOLA] = { .baseHP = 60, },
""",
    )
    ruleset = _ruleset(tmp_path, {
        "cubone": "name: Cubone\nchrooked_id: cubone\naka: { pokeemerald: SPECIES_CUBONE }\n",
        "marowak": (
            "name: Marowak\nchrooked_id: marowak\naka: { pokeemerald: SPECIES_MAROWAK }\n"
            "evolution: { from: Cubone, method: { level: 28 } }\n"
        ),
        "marowakalola": (
            "name: Marowak Alola\nchrooked_id: marowakalola\n"
            "aka: { pokeemerald: SPECIES_MAROWAK_ALOLA }\n"
            "evolution: { from: Cubone, method: { level: 28 } }\n"
        ),
    })
    resmap = build_resolution_map(target, ruleset)

    apply_evolutions(target, ruleset, resmap, ApplyReport())

    cubone = parse_evolutions(target)["SPECIES_CUBONE"]
    targets = {e.target_species for e in cubone}
    # Both branches survive — the form is not clobbered by the base form.
    assert targets == {"SPECIES_MAROWAK", "SPECIES_MAROWAK_ALOLA"}


def test_passthrough_method_round_trips(tmp_path: Path) -> None:
    target = _target(
        tmp_path,
        """\
    [SPECIES_SLIGGOO] = { .baseHP = 68, },
    [SPECIES_GOODRA] = { .baseHP = 90, },
""",
    )
    ruleset = _ruleset(tmp_path, {
        "sliggoo": "name: Sliggoo\nchrooked_id: sliggoo\naka: { pokeemerald: SPECIES_SLIGGOO }\n",
        "goodra": (
            "name: Goodra\nchrooked_id: goodra\naka: { pokeemerald: SPECIES_GOODRA }\n"
            "evolution: { from: Sliggoo, method: { pokeemerald: EVO_LEVEL_RAIN, param: 0 } }\n"
        ),
    })
    resmap = build_resolution_map(target, ruleset)

    apply_evolutions(target, ruleset, resmap, ApplyReport())

    sliggoo = parse_evolutions(target)["SPECIES_SLIGGOO"]
    assert sliggoo == [EvolutionEntry("EVO_LEVEL_RAIN", "0", "SPECIES_GOODRA")]
