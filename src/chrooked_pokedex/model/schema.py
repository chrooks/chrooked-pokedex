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

# The neutral primary effect of a plain damaging move — `MoveDef.effect` defaults to
# this. Named so callers can test "is this just damage?" without a magic literal.
DEFAULT_EFFECT: str = "hit"

# Neutral move flags the Ruleset models. Several abilities key off these (e.g.
# Infernal Maw boosts `biting` moves), so a dropped flag silently breaks a mechanic —
# the loader validates against this closed set rather than letting a typo through.
MOVE_FLAGS: frozenset[str] = frozenset({
    "contact", "punching", "biting", "sound", "slicing", "wind",
    "wing", "kicking", "piercing", "bone", "hammer", "ballistic",
    "pulse", "high_crit",
})

# Neutral move targets the Ruleset models — the union of pokeemerald's neutralized
# `MOVE_TARGET_*` symbols (per the committed base snapshot) and the Essentials
# `_TARGET` keys (appliers/essentials/vocab.py). A target with no closed vocabulary
# silently degrades to a single-target default at apply time, so the loader
# validates against this set rather than letting a typo through.
MOVE_TARGETS: frozenset[str] = frozenset({
    "selected", "user", "ally", "both", "foes_and_ally", "opponent",
    "opponents_field", "users_field", "entire_field", "all_battlers",
    "random", "depends",
})


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
    # Design metadata, not game data: coverage types that fit what the creature
    # IS (Goodra-Hisui the slug → Water, Poison) — never weakness-patching.
    # Confirmed once in the makeover lore step; the learnset slot skeleton reads
    # it to build flavor ladders. Appliers ignore it.
    flavor_types: Optional[tuple[str, ...]] = None


@dataclass(frozen=True)
class AdditionalEffect:
    """One secondary effect a move may apply, with its percent chance.

    `effect` is a neutral name (`burn`, `flinch`, `sp_atk_minus_1`); `chance` is the
    percent it triggers (100 for a guaranteed effect).
    """

    effect: str
    chance: int


@dataclass(frozen=True)
class MoveDef:
    """A Ruleset-owned move definition (new or changed).

    Beyond the headline numbers, a move carries the data that makes it *behave*:
    its primary `effect` (usually `hit`), an optional `argument` for parameterized
    effects (e.g. `super_effective_on_arg` against a type), the `additional_effects`
    it may apply (burn, flinch, stat drops), engine-neutral `flags` (contact, biting,
    punching — which abilities key off), `priority`, and `target`. Dropping these
    creates an inert move: right numbers, no secondary effect, no flags.
    """

    name: str
    chrooked_id: str
    type: str
    category: str
    # Dual-damage-type move (Flying Press): damage counts BOTH types. Only
    # engines with native support (Rejuv :secondtype) can express it.
    second_type: Optional[str] = None
    power: Optional[int] = None
    accuracy: Optional[int] = None
    pp: Optional[int] = None
    description: str = ""
    aka: Mapping[str, object] = field(default_factory=dict)
    effect: str = DEFAULT_EFFECT
    argument: Optional[Mapping[str, object]] = None
    additional_effects: tuple[AdditionalEffect, ...] = ()
    flags: tuple[str, ...] = ()
    priority: int = 0
    target: str = "selected"


@dataclass(frozen=True)
class AbilityDef:
    """A Ruleset-owned ability definition (new or changed).

    This is data only. An ability's *mechanic* lives in a separate, human-owned
    BehaviorSpec under `ruleset/behaviors/`, not here.
    """

    name: str
    chrooked_id: str
    description: str = ""
    aka: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class StatusDef:
    """A Ruleset-owned status condition (burn, frostbite, paralysis, ...).

    Statuses are owned outright, not Overrides: the base snapshot has no status
    data to diff against, because the concept does not exist upstream. `aka` maps
    an engine to the symbol that engine already uses — `{rejuv: FROZEN}` is how a
    reskin is recorded, where the engine keeps its old symbol and only the
    behavior and player-facing text change.

    Data only. The mechanic lives in a BehaviorSpec under `ruleset/behaviors/`.
    """

    name: str
    chrooked_id: str
    description: str = ""
    effects: tuple[str, ...] = ()
    aka: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TypeChartOverride:
    """One attacker/defender effectiveness multiplier override."""

    attacker: str
    defender: str
    multiplier: float
