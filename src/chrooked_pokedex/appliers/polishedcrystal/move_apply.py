"""Moves category: splice MoveDef stats into data/moves/moves.asm.

The `move` macro line carries: name(1), effect(2), power(3), type(4),
accuracy(5), pp(6), effect_chance(7), category(8). Only args 3-8 are data this
Applier owns for a plain stat override; a MoveDef's `effect`, `priority`,
`flags`, and the identity of its `additional_effects` live in engine code (or
separate tables) and are reported as partial fields, never written.

TAKEOVER: an `aka: polishedcrystal:` hint means the Ruleset move OWNS that
slot — the host move is retired. Beyond stats, a takeover also writes the
effect class (when the neutral shape maps to an existing EFFECT_*), the `li`
display name, an unshared description block, and removes the host from the
crit-ratio table.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from .asm_edit import find_macro_line, splice_args
from .resolution import ResolutionMap

# MoveDef fields the macro line cannot carry. `additional_effects` is listed
# because only its *chance* lands (arg 7) — the effect identity is engine code.
_ENGINE_CODE_FIELDS = ("effect", "priority", "flags", "additional_effects")

_MOVES_FILE = Path("data") / "moves" / "moves.asm"
_NAMES_FILE = Path("data") / "moves" / "names.asm"
_DESCS_FILE = Path("data") / "moves" / "descriptions.asm"
_CRIT_FILE = Path("data") / "moves" / "critical_hit_moves.asm"

# In-game move names fit MOVE_NAME_LENGTH (13) minus the terminator.
_NAME_LIMIT = 12
_DESC_WIDTH = 18

# Neutral (effect, single-additional-effect) shape -> existing EFFECT_* class.
# Only shapes with a 1:1 existing routine are written; anything else stays a
# partial field — this Applier never authors new effect code.
_EFFECT_BY_SHAPE = {
    ("hit", None): "EFFECT_NORMAL_HIT",
    ("hit", "flinch"): "EFFECT_FLINCH_HIT",
    ("hit", "burn"): "EFFECT_BURN_HIT",
    ("hit", "frostbite"): "EFFECT_FREEZE_HIT",
    ("hit", "paralyze"): "EFFECT_PARALYZE_HIT",
    ("hit", "poison"): "EFFECT_POISON_HIT",
    ("hit", "def_minus_1"): "EFFECT_DEFENSE_DOWN_HIT",
    ("hit", "acc_minus_1"): "EFFECT_ACCURACY_DOWN_HIT",
    ("hit", "spe_minus_1"): "EFFECT_SPEED_DOWN_HIT",
}


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
            # Ruleset accuracy 0 means "can't miss"; PC spells that -1.
            replacements[5] = str(move.accuracy if move.accuracy != 0 else -1)
        if move.pp is not None:
            replacements[6] = str(move.pp)
        if move.additional_effects:
            replacements[7] = str(move.additional_effects[0].chance)

        is_takeover = bool(dict(move.aka).get("polishedcrystal"))
        takeover_misses: list[str] = []
        if is_takeover:
            effect_symbol = _effect_class(move)
            if effect_symbol and effect_symbol in text:
                replacements[2] = effect_symbol
            elif effect_symbol is None:
                takeover_misses.append("effect")
            takeover_misses += _retire_host_identity(Path(target), resmap, symbol, move)

        new_line = splice_args(lines[index].rstrip("\n"), replacements)
        if new_line != lines[index].rstrip("\n"):
            ending = "\n" if lines[index].endswith("\n") else ""
            lines[index] = new_line + ending
            changed = True

        if is_takeover:
            # A mapped takeover owns effect/additional_effects; only report
            # what genuinely could not land.
            left_behind = tuple(
                f for f in _unwritable_fields(move)
                if f in ("priority", "flags") or f in takeover_misses
            ) + tuple(f for f in takeover_misses if f == "name")
        else:
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


def _effect_class(move) -> str | None:
    """EFFECT_* symbol for this MoveDef's neutral shape, when 1:1 exists."""
    if len(move.additional_effects) > 1:
        return None
    extra = move.additional_effects[0].effect if move.additional_effects else None
    return _EFFECT_BY_SHAPE.get((move.effect, extra))


def _retire_host_identity(
    target: Path, resmap: ResolutionMap, host: str, move
) -> list[str]:
    """Rename, re-describe, and de-crit the taken-over slot; return misses."""
    misses: list[str] = []
    display = str(dict(move.aka).get("polishedcrystal_name") or move.name)
    if len(display) <= _NAME_LIMIT:
        _rename_li_entry(target / _NAMES_FILE, resmap, host, display)
    else:
        misses.append("name")
    if move.description:
        _unshare_description(target / _DESCS_FILE, host, move.description)
    # The neutral schema has no crit field; `polishedcrystal_crit: true` in aka
    # keeps the host's crit-table entry for the new move.
    if not dict(move.aka).get("polishedcrystal_crit"):
        _remove_from_table(target / _CRIT_FILE, host)
    return misses


def _rename_li_entry(path: Path, resmap: ResolutionMap, host: str, display: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    li_index = resmap.move_order.index(host)  # li lines follow move-ID order
    seen = -1
    for index, line in enumerate(lines):
        if line.startswith("\tli "):
            seen += 1
            if seen == li_index:
                if line != f'\tli "{display}"':
                    lines[index] = f'\tli "{display}"'
                    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return


def _unshare_description(path: Path, host: str, description: str) -> None:
    """Give the host label its own text block, leaving any shared block intact."""
    label = "".join(part.capitalize() for part in host.split("_")) + "Description"
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        at = lines.index(f"{label}:")
    except ValueError:
        return
    safe = description.replace('"', "'")
    wrapped = textwrap.wrap(safe, _DESC_WIDTH) or [""]
    block = [f"{label}:", f'\ttext "{wrapped[0]}"'] + [
        f'\tnext "{part}"' for part in wrapped[1:]
    ] + ["\tdone"]

    next_line = lines[at + 1] if at + 1 < len(lines) else ""
    shares_block = next_line.rstrip().endswith(":") or lines[at - 1].rstrip().endswith(":")
    if shares_block:
        # Pull the label out of the stacked group; append its own block.
        del lines[at]
        lines += [""] + block
    else:
        # Standalone label: replace its body (text/next lines up to `done`).
        end = at + 1
        while end < len(lines) and lines[end].strip() != "done":
            end += 1
        lines[at : end + 1] = block
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _remove_from_table(path: Path, host: str) -> None:
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [l for l in lines if l.strip() != f"db {host}"]
    if kept != lines:
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")


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
