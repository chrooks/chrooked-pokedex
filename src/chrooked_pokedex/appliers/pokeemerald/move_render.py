"""Render MoveDef behavior fields to pokeemerald C expressions.

Shared by creation (writes a whole new move entry) and move_apply (edits the
behavior fields of an existing entry) so the two renderings cannot drift. Each
helper returns a C expression string; the caller decides where it goes.
"""

from __future__ import annotations

from ...model.schema import MoveDef
from ...seed import neutralize as nz
from .resolution import ResolutionMap

# The camelCase C field name for every modeled move flag (makesContact, bitingMove,
# …). move_apply reconciles exactly this set on an existing entry, never touching the
# engine's own unmodeled flags.
MODELED_FLAG_FIELDS: tuple[str, ...] = tuple(nz.NEUTRAL_TO_MOVE_FLAG.values())


def effect_symbol(move: MoveDef) -> str:
    return nz.primary_effect_symbol(move.effect)


def target_symbol(move: MoveDef) -> str:
    return nz.move_target_symbol(move.target)


def flag_fields(move: MoveDef) -> list[str]:
    """The camelCase flag fields this move sets — modeled flags only (an unmodeled
    neutral flag has no C field and is dropped here; callers note it as unresolved)."""
    fields: list[str] = []
    for flag in move.flags:
        symbol = nz.move_flag_symbol(flag)
        if symbol is not None:
            fields.append(symbol)
    return fields


def argument_braced(argument, resmap: ResolutionMap) -> str:
    """`{'type': 'Dragon'}` -> `{ .type = TYPE_DRAGON }`; ints render as-is."""
    parts = []
    for field, value in argument.items():
        camel = nz.snake_to_camel(field)
        if isinstance(value, int):
            rendered = str(value)
        else:  # a string argument is a type in practice (super-effective-on-type)
            rendered = resmap.type(value) or ("TYPE_" + str(value).upper().replace(" ", "_"))
        parts.append(f".{camel} = {rendered}")
    return "{ " + ", ".join(parts) + " }"


def additional_effects_expr(additional_effects) -> str:
    """Single-line `ADDITIONAL_EFFECTS({ .moveEffect = X, .chance = N }, ...)`."""
    inner = ", ".join(
        "{ .moveEffect = " + nz.move_effect_symbol(ae.effect) + f", .chance = {ae.chance} }}"
        for ae in additional_effects
    )
    return f"ADDITIONAL_EFFECTS({inner})"
