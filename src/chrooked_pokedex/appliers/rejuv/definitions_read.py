"""Inventory scans of the target's base Ruby definition files.

Rejuvenation stores its dex/move/ability data as Ruby hash literals in
``Scripts/Rejuv/Definitions/`` (``MONHASH``, ``MOVEHASH``, ``ABILHASH``). We do
NOT parse those hashes — the delta patch files eval the base at compile time and
mutate it. All we need up front is an *inventory*: which top-level symbol keys
exist (so an Override that names a missing species/move/ability is reported
blocked, never fabricated), which form names a species carries, and the highest
ability ID in use (so a newly-added ability gets a non-colliding ID).

These are deliberately regex scans, not a Ruby parser. The files are
machine-formatted with a stable two-space indent, so line-anchored patterns are
enough and cannot be fooled by the nesting the way a naive brace counter could.
"""

from __future__ import annotations

import re
from pathlib import Path

# Top-level MONHASH key:  two-space indent, ``:SYMBOL => {``.
_MON_KEY = re.compile(r'^  :([A-Z0-9_]+) => \{')
# Form name inside a species block: four-space indent, ``"Form Name" => {``.
_FORM = re.compile(r'^    "([^"]+)" => \{')
# Top-level key for MOVEHASH / ABILHASH: same two-space ``:SYMBOL => {``.
_SYM_KEY = re.compile(r'^  :([A-Z0-9_]+) => \{')
# An ``:ID => 123`` line (any indent).
_ID = re.compile(r':ID => (\d+)')
# A ``:name => "Display"`` line (any indent).
_NAME = re.compile(r':name => "([^"]*)"')


def scan_monhash_keys(path: Path) -> dict[str, list[str]]:
    """Map each MONHASH species key to its ordered list of form names.

    Example: ``{"BULBASAUR": ["Normal Form"], "ABSOL": ["Normal Form", "Mega Form"]}``.
    """
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        key = _MON_KEY.match(line)
        if key:
            current = key.group(1)
            result[current] = []
            continue
        form = _FORM.match(line)
        if form and current is not None:
            result[current].append(form.group(1))
    return result


def scan_symbol_keys(path: Path) -> set[str]:
    """Return the set of top-level ``:SYMBOL`` keys in a MOVEHASH/ABILHASH file."""
    return {m.group(1) for line in path.read_text(encoding="utf-8").splitlines()
            if (m := _SYM_KEY.match(line))}


def scan_symbol_names(path: Path) -> dict[str, str]:
    """Map each top-level entry's display ``:name`` (slugged) to its ``:SYMBOL``.

    Rescues the cases where Rejuv's internal symbol differs from the display name
    (``:VICEGRIP`` / "Vise Grip", ``:HIJUMPKICK`` / "High Jump Kick"): the Ruleset
    cites the display name, so a name index resolves what a symbol slug cannot.
    """
    from ...seed.neutralize import slug
    result: dict[str, str] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        key = _SYM_KEY.match(line)
        if key:
            current = key.group(1)
            continue
        name = _NAME.search(line)
        if name and current is not None:
            result.setdefault(slug(name.group(1)), current)
            current = None  # first :name per block only
    return result


def max_ability_id(path: Path) -> int:
    """Return the highest ``:ID`` value in an ABILHASH file (0 if none)."""
    return _max_id(path)


def max_move_id(path: Path) -> int:
    """Return the highest ``:ID`` value in a MOVEHASH file (0 if none)."""
    return _max_id(path)


def _max_id(path: Path) -> int:
    ids = [int(m.group(1)) for m in _ID.finditer(path.read_text(encoding="utf-8"))]
    return max(ids) if ids else 0
