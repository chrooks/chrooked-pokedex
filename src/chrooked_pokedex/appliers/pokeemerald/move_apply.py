"""Apply retunes to moves the target already has — scalars AND behavior.

The Ruleset owns a move's whole definition, so a move the fork merely changed
(Fly's power, or a move's effect/flags) is owned but already present in the target.
Creation skips present moves; without this tier that change would land nowhere and
never appear in the Apply Report — a silent drop. This tier closes it.

It overlays both the scalar fields (type, category, power, accuracy, pp, priority)
and the behavior fields (effect, target, argument, additional_effects, and the
modeled flags) onto the existing `[MOVE_X] = { ... }` entry, diff-based: only a
field whose current value differs is rewritten, so a move that already matches
produces no churn and no report line.

Flags reconcile against the engine's modeled flag fields only: a flag the Ruleset
sets is added, a modeled flag it no longer sets is removed, and the engine's own
unmodeled flags are left untouched. argument and additional_effects are written when
the Ruleset specifies them; they are not cleared when absent (a rare case for a
retune, and clearing risks dropping engine state).

Runs before creation so each owned move is handled by exactly one tier.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...model import Ruleset
from ...model.schema import MoveDef
from ...report import ApplyReport, ReportEntry
from . import c_edit, move_render
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
            reason="retuned: " + ", ".join(changed_fields),
        ))

    if text != original:
        path.write_text(text, encoding="utf-8")
        return {path}
    return set()


def _overlay(body: str, move: MoveDef, resmap: ResolutionMap) -> tuple[str, list[str]]:
    body, changed = _overlay_scalars(body, move, resmap)
    body, behavior_changed = _overlay_behavior(body, move, resmap)
    return body, changed + behavior_changed


def _overlay_scalars(body: str, move: MoveDef, resmap: ResolutionMap) -> tuple[str, list[str]]:
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


def _overlay_behavior(body: str, move: MoveDef, resmap: ResolutionMap) -> tuple[str, list[str]]:
    """Overlay effect, target, argument, additional_effects, and the modeled flags.

    pokeemerald is the native engine: every modeled effect, target, and flag has a
    direct C field, so there is nothing unmappable here — the overlay is always clean.
    """
    changed: list[str] = []

    desired_effect = move_render.effect_symbol(move)
    if c_edit.get_field(body, "effect") != desired_effect:
        body = c_edit.set_field_all(body, "effect", desired_effect)
        changed.append("effect")

    body, target_changed = _overlay_target(body, move)
    changed.extend(target_changed)

    if move.argument:
        desired_arg = move_render.argument_braced(move.argument, resmap)
        if _norm(c_edit.get_field(body, "argument")) != _norm(desired_arg):
            body = c_edit.set_field_all(body, "argument", desired_arg)
            changed.append("argument")

    if move.additional_effects:
        desired_ae = move_render.additional_effects_expr(move.additional_effects)
        if _norm(c_edit.get_field(body, "additionalEffects")) != _norm(desired_ae):
            body = c_edit.set_field_all(body, "additionalEffects", desired_ae)
            changed.append("additionalEffects")

    body, flag_changed = _overlay_flags(body, move)
    changed.extend(flag_changed)
    return body, changed


def _overlay_target(body: str, move: MoveDef) -> tuple[str, list[str]]:
    """Set .target, but don't insert it on a default-target move that omits the field
    (every plain move would otherwise gain a redundant .target line)."""
    desired = move_render.target_symbol(move)
    current = c_edit.get_field(body, "target")
    if current is not None:
        if current != desired:
            return c_edit.set_field_all(body, "target", desired), ["target"]
    elif move.target != "selected":
        return c_edit.set_field_all(body, "target", desired), ["target"]
    return body, []


def _overlay_flags(body: str, move: MoveDef) -> tuple[str, list[str]]:
    """Reconcile the modeled flag fields: add what the Ruleset sets, remove a modeled
    flag it no longer sets, and never touch the engine's own unmodeled flags."""
    changed: list[str] = []
    desired = set(move_render.flag_fields(move))
    for field in move_render.MODELED_FLAG_FIELDS:
        present = c_edit.get_field(body, field) is not None
        if field in desired and not present:
            body = c_edit.set_field(body, field, "TRUE")
            changed.append(f"+{field}")
        elif field not in desired and present:
            body = c_edit.remove_field(body, field)
            changed.append(f"-{field}")
    return body, changed


def _norm(value: str | None) -> str:
    """Whitespace-insensitive form, so a multi-line macro in the target compares equal
    to the single-line one we render when they mean the same thing."""
    return re.sub(r"\s+", "", value) if value else ""
