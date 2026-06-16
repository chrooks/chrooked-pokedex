"""Quote-aware flat-CSV read/edit for Essentials 16.2 moves.txt / abilities.txt.

These files are flat positional CSV (one row per line, no section headers):

  moves.txt:     idx,INTERNALNAME,SpanishName,HEX,power,TYPE,cat,acc,pp,effect,target,priority,flags,"desc"
  abilities.txt: idx,INTERNALNAME,SpanishName,"desc"

The trailing description column is double-quoted and contains commas, so a naive
`line.split(",")` corrupts it. The splitter here is quote-aware: it treats a `"`
quote as protecting commas until the matching close quote.

Editing is a surgical per-row splice. `find_row` locates a row by its INTERNALNAME
(column 1); `set_column` replaces a single column's text and re-joins the columns
verbatim, so untouched columns — including the quoted Spanish description — stay
byte-identical. Row splices keep CRLF intact.
"""

from __future__ import annotations

import re

_INTERNAL_COL = 1


def split_columns(line: str) -> list[str]:
    """Split one CSV line into columns, honoring double-quoted fields.

    A `"`-quoted field may contain commas; everything else splits on commas. The
    quote characters are kept in the returned column text so a re-join is verbatim.
    """
    columns: list[str] = []
    field: list[str] = []
    in_quotes = False
    for char in line:
        if char == '"':
            in_quotes = not in_quotes
            field.append(char)
        elif char == "," and not in_quotes:
            columns.append("".join(field))
            field = []
        else:
            field.append(char)
    columns.append("".join(field))
    return columns


def join_columns(columns: list[str]) -> str:
    """Re-join columns into a CSV line. Inverse of `split_columns` for splice work."""
    return ",".join(columns)


def find_row(text: str, internal: str) -> tuple[int, int] | None:
    """Return `(start, end)` char offsets of the row whose column 1 == `internal`.

    `start` is the first char of the line; `end` is the char *before* the line's
    trailing CRLF/LF (the newline is left in place so the splice preserves it). Returns
    None when no row matches.
    """
    for match in re.finditer(r"^[^\r\n]*", text, re.MULTILINE):
        line = match.group(0)
        if not line:
            continue
        columns = split_columns(line)
        if len(columns) > _INTERNAL_COL and columns[_INTERNAL_COL].strip() == internal:
            return (match.start(), match.end())
    return None


def get_column(text: str, internal: str, index: int) -> str | None:
    """Return column `index` of the `internal` row (stripped), or None if absent."""
    span = find_row(text, internal)
    if span is None:
        return None
    columns = split_columns(text[span[0]:span[1]])
    if not 0 <= index < len(columns):
        return None
    return columns[index]


def set_column(text: str, internal: str, index: int, value: str) -> tuple[str, bool]:
    """Replace one column of the `internal` row, splicing it back in place.

    Returns `(new_text, applied)`. Untouched columns and rows stay byte-identical; the
    line's CRLF is preserved. `applied` is False (text unchanged) when the row is
    missing or the column index is out of range, so the caller can report it unresolved.
    """
    span = find_row(text, internal)
    if span is None:
        return text, False
    line = text[span[0]:span[1]]
    columns = split_columns(line)
    if not 0 <= index < len(columns):
        return text, False
    columns[index] = value
    new_line = join_columns(columns)
    return text[: span[0]] + new_line + text[span[1]:], True


def max_index(text: str) -> int:
    """The largest column-0 sequence index across rows, or 0 when there are none.

    Creation appends a new row with `max_index + 1` as its leading index.
    """
    largest = 0
    for match in re.finditer(r"^[^\r\n]*", text, re.MULTILINE):
        line = match.group(0)
        if not line:
            continue
        first = split_columns(line)[0].strip()
        if first.isdigit():
            largest = max(largest, int(first))
    return largest


def append_row(text: str, row: str) -> str:
    """Append a CSV row to the end of the file, emitting CRLF.

    The new line ends in CRLF to match the file's existing endings; a trailing blank
    line in the source is preserved by appending after the final newline.
    """
    base = text
    if base and not base.endswith("\n"):
        base += "\r\n"
    return base + row.rstrip("\r\n") + "\r\n"
