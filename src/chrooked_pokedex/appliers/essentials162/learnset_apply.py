"""Apply learnsets by replacing a 16.2 species' whole flat `Moves=` line.

The 16.2 analogue of `appliers/essentials/learnset_apply.py`. The Ruleset owns the
whole level-up list, so the target's `Moves=` line is discarded and rebuilt — a move
appears at most as many times as the Ruleset lists it (the v1 duplicate-move fix).

16.2 stores the list flat as `Moves=level,MOVE,level,MOVE,...` (no spaces). Moves the
target lacks are not written (an unknown internal name would fail to load); they are
recorded partial. A species with no resolvable move at all is blocked rather than
written with an empty list. Resolution is by INTERNAL name.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from . import pbs_io, section_edit
from .resolution import ResolutionMap


def apply_learnsets(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    path = target / "PBS" / "pokemon.txt"
    if not path.exists():
        return set()
    text, had_bom = pbs_io.read(path)
    original = text

    for chrooked_id in sorted(ruleset.species):
        override = ruleset.species[chrooked_id]
        if override.learnset is None:
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

    if text != original:
        pbs_io.write(path, text, had_bom)
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
