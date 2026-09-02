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
from ..model.schema import AbilityDef, MoveDef, StatusDef, TypeChartOverride


def build_moves(ruleset: Ruleset) -> list[dict[str, Any]]:
    return [serialize_move(m) for m in sorted(ruleset.moves.values(), key=lambda m: m.name)]


def build_abilities(ruleset: Ruleset) -> list[dict[str, Any]]:
    return [
        serialize_ability(a)
        for a in sorted(ruleset.abilities.values(), key=lambda a: a.name)
    ]


def build_type_chart(ruleset: Ruleset) -> list[dict[str, Any]]:
    return [serialize_type_chart_entry(t) for t in ruleset.type_chart]


def build_behaviors(ruleset: Ruleset) -> list[dict[str, Any]]:
    return [
        serialize_behavior(b)
        for b in sorted(ruleset.behaviors.values(), key=lambda b: b.name)
    ]


def serialize_move(move: MoveDef) -> dict[str, Any]:
    return {
        "name": move.name,
        "chrooked_id": move.chrooked_id,
        # aka carries the engine symbol(s); surfaced so the editor round-trips it
        # on save instead of silently dropping it (it powers apply in M3).
        "aka": dict(move.aka),
        "type": move.type,
        # Dual-type moves (Muddy Water is Water AND Ground). The loader stores it
        # and the rejuv applier writes it as :secondtype, so omitting it here made
        # every editor save silently delete the move's second half.
        "second_type": move.second_type,
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
        "recoil": move.recoil,
        "strike_count": move.strike_count,
    }


def serialize_ability(ability: AbilityDef) -> dict[str, Any]:
    return {
        "name": ability.name,
        "chrooked_id": ability.chrooked_id,
        "description": ability.description,
        # see serialize_move: aka rides along so an edit doesn't strip it.
        "aka": dict(ability.aka),
        # Which behaviors this ability is built from; [] means its own.
        "behaviors": list(ability.behaviors),
    }


def serialize_status(status: StatusDef) -> dict[str, Any]:
    return {
        "name": status.name,
        "chrooked_id": status.chrooked_id,
        "description": status.description,
        "effects": list(status.effects),
        # see serialize_move: aka rides along so an edit doesn't strip it.
        "aka": dict(status.aka),
    }


def serialize_type_chart_entry(entry: TypeChartOverride) -> dict[str, Any]:
    return {
        "attacker": entry.attacker,
        "defender": entry.defender,
        "multiplier": entry.multiplier,
    }


def serialize_behavior(spec: BehaviorSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "chrooked_id": spec.chrooked_id,
        "applies_to": spec.applies_to,
        # see serialize_move: aka rides along so an edit doesn't strip it.
        "aka": dict(spec.aka),
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
