"""Read-only serialization of the four Ruleset-owned collections.

The Canon dex (`web/dex`) merges species onto a base snapshot; these four kinds
are *not* merged — the Ruleset owns them outright, so they serialize straight
from the in-memory `Ruleset` into JSON-able lists for the read-only tabs
(Milestone 1). Each builder is total: an absent kind yields `[]`, never an error.

Moves and abilities sort by display name so the tabs read alphabetically; the
type chart and behaviors keep their source order.
"""

from __future__ import annotations

from typing import Any

from ..model import Ruleset
from ..model.behavior_spec import BehaviorSpec
from ..model.schema import AbilityDef, MoveDef, TypeChartOverride


def build_moves(ruleset: Ruleset) -> list[dict[str, Any]]:
    return [_move(m) for m in sorted(ruleset.moves.values(), key=lambda m: m.name)]


def build_abilities(ruleset: Ruleset) -> list[dict[str, Any]]:
    return [
        _ability(a) for a in sorted(ruleset.abilities.values(), key=lambda a: a.name)
    ]


def build_type_chart(ruleset: Ruleset) -> list[dict[str, Any]]:
    return [_type_chart_entry(t) for t in ruleset.type_chart]


def build_behaviors(ruleset: Ruleset) -> list[dict[str, Any]]:
    return [
        _behavior(b) for b in sorted(ruleset.behaviors.values(), key=lambda b: b.name)
    ]


def _move(move: MoveDef) -> dict[str, Any]:
    return {
        "name": move.name,
        "chrooked_id": move.chrooked_id,
        "type": move.type,
        "category": move.category,
        "power": move.power,
        "accuracy": move.accuracy,
        "pp": move.pp,
        "description": move.description,
        "effect": move.effect,
        "argument": dict(move.argument) if move.argument is not None else None,
        "additional_effects": [
            {"effect": e.effect, "chance": e.chance} for e in move.additional_effects
        ],
        "flags": list(move.flags),
        "priority": move.priority,
        "target": move.target,
    }


def _ability(ability: AbilityDef) -> dict[str, Any]:
    return {
        "name": ability.name,
        "chrooked_id": ability.chrooked_id,
        "description": ability.description,
    }


def _type_chart_entry(entry: TypeChartOverride) -> dict[str, Any]:
    return {
        "attacker": entry.attacker,
        "defender": entry.defender,
        "multiplier": entry.multiplier,
    }


def _behavior(spec: BehaviorSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "chrooked_id": spec.chrooked_id,
        "applies_to": spec.applies_to,
        "effects": [
            {
                "summary": e.summary,
                "trigger": e.trigger,
                "effect": e.effect,
                "when": e.when,
            }
            for e in spec.effects
        ],
        "test_cases": [{"given": t.given, "expect": t.expect} for t in spec.test_cases],
        "notes": list(spec.notes),
        "engine_hints": dict(spec.engine_hints),
    }
