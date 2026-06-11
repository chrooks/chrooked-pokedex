"""Parse pokeemerald-expansion's type effectiveness table.

The table lives in `src/data/types_info.h` as a square matrix
`gTypeEffectivenessTable[NUMBER_OF_MON_TYPES][NUMBER_OF_MON_TYPES]`, with rows
labelled `[TYPE_X] = { ... }`. Each cell is a multiplier token:

    ______        regular effectiveness (1.0)
    X(0.5)        a literal multiplier
    STL_RS        a named macro #defined elsewhere in the file, sometimes as a
                  build-flag conditional like `(COND ? X(1.0) : X(0.5))`

There is no parser for this in v1; this is written new. Two views are returned
per cell so callers can both diff and emit:

  * the raw token text, for exact diffing (a fork that changed nothing keeps the
    same macro token, so diffing raw text avoids false positives from build flags);
  * a resolved float multiplier, for writing a neutral Override (named macros are
    resolved by taking the modern/"true" branch of any conditional).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class TypeChartCell:
    attacker: str  # neutral type name, e.g. "Flying"
    defender: str  # neutral type name, e.g. "Ice"
    raw: str       # raw token text, e.g. "X(0.5)" or "______" or "STL_RS"
    value: Optional[float]  # resolved multiplier, or None if unresolvable


_TABLE_HEADER = re.compile(
    r"gTypeEffectivenessTable\s*\[[^\]]*\]\s*\[[^\]]*\]\s*=\s*\{"
)
_ROW = re.compile(r"\[\s*(TYPE_\w+)\s*\]\s*=\s*\{")
_DEFINE = re.compile(r"^\s*#define\s+(\w+)\s+(.*?)\s*$", re.MULTILINE)
_X_LITERAL = re.compile(r"X\(\s*([0-9.]+)\s*\)")
_CONDITIONAL = re.compile(r"\?\s*(.+?)\s*:")


def type_constant_to_name(constant: str) -> str:
    """`TYPE_FLYING` -> `Flying`. Title-cases the single-word type name."""
    return constant.removeprefix("TYPE_").replace("_", " ").title()


def parse_type_chart(repo_path: Path) -> dict[tuple[str, str], TypeChartCell]:
    """Return {(attacker_name, defender_name): TypeChartCell} for one repo."""
    path = repo_path / "src" / "data" / "types_info.h"
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    macros = _collect_macros(text)

    header = _TABLE_HEADER.search(text)
    if header is None:
        return {}
    table_end = _find_matching_brace(text, header.end() - 1)
    table_text = text[header.end() : table_end] if table_end else text[header.end() :]

    rows = _parse_rows(table_text)
    ordered_types = [attacker for attacker, _ in rows]

    result: dict[tuple[str, str], TypeChartCell] = {}
    for attacker_const, tokens in rows:
        attacker = type_constant_to_name(attacker_const)
        for index, token in enumerate(tokens):
            if index >= len(ordered_types):
                break
            defender = type_constant_to_name(ordered_types[index])
            result[(attacker, defender)] = TypeChartCell(
                attacker=attacker,
                defender=defender,
                raw=token,
                value=_resolve_token(token, macros),
            )
    return result


def _parse_rows(table_text: str) -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = []
    for match in _ROW.finditer(table_text):
        constant = match.group(1)
        close = _find_matching_brace(table_text, match.end() - 1)
        if close is None:
            continue
        body = table_text[match.end() : close]
        tokens = [tok.strip() for tok in _split_top_level(body) if tok.strip()]
        rows.append((constant, tokens))
    return rows


def _collect_macros(text: str) -> dict[str, str]:
    macros: dict[str, str] = {}
    for match in _DEFINE.finditer(text):
        macros[match.group(1)] = match.group(2)
    return macros


def _resolve_token(token: str, macros: dict[str, str]) -> Optional[float]:
    token = token.strip()
    if not token:
        return None
    if set(token) == {"_"}:  # the ______ regular-effectiveness sentinel
        return 1.0
    literal = _X_LITERAL.fullmatch(token)
    if literal:
        return float(literal.group(1))
    if token in macros:
        return _resolve_macro_body(macros[token], macros)
    # A bare X(n) caught loosely, or unknown — try a loose literal search.
    loose = _X_LITERAL.search(token)
    if loose and token.startswith("X("):
        return float(loose.group(1))
    return None


def _resolve_macro_body(body: str, macros: dict[str, str]) -> Optional[float]:
    body = body.strip()
    conditional = _CONDITIONAL.search(body)
    if conditional:
        # Take the modern/"true" branch: `(COND >= GEN_x ? X(a) : X(b))` -> X(a).
        branch = conditional.group(1).strip()
        return _resolve_token(branch, macros)
    return _resolve_token(body, macros)


def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(text):
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    tail = text[start:]
    if tail.strip():
        parts.append(tail)
    return parts


def _find_matching_brace(text: str, open_index: int) -> Optional[int]:
    depth = 0
    for pos in range(open_index, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return pos
    return None
