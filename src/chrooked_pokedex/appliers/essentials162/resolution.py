"""The Essentials 16.2 Resolution map: neutral identity -> the target's INTERNAL name.

Built from the target project's own 16.2 PBS. Every lookup resolves by INTERNAL
name, never the Spanish display `Name`: pokemon.txt and types.txt carry their identity
in an `InternalName=` field, and moves.txt/abilities.txt carry it in CSV column 1. A
move the Ruleset cites as `MEGAHORN` finds the row whose column 1 is `MEGAHORN`, while
its Spanish `Megacuerno` does not match — that is the whole point of the 16.2 split.

A name the target genuinely lacks resolves to None (surfaced in the Apply Report),
never a fabricated token. The 18 standard types are pre-seeded as a safety net for when
types.txt could not be read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ...model import Ruleset
from ..essentials import vocab
from . import csv_io, pbs_io, section_read

# Names that map a row to its INTERNAL via CSV column 1.
_CSV_INTERNAL_COL = 1


@dataclass
class ResolutionMap:
    """Lookups from neutral identity to 16.2 INTERNAL names, for one target."""

    species_by_id: dict[str, str] = field(default_factory=dict)
    type_by_name: dict[str, str] = field(default_factory=dict)
    ability_by_name: dict[str, str] = field(default_factory=dict)
    move_by_name: dict[str, str] = field(default_factory=dict)

    def species(self, chrooked_id: str, aka: dict) -> Optional[str]:
        symbol = aka.get("essentials") if aka else None
        if symbol:
            return symbol
        return self.species_by_id.get(chrooked_id)

    def type(self, name: str) -> Optional[str]:
        return self.type_by_name.get(name.lower())

    def ability(self, name: str) -> Optional[str]:
        return self.ability_by_name.get(name.lower())

    def move(self, name: str) -> Optional[str]:
        return self.move_by_name.get(name.lower())


# The 18 standard types, used only as a fallback when types.txt could not be read.
_STANDARD_TYPES = (
    "Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost",
    "Steel", "Fire", "Water", "Grass", "Electric", "Psychic", "Ice", "Dragon",
    "Dark", "Fairy",
)


def _read(target: Path, rel: str) -> str:
    path = target / "PBS" / rel
    if not path.exists():
        return ""
    text, _ = pbs_io.read(path)
    return text


def _internal_to_self(internals: list[str]) -> dict[str, str]:
    """Map each INTERNAL name (lowercased) to itself, for the resolver's `.lower()` keys."""
    return {internal.lower(): internal for internal in internals}


def _csv_internals(text: str) -> list[str]:
    """Every column-1 INTERNAL name in a flat-CSV file (moves/abilities)."""
    internals: list[str] = []
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if not line:
            continue
        columns = csv_io.split_columns(line)
        if len(columns) > _CSV_INTERNAL_COL:
            internals.append(columns[_CSV_INTERNAL_COL].strip())
    return internals


def build_resolution_map(target: Path, ruleset: Ruleset) -> ResolutionMap:
    type_internals = list(section_read.internalname_to_index(_read(target, "types.txt")))
    type_by_name = _internal_to_self(type_internals)
    if not type_by_name:
        type_by_name = {name.lower(): vocab.type_internal(name) for name in _STANDARD_TYPES}

    ability_by_name = _internal_to_self(_csv_internals(_read(target, "abilities.txt")))
    move_by_name = _internal_to_self(_csv_internals(_read(target, "moves.txt")))

    species_by_id: dict[str, str] = {}
    for chrooked_id, override in ruleset.species.items():
        hint = (override.aka or {}).get("essentials")
        species_by_id[chrooked_id] = hint or vocab.type_internal(override.name)

    return ResolutionMap(
        species_by_id=species_by_id,
        type_by_name=type_by_name,
        ability_by_name=ability_by_name,
        move_by_name=move_by_name,
    )
