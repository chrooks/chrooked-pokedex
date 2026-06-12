"""Apply scalar retunes to moves the target already has.

The Ruleset owns a move's whole definition, so a move the fork merely retuned
(e.g. Fly's power) is owned but already present in the target. Creation skips
present moves; without this tier that retune would land nowhere and — worse —
never appear in the Apply Report. This tier closes that silent drop.

It overlays the scalar fields the fork actually retunes — type, category, power,
accuracy, pp, priority — onto the existing `[MOVE_X] = { ... }` entry, diff-based:
only a field whose current value differs is rewritten, so a move that already
matches produces no churn and no report line. Behavior fields (effect, flags,
additional_effects) are not overlaid here; when a touched move carries one, the
report says so, so the boundary is visible rather than silent.

Runs before creation so each owned move is handled by exactly one tier: edited
when present, created when absent.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...model.schema import DEFAULT_EFFECT, MoveDef
from ...report import ApplyReport, ReportEntry
from . import c_edit
from .resolution import ResolutionMap

_CATEGORY_TO_SYMBOL = {
    "physical": "DAMAGE_CATEGORY_PHYSICAL",
    "special": "DAMAGE_CATEGORY_SPECIAL",
    "status": "DAMAGE_CATEGORY_STATUS",
}


def apply_moves(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    path = target / "src" / "data" / "moves_info.h"
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    original = text

    for chrooked_id in sorted(ruleset.moves):
        move = ruleset.moves[chrooked_id]
        symbol = resmap.move(move.name)
        if symbol is None:
            continue  # absent from target -> creation's job, not this tier's
        span = c_edit.find_entry(text, symbol)  # generic [SYMBOL] = {...} locator
        if span is None:
            report.add(ReportEntry(
                status="blocked", category="move", chrooked_id=chrooked_id,
                symbol=symbol, reason="move entry not found or macro form",
            ))
            continue

        body = text[span[0] + 1 : span[1]]
        new_body, changed_fields = _overlay(body, move, resmap)
        if not changed_fields:
            continue  # already matches; nothing to do, nothing to report

        text = c_edit.replace_entry_body(text, span, new_body)
        report.add(ReportEntry(
            status="applied", category="move", chrooked_id=chrooked_id, symbol=symbol,
            reason=_reason(move, changed_fields),
        ))

    if text != original:
        path.write_text(text, encoding="utf-8")
        return {path}
    return set()


def _overlay(body: str, move: MoveDef, resmap: ResolutionMap) -> tuple[str, list[str]]:
    """Set each scalar field only when it differs from the entry's current value."""
    changed: list[str] = []
    type_symbol = resmap.type(move.type) or ("TYPE_" + move.type.upper().replace(" ", "_"))
    desired = {
        "type": type_symbol,
        "category": _CATEGORY_TO_SYMBOL.get(move.category, "DAMAGE_CATEGORY_PHYSICAL"),
    }
    if move.power is not None:
        desired["power"] = str(move.power)
    if move.accuracy is not None:
        desired["accuracy"] = str(move.accuracy)
    if move.pp is not None:
        desired["pp"] = str(move.pp)
    if move.priority:
        # priority defaults to 0; overlay only a non-zero value. Reverting a move to
        # 0 is a no-op here (matches the creation tier) — 0 is the engine default.
        desired["priority"] = str(move.priority)

    for field, value in desired.items():
        if c_edit.get_field(body, field) != value:
            body = c_edit.set_field_all(body, field, value)
            changed.append(field)
    return body, changed


def _reason(move: MoveDef, changed_fields: list[str]) -> str:
    reason = "retuned: " + ", ".join(changed_fields)
    if move.effect != DEFAULT_EFFECT or move.flags or move.additional_effects:
        reason += " (behavior fields effect/flags/secondary not overlaid by this tier)"
    return reason
