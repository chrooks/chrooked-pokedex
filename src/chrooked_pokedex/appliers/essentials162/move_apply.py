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
from ...model.schema import MoveDef
from ...report import ApplyReport, ReportEntry
from ..essentials import vocab
from . import csv_io, pbs_io
from .resolution import ResolutionMap

# The moves.txt scalar columns #21 owns. Behavior columns (3/9/10/12/13) are #22.
_COLUMN = {"power": 4, "type": 5, "category": 6, "accuracy": 7, "pp": 8, "priority": 11}

# Total columns in a 16.2 moves.txt row, for emitting a brand-new row.
_ROW_WIDTH = 14
# Safe placeholder behavior columns for a created row (effects come in #22).
_DEFAULT_FUNCCODE = "000"
_DEFAULT_EFFECTCHANCE = "0"
_DEFAULT_TARGET = "00"
_DEFAULT_FLAGS = ""
_DEFAULT_DESC = '""'


def apply_moves(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    path = target / "PBS" / "moves.txt"
    if not path.exists():
        return set()
    text, had_bom = pbs_io.read(path)
    original = text

    for chrooked_id in sorted(ruleset.moves):
        move = ruleset.moves[chrooked_id]
        # Edit when a row already exists under EITHER the resolved symbol or the
        # name-derived internal — so a move present but not indexed by the
        # ResolutionMap is edited in place, never appended as a duplicate row.
        symbol = resmap.move(move.name) or _internal_of(move)
        if csv_io.find_row(text, symbol) is not None:
            text = _edit_existing(text, symbol, move, resmap, report, chrooked_id)
        else:
            text = _create_row(text, move, resmap, report, chrooked_id)

    if text != original:
        pbs_io.write(path, text, had_bom)
        return {path}
    return set()


def _edit_existing(
    text: str, symbol: str, move: MoveDef, resmap: ResolutionMap,
    report: ApplyReport, chrooked_id: str,
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

    if not changed and not unresolved:
        return text  # already matches — no churn, no report line
    report.add(ReportEntry(
        status="partial" if unresolved else "applied", category="move",
        chrooked_id=chrooked_id, symbol=symbol,
        reason="retuned: " + ", ".join(changed) if changed else "scalars unchanged",
        partial_fields=tuple(unresolved),
    ))
    return text


def _create_row(
    text: str, move: MoveDef, resmap: ResolutionMap,
    report: ApplyReport, chrooked_id: str,
) -> str:
    internal = _internal_of(move)
    desired, unresolved = _scalar_columns(move, resmap)

    columns = [""] * _ROW_WIDTH
    columns[0] = str(csv_io.max_index(text) + 1)
    columns[1] = internal
    columns[2] = move.name
    columns[3] = _DEFAULT_FUNCCODE
    columns[9] = _DEFAULT_EFFECTCHANCE
    columns[10] = _DEFAULT_TARGET
    columns[12] = _DEFAULT_FLAGS
    columns[13] = _DEFAULT_DESC
    for name, index in _COLUMN.items():
        columns[index] = desired.get(name, "0")

    text = csv_io.append_row(text, csv_io.join_columns(columns))
    status = "partial" if unresolved else "applied"
    report.add(ReportEntry(
        status=status, category="move", chrooked_id=chrooked_id, symbol=internal,
        reason="created new move" + (" (some scalars unresolved)" if unresolved else ""),
        partial_fields=tuple(unresolved),
    ))
    return text


def _scalar_columns(move: MoveDef, resmap: ResolutionMap) -> tuple[dict[str, str], list[str]]:
    """The scalar column values the Ruleset specifies, plus any unresolved notes."""
    unresolved: list[str] = []
    desired: dict[str, str] = {"category": vocab.category(move.category)}

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


def _internal_of(move: MoveDef) -> str:
    hint = (move.aka or {}).get("essentials")
    return str(hint) if hint else vocab.internal_name(move.name)
