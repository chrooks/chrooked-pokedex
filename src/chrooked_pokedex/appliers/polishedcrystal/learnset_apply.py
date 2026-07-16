"""Learnsets category: whole-list replacement in data/pokemon/evos_attacks.asm.

A species' block runs from its `\tevos_attacks <Label>` line to the next blank
line. Within the block, the learnset region is the largest trailing run of
lines that are `learnset` entries or FAITHFUL conditional scaffolding
(if/else/endc) — everything before it (`evo_data` lines) is preserved
byte-for-byte. The Ruleset owns the whole list, so embedded conditionals are
flattened by the replacement.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from .resolution import ResolutionMap

_EVOS_FILE = Path("data") / "pokemon" / "evos_attacks.asm"


def apply_learnsets(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> list[Path]:
    """Replace each Ruleset-owned learnset; return the files changed."""
    evos_path = Path(target) / _EVOS_FILE
    lines = evos_path.read_text(encoding="utf-8").splitlines()
    changed = False

    for chrooked_id, override in sorted(ruleset.species.items()):
        if override.learnset is None:
            continue
        label = resmap.species_label(override.name, dict(override.aka))

        moves = []
        dropped = []
        for entry in override.learnset:
            symbol = resmap.move_reference(entry.move)
            if symbol is None:
                dropped.append(entry.move)
            else:
                moves.append((entry.level, symbol))
        # Relaxed rule (2026-07-15): write what resolves, name every dropped
        # move in a partial entry. Only an all-dropped learnset blocks — an
        # empty list would corrupt the species.
        if not moves:
            report.add(ReportEntry(
                status="blocked", category="learnset", chrooked_id=chrooked_id,
                symbol=label,
                reason="no move in the learnset resolves in target: "
                + ", ".join(dropped),
            ))
            continue

        block = _find_block(lines, label)
        if block is None:
            report.add(ReportEntry(
                status="blocked", category="learnset", chrooked_id=chrooked_id,
                reason=f"no evos_attacks block for {label} in target",
            ))
            continue

        start, end = block
        region_start = _learnset_region_start(lines, start, end)
        if not _region_is_balanced(lines, region_start, end):
            report.add(ReportEntry(
                status="blocked", category="learnset", chrooked_id=chrooked_id,
                symbol=label,
                reason="conditional scaffolding around the learnset is unbalanced; "
                "refusing to splice",
            ))
            continue
        new_lines = [f"\tlearnset {level}, {symbol}" for level, symbol in sorted(moves, key=lambda m: m[0])]
        if lines[region_start:end] != new_lines:
            lines[region_start:end] = new_lines
            changed = True
        if dropped:
            report.add(ReportEntry(
                status="partial", category="learnset", chrooked_id=chrooked_id,
                symbol=label,
                reason="dropped move(s) the target lacks: " + ", ".join(dropped),
                partial_fields=tuple(dropped),
            ))
        else:
            report.add(ReportEntry(
                status="applied", category="learnset", chrooked_id=chrooked_id, symbol=label,
            ))

    if changed:
        evos_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return [evos_path]
    return []


def _find_block(lines: list[str], label: str) -> tuple[int, int] | None:
    """(start, end) line span of the species' block: header line to next blank.

    Form species label their default form `<Label>Plain` (FarfetchDPlain), so
    that suffix is tried when the bare label has no block.
    """
    for candidate in (label, label + "Plain"):
        header = f"\tevos_attacks {candidate}"
        for index, line in enumerate(lines):
            if line == header:
                end = index + 1
                while end < len(lines) and lines[end].strip() != "":
                    end += 1
                return index, end
    return None


def _learnset_region_start(lines: list[str], start: int, end: int) -> int:
    """First line of the trailing learnset/conditional run inside the block.

    The backward walk stops at the first non-learnset-ish line, but a FAITHFUL
    conditional wrapping `evo_data` (Flaaffy in the real file) leaves its
    closing `endc`/`else` dangling at the region head — those belong to the
    evo_data block above, so trim them back out of the region.
    """
    region_start = end
    for index in range(end - 1, start, -1):
        stripped = lines[index].strip()
        is_learnset_ish = (
            stripped.startswith("learnset")
            or stripped in ("else", "endc")
            or stripped.startswith("if ")
        )
        if not is_learnset_ish:
            break
        region_start = index
    while region_start < end and lines[region_start].strip() in ("else", "endc"):
        region_start += 1
    return region_start


def _region_is_balanced(lines: list[str], start: int, end: int) -> bool:
    """Every `if` inside the region closes inside it, and no stray closers."""
    depth = 0
    for index in range(start, end):
        stripped = lines[index].strip()
        if stripped.startswith("if "):
            depth += 1
        elif stripped == "endc":
            if depth == 0:
                return False
            depth -= 1
        elif stripped == "else" and depth == 0:
            return False
    return depth == 0
