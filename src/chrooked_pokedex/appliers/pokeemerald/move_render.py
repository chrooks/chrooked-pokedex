"""Render MoveDef behavior fields to pokeemerald C expressions.

Shared by creation (writes a whole new move entry) and move_apply (edits the
behavior fields of an existing entry) so the two renderings cannot drift. Each
helper returns a C expression string; the caller decides where it goes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ...model.schema import MoveDef
from ...seed import neutralize as nz
from .resolution import ResolutionMap

# The camelCase C field name for every modeled move flag (makesContact, bitingMove,
# …). move_apply reconciles exactly this set on an existing entry, never touching the
# engine's own unmodeled flags.
MODELED_FLAG_FIELDS: tuple[str, ...] = tuple(nz.NEUTRAL_TO_MOVE_FLAG.values())


@dataclass(frozen=True)
class MoveDialect:
    """What the target's move layer actually speaks.

    Expansion 1.14 renamed `MOVE_TARGET_*` to `TARGET_*`, and forks differ on which
    flag bitfields `struct MoveInfo` carries (hammerMove/wingMove are Ruleset-custom).
    Rendering a symbol the target lacks breaks the ROM build, so both are detected
    from the target itself.
    """

    target_prefix: str = "MOVE_TARGET_"
    # None = struct not found, don't filter (pre-detection behavior).
    supported_flags: frozenset[str] | None = None

    def supports_flag(self, field: str) -> bool:
        return self.supported_flags is None or field in self.supported_flags


def detect_move_dialect(target: Path, moves_info_text: str) -> MoveDialect:
    prefix = "MOVE_TARGET_"
    if re.search(r"\.target\s*=\s*TARGET_", moves_info_text) and not re.search(
        r"\.target\s*=\s*MOVE_TARGET_", moves_info_text
    ):
        prefix = "TARGET_"
    return MoveDialect(
        target_prefix=prefix, supported_flags=_struct_move_info_flags(target)
    )


def _struct_move_info_flags(target: Path) -> frozenset[str] | None:
    """The bitfield names of the target's `struct MoveInfo`, or None if not found."""
    for rel in ("include/move.h", "include/pokemon.h", "include/battle.h"):
        path = target / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"struct MoveInfo\s*\{(.*?)\n\};", text, re.S)
        if m:
            return frozenset(re.findall(r"(\w+)\s*:\s*1\s*;", m.group(1)))
    return None


def effect_symbol(move: MoveDef) -> str:
    return nz.primary_effect_symbol(move.effect)


def target_symbol(move: MoveDef, dialect: MoveDialect | None = None) -> str:
    prefix = dialect.target_prefix if dialect else "MOVE_TARGET_"
    return prefix + move.target.upper()


def flag_fields(move: MoveDef, dialect: MoveDialect | None = None) -> list[str]:
    """The camelCase flag fields this move sets — modeled flags only, restricted to
    fields the target's struct carries (an unsupported flag has no C field there;
    callers note the drop as unresolved)."""
    fields: list[str] = []
    for flag in move.flags:
        symbol = nz.move_flag_symbol(flag)
        if symbol is not None and (dialect is None or dialect.supports_flag(symbol)):
            fields.append(symbol)
    return fields


def dropped_flag_fields(move: MoveDef, dialect: MoveDialect) -> list[str]:
    """Modeled flags the target's struct cannot hold — for honest report rows."""
    return [
        symbol
        for flag in move.flags
        if (symbol := nz.move_flag_symbol(flag)) is not None
        and not dialect.supports_flag(symbol)
    ]


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
