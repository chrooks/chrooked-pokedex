"""The pokeemerald Resolution map: `chrooked_id`/plain name -> C symbol.

Built from the Ruleset's `aka:` hints and the target fork's own symbol tables.
Unresolved ids are surfaced (not guessed away) so the Apply Report can show what
the target genuinely lacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ...model import Ruleset
from ...readers.pokeemerald import ability_parser, move_parser
from ...readers.pokeemerald.type_chart_parser import parse_type_chart


@dataclass
class ResolutionMap:
    """Lookups from neutral identity to pokeemerald symbols, for one target."""

    species_by_id: dict[str, str] = field(default_factory=dict)
    type_by_name: dict[str, str] = field(default_factory=dict)
    ability_by_name: dict[str, str] = field(default_factory=dict)
    move_by_name: dict[str, str] = field(default_factory=dict)

    def species(self, chrooked_id: str, aka: dict) -> Optional[str]:
        symbol = aka.get("pokeemerald") if aka else None
        if symbol:
            return symbol
        return self.species_by_id.get(chrooked_id)

    def type(self, name: str) -> Optional[str]:
        return self.type_by_name.get(name.lower())

    def ability(self, name: str) -> Optional[str]:
        return self.ability_by_name.get(name.lower())

    def move(self, name: str) -> Optional[str]:
        return self.move_by_name.get(name.lower())


def build_resolution_map(target: Path, ruleset: Ruleset) -> ResolutionMap:
    type_by_name: dict[str, str] = {}
    for (attacker, _defender) in parse_type_chart(target):
        type_by_name[attacker.lower()] = "TYPE_" + attacker.upper().replace(" ", "_")
    # Fall back to a deterministic construction if the chart was unreadable.
    if not type_by_name:
        for name in _COMMON_TYPES:
            type_by_name[name.lower()] = "TYPE_" + name.upper()

    ability_by_name = {
        name.lower(): const
        for const, (name, _desc) in ability_parser.parse_ability_text(target).items()
    }
    move_by_name = {
        info.name.lower(): const
        for const, info in move_parser.parse_moves(target).items()
    }

    # Resolve from each species' own aka hint (exact, and correct for forms like
    # SPECIES_RATTATA_ALOLA); fall back to a constructed symbol only when absent.
    species_by_id = {}
    for chrooked_id, override in ruleset.species.items():
        symbol = (override.aka or {}).get("pokeemerald")
        species_by_id[chrooked_id] = symbol or ("SPECIES_" + chrooked_id.upper())

    return ResolutionMap(
        species_by_id=species_by_id,
        type_by_name=type_by_name,
        ability_by_name=ability_by_name,
        move_by_name=move_by_name,
    )


# Used only if the target's type chart could not be parsed.
_COMMON_TYPES = (
    "Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost",
    "Steel", "Fire", "Water", "Grass", "Electric", "Psychic", "Ice", "Dragon",
    "Dark", "Fairy",
)
