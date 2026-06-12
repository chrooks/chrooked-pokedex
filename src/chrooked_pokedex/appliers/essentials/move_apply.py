"""Apply scalar retunes to moves the target already has (PBS side).

The Essentials counterpart of the pokeemerald move tier: a move the fork merely
retuned is owned but already present, so creation skips it. Without this tier the
retune would land nowhere and never show in the Apply Report — a silent drop.

It overlays the scalar fields — Type, Category, Power, Accuracy, TotalPP, Priority —
onto the existing `[INTERNAL]` section, diff-based: only a field that differs is
rewritten, so an already-matching move makes no change and no report line. An
unresolvable Type is reported (partial) and the existing value is left intact rather
than overwritten with a bad token. Behavior fields are not overlaid here; a touched
move that carries one is noted so the boundary stays visible.

Runs before creation so each owned move is edited (present) or created (absent),
never both.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...model.schema import DEFAULT_EFFECT, MoveDef
from ...report import ApplyReport, ReportEntry
from . import pbs_edit, vocab
from .resolution import ResolutionMap


def apply_moves(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    path = target / "PBS" / "moves.txt"
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    original = text

    for chrooked_id in sorted(ruleset.moves):
        move = ruleset.moves[chrooked_id]
        symbol = resmap.move(move.name)
        if symbol is None:
            continue  # absent from target -> creation's job
        if pbs_edit.find_section(text, symbol) is None:
            report.add(ReportEntry(
                status="blocked", category="move", chrooked_id=chrooked_id,
                symbol=symbol, reason="move section not found",
            ))
            continue

        text, changed_fields, unresolved = _overlay(text, symbol, move, resmap)
        if not changed_fields and not unresolved:
            continue  # already matches

        status = "partial" if unresolved else "applied"
        report.add(ReportEntry(
            status=status, category="move", chrooked_id=chrooked_id, symbol=symbol,
            reason=_reason(move, changed_fields), partial_fields=tuple(unresolved),
        ))

    if text != original:
        path.write_text(text, encoding="utf-8")
        return {path}
    return set()


def _overlay(
    text: str, symbol: str, move: MoveDef, resmap: ResolutionMap
) -> tuple[str, list[str], list[str]]:
    """Set each scalar field only when it differs; never write an unresolvable Type."""
    changed: list[str] = []
    unresolved: list[str] = []

    desired: dict[str, str] = {"Category": vocab.category(move.category)}
    type_internal = resmap.type(move.type)
    if type_internal is None:
        unresolved.append(f"type:{move.type}")
    else:
        desired["Type"] = type_internal
    if move.power is not None:
        desired["Power"] = str(move.power)
    if move.accuracy is not None:
        desired["Accuracy"] = str(move.accuracy)
    if move.pp is not None:
        desired["TotalPP"] = str(move.pp)
    if move.priority:
        # priority defaults to 0; overlay only a non-zero value (matches creation).
        desired["Priority"] = str(move.priority)

    for key, value in desired.items():
        span = pbs_edit.find_section(text, symbol)
        if span is None:
            break  # section vanished mid-loop (cannot happen — outer checked); be safe
        if pbs_edit.get_field(text[span[0]:span[1]], key) != value:
            text = pbs_edit.set_section_field(text, symbol, key, value)
            changed.append(key)
    return text, changed, unresolved


def _reason(move: MoveDef, changed_fields: list[str]) -> str:
    reason = "retuned: " + ", ".join(changed_fields) if changed_fields else "no scalar change"
    if move.effect != DEFAULT_EFFECT or move.flags or move.additional_effects:
        reason += " (behavior fields effect/flags/secondary not overlaid by this tier)"
    return reason
