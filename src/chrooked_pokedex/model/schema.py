"""Frozen dataclasses for the engine-neutral Ruleset schema.

These describe Chris's preferred Pokémon changes in plain names (`Water`,
`Poison Heal`), never engine symbols. Scalar species fields are Overrides:
present only when changed. Learnsets are the exception — when present, the
list is whole and the Applier replaces the target's list outright.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional


# The six base stats, by their short Ruleset keys.
STAT_KEYS: tuple[str, ...] = ("hp", "atk", "def", "spa", "spd", "spe")

# Move damage categories allowed in the Ruleset.
MOVE_CATEGORIES: frozenset[str] = frozenset({"physical", "special", "status"})


@dataclass(frozen=True)
class AbilitiesOverride:
    """Ability slots. Each is optional — present only when overridden."""

    primary: Optional[str] = None
    secondary: Optional[str] = None
    hidden: Optional[str] = None


@dataclass(frozen=True)
class LearnsetMove:
    """One level-up move. Stored only as part of a whole learnset list."""

    level: int
    move: str


@dataclass(frozen=True)
class EvolutionOverride:
    """How a species evolves: from a pre-evolution, by some method."""

    from_species: Optional[str] = None
    method: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SpeciesOverride:
    """The set of fields that differ from base for one species.

    Scalar fields default to None and appear only when overridden. `learnset`
    is None unless the Ruleset owns the whole list for this species.
    """

    name: str
    chrooked_id: str
    aka: Mapping[str, object] = field(default_factory=dict)
    types: Optional[tuple[str, ...]] = None
    abilities: Optional[AbilitiesOverride] = None
    stats: Optional[Mapping[str, int]] = None
    learnset: Optional[tuple[LearnsetMove, ...]] = None
    evolution: Optional[EvolutionOverride] = None


@dataclass(frozen=True)
class MoveDef:
    """A Ruleset-owned move definition (new or changed)."""

    name: str
    chrooked_id: str
    type: str
    category: str
    power: Optional[int] = None
    accuracy: Optional[int] = None
    pp: Optional[int] = None
    description: str = ""
    aka: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AbilityDef:
    """A Ruleset-owned ability definition (new or changed)."""

    name: str
    chrooked_id: str
    description: str = ""
    aka: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TypeChartOverride:
    """One attacker/defender effectiveness multiplier override."""

    attacker: str
    defender: str
    multiplier: float
