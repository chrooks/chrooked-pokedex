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

from .behavior_spec import (
    APPLIES_TO,
    TRIGGERS,
    BehaviorEffect,
    BehaviorSpec,
    BehaviorTestCase,
)
from .schema import (
    MOVE_CATEGORIES,
    MOVE_FLAGS,
    MOVE_TARGETS,
    STAT_KEYS,
    AbilitiesOverride,
    AbilityDef,
    AdditionalEffect,
    EvolutionOverride,
    LearnsetMove,
    MoveDef,
    SpeciesOverride,
    StatusDef,
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
    "abilities", "stats", "learnset", "evolution", "flavor_types",
)
_ABILITIES_KEYS = ("primary", "secondary", "hidden")
_LEARNSET_KEYS = ("level", "move")
_EVOLUTION_KEYS = ("from", "method")
_MOVE_KEYS = (
    "name", "chrooked_id", "aka", "type", "second_type",
    "category", "power", "accuracy", "pp", "description",
    "effect", "argument", "additional_effects", "flags", "priority", "target",
    "recoil", "strike_count",
)
_ADDITIONAL_EFFECT_KEYS = ("effect", "chance")
_ABILITY_KEYS = ("name", "chrooked_id", "aka", "description", "behaviors")
_STATUS_KEYS = ("name", "chrooked_id", "aka", "description", "effects")
_TYPE_CHART_ENTRY_KEYS = ("attacker", "defender", "multiplier")
_BEHAVIOR_KEYS = (
    "name", "chrooked_id", "applies_to", "aka",
    "effects", "test_cases", "notes", "engine_hints",
)
_EFFECT_KEYS = ("summary", "trigger", "effect", "when")
_TEST_CASE_KEYS = ("given", "expect")


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
    flavor_types = tuple(data["flavor_types"]) if "flavor_types" in data else None

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
        flavor_types=flavor_types,
    )


def _strike_count(data: dict, path: Path) -> int | None:
    """Validate `strike_count`: absent, or a whole number of hits from 2 to 10.

    1 is rejected rather than accepted-and-ignored — a single hit is the
    default, so writing it means the author expected it to mean something.
    """
    raw = data.get("strike_count")
    if raw is None:
        return None
    if not isinstance(raw, int) or isinstance(raw, bool) or not 2 <= raw <= 10:
        raise ValueError(
            f"{path.name}:strike_count: expected a whole number of hits "
            f"between 2 and 10, got {raw!r}"
        )
    return raw


def load_move(path: Path) -> MoveDef:
    data = _read_yaml(path)
    _check_keys(data, _MOVE_KEYS, path.name)
    category = data["category"]
    if category not in MOVE_CATEGORIES:
        raise ValueError(
            f"{path.name}: invalid move category {category!r}; "
            f"expected one of {', '.join(sorted(MOVE_CATEGORIES))}"
        )
    additional_effects: list[AdditionalEffect] = []
    for entry in data.get("additional_effects") or []:
        _check_keys(entry, _ADDITIONAL_EFFECT_KEYS, f"{path.name}:additional_effects")
        additional_effects.append(
            AdditionalEffect(effect=entry["effect"], chance=int(entry["chance"]))
        )

    flags = tuple(data.get("flags") or ())
    unknown_flags = [flag for flag in flags if flag not in MOVE_FLAGS]
    if unknown_flags:
        raise ValueError(
            f"{path.name}:flags: unknown flag(s) {', '.join(sorted(unknown_flags))}; "
            f"allowed flags are {', '.join(sorted(MOVE_FLAGS))}"
        )

    target = data.get("target", "selected")
    if target not in MOVE_TARGETS:
        raise ValueError(
            f"{path.name}:target: unknown target {target!r}; "
            f"allowed targets are {', '.join(sorted(MOVE_TARGETS))}"
        )

    return MoveDef(
        name=data["name"],
        chrooked_id=data["chrooked_id"],
        type=data["type"],
        second_type=data.get("second_type"),
        category=data["category"],
        power=data.get("power"),
        accuracy=data.get("accuracy"),
        pp=data.get("pp"),
        description=data.get("description", ""),
        aka=dict(data.get("aka") or {}),
        effect=data.get("effect", "hit"),
        argument=dict(data["argument"]) if data.get("argument") else None,
        additional_effects=tuple(additional_effects),
        flags=flags,
        priority=int(data.get("priority", 0)),
        target=target,
        recoil=data.get("recoil"),
        strike_count=_strike_count(data, path),
    )


