"""Read Essentials PBS text into sections.

A PBS file is a flat list of sections. A section starts at a `[INTERNAL_NAME]`
line and runs until the next one (or end of file). Inside a section each
meaningful line is `Key = value`; blank lines and `#` comments are ignored.

This reader is deliberately lossy-for-reading-only: it powers resolution
(which internal names exist, and display-Name -> INTERNAL) and never writes.
Edits go through `pbs_edit`, which preserves the original bytes around a change.
"""

from __future__ import annotations

import re

_HEADER = re.compile(r"^\[\s*([^\]]+?)\s*\]\s*$")


def parse_sections(text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Return `[(header, [(key, value), ...]), ...]` in file order.

    Duplicate keys are kept in order (Essentials does not use them, but a faithful
    reader should not silently collapse them).
    """
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    current: list[tuple[str, str]] | None = None
    for line in text.splitlines():
        header = _HEADER.match(line)
        if header:
            current = []
            sections.append((header.group(1), current))
            continue
        if current is None:
            continue  # preamble before the first section
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        current.append((key.strip(), value.strip()))
    return sections


def section_headers(text: str) -> set[str]:
    """The set of `INTERNAL_NAME`s defined in the file."""
    return {header for header, _ in parse_sections(text)}


def name_to_header(text: str) -> dict[str, str]:
    """Map each section's display `Name` (lowercased) to its `INTERNAL_NAME`.

    Resolution needs this because the Ruleset cites moves/abilities by display
    name, while a PBS section is keyed by its internal name. Falls back to the
    header itself when a section has no `Name` line.
    """
    mapping: dict[str, str] = {}
    for header, fields in parse_sections(text):
        name = next((v for k, v in fields if k == "Name"), header)
        mapping[name.lower()] = header
    return mapping
