"""The polishedcrystal Resolution map: chrooked_id/aka hint -> RGBDS symbol.

Move and ability symbols are verified against the target's constants files;
an unverifiable id resolves to None so the caller reports `blocked` rather
than writing a symbol the assembler would reject. Species labels (the
CamelCase names used by `evos_attacks` and base_stats filenames) cannot be
verified here — each category applier verifies presence at its own file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

_CONST_RE = re.compile(r"^\tconst\s+([A-Z0-9_]+)")


def _parse_constants(path: Path, stop_at: str | None = None) -> tuple[str, ...]:
    """`const` symbols in file order; `stop_at` cuts before unrelated tables."""
    symbols = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if stop_at and stop_at in line:
            break
        match = _CONST_RE.match(line)
        if match:
            symbols.append(match.group(1))
    return tuple(symbols)


def _derive_symbol(name: str) -> str:
    """Display name or id -> constant guess: `Ice Punch` -> ICE_PUNCH."""
    cleaned = name.replace("'", "").upper()
    return re.sub(r"[^A-Z0-9]+", "_", cleaned).strip("_")


@dataclass(frozen=True)
class ResolutionMap:
    """Verified symbol lookups for one Polished Crystal target."""

    move_symbols: frozenset[str]
    ability_symbols: frozenset[str]
    # Move constants in ID order (NO_MOVE excluded): index+1 == move ID, which
    # is also the position of the move's `li` line in data/moves/names.asm.
    move_order: tuple[str, ...] = ()
    # type_constants.asm holds both type symbols (WATER) and the damage
    # categories (PHYSICAL/SPECIAL/STATUS), so one set verifies both.
    type_symbols: frozenset[str] = frozenset()
    # Display name -> existing target symbol, from ruleset meta `standins:`.
    # Consulted only for move REFERENCES (learnsets) — never for stat writes;
    # the stand-in move stays itself, species just learn it.
    standins: Mapping[str, str] = field(default_factory=dict)

    def _resolve(
        self,
        chrooked_id: str,
        aka: Mapping[str, object],
        symbols: frozenset[str],
        name: Optional[str] = None,
    ) -> Optional[str]:
        # An aka hint is authoritative (but still verified). Otherwise try the
        # chrooked_id first — for a *renamed* entity the id keeps the original
        # identity while `name` holds the new display name — then the name.
        hint = (aka or {}).get("polishedcrystal")
        if hint:
            return str(hint) if str(hint) in symbols else None
        for source in (chrooked_id, name):
            if not source:
                continue
            derived = _derive_symbol(source)
            # GB name-length limits make PC squash some long names
            # (ANCIENTPOWER, THUNDERPUNCH) — try the squashed form too.
            for candidate in (derived, derived.replace("_", "")):
                if candidate in symbols:
                    return candidate
        return None

    def move(
        self, chrooked_id: str, aka: Mapping[str, object], name: Optional[str] = None
    ) -> Optional[str]:
        return self._resolve(chrooked_id, aka, self.move_symbols, name)

    def ability(
        self, chrooked_id: str, aka: Mapping[str, object], name: Optional[str] = None
    ) -> Optional[str]:
        return self._resolve(chrooked_id, aka, self.ability_symbols, name)

    def move_reference(self, name: str) -> Optional[str]:
        """Resolve a move reference (learnset entry): stand-in first, then direct."""
        standin = self.standins.get(name)
        if standin:
            return standin if standin in self.move_symbols else None
        return self.move(name, {})

    def type(self, name: str) -> Optional[str]:
        candidate = _derive_symbol(name)
        return candidate if candidate in self.type_symbols else None

    def species_label(self, name: str, aka: Mapping[str, object]) -> str:
        """CamelCase label guess (`Farfetch'd` -> FarfetchD); aka hint wins.

        Form-suffixed labels (FarfetchDPlain) are not derivable — the guess
        misses, the category applier reports blocked, and an aka hint fixes it.
        """
        hint = (aka or {}).get("polishedcrystal")
        if hint:
            return str(hint)
        return re.sub(r"[^A-Za-z0-9]+", " ", name).title().replace(" ", "")


def build_resolution_map(
    target: Path, standins: Mapping[str, str] | None = None
) -> ResolutionMap:
    constants = Path(target) / "constants"
    # Cut at NUM_ATTACKS: past it the same file defines animation constants,
    # which are not moves and would poison both the symbol set and ID order.
    order = _parse_constants(constants / "move_constants.asm", stop_at="NUM_ATTACKS")
    move_order = tuple(sym for sym in order if sym != "NO_MOVE")
    return ResolutionMap(
        move_symbols=frozenset(move_order),
        ability_symbols=frozenset(_parse_constants(constants / "ability_constants.asm")),
        type_symbols=frozenset(_parse_constants(constants / "type_constants.asm")),
        move_order=move_order,
        standins=dict(standins or {}),
    )
