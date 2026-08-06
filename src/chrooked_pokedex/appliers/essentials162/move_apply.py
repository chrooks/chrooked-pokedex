"""Apply move SCALAR Overrides into an Essentials 16.2 `PBS/moves.txt`.

16.2 moves.txt is flat positional CSV (no `[N]` sections), one row per move:

  idx,INTERNALNAME,SpanishName,HEXfunccode,power,TYPE,category,accuracy,pp,
  effectchance,target,priority,flags,"desc"

Issue #21 writes ONLY the scalar columns — power(4), type(5), category(6),
accuracy(7), pp(8), priority(11) — via `csv_io.set_column`. The behavior columns
(funccode 3, effectchance 9, target 10, flags 12, desc 13) are left byte-identical;
effects → HEX functioncodes are issue #22.

A move the target already has is edited in place (only a column that differs is
rewritten). A move the target lacks is CREATED: a new CSV row is appended with the
next index and the scalar columns filled, the behavior columns left as safe defaults.
Resolution is by INTERNAL name (never the Spanish display Name).
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...model.holds import HoldSet
from ...model.schema import MoveDef
from ...report import ApplyReport, ReportEntry
from ..essentials import vocab
from . import csv_io, effect_tables, pbs_io
from .effect_tables import Behavior
from .resolution import ResolutionMap

# The moves.txt scalar columns #21 owns. Behavior columns (3/9/10/12/13) are #22.
_COLUMN = {"power": 4, "type": 5, "category": 6, "accuracy": 7, "pp": 8, "priority": 11}

# Behavior columns #22 owns: funccode(3), effectchance(9), target(10), flags(12).
_FUNCCODE_COL = 3
_EFFECTCHANCE_COL = 9
_TARGET_COL = 10
_FLAGS_COL = 12
_DESC_COL = 13

# Total columns in a 16.2 moves.txt row, for emitting a brand-new row.
_ROW_WIDTH = 14
# Safe placeholder behavior columns for a created row (effects come in #22).
_DEFAULT_FUNCCODE = "000"
_DEFAULT_EFFECTCHANCE = "0"
_DEFAULT_TARGET = "00"
_DEFAULT_FLAGS = ""
_DEFAULT_DESC = '""'


def apply_moves(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport,
    holds: HoldSet | None = None,
) -> set[Path]:
    holds = holds or HoldSet()
    path = target / "PBS" / "moves.txt"
    if not path.exists():
        return set()
    text, had_bom = pbs_io.read(path)
    original = text
    named = _uses_named_targets(text)

    for chrooked_id in sorted(ruleset.moves):
        if holds.is_held(chrooked_id, "moves"):
            report.add(ReportEntry(
                status="held", category="move", chrooked_id=chrooked_id,
                reason="target-pinned",
            ))
            continue
        move = ruleset.moves[chrooked_id]
        # Edit when a row already exists under EITHER the resolved symbol or the
        # name-derived internal — so a move present but not indexed by the
        # ResolutionMap is edited in place, never appended as a duplicate row.
        symbol = resmap.move(move.name) or _internal_of(move)
        if csv_io.find_row(text, symbol) is not None:
            text = _edit_existing(text, symbol, move, resmap, report, chrooked_id, named)
        else:
            text = _create_row(text, move, resmap, report, chrooked_id, named)

    if text != original:
        pbs_io.write(path, text, had_bom)
        return {path}
    return set()


def _edit_existing(
    text: str, symbol: str, move: MoveDef, resmap: ResolutionMap,
    report: ApplyReport, chrooked_id: str, named: bool,
) -> str:
    desired, unresolved = _scalar_columns(move, resmap)
    changed: list[str] = []
    for name, index in _COLUMN.items():
        if name not in desired:
            continue
        current = csv_io.get_column(text, symbol, index)
        if current == desired[name]:
            continue
        text, applied = csv_io.set_column(text, symbol, index, desired[name])
        if applied:
            changed.append(name)

    text = _edit_behavior(text, symbol, move, changed, unresolved, named)

    # Description col is display text (neither #21 scalar nor #22 behavior). Write it
    # only when the Ruleset states one — an Override means intent; an empty desc leaves
    # the engine's existing text alone rather than blanking it.
    if move.description:
        desired_desc = _quote_desc(move.description)
        if (csv_io.get_column(text, symbol, _DESC_COL) or "") != desired_desc:
            text, applied = csv_io.set_column(text, symbol, _DESC_COL, desired_desc)
            if applied:
                changed.append("description")

    if not changed and not unresolved:
        return text  # already matches — no churn, no report line
    report.add(ReportEntry(
        status="partial" if unresolved else "applied", category="move",
        chrooked_id=chrooked_id, symbol=symbol,
        reason="retuned: " + ", ".join(changed) if changed else "scalars unchanged",
        partial_fields=tuple(unresolved),
    ))
    return text


def _edit_behavior(
    text: str, symbol: str, move: MoveDef, changed: list[str], unresolved: list[str],
    named: bool,
) -> str:
    """Reconcile the four behavior columns of an existing row from the effect tables.

    When the effect signature resolves, only a column that differs is rewritten (and
    its name is appended to `changed`). When it does not resolve, the row's existing
    safe defaults are kept and an unresolved note is added so #12 picks the move up.
    A move with no behavior intent at all is left wholly untouched (it may be a known
    vanilla move whose existing columns we must not blank).

    Three preservation rules keep an edit from clobbering engine-owned data on a row:
    the FUNCCODE/EFFECTCHANCE columns are only written when the Ruleset states an EFFECT
    (a flags/target-only retune leaves the engine's existing code — #22 AC4, never
    silently flatten recoil/charge to plain `000`); the TARGET column is only written for
    a non-default target (`selected` means "keep the file's value"); and the FLAGS column
    is MERGED additively so engine-default letters (b/e/f) survive.
    """
    if not effect_tables.specifies_behavior(move):
        return text
    behavior = effect_tables.resolve_behavior(move, named)
    if behavior is None:
        unresolved.append(f"effect:{_effect_label(move)} has no 16.2 funccode -> #12")
        return text

    # A flags-only move never returns None above (plain-hit always resolves to 000), so
    # this guard — not the None branch — is what spares its existing funccode.
    specifies_effect = effect_tables.specifies_effect(move)
    for index, value, label in _behavior_columns(behavior):
        if index in (_FUNCCODE_COL, _EFFECTCHANCE_COL) and not specifies_effect:
            continue  # no effect intent: never flatten the engine's existing funccode
        if index == _TARGET_COL and move.target == "selected":
            continue  # default target: keep the file's existing value, don't impose
        if index == _FLAGS_COL:
            existing = (csv_io.get_column(text, symbol, index) or "").strip()
            value = effect_tables.merge_flags(existing, value)
        if csv_io.get_column(text, symbol, index) == value:
            continue
        text, applied = csv_io.set_column(text, symbol, index, value)
        if applied:
            changed.append(label)

    for flag in effect_tables.dropped_flags(move):
        unresolved.append(f"flag:{flag} has no 16.2 letter -> dropped")
    for note in effect_tables.deferred_effects(move):
        unresolved.append(note)
    return text


def _create_row(
    text: str, move: MoveDef, resmap: ResolutionMap,
    report: ApplyReport, chrooked_id: str, named: bool,
) -> str:
    internal = _internal_of(move)
    desired, unresolved = _scalar_columns(move, resmap)

    columns = [""] * _ROW_WIDTH
    columns[0] = str(csv_io.max_index(text) + 1)
    columns[1] = internal
    columns[2] = move.name
    columns[3] = _DEFAULT_FUNCCODE
    columns[9] = _DEFAULT_EFFECTCHANCE
    # Named-format files need a named default; an unresolved created move keeps this.
    columns[10] = effect_tables.DEFAULT_TARGET_NAME if named else _DEFAULT_TARGET
    # ponytail: a created move's engine-default flags (b/e/f) are #22's job — a brand
    # new row has no existing letters to preserve, so it carries only modeled flags.
    columns[12] = _DEFAULT_FLAGS
    columns[13] = _quote_desc(move.description) if move.description else _DEFAULT_DESC
    for name, index in _COLUMN.items():
        columns[index] = desired.get(name, "0")

    # Behavior columns from the effect tables; an unresolvable signature keeps the
    # safe defaults above and is reported for the #12 loop (never written wrong).
    # Unlike the edit path, a created row has no existing target to preserve, so the
    # resolved target always overwrites the default stamped above (same value for
    # `selected`; an explicit `both` upgrades it).
    behavior = effect_tables.resolve_behavior(move, named)
    if behavior is None:
        unresolved.append(f"effect:{_effect_label(move)} has no 16.2 funccode -> #12")
    else:
        for index, value, _label in _behavior_columns(behavior):
            columns[index] = value
        for flag in effect_tables.dropped_flags(move):
            unresolved.append(f"flag:{flag} has no 16.2 letter -> dropped")
        for note in effect_tables.deferred_effects(move):
            unresolved.append(note)

    # Fail loud: a damaging move created with no power lands as 0, which the engine
    # silently demotes to a Status move. Surface it instead of shipping a dud.
    if move.category != "status" and columns[_COLUMN["power"]] in ("0", ""):
        unresolved.append("damaging move created with power 0 -> engine demotes to Status")

    text = csv_io.append_row(text, csv_io.join_columns(columns))
    status = "partial" if unresolved else "applied"
    report.add(ReportEntry(
        status=status, category="move", chrooked_id=chrooked_id, symbol=internal,
        reason="created new move" + (" (some fields unresolved)" if unresolved else ""),
        partial_fields=tuple(unresolved),
    ))
    return text


def _behavior_columns(behavior: Behavior) -> tuple[tuple[int, str, str], ...]:
    """`(column index, value, report label)` for each behavior column to write."""
    return (
        (_FUNCCODE_COL, behavior.funccode, "funccode"),
        (_EFFECTCHANCE_COL, behavior.effectchance, "effectchance"),
        (_TARGET_COL, behavior.target, "target"),
        (_FLAGS_COL, behavior.flags, "flags"),
    )


def _effect_label(move: MoveDef) -> str:
    """A human label for the move's effect signature, for unresolved reporting."""
    if move.effect != "hit":
        return move.effect
    if len(move.additional_effects) >= 2:
        return "+".join(ae.effect for ae in move.additional_effects)
    if move.additional_effects:
        return move.additional_effects[0].effect
    return move.effect