def load_ability(path: Path) -> AbilityDef:
    data = _read_yaml(path)
    _check_keys(data, _ABILITY_KEYS, path.name)
    return AbilityDef(
        name=data["name"],
        chrooked_id=data["chrooked_id"],
        description=data.get("description", ""),
        aka=dict(data.get("aka") or {}),
        behaviors=tuple(data.get("behaviors") or ()),
    )


def load_status(path: Path) -> StatusDef:
    data = _read_yaml(path)
    _check_keys(data, _STATUS_KEYS, path.name)
    for required in ("name", "chrooked_id"):
        if not data.get(required):
            raise ValueError(f"{path.name}: missing required field {required!r}")
    return StatusDef(
        name=data["name"],
        chrooked_id=data["chrooked_id"],
        description=data.get("description", ""),
        effects=tuple(data.get("effects") or ()),
        aka=dict(data.get("aka") or {}),
    )


def load_behavior(path: Path) -> BehaviorSpec:
    """Load one hand-authored behavior spec from `ruleset/behaviors/`."""
    data = _read_yaml(path)
    where = path.name
    _check_keys(data, _BEHAVIOR_KEYS, where)

    for required in ("name", "chrooked_id", "applies_to"):
        if not data.get(required):
            raise ValueError(f"{where}: missing required field {required!r}")
    applies_to = data["applies_to"]
    if applies_to not in APPLIES_TO:
        raise ValueError(
            f"{where}: invalid applies_to {applies_to!r}; "
            f"expected one of {', '.join(sorted(APPLIES_TO))}"
        )

    raw_effects = data.get("effects") or []
    if not raw_effects:
        raise ValueError(f"{where}: at least one effect is required")
    effects = tuple(_load_effect(entry, where) for entry in raw_effects)

    test_cases = tuple(
        _load_test_case(entry, where) for entry in (data.get("test_cases") or [])
    )
    return BehaviorSpec(
        name=data["name"],
        chrooked_id=data["chrooked_id"],
        applies_to=applies_to,
        aka=dict(data.get("aka") or {}),
        effects=effects,
        test_cases=test_cases,
        notes=tuple(data.get("notes") or []),
        engine_hints=dict(data.get("engine_hints") or {}),
    )


def _load_effect(entry: dict[str, Any], where: str) -> BehaviorEffect:
    _check_keys(entry, _EFFECT_KEYS, f"{where}:effects")
    for required in ("summary", "trigger", "effect"):
        if not entry.get(required):
            raise ValueError(f"{where}:effects: missing required field {required!r}")
    trigger = entry["trigger"]
    if trigger not in TRIGGERS:
        raise ValueError(
            f"{where}:effects: unknown trigger {trigger!r}; "
            f"allowed triggers are {', '.join(sorted(TRIGGERS))}"
        )
    return BehaviorEffect(
        summary=entry["summary"],
        trigger=trigger,
        effect=entry["effect"],
        when=entry.get("when"),
    )


def _load_test_case(entry: dict[str, Any], where: str) -> BehaviorTestCase:
    _check_keys(entry, _TEST_CASE_KEYS, f"{where}:test_cases")
    for required in ("given", "expect"):
        if not entry.get(required):
            raise ValueError(f"{where}:test_cases: missing required field {required!r}")
    return BehaviorTestCase(given=entry["given"], expect=entry["expect"])


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
