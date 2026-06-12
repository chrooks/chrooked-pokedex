"""Render MoveDef behavior to Essentials PBS values.

Shared by creation (new move sections) and move_apply (editing existing sections)
so the FunctionCode and flag logic cannot drift. `function_code` returns the desired
FunctionCode and EffectChance, or `(None, None)` when the effect has no faithful
Essentials equivalent — letting creation fall back to "None" for a brand-new move
while move_apply leaves an existing move's real FunctionCode untouched. Both append
unresolved notes for anything that could not be ported.
"""

from __future__ import annotations

from ...model.schema import MoveDef
from . import vocab


def function_code(move: MoveDef, unresolved: list[str]) -> tuple[str | None, int | None]:
    """Desired (FunctionCode, EffectChance). Returns (None, None) when the primary
    effect cannot be ported — the caller decides whether to default it or leave it."""
    primary = vocab.function_code(move.effect)  # "None" for hit, a code, or None
    if primary is None:
        unresolved.append(f"effect:{move.effect}")
        return None, None

    code = primary
    chance: int | None = None
    if move.additional_effects:
        first = move.additional_effects[0]
        secondary = vocab.additional_function_code(first.effect)
        if secondary is not None and code == vocab.NO_FUNCTION_CODE:
            code = secondary
            chance = first.chance
        else:
            unresolved.append(f"effect:{first.effect}")
        for extra in move.additional_effects[1:]:
            unresolved.append(f"effect:{extra.effect}(extra)")
    return code, chance


def flag_names(move: MoveDef, unresolved: list[str]) -> list[str]:
    """The Essentials flag names this move sets; an unmodeled neutral flag is noted."""
    names: list[str] = []
    for flag in move.flags:
        mapped = vocab.flag(flag)
        if mapped is None:
            unresolved.append(f"flag:{flag}")
        else:
            names.append(mapped)
    return names
