"""Moves category: splice MoveDef stats into data/moves/moves.asm.

The `move` macro line carries: name(1), effect(2), power(3), type(4),
accuracy(5), pp(6), effect_chance(7), category(8). Only args 3-8 are data this
Applier owns; a MoveDef's `effect`, `priority`, `flags`, and the identity of
its `additional_effects` live in engine code (or separate tables) and are
reported as partial fields, never written.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from .asm_edit import find_macro_line, splice_args
from .resolution import ResolutionMap

# MoveDef fields the macro line cannot carry. `additional_effects` is listed
# because only its *chance* lands (arg 7) — the effect identity is engine code.
_ENGINE_CODE_FIELDS = ("effect", "priority", "flags", "additional_effects")

_MOVES_FILE = Path("data") / "moves" / "moves.asm"


def apply_moves(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> list[Path]:
    """Apply every Ruleset MoveDef; return the files changed."""
    moves_path = Path(target) / _MOVES_FILE
    text = moves_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    changed = False

    for chrooked_id, move in sorted(ruleset.moves.items()):
        symbol = resmap.move(chrooked_id, dict(move.aka), name=move.name)
        if symbol is None:
            report.add(ReportEntry(
                status="blocked", category="move", chrooked_id=chrooked_id,
                reason=f"no such move in target (derived {_derived(move)})",
            ))
            continue

        type_symbol = resmap.type(move.type)
        if type_symbol is None:
            report.add(ReportEntry(
                status="blocked", category="move", chrooked_id=chrooked_id,
                symbol=symbol, reason=f"unknown type {move.type!r}",
            ))
            continue

        index = find_macro_line(lines, "move", symbol)
        if index is None:
            report.add(ReportEntry(
                status="blocked", category="move", chrooked_id=chrooked_id,
                symbol=symbol, reason="constant exists but no moves.asm entry",
            ))
            continue

        # Only args the Ruleset actually states are written; an absent field
        # (power: None on Fly) means "keep the target's value", not zero.
        replacements = {4: type_symbol, 8: move.category.upper()}
        if move.power is not None:
            replacements[3] = str(move.power)
        if move.accuracy is not None:
            replacements[5] = str(move.accuracy)
        if move.pp is not None:
            replacements[6] = str(move.pp)
        if move.additional_effects:
            replacements[7] = str(move.additional_effects[0].chance)
        new_line = splice_args(lines[index].rstrip("\n"), replacements)
        if new_line != lines[index].rstrip("\n"):
            ending = "\n" if lines[index].endswith("\n") else ""
            lines[index] = new_line + ending
            changed = True

        left_behind = _unwritable_fields(move)
        report.add(ReportEntry(
            status="partial" if left_behind else "applied",
            category="move", chrooked_id=chrooked_id, symbol=symbol,
            reason="stats written; engine-code fields left behind" if left_behind else "",
            partial_fields=left_behind,
        ))

    if changed:
        moves_path.write_text("".join(lines), encoding="utf-8")
        return [moves_path]
    return []


def _unwritable_fields(move) -> tuple[str, ...]:
    present = {
        "effect": move.effect != "hit",
        "priority": move.priority != 0,
        "flags": bool(move.flags),
        "additional_effects": bool(move.additional_effects),
    }
    return tuple(name for name in _ENGINE_CODE_FIELDS if present[name])


def _derived(move) -> str:
    hint = dict(move.aka).get("polishedcrystal")
    if hint:
        return str(hint)
    from .resolution import _derive_symbol

    return _derive_symbol(move.name)
