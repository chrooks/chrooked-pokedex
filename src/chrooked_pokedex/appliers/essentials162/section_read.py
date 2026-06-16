"""Read Essentials 16.2 numeric-header PBS sections (pokemon.txt, types.txt).

Unlike v21 PBS — where a section header *is* the internal name (`[BULBASAUR]`) —
16.2 headers are bare sequential indices (`[1]`, `[2]`, ...) and the real identity
lives in an `InternalName=` field inside the section. Display names are Spanish
(`Name=`), so resolution must key off `InternalName=`, never the header or `Name`.

This reader is read-only and lossy-for-reading: it powers resolution (which internal
names exist) and never writes. Edits go through `section_edit`, which preserves the
bytes around a change. Note `Key=value` here has no spaces around `=`.
"""

from __future__ import annotations

import re

_HEADER = re.compile(r"^\[\s*(\d+)\s*\]\s*$")


def parse_sections(text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Return `[(header_index, [(key, value), ...]), ...]` in file order.

    `header_index` is the bare `[N]` number as a string. Lines are split on the first
    `=`; blank lines and `#` comments are skipped. Duplicate keys are kept in order.
    """
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    current: list[tuple[str, str]] | None = None
    for line in text.split("\n"):
        line = line.rstrip("\r")
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


def internalname_to_index(text: str) -> dict[str, str]:
    """Map each section's `InternalName=` to its bare `[N]` header index.

    A section without an `InternalName=` line is skipped (it has no stable identity).
    """
    mapping: dict[str, str] = {}
    for index, fields in parse_sections(text):
        internal = next((v for k, v in fields if k == "InternalName"), None)
        if internal:
            mapping[internal] = index
    return mapping


def internal_names(text: str) -> set[str]:
    """The set of `InternalName`s defined in the file."""
    return set(internalname_to_index(text))


def max_index(text: str) -> int:
    """The largest `[N]` header number in the file, or 0 if there are none.

    Creation (appending new owned content) uses `max_index + 1` as the next header.
    """
    indices = [int(index) for index, _ in parse_sections(text)]
    return max(indices) if indices else 0
