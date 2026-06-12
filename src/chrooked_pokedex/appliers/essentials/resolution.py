"""The Essentials Resolution map: `chrooked_id` / plain name -> INTERNAL name.

Built from the Ruleset's `aka:` hints and the target project's own PBS sections.
Species fall back to a name-derived INTERNAL (`Goodra` -> `GOODRA`); moves,
abilities, and types resolve by the target's own display `Name` lines so a move
the Ruleset cites as `Flamethrower` finds the `[FLAMETHROWER]` section even if its
internal name were spelled differently. Unresolved names are surfaced as None, not
guessed, so the Apply Report can show what the target genuinely lacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ...model import Ruleset
from . import pbs_read, vocab


@dataclass
class ResolutionMap:
    """Lookups from neutral identity to Essentials INTERNAL names, for one target."""

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
        # None (not a fabricated INTERNAL) for a type the target lacks, so the
        # species tier marks it unresolved rather than writing a token that fails
        # to load. Standard types are pre-seeded in `type_by_name` as a safety net.
        return self.type_by_name.get(name.lower())

    def ability(self, name: str) -> Optional[str]:
        return self.ability_by_name.get(name.lower())

    def move(self, name: str) -> Optional[str]:
        return self.move_by_name.get(name.lower())


def _read(target: Path, rel: str) -> str:
    path = target / "PBS" / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


# The 18 standard types, used only as a fallback when the target's `types.txt`
# could not be read — so standard-typed Overrides still apply, while a genuinely
# unknown (Fakemon) type stays unresolved.
_STANDARD_TYPES = (
    "Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost",
    "Steel", "Fire", "Water", "Grass", "Electric", "Psychic", "Ice", "Dragon",
    "Dark", "Fairy",
)


def build_resolution_map(target: Path, ruleset: Ruleset) -> ResolutionMap:
    type_by_name = pbs_read.name_to_header(_read(target, "types.txt"))
    if not type_by_name:
        type_by_name = {name.lower(): vocab.type_internal(name) for name in _STANDARD_TYPES}
    ability_by_name = pbs_read.name_to_header(_read(target, "abilities.txt"))
    move_by_name = pbs_read.name_to_header(_read(target, "moves.txt"))

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
