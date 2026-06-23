"""Surgical, whole-line edits to one Essentials 16.2 `[BASE-N]` form section.

The 16.2 analogue of `section_edit`, but addressed by the `[BASE-N]` header string
rather than by `InternalName=` — form sections in `pokemonforms.txt` carry no
InternalName. The block-level field helpers (`get_field`/`set_field`) are shared with
`section_edit`; only the section-locating differs. Edits are whole-line and preserve
the surrounding bytes (CRLF endings, every untouched section) exactly.
"""

from __future__ import annotations

import re
from typing import Optional

from . import section_edit

# A `[BASE-N]` header line, shared so edits and parses agree on section boundaries.
# Horizontal-only whitespace before the CRLF keeps `$` on the header line and never
# lets the match swallow following blank lines.
_HEADER_LINE = re.compile(r"^\[[ \t]*[A-Za-z0-9_]+-\d+[ \t]*\][ \t]*\r?$", re.MULTILINE)


def find_section_by_header(text: str, header: str) -> Optional[tuple[int, int]]:
    """Return `(start, end)` char offsets of the `[header]` form section.

    `header` is the inside-bracket string (e.g. "DEOXYS-1"). `start` is the index of
    the `[` on that header line; `end` is the next `[BASE-N]` header (or end of file).
    Returns None when no section matches.
    """
    headers = list(_HEADER_LINE.finditer(text))
    for position, match in enumerate(headers):
        start = match.start()
        end = headers[position + 1].start() if position + 1 < len(headers) else len(text)
        inside = text[start:end].split("]", 1)[0].lstrip("[").strip()
        if inside == header:
            return (start, end)
    return None


def set_section_field(text: str, header: str, key: str, value: str) -> tuple[str, bool]:
    """Set `key` inside the `[header]` form section only. Returns `(new_text, applied)`.

    A missing section is a no-op `(text, False)`, so the caller can report it
    unresolved instead of silently dropping the change.
    """
    span = find_section_by_header(text, header)
    if span is None:
        return text, False
    block = text[span[0]:span[1]]
    return text[: span[0]] + section_edit.set_field(block, key, value) + text[span[1]:], True


def set_comma_index(
    text: str, header: str, key: str, index: int, value: str
) -> tuple[str, bool]:
    """Set one position of a comma-list field (e.g. `BaseStats`) in `[header]`.

    Returns `(new_text, applied)`; `applied` is False (text unchanged) when the
    section/field is missing or the index is out of range.
    """
    span = find_section_by_header(text, header)
    if span is None:
        return text, False
    block = text[span[0]:span[1]]
    current = section_edit.get_field(block, key)
    if current is None:
        return text, False
    parts = [p.strip() for p in current.split(",")]
    if not 0 <= index < len(parts):
        return text, False
    parts[index] = value
    new_block = section_edit.set_field(block, key, ",".join(parts))
    return text[: span[0]] + new_block + text[span[1]:], True


def remove_section_field(text: str, header: str, key: str) -> tuple[str, bool]:
    """Delete the `key=...` line from the `[header]` form section. Returns `(new_text, removed)`.

    A mono-type Override drops `Type2` entirely (it is absent, not blank). A missing
    section or field is a no-op `(text, False)`. The line's trailing CRLF goes with it.
    """
    span = find_section_by_header(text, header)
    if span is None:
        return text, False
    block = text[span[0]:span[1]]
    line = re.compile(r"^" + re.escape(key) + r"[ \t]*=[^\r\n]*\r?\n?", re.MULTILINE)
    match = line.search(block)
    if match is None:
        return text, False
    new_block = block[: match.start()] + block[match.end():]
    return text[: span[0]] + new_block + text[span[1]:], True


def get_section_field(text: str, header: str, key: str) -> Optional[str]:
    """Return the value of `key` in the `[header]` section, or None."""
    span = find_section_by_header(text, header)
    if span is None:
        return None
    return section_edit.get_field(text[span[0]:span[1]], key)
