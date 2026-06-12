"""Apply retunes to moves the target already has — scalars AND behavior (PBS side).

The Essentials counterpart of the pokeemerald move tier: a move the fork merely
changed is owned but already present, so creation skips it. Without this tier the
change would land nowhere and never show in the Apply Report — a silent drop.

It overlays the scalar fields (Type, Category, Power, Accuracy, TotalPP, Priority)
and the behavior fields (FunctionCode + EffectChance, Target, and the modeled Flags)
onto the existing `[INTERNAL]` section, diff-based: only a field that differs is
rewritten.

Honesty over mistranslation: an unresolvable Type or an effect with no Essentials
FunctionCode is left intact (never overwritten with a bad token or with "None") and
reported as unresolved. Because some real moves carry permanently-unportable behavior
(Fly's two-turn effect), such a move shows as partial with that note even when nothing
else changed — a standing list of moves whose behavior the data layer cannot express,
not noise. Flags reconcile only the modeled flag names, preserving the engine's own.

Runs before creation so each owned move is edited (present) or created (absent).
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...model.schema import MoveDef
from ...report import ApplyReport, ReportEntry
from . import move_render, pbs_edit, vocab
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

    # FunctionCode: overlay ONLY a concretely-mapped code (a real effect/secondary).
    # A plain `hit` maps to "None", but the Ruleset's effect is seeded from pokeemerald
    # — "hit" there does not mean "no Essentials behavior", so writing "None" would
    # wipe a legitimate target FunctionCode. An unportable effect is likewise left
    # intact (and noted). Only a specific code (BurnTarget, OHKO, ...) is authoritative.
    code, chance = move_render.function_code(move, unresolved)
    if code is not None and code != vocab.NO_FUNCTION_CODE:
        desired["FunctionCode"] = code
        if chance is not None:
            desired["EffectChance"] = str(chance)

    for key, value in desired.items():
        text, did = _set_if_differs(text, symbol, key, value)
        if did:
            changed.append(key)

    text, target_changed = _overlay_target(text, symbol, move)
    changed.extend(target_changed)
    text, flag_changed = _overlay_flags(text, symbol, move, unresolved)
    changed.extend(flag_changed)
    return text, changed, unresolved


def _overlay_target(text: str, symbol: str, move: MoveDef) -> tuple[str, list[str]]:
    """Set Target, but don't insert NearOther onto a default-target move that omits
    the field (real Essentials moves carry Target, so this only guards odd inputs)."""
    span = pbs_edit.find_section(text, symbol)
    if span is None:
        return text, []
    current = pbs_edit.get_field(text[span[0]:span[1]], "Target")
    desired = vocab.target(move.target)
    if current is not None:
        if current != desired:
            return pbs_edit.set_section_field(text, symbol, "Target", desired), ["Target"]
    elif move.target != "selected":
        return pbs_edit.set_section_field(text, symbol, "Target", desired), ["Target"]
    return text, []


def _overlay_flags(
    text: str, symbol: str, move: MoveDef, unresolved: list[str]
) -> tuple[str, list[str]]:
    """Reconcile the modeled Flags only: drop a modeled flag the Ruleset no longer
    sets, add the ones it does, and keep the engine's own unmodeled flags in place."""
    desired = move_render.flag_names(move, unresolved)
    span = pbs_edit.find_section(text, symbol)
    if span is None:
        return text, []
    current_raw = pbs_edit.get_field(text[span[0]:span[1]], "Flags")
    current = [f.strip() for f in current_raw.split(",")] if current_raw else []

    new = [f for f in current if f not in vocab.MODELED_FLAG_NAMES or f in desired]
    for f in desired:
        if f not in new:
            new.append(f)

    if new != current:
        # Write even when `new` is empty (every modeled flag was dropped and no
        # unmodeled flag remains) — otherwise stale flags would silently survive.
        text = pbs_edit.set_section_field(text, symbol, "Flags", ",".join(new))
        return text, ["Flags"]
    return text, []


def _set_if_differs(text: str, symbol: str, key: str, value: str) -> tuple[str, bool]:
    span = pbs_edit.find_section(text, symbol)
    if span is None:
        return text, False  # section vanished mid-loop (cannot happen — outer checked)
    if pbs_edit.get_field(text[span[0]:span[1]], key) == value:
        return text, False
    return pbs_edit.set_section_field(text, symbol, key, value), True


def _reason(move: MoveDef, changed_fields: list[str]) -> str:
    return "retuned: " + ", ".join(changed_fields) if changed_fields else "behavior not fully portable"
