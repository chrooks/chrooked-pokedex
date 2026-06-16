"""Byte-faithful read/write for Essentials 16.2 (Africanvs-era) PBS files.

These files differ from the v21 PBS in two ways that matter for round-tripping: a
BOM is present on some files but not others (pokemon.txt has none), and every line
ends in CRLF. This module is the one place that knows about those raw bytes.

`read` strips a leading BOM (remembering whether there was one) and decodes UTF-8,
leaving the CRLF line endings intact inside the returned string — we deliberately
never `splitlines()`, because that would lose the exact newline bytes we must write
back. `write` re-attaches the BOM iff the original had one and writes verbatim, so a
read-then-write with no edits is byte-identical.
"""

from __future__ import annotations

from pathlib import Path

_BOM_BYTES = b"\xef\xbb\xbf"
_BOM_CHAR = "﻿"


def read(path: Path) -> tuple[str, bool]:
    """Return `(text, had_bom)`.

    `text` keeps its CRLF line endings; a leading UTF-8 BOM is stripped from `text`
    and reported separately so `write` can faithfully restore it.
    """
    raw = path.read_bytes()
    had_bom = raw[:3] == _BOM_BYTES
    body = raw[3:] if had_bom else raw
    return body.decode("utf-8"), had_bom


def write(path: Path, text: str, had_bom: bool) -> None:
    """Write `text` back, re-attaching a BOM iff `had_bom`.

    The text is written verbatim — no newline normalization — so splices that keep
    CRLF intact produce byte-identical output for the untouched regions.
    """
    payload = (_BOM_CHAR + text) if had_bom else text
    path.write_bytes(payload.encode("utf-8"))
