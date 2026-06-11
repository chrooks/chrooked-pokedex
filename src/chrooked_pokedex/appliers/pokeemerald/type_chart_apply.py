"""Apply type-chart multiplier overrides into `src/data/types_info.h`.

The effectiveness table is a square matrix of cell tokens. Each override names an
attacker (the row) and a defender (the column); the cell at that intersection is
rewritten to the override's multiplier, rendered as `X(n)` (or `______` for 1.0,
matching the file's regular-effectiveness sentinel).
"""

from __future__ import annotations

import re
from pathlib import Path

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from ...readers.pokeemerald.type_chart_parser import type_constant_to_name

_TABLE_HEADER = re.compile(
    r"gTypeEffectivenessTable\s*\[[^\]]*\]\s*\[[^\]]*\]\s*=\s*\{"
)
_ROW = re.compile(r"\[\s*(TYPE_\w+)\s*\]\s*=\s*\{")


def apply_type_chart(target: Path, ruleset: Ruleset, report: ApplyReport) -> set[Path]:
    path = target / "src" / "data" / "types_info.h"
    if not ruleset.type_chart:
        return set()
    if not path.exists():
        for override in ruleset.type_chart:
            report.add(ReportEntry(
                status="blocked", category="type-chart",
                chrooked_id=f"{override.attacker}->{override.defender}",
                reason="types_info.h not found",
            ))
        return set()

    text = path.read_text(encoding="utf-8")
    ordered_types = _ordered_types(text)
    index_by_type = {name: i for i, name in enumerate(ordered_types)}

    changed = False
    for override in ruleset.type_chart:
        chrooked_id = f"{override.attacker}->{override.defender}"
        col = index_by_type.get(override.defender)
        if col is None or override.attacker not in index_by_type:
            report.add(ReportEntry(
                status="blocked", category="type-chart", chrooked_id=chrooked_id,
                reason="type not present in target chart",
            ))
            continue
        new_text = _set_cell(text, override.attacker, col, _render(override.multiplier))
        if new_text != text:
            text = new_text
            changed = True
        report.add(ReportEntry(
            status="applied", category="type-chart", chrooked_id=chrooked_id,
        ))

    if changed:
        path.write_text(text, encoding="utf-8")
        return {path}
    return set()


def _ordered_types(text: str) -> list[str]:
    header = _TABLE_HEADER.search(text)
    if header is None:
        return []
    table_end = _find_matching_brace(text, header.end() - 1)
    table_text = text[header.end() : table_end] if table_end else text[header.end() :]
    return [type_constant_to_name(m.group(1)) for m in _ROW.finditer(table_text)]


def _set_cell(text: str, attacker: str, col: int, value: str) -> str:
    attacker_const = "TYPE_" + attacker.upper().replace(" ", "_")
    header = _TABLE_HEADER.search(text)
    start = header.end() if header else 0
    row = re.compile(r"\[\s*" + re.escape(attacker_const) + r"\s*\]\s*=\s*\{")
    match = row.search(text, start)
    if match is None:
        return text
    open_brace = match.end() - 1
    close_brace = _find_matching_brace(text, open_brace)
    if close_brace is None:
        return text
    body = text[open_brace + 1 : close_brace]
    cells = _split_cells(body)
    if col >= len(cells):
        return text
    cells[col] = (cells[col][0], value)  # keep leading whitespace, swap token
    new_body = ",".join(ws + tok for ws, tok in cells)
    return text[: open_brace + 1] + new_body + text[close_brace:]


def _split_cells(body: str) -> list[tuple[str, str]]:
    """Split a row body into (leading_whitespace, token) pairs, depth-aware."""
    parts: list[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(body):
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(body[start:i])
            start = i + 1
    parts.append(body[start:])
    result: list[tuple[str, str]] = []
    for part in parts:
        stripped = part.lstrip()
        ws = part[: len(part) - len(stripped)]
        result.append((ws, stripped.rstrip()))
    # A trailing empty part (from a final comma) would add a phantom cell; drop it.
    if result and result[-1][1] == "":
        result.pop()
    return result


def _render(multiplier: float) -> str:
    if multiplier == 1.0:
        return "______"
    if multiplier == int(multiplier):
        return f"X({int(multiplier)}.0)"
    return f"X({multiplier})"


def _find_matching_brace(text: str, open_index: int):
    depth = 0
    for pos in range(open_index, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return pos
    return None
