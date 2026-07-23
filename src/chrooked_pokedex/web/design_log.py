"""Append a dated makeover entry to ``ruleset/DESIGN-LOG.md``.

The design log records the *why* behind each makeover — the direction picked, any
new mechanics created, and the corrections given in the tweak loops — mirroring
the format already in that file (see the Galvantula / Zoroark sections). The
Change Ledger records *what* changed; this records *why*, as raw material for
refining the suggest-skill rubrics and for loop-audits.

This module owns rendering + appending; the route is a thin wrapper. It only ever
appends — existing history is never rewritten.
"""

from __future__ import annotations

from datetime import date as _date
from pathlib import Path

_DEFAULT_HEADER = "# Design Log\n"


class DesignLogError(ValueError):
    """A design-log request could not be served (→ a clean 4xx detail).

    Raised when the entry is missing the two load-bearing fields (line name and
    the direction picked); the route maps it to a 422 with the honest message.
    """


def render_entry(
    *,
    line: str,
    direction: str,
    on_date: str,
    new_mechanics: str | None = None,
    corrections: str | None = None,
) -> str:
    """Render one dated section, mirroring the existing DESIGN-LOG.md format.

    ``line`` and ``direction`` are required (an entry with neither says nothing).
    ``new_mechanics`` and ``corrections`` are optional bullets, omitted when blank.
    Returns the section text ending in a single newline.
    """
    line = (line or "").strip()
    direction = (direction or "").strip()
    if not line:
        raise DesignLogError("A design-log entry needs a line name.")
    if not direction:
        raise DesignLogError("A design-log entry needs the direction picked.")

    parts = [f"## {on_date} — {line}", "", f"- **Direction:** {direction}"]
    if new_mechanics and new_mechanics.strip():
        parts.append(f"- **New mechanics:** {new_mechanics.strip()}")
    if corrections and corrections.strip():
        parts.append(f"- **Corrections:** {corrections.strip()}")
    return "\n".join(parts) + "\n"


def append_entry(
    design_log_path: Path | str,
    *,
    line: str,
    direction: str,
    on_date: str | None = None,
    new_mechanics: str | None = None,
    corrections: str | None = None,
) -> str:
    """Append a rendered section to the design log, creating the file if absent.

    Separates the new section from prior content with one blank line, matching the
    ``\\n\\n## `` section boundary the file already uses. Returns the appended
    section text so the caller can echo exactly what landed.
    """
    on_date = on_date or _date.today().isoformat()
    section = render_entry(
        line=line,
        direction=direction,
        on_date=on_date,
        new_mechanics=new_mechanics,
        corrections=corrections,
    )
    path = Path(design_log_path)
    existing = (
        path.read_text(encoding="utf-8") if path.exists() else _DEFAULT_HEADER
    )
    if not existing.endswith("\n"):
        existing += "\n"
    path.write_text(existing + "\n" + section, encoding="utf-8")
    return section
