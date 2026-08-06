"""Write a SeedData to a `ruleset/` folder as hand-readable, stable YAML.

Output is hand-rolled rather than `yaml.dump`ed so the format matches the
canonical sample (flow-style `aka`, `stats`, and learnset rows) and is fully
deterministic — re-running the seed produces byte-identical files, which is what
makes the seed idempotent.
"""

from __future__ import annotations

from pathlib import Path

from ..model.behavior_spec import BehaviorSpec
from ..model.schema import (
    AbilityDef,
    EvolutionOverride,
    MoveDef,
    SpeciesOverride,
    TypeChartOverride,
)
from .extractor import SeedData


def write_ruleset(seed: SeedData, ruleset_dir: Path) -> None:
    ruleset_dir = Path(ruleset_dir)
    _write_dir(ruleset_dir / "species", seed.species, species_yaml)
    _write_dir(ruleset_dir / "moves", seed.moves, move_yaml)
    _write_dir(ruleset_dir / "abilities", seed.abilities, ability_yaml)
    _write_type_chart(ruleset_dir / "type-chart" / "overrides.yaml", seed.type_chart)


def _write_dir(directory: Path, items: dict, render) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _clear_yaml(directory)
    for chrooked_id in sorted(items):
        (directory / f"{chrooked_id}.yaml").write_text(
            render(items[chrooked_id]), encoding="utf-8"
        )


def _clear_yaml(directory: Path) -> None:
    """Remove stale generated YAML so a re-seed leaves no orphans."""
    for path in directory.glob("*.yaml"):
        path.unlink()


# YAML indicator characters that change meaning when they lead a plain scalar.
_YAML_LEADING_SPECIALS = "[]{}*&!|>%@`#?,:-\"'"


