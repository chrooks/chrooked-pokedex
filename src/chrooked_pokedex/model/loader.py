"""Load a `ruleset/` folder of YAML into the frozen schema dataclasses.

Validation fails fast at the boundary: any unknown key in any file raises a
ValueError naming the offending key and the file it came from. Nothing is
silently ignored — an unknown field almost always means a typo, and a silent
drop would let a typo quietly disable an Override.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml

from .schema import (
    MOVE_CATEGORIES,
    STAT_KEYS,
    AbilitiesOverride,
    AbilityDef,
    EvolutionOverride,
    LearnsetMove,
    MoveDef,
    SpeciesOverride,
    TypeChartOverride,
)


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a YAML mapping at the top level")
    return data


def _check_keys(data: dict[str, Any], allowed: Iterable[str], where: str) -> None:
    unknown = [key for key in data if key not in set(allowed)]
    if unknown:
        raise ValueError(
            f"{where}: unknown field(s) {', '.join(sorted(unknown))}; "
            f"allowed fields are {', '.join(sorted(allowed))}"
        )


_SPECIES_KEYS = (
    "name", "chrooked_id", "aka", "types",
    "abilities", "stats", "learnset", "evolution",
)
_ABILITIES_KEYS = ("primary", "secondary", "hidden")
_LEARNSET_KEYS = ("level", "move")
_EVOLUTION_KEYS = ("from", "method")
_MOVE_KEYS = (
    "name", "chrooked_id", "aka", "type",
    "category", "power", "accuracy", "pp", "description",
)
_ABILITY_KEYS = ("name", "chrooked_id", "aka", "description")
_TYPE_CHART_ENTRY_KEYS = ("attacker", "defender", "multiplier")


def load_species(path: Path) -> SpeciesOverride:
    data = _read_yaml(path)
    _check_keys(data, _SPECIES_KEYS, path.name)

    abilities = None
    if "abilities" in data:
        ab = data["abilities"] or {}
        _check_keys(ab, _ABILITIES_KEYS, f"{path.name}:abilities")
        abilities = AbilitiesOverride(
            primary=ab.get("primary"),
            secondary=ab.get("secondary"),
            hidden=ab.get("hidden"),
        )

    learnset = None
    if "learnset" in data:
        moves: list[LearnsetMove] = []
        for entry in data["learnset"] or []:
            _check_keys(entry, _LEARNSET_KEYS, f"{path.name}:learnset")
            moves.append(LearnsetMove(level=entry["level"], move=entry["move"]))
        learnset = tuple(moves)

    evolution = None
    if "evolution" in data:
        evo = data["evolution"] or {}
        _check_keys(evo, _EVOLUTION_KEYS, f"{path.name}:evolution")
        evolution = EvolutionOverride(
            from_species=evo.get("from"),
            method=dict(evo.get("method") or {}),
        )

    types = tuple(data["types"]) if "types" in data else None

    stats = None
    if "stats" in data:
        stats = dict(data["stats"] or {})
        _check_keys(stats, STAT_KEYS, f"{path.name}:stats")

    return SpeciesOverride(
        name=data["name"],
        chrooked_id=data["chrooked_id"],
        aka=dict(data.get("aka") or {}),
        types=types,
        abilities=abilities,
        stats=stats,
        learnset=learnset,
        evolution=evolution,
    )


def load_move(path: Path) -> MoveDef:
    data = _read_yaml(path)
    _check_keys(data, _MOVE_KEYS, path.name)
    category = data["category"]
    if category not in MOVE_CATEGORIES:
        raise ValueError(
            f"{path.name}: invalid move category {category!r}; "
            f"expected one of {', '.join(sorted(MOVE_CATEGORIES))}"
        )
    return MoveDef(
        name=data["name"],
        chrooked_id=data["chrooked_id"],
        type=data["type"],
        category=data["category"],
        power=data.get("power"),
        accuracy=data.get("accuracy"),
        pp=data.get("pp"),
        description=data.get("description", ""),
        aka=dict(data.get("aka") or {}),
    )


def load_ability(path: Path) -> AbilityDef:
    data = _read_yaml(path)
    _check_keys(data, _ABILITY_KEYS, path.name)
    return AbilityDef(
        name=data["name"],
        chrooked_id=data["chrooked_id"],
        description=data.get("description", ""),
        aka=dict(data.get("aka") or {}),
    )


def load_type_chart(path: Path) -> tuple[TypeChartOverride, ...]:
    data = _read_yaml(path)
    _check_keys(data, ("overrides",), path.name)
    entries: list[TypeChartOverride] = []
    for entry in data.get("overrides") or []:
        _check_keys(entry, _TYPE_CHART_ENTRY_KEYS, f"{path.name}:overrides")
        entries.append(
            TypeChartOverride(
                attacker=entry["attacker"],
                defender=entry["defender"],
                multiplier=float(entry["multiplier"]),
            )
        )
    return tuple(entries)
