"""Essentials PBS dialect detector.

Pure, read-only function — safe to call from CLI apply and web endpoints.

Detection keys on file SHAPE, never display language:

Primary signal — ``PBS/moves.txt`` first non-blank, non-comment line:
  - Starts with ``<digits>,<NAME>,...``  (flat CSV)   → essentials16
  - Starts with ``[SECTION]`` (section header)         → essentials21

Corroboration — ``PBS/pokemon.txt`` first non-blank, non-comment line:
  - A ``[<digits>]`` numeric header                   → essentials16
  - A ``[<word>]`` text header (INTERNALNAME)          → essentials21

When both signals agree, return that dialect. When they disagree, or when
neither file exists / neither pattern matches, return None.
"""

from __future__ import annotations

import re
from pathlib import Path

# 16.2 moves.txt: first data row is a flat CSV, starts with a numeric id.
# Example: ``001,TACKLE,Tackle,NORMAL,Physical,...``
_MOVES_16_RE = re.compile(r"^\d+,\S+")

# 21+ moves.txt: first data is a section header like ``[TACKLE]``
_MOVES_21_RE = re.compile(r"^\[[^\]]+\]\s*$")

# 16.2 pokemon.txt: sections are numeric like ``[1]`` or ``[001]``
_POKEMON_16_RE = re.compile(r"^\[\d+\]\s*$")

# 21+ pokemon.txt: sections are word-based like ``[BULBASAUR]``
_POKEMON_21_RE = re.compile(r"^\[[A-Za-z_][^\]]*\]\s*$")


def _first_meaningful_line(text: str) -> str | None:
    """Return the first non-blank, non-comment line, or None."""
    for line in text.splitlines():
        # PBS files exported by Essentials often carry a UTF-8 BOM on line 1;
        # str.strip() doesn't drop ﻿, so lstrip it before the comment check.
        stripped = line.lstrip("﻿").strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return None


def _signal_from_moves(pbs_dir: Path) -> str | None:
    """Return 'essentials16', 'essentials21', or None from moves.txt shape."""
    moves_path = pbs_dir / "moves.txt"
    if not moves_path.exists():
        return None
    try:
        text = moves_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    line = _first_meaningful_line(text)
    if line is None:
        return None
    if _MOVES_16_RE.match(line):
        return "essentials16"
    if _MOVES_21_RE.match(line):
        return "essentials21"
    return None


def _signal_from_pokemon(pbs_dir: Path) -> str | None:
    """Return 'essentials16', 'essentials21', or None from pokemon.txt shape."""
    pokemon_path = pbs_dir / "pokemon.txt"
    if not pokemon_path.exists():
        return None
    try:
        text = pokemon_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    line = _first_meaningful_line(text)
    if line is None:
        return None
    if _POKEMON_16_RE.match(line):
        return "essentials16"
    if _POKEMON_21_RE.match(line):
        return "essentials21"
    return None


def detect_dialect(target: Path) -> str | None:
    """Detect the Essentials PBS dialect of a game directory.

    Args:
        target: Root directory of the Essentials game (parent of ``PBS/``).

    Returns:
        ``"essentials16"`` for Essentials 16.x-shaped PBS,
        ``"essentials21"`` for modern (v19+) section-based PBS, or
        ``None`` when the format cannot be determined (missing files,
        unrecognised shape, or conflicting signals between files).
    """
    pbs_dir = target / "PBS"
    if not pbs_dir.is_dir():
        return None

    moves_signal = _signal_from_moves(pbs_dir)
    pokemon_signal = _signal_from_pokemon(pbs_dir)

    # Both signals present — require agreement
    if moves_signal is not None and pokemon_signal is not None:
        return moves_signal if moves_signal == pokemon_signal else None

    # Only one signal available — use it
    return moves_signal or pokemon_signal
