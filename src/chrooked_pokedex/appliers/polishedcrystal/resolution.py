"""The polishedcrystal Resolution map: chrooked_id/aka hint -> RGBDS symbol.

Move and ability symbols are verified against the target's constants files;
an unverifiable id resolves to None so the caller reports `blocked` rather
than writing a symbol the assembler would reject. Species labels (the
CamelCase names used by `evos_attacks` and base_stats filenames) cannot be
verified here — each category applier verifies presence at its own file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

_CONST_RE = re.compile(r"^\tconst\s+([A-Z0-9_]+)")


def _parse_constants(path: Path) -> frozenset[str]:
    symbols = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _CONST_RE.match(line)
        if match:
            symbols.add(match.group(1))
    return frozenset(symbols)


def _derive_symbol(name: str) -> str:
    """Display name or id -> constant guess: `Ice Punch` -> ICE_PUNCH."""
    cleaned = name.replace("'", "").upper()
    return re.sub(r"[^A-Z0-9]+", "_", cleaned).strip("_")


@dataclass(frozen=True)
class ResolutionMap:
    """Verified symbol lookups for one Polished Crystal target."""

    move_symbols: frozenset[str]
    ability_symbols: frozenset[str]
    # type_constants.asm holds both type symbols (WATER) and the damage
    # categories (PHYSICAL/SPECIAL/STATUS), so one set verifies both.
    type_symbols: frozenset[str] = frozenset()

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


def build_resolution_map(target: Path) -> ResolutionMap:
    constants = Path(target) / "constants"
    return ResolutionMap(
        move_symbols=_parse_constants(constants / "move_constants.asm"),
        ability_symbols=_parse_constants(constants / "ability_constants.asm"),
        type_symbols=_parse_constants(constants / "type_constants.asm"),
    )