def _scalar(value: object) -> str:
    if isinstance(value, str) and _needs_quoting(value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return '"' + escaped + '"'
    return str(value)


def _needs_quoting(value: str) -> bool:
    if value == "" or value != value.strip():
        return True
    if ":" in value or " #" in value:
        return True
    return value[0] in _YAML_LEADING_SPECIALS


def _aka_flow(aka: dict) -> str:
    parts = [f"{key}: {_scalar(aka[key])}" for key in aka]
    return "{ " + ", ".join(parts) + " }"


def species_yaml(species: SpeciesOverride) -> str:
    lines = [
        f"name: {species.name}",
        f"chrooked_id: {species.chrooked_id}",
        f"aka: {_aka_flow(dict(species.aka))}",
    ]
    if species.types:
        lines.append(f"types: [{', '.join(species.types)}]")
    if species.flavor_types:
        lines.append(f"flavor_types: [{', '.join(species.flavor_types)}]")
    if species.abilities:
        lines.append("abilities:")
        for slot in ("primary", "secondary", "hidden"):
            value = getattr(species.abilities, slot)
            if value is not None:
                lines.append(f"  {slot}: {value}")
    if species.stats:
        stats = ", ".join(f"{k}: {species.stats[k]}" for k in species.stats)
        lines.append(f"stats: {{ {stats} }}")
    if species.learnset is not None:
        lines.append("learnset:")
        for entry in species.learnset:
            lines.append(f"  - {{ level: {entry.level}, move: {_scalar(entry.move)} }}")
    if species.evolution is not None and species.evolution.from_species:
        lines.append(f"evolution: {_evolution_flow(species.evolution)}")
    return "\n".join(lines) + "\n"


def _evolution_flow(evolution: EvolutionOverride) -> str:
    method_parts = [f"{key}: {_scalar(value)}" for key, value in evolution.method.items()]
    method = "{ " + ", ".join(method_parts) + " }" if method_parts else "{}"
    return f"{{ from: {_scalar(evolution.from_species)}, method: {method} }}"


def move_yaml(move: MoveDef) -> str:
    lines = [
        f"name: {move.name}",
        f"chrooked_id: {move.chrooked_id}",
        f"aka: {_aka_flow(dict(move.aka))}",
        f"type: {move.type}",
        f"category: {move.category}",
    ]
    if move.power is not None:
        lines.append(f"power: {move.power}")
    if move.accuracy is not None:
        lines.append(f"accuracy: {move.accuracy}")
    if move.pp is not None:
        lines.append(f"pp: {move.pp}")
    if move.description:
        lines.append(f"description: {_scalar(move.description)}")
    if move.effect and move.effect != "hit":
        lines.append(f"effect: {move.effect}")
    if move.argument:
        arg = ", ".join(f"{k}: {_scalar(v)}" for k, v in move.argument.items())
        lines.append(f"argument: {{ {arg} }}")
    if move.additional_effects:
        lines.append("additional_effects:")
        for ae in move.additional_effects:
            lines.append(f"  - {{ effect: {ae.effect}, chance: {ae.chance} }}")
    if move.flags:
        lines.append(f"flags: [{', '.join(move.flags)}]")
    if move.priority:
        lines.append(f"priority: {move.priority}")
    if move.target and move.target != "selected":
        lines.append(f"target: {move.target}")
    return "\n".join(lines) + "\n"


def ability_yaml(ability: AbilityDef) -> str:
    lines = [
        f"name: {ability.name}",
        f"chrooked_id: {ability.chrooked_id}",
        f"aka: {_aka_flow(dict(ability.aka))}",
    ]
    if ability.description:
        lines.append(f"description: {_scalar(ability.description)}")
    return "\n".join(lines) + "\n"


def _write_type_chart(path: Path, overrides: list[TypeChartOverride]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(type_chart_yaml(overrides), encoding="utf-8")


def type_chart_yaml(overrides: list[TypeChartOverride]) -> str:
    """Render the whole type-chart override list as the canonical overrides.yaml."""
    lines = [
        "# Attacker/defender multiplier overrides relative to the base type chart.",
        "# multiplier: 0 = immune, 0.5 = not very effective, 1 = neutral, 2 = super effective.",
        "overrides:",
    ]
    for entry in sorted(overrides, key=lambda e: (e.attacker, e.defender)):
        lines.append(
            f"  - {{ attacker: {entry.attacker}, defender: {entry.defender}, "
            f"multiplier: {_format_multiplier(entry.multiplier)} }}"
        )
    return "\n".join(lines) + "\n"


def behavior_yaml(spec: BehaviorSpec) -> str:
    """Render one human-owned behavior spec as canonical, block-style YAML.

    The seed never writes behaviors, so this is the UI's renderer (slice 2b). It
    matches the hand-authored format: a header comment, flow-style `aka`, and
    block-style `effects` / `test_cases` / `notes` / `engine_hints`. String values
    go through `_scalar` so colons and leading specials in plain-language effect
    text are quoted and round-trip through the loader unchanged.
    """
    lines = [
        "# Behavior spec — human-owned. The seed never touches this folder.",
        f"name: {_scalar(spec.name)}",
        f"chrooked_id: {spec.chrooked_id}",
        f"applies_to: {spec.applies_to}",
        f"aka: {_aka_flow(dict(spec.aka))}",
    ]
    if spec.effects:
        lines.append("effects:")
        for effect in spec.effects:
            lines.append(f"  - summary: {_scalar(effect.summary)}")
            lines.append(f"    trigger: {effect.trigger}")
            if effect.when:
                lines.append(f"    when: {_scalar(effect.when)}")
            lines.append(f"    effect: {_scalar(effect.effect)}")
    if spec.test_cases:
        lines.append("test_cases:")
        for case in spec.test_cases:
            lines.append(f"  - given: {_scalar(case.given)}")
            lines.append(f"    expect: {_scalar(case.expect)}")
    if spec.notes:
        lines.append("notes:")
        for note in spec.notes:
            lines.append(f"  - {_scalar(note)}")
    if spec.engine_hints:
        lines.append("engine_hints:")
        for engine, hint in spec.engine_hints.items():
            lines.append(f"  {engine}: {_scalar(hint)}")
    return "\n".join(lines) + "\n"


def _format_multiplier(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return str(value)
