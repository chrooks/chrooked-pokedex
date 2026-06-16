"""Surgical, whole-line edits to one Essentials 16.2 `[N]` PBS section.

Sections are addressed by `InternalName=` (not the `[N]` header, not the Spanish
`Name=`). `find_section_by_internalname` scans for the section whose `InternalName=`
matches and returns its char span; the field helpers operate on that block and splice
it back so the rest of the file — every other section, and every untouched line —
stays byte-identical.

Edits are whole-line: the value after `=` is replaced wholesale, never merged token by
token. 16.2 writes `Key=value` with no surrounding spaces, and lines end in CRLF; the
helpers preserve both. An absent field is inserted just under the section header.
"""

from __future__ import annotations

import re
from typing import Optional

# A `[N]` numeric header line, shared so edits and parses agree on section boundaries.
_HEADER_LINE = re.compile(r"^\[\d+\]\r?$", re.MULTILINE)


def find_section_by_internalname(text: str, internal: str) -> Optional[tuple[int, int]]:
    """Return `(start, end)` char offsets of the section whose `InternalName=internal`.

    `start` is the index of the `[` on that section's header line; `end` is the index of
    the next `[N]` header (or end of file). Returns None when no section matches.
    """
    headers = list(_HEADER_LINE.finditer(text))
    for position, match in enumerate(headers):
        start = match.start()
        end = headers[position + 1].start() if position + 1 < len(headers) else len(text)
        block = text[start:end]
        if _internalname_of(block) == internal:
            return (start, end)
    return None


def get_field(block: str, key: str) -> Optional[str]:
    """Return the value of the first `key=...` line in a block (stripped), or None."""
    match = _field_pattern(key).search(block)
    return match.group(1).strip() if match else None


def set_field(block: str, key: str, value: str) -> str:
    """Return a new block with `key` set to `value` (replace in place, else insert).

    The captured value text is replaced exactly, so the surrounding line — including
    its trailing `\r` — is preserved when present.
    """
    pattern = _field_pattern(key)
    match = pattern.search(block)
    if match:
        return block[: match.start(1)] + value + block[match.end(1):]
    return _insert_field(block, key, value)


def set_section_field(text: str, internal: str, key: str, value: str) -> tuple[str, bool]:
    """Set `key` inside the `[internal]` section only. Returns `(new_text, applied)`.

    A missing section is a no-op `(text, False)`, so the caller can report it unresolved
    instead of silently dropping the change.
    """
    span = find_section_by_internalname(text, internal)
    if span is None:
        return text, False
    block = text[span[0]:span[1]]
    return text[: span[0]] + set_field(block, key, value) + text[span[1]:], True


def set_comma_index(
    text: str, internal: str, key: str, index: int, value: str
) -> tuple[str, bool]:
    """Set one position of a comma-list field (e.g. `BaseStats`) in `[internal]`.

    A single base stat changes without re-rendering the other five. Returns
    `(new_text, applied)`; `applied` is False (text unchanged) when the section/field is
    missing or the index is out of range.
    """
    span = find_section_by_internalname(text, internal)
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


def append_section(text: str, header_index: int, block_body: str) -> str:
    """Append a new `[header_index]` section, emitting CRLF line endings.

    `block_body` is the section's field lines (without the header). The header and a
    separating blank line are added; everything emitted ends in CRLF to match 16.2.
    """
    base = text.rstrip("\r\n")
    body = block_body.strip("\r\n")
    lines = [f"[{header_index}]"] + body.split("\n")
    section = "\r\n".join(line.rstrip("\r") for line in lines) + "\r\n"
    separator = "\r\n" if base else ""
    return base + ("\r\n" if base else "") + separator + section


def _internalname_of(block: str) -> Optional[str]:
    return get_field(block, "InternalName")


def _field_pattern(key: str) -> re.Pattern[str]:
    # Capture the value (group 1) up to end of line, not crossing the trailing \r.
    return re.compile(r"^" + re.escape(key) + r"\s*=\s*([^\r\n]*)", re.MULTILINE)


def _insert_field(block: str, key: str, value: str) -> str:
    """Insert `Key=value` on its own line just after the section header line.

    The inserted line copies the block's existing newline style (CRLF when the header
    line ends in `\r\n`), so an insert into a CRLF file stays CRLF.
    """
    newline = block.find("\n")
    uses_crlf = newline > 0 and block[newline - 1] == "\r"
    eol = "\r\n" if uses_crlf else "\n"
    insertion = f"{key}={value}{eol}"
    if newline == -1:
        return block.rstrip("\r\n") + eol + insertion
    return block[: newline + 1] + insertion + block[newline + 1:]
