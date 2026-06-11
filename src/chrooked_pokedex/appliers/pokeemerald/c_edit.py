"""Low-level, surgical edits to pokeemerald species_info C entries.

The applier rewrites individual fields inside a `[SPECIES_X] = { ... }` entry
without disturbing the rest of the file. It uses whole-field replacement — the
entire `.field = <expr>,` value is swapped, never merged token-by-token — so
there is no way to half-edit a value.

Only brace-form entries can be field-edited. A macro-form entry
(`[SPECIES_UNOWN] = UNOWN_MISC_INFO(...)`) has no literal fields to rewrite;
callers detect the `None` return and report the species as blocked.
"""

from __future__ import annotations

import re
from typing import Optional

_INDENT = "        "  # 8 spaces, matching species_info style


def find_species_entry(text: str, species_const: str) -> Optional[tuple[int, int]]:
    """Return (open_brace_index, close_brace_index) for a brace-form entry.

    Returns None when the species is absent or written in macro form.
    """
    pattern = re.compile(r"\[\s*" + re.escape(species_const) + r"\s*\]\s*=\s*")
    match = pattern.search(text)
    if match is None:
        return None
    pos = match.end()
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] != "{":
        return None  # macro form or unexpected — cannot field-edit
    close = _find_matching_brace(text, pos)
    if close is None:
        return None
    return (pos, close)


def get_field(body: str, field: str) -> Optional[str]:
    """Return the raw expression of `.field` inside an entry body, or None."""
    span = _field_value_span(body, field)
    if span is None:
        return None
    start, end = span
    return body[start:end].strip()


def set_field(body: str, field: str, value: str) -> str:
    """Return a new entry body with `.field` set to `value`.

    Replaces the existing value in place when present; otherwise inserts a new
    `.field = value,` line just after the opening of the body.
    """
    span = _field_value_span(body, field)
    if span is not None:
        start, end = span
        return body[:start] + value + body[end:]
    # Insert a new field line at the top of the body.
    insertion = f"\n{_INDENT}.{field} = {value},"
    newline = body.find("\n")
    if newline == -1:
        return f"{body}{insertion}"
    return body[: newline] + insertion + body[newline:]


def replace_entry_body(text: str, span: tuple[int, int], new_body: str) -> str:
    """Replace the brace body (exclusive of braces) at the given span."""
    open_brace, close_brace = span
    return text[: open_brace + 1] + new_body + text[close_brace:]


def _field_value_span(body: str, field: str) -> Optional[tuple[int, int]]:
    pattern = re.compile(r"\.\s*" + re.escape(field) + r"\s*=\s*")
    match = pattern.search(body)
    if match is None:
        return None
    value_start = match.end()
    value_end = _find_expression_end(body, value_start)
    return (value_start, value_end)


def _find_expression_end(text: str, start: int) -> int:
    depth = 0
    pos = start
    while pos < len(text):
        char = text[pos]
        if char in "{([":
            depth += 1
        elif char in "})]":
            if depth == 0:
                return pos
            depth -= 1
        elif char == "," and depth == 0:
            return pos
        pos += 1
    return pos


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
