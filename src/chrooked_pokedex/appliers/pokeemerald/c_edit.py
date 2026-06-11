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
    """Return the raw expression of the first `.field` in an entry body, or None."""
    spans = _field_value_spans(body, field)
    if not spans:
        return None
    start, end = spans[0]
    return body[start:end].strip()


def get_field_values(body: str, field: str) -> list[str]:
    """Return every raw `.field` expression in the body, in order.

    A species entry may carry the same field more than once, each branch of a
    `#if .../#else/#endif` block holding a different value (pokeemerald gates
    modern vs legacy stats/types/abilities this way).
    """
    return [body[start:end].strip() for start, end in _field_value_spans(body, field)]


def set_field(body: str, field: str, value: str) -> str:
    """Return a new entry body with `.field` set to `value`.

    Replaces the first existing value in place when present; otherwise inserts a
    new `.field = value,` line just after the opening of the body.
    """
    spans = _field_value_spans(body, field)
    if spans:
        start, end = spans[0]
        return body[:start] + value + body[end:]
    return _insert_field(body, field, value)


def set_field_all(body: str, field: str, value: str) -> str:
    """Set every occurrence of `.field` to the same `value`; insert if none exist.

    Use for fields whose desired value is absolute (stats, types): each
    preprocessor branch must end up holding the same Override value.
    """
    spans = _field_value_spans(body, field)
    if not spans:
        return _insert_field(body, field, value)
    for start, end in reversed(spans):  # right-to-left keeps earlier spans valid
        body = body[:start] + value + body[end:]
    return body


def set_field_per_occurrence(body: str, field: str, render) -> str:
    """Replace each `.field` value with `render(current_value)`.

    Use when the new value depends on the branch's own current value — e.g.
    abilities, where the Override changes only some slots and each branch keeps
    its own values for the rest.
    """
    spans = _field_value_spans(body, field)
    for start, end in reversed(spans):
        current = body[start:end].strip()
        body = body[:start] + render(current) + body[end:]
    return body


def _insert_field(body: str, field: str, value: str) -> str:
    insertion = f"\n{_INDENT}.{field} = {value},"
    newline = body.find("\n")
    if newline == -1:
        return f"{body}{insertion}"
    return body[:newline] + insertion + body[newline:]


def replace_entry_body(text: str, span: tuple[int, int], new_body: str) -> str:
    """Replace the brace body (exclusive of braces) at the given span."""
    open_brace, close_brace = span
    return text[: open_brace + 1] + new_body + text[close_brace:]


def _field_value_spans(body: str, field: str) -> list[tuple[int, int]]:
    pattern = re.compile(r"\.\s*" + re.escape(field) + r"\s*=\s*")
    spans: list[tuple[int, int]] = []
    for match in pattern.finditer(body):
        value_start = match.end()
        value_end = _find_expression_end(body, value_start)
        spans.append((value_start, value_end))
    return spans


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
