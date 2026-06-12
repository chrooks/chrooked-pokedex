"""Apply learnsets by replacing a species' whole `Moves =` line outright.

Like the pokeemerald applier, the Ruleset owns the entire level-up list: the
target's `Moves` line is discarded and rebuilt from the Ruleset, so a move can
appear at most as many times as the Ruleset lists it (the v1 duplicate-move fix).

Essentials stores the list flat as `Moves = level,MOVE,level,MOVE,...`. Moves the
target lacks are not written (an unknown internal name would fail to load); they
are recorded partial, tagged owned/unknown. A species with no resolvable move at
all is blocked rather than written with an empty list.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from . import pbs_edit
from .resolution import ResolutionMap


def apply_learnsets(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    path = target / "PBS" / "pokemon.txt"
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    original = text

    for chrooked_id in sorted(ruleset.species):
        override = ruleset.species[chrooked_id]
        if override.learnset is None:
            continue
        symbol = resmap.species(chrooked_id, dict(override.aka))
        if symbol is None:
            report.add(ReportEntry(
                status="blocked", category="learnset", chrooked_id=chrooked_id,
                reason="no species symbol resolved",
            ))
            continue
        if pbs_edit.find_section(text, symbol) is None:
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

        text = pbs_edit.set_section_field(text, symbol, "Moves", ",".join(parts))
        if unresolved:
            report.add(ReportEntry(
                status="partial", category="learnset", chrooked_id=chrooked_id,
                symbol=symbol, reason="some moves not yet in target",
                partial_fields=tuple(unresolved),
            ))
        else:
            report.add(ReportEntry(
                status="applied", category="learnset", chrooked_id=chrooked_id,
                symbol=symbol,
            ))

    if text != original:
        path.write_text(text, encoding="utf-8")
        return {path}
    return set()


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
