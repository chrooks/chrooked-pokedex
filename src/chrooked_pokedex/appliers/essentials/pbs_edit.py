"""Surgical, whole-line edits to one Essentials PBS section.

The Applier rewrites individual `Key = value` lines inside a single
`[INTERNAL_NAME]` section without disturbing the rest of the file. Edits are
whole-line: the entire value after `=` is replaced, never merged token by token,
so there is no way to half-write a value. A field that is absent is inserted
just under the section header.

`find_section` returns the character span of a section block (header line through
the line before the next header). All field helpers operate on that block string;
`set_section_field` and `set_comma_index` splice the new block back into the file.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

# One source of truth for "a line that is a section header", shared by the reader.
# Matching the reader's pattern keeps section-boundary detection consistent
# everywhere, so an edit can never disagree with a parse about where a section ends.
_HEADER_LINE = re.compile(r"^\[\s*[^\]]+?\s*\]\s*$", re.MULTILINE)


def find_section(text: str, header: str) -> Optional[tuple[int, int]]:
    """Return `(block_start, block_end)` char offsets for `[header]`, or None.

    `block_start` is the index of the `[` on the header line; `block_end` is the
    index of the next section header (or end of file).
    """
    open_pattern = re.compile(r"^\[\s*" + re.escape(header) + r"\s*\]\s*$", re.MULTILINE)
    match = open_pattern.search(text)
    if match is None:
        return None
    start = match.start()
    nxt = _HEADER_LINE.search(text, match.end())
    end = nxt.start() if nxt else len(text)
    return (start, end)


def get_field(block: str, key: str) -> Optional[str]:
    """Return the value of the first `key = ...` line in a section block, or None."""
    match = _field_pattern(key).search(block)
    return match.group(1).strip() if match else None


def set_field(block: str, key: str, value: str) -> str:
    """Return a new block with `key` set to `value` (replace in place, else insert)."""
    pattern = _field_pattern(key)
    match = pattern.search(block)
    if match:
        return block[: match.start(1)] + value + block[match.end(1):]
    return _insert_field(block, key, value)


def set_section_field(text: str, header: str, key: str, value: str) -> str:
    """Replace `key` inside `[header]` only, returning the whole new file text.

    A no-op (section missing) returns the text unchanged.
    """
    span = find_section(text, header)
    if span is None:
        return text
    block = text[span[0]:span[1]]
    return text[: span[0]] + set_field(block, key, value) + text[span[1]:]


def set_comma_index(
    text: str, header: str, key: str, index: int, value: str
) -> tuple[str, bool]:
    """Set one position of a comma-list field (e.g. `BaseStats`) inside `[header]`.

    Used for stat Overrides: a single base stat is changed without re-rendering the
    other five. Returns `(new_text, applied)`. `applied` is False — and the text is
    unchanged — when the section or field is missing or the index is out of range,
    so the caller reports it unresolved instead of silently dropping the change.
    """
    span = find_section(text, header)
    if span is None:
        return text, False
    block = text[span[0]:span[1]]
    current = get_field(block, key)
    if current is None:
        return text, False
    parts = [p.strip() for p in current.split(",")]
    if not 0 <= index < len(parts):
        return text, False
    parts[index] = value
    new_block = set_field(block, key, ",".join(parts))
    return text[: span[0]] + new_block + text[span[1]:], True


def _field_pattern(key: str) -> re.Pattern[str]:
    # Capture the value (group 1) up to end of line.
    return re.compile(r"^" + re.escape(key) + r"\s*=\s*(.*)$", re.MULTILINE)


def _insert_field(block: str, key: str, value: str) -> str:
    """Insert `Key = value` on its own line just after the section header line."""
    newline = block.find("\n")
    insertion = f"{key} = {value}\n"
    if newline == -1:
        return block.rstrip("\n") + "\n" + insertion
    return block[: newline + 1] + insertion + block[newline + 1:]


def append_section(text: str, block: str) -> str:
    """Append a new section block to the end of a PBS file, separated by a blank line."""
    base = text.rstrip("\n")
    separator = "\n\n" if base else ""
    return base + separator + block.rstrip("\n") + "\n"


def apply_field_render(block: str, key: str, render: Callable[[Optional[str]], str]) -> str:
    """Set `key` to `render(current_value)` (current is None when absent)."""
    return set_field(block, key, render(get_field(block, key)))
