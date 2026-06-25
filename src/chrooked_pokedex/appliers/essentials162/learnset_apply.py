"""Apply learnsets by replacing a 16.2 species' whole flat `Moves=` line.

The 16.2 analogue of `appliers/essentials/learnset_apply.py`. The Ruleset owns the
whole level-up list, so the target's `Moves=` line is discarded and rebuilt — a move
appears at most as many times as the Ruleset lists it (the v1 duplicate-move fix).

16.2 stores the list flat as `Moves=level,MOVE,level,MOVE,...` (no spaces). Moves the
target lacks are not written (an unknown internal name would fail to load); they are
recorded partial. A species with no resolvable move at all is blocked rather than
written with an empty list. Resolution is by INTERNAL name.

Two per-Target layers run on top of the canonical replace:
  * a `learnset` HOLD skips the canon replace, keeping the Target's own `Moves=` line;
  * an additive Target Edit (`learnset_add`) APPENDS moves to whatever `Moves=` line
    is present after the canon step — kept-and-appended, never replaced. Holding a
    species' learnset and adding to it compose: the canon list is suppressed, and the
    additions land on the Target's own list.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...model.holds import HoldSet
from ...model.target_edits import TargetEdits
from ...report import ApplyReport, ReportEntry
from . import pbs_io, section_edit
from .resolution import ResolutionMap


def apply_learnsets(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport,
    holds: HoldSet | None = None,
    target_edits: TargetEdits | None = None,
) -> set[Path]:
    holds = holds or HoldSet()
    target_edits = target_edits or TargetEdits()
    path = target / "PBS" / "pokemon.txt"
    if not path.exists():
        return set()
    text, had_bom = pbs_io.read(path)
    original = text

    for chrooked_id in sorted(ruleset.species):
        override = ruleset.species[chrooked_id]
        if override.learnset is None:
            continue
        if holds.is_held(chrooked_id, "learnset"):
            report.add(ReportEntry(
                status="held", category="learnset", chrooked_id=chrooked_id,
                reason="target-pinned",
            ))
            continue
        symbol = resmap.species(chrooked_id, dict(override.aka))
        if symbol is None or section_edit.find_section_by_internalname(text, symbol) is None:
            report.add(ReportEntry(
                status="blocked", category="learnset", chrooked_id=chrooked_id,
                symbol=symbol, reason="species section not found",
            ))
            continue

        parts, unresolved = _render_list(override.learnset, ruleset, resmap)
        if not parts:
            report.add(ReportEntry(
                status="blocked", category="learnset", chrooked_id=chrooked_id,
                symbol=symbol, reason="no moves resolved in target",
                partial_fields=tuple(unresolved),
            ))
            continue

        text, _ = section_edit.set_section_field(text, symbol, "Moves", ",".join(parts))
        report.add(ReportEntry(
            status="partial" if unresolved else "applied", category="learnset",
            chrooked_id=chrooked_id, symbol=symbol,
            reason="some moves not yet in target" if unresolved else "",
            partial_fields=tuple(unresolved),
        ))

    # Additive Target Edits run last, appending to whatever Moves line is now present
    # (the Target's own list when held, or the canon list otherwise).
    text = _apply_learnset_additions(text, ruleset, resmap, target_edits, report)

    if text != original:
        pbs_io.write(path, text, had_bom)
        return {path}
    return set()


def _apply_learnset_additions(
    text: str, ruleset: Ruleset, resmap: ResolutionMap,
    target_edits: TargetEdits, report: ApplyReport,
) -> str:
    """Append `learnset_add` moves onto each entity's existing flat `Moves=` line.

    Idempotent: a `(level, MOVE)` pair already in the line is not re-added, so a
    repeated apply converges. A move that does not resolve in the Target is reported
    partial (not written); a species whose section is absent is blocked.
    """
    for chrooked_id, additions in target_edits.learnset_add.items():
        if not additions:
            continue
        override = ruleset.species.get(chrooked_id)
        aka = dict(override.aka) if override is not None else {}
        symbol = resmap.species(chrooked_id, aka)
        span = (
            section_edit.find_section_by_internalname(text, symbol)
            if symbol is not None else None
        )
        if span is None:
            report.add(ReportEntry(
                status="blocked", category="learnset", chrooked_id=chrooked_id,
                symbol=symbol, reason="species section not found for target edit",
            ))
            continue

        current = section_edit.get_field(text[span[0]:span[1]], "Moves") or ""
        pairs = _parse_pairs(current)
        added: list[str] = []
        unresolved: list[str] = []
        for addition in additions:
            move_symbol = resmap.move(addition.move)
            if move_symbol is None:
                tag = "owned" if ruleset.owned_move(addition.move) is not None else "unknown"
                unresolved.append(f"move:{addition.move}({tag})")
                continue
            pair = (str(addition.level), move_symbol)
            if pair in pairs:
                continue  # idempotent — already taught at this level
            pairs.append(pair)
            added.append(addition.move)

        if added:
            line = ",".join(f"{level},{move}" for level, move in pairs)
            text, _ = section_edit.set_section_field(text, symbol, "Moves", line)
        if unresolved:
            report.add(ReportEntry(
                status="partial", category="learnset", chrooked_id=chrooked_id,
                symbol=symbol,
                reason="target-edit: " + ", ".join(f"+{m}" for m in added)
                if added else "target-edit: no moves resolved",
                partial_fields=tuple(unresolved),
            ))
        elif added:
            report.add(ReportEntry(
                status="applied", category="learnset", chrooked_id=chrooked_id,
                symbol=symbol,
                reason="target-edit: " + ", ".join(f"+{m}" for m in added),
            ))
    return text


def _parse_pairs(moves_line: str) -> list[tuple[str, str]]:
    """Split a flat `level,MOVE,level,MOVE,...` line into (level, MOVE) pairs."""
    tokens = [t for t in moves_line.split(",") if t != ""]
    return [(tokens[i], tokens[i + 1]) for i in range(0, len(tokens) - 1, 2)]


def _render_list(learnset, ruleset: Ruleset, resmap: ResolutionMap) -> tuple[list[str], list[str]]:
    parts: list[str] = []
    unresolved: list[str] = []
    for entry in learnset:
        symbol = resmap.move(entry.move)
        if symbol is None:
            tag = "owned" if ruleset.owned_move(entry.move) is not None else "unknown"
            unresolved.append(f"move:{entry.move}({tag})")
            continue
        parts.extend([str(entry.level), symbol])
    return parts, unresolved