def _scalar_columns(move: MoveDef, resmap: ResolutionMap) -> tuple[dict[str, str], list[str]]:
    """The scalar column values the Ruleset specifies, plus any unresolved notes."""
    unresolved: list[str] = []
    desired: dict[str, str] = {"category": vocab.category(move.category)}
    if move.second_type:
        unresolved.append(f"second_type:{move.second_type} (no 16.2 dual-type)")

    type_internal = resmap.type(move.type)
    if type_internal is None:
        unresolved.append(f"type:{move.type}")
    else:
        desired["type"] = type_internal

    if move.power is not None:
        desired["power"] = str(move.power)
    if move.accuracy is not None:
        desired["accuracy"] = str(move.accuracy)
    if move.pp is not None:
        desired["pp"] = str(move.pp)
    # priority defaults to 0; only overlay a non-zero value when editing, but always
    # emit a column for a new row (handled by the caller's `.get(name, "0")`).
    if move.priority:
        desired["priority"] = str(move.priority)
    return desired, unresolved


def _uses_named_targets(text: str) -> bool:
    """True when moves.txt col 10 spells targets as names (`NearOther`) not hex (`00`).

    Sniffs the first data row with a non-empty target; a moves.txt is uniformly one
    format, so a single sample decides it.
    """
    for line in text.split("\n"):
        # lstrip a stray BOM so the first row's index column still reads as a digit
        # even if this is ever called on un-stripped text (apply_moves goes via pbs_io).
        columns = csv_io.split_columns(line.rstrip("\r").lstrip("﻿"))
        if len(columns) <= _TARGET_COL or not columns[0].strip().isdigit():
            continue
        token = columns[_TARGET_COL].strip()
        if token:
            return any(char.isalpha() for char in token)
    return False


def _quote_desc(description: str) -> str:
    """CSV-quote a move description for col 13: wrap in quotes, neutralize inner quotes.

    Inner double-quotes are swapped to single quotes rather than CSV-escaped. The escape
    convention differs by Essentials fork — 16.2 uses doubled-quote (""), but IF2's fork
    uses backslash (\\") and treats a bare " as the field terminator, so a ""-escaped inner
    quote crashes IF2's compiler (the CLAMP "BINDING_TURNS" brick). Descriptions are flavor
    text, so neutralizing inner quotes is safe and dialect-agnostic."""
    return '"' + description.replace('"', "'") + '"'


def _internal_of(move: MoveDef) -> str:
    hint = (move.aka or {}).get("essentials")
    return str(hint) if hint else vocab.internal_name(move.name)
