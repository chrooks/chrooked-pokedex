"""Translate the Ruleset's neutral move/type vocabulary into Essentials spellings.

The Ruleset speaks in neutral names (`Water`, `physical`, `contact`, `burn`).
Essentials uses its own: INTERNAL type names (`WATER`), capitalized categories
(`Physical`), CamelCase flags (`Contact`), and `FunctionCode` strings
(`BurnTarget`).

Every helper that might not have a faithful Essentials equivalent returns None
rather than inventing one — an Honest Signifier. The Applier turns a None into an
unresolved note in the Apply Report instead of writing a token Essentials would
reject at load.
"""

from __future__ import annotations

import re
from typing import Optional

# The Essentials FunctionCode literal for "no scripted effect, just deal damage".
# It is the string "None", not Python None — a plain damaging move carries it.
NO_FUNCTION_CODE = "None"

_CATEGORY = {"physical": "Physical", "special": "Special", "status": "Status"}

# Neutral move flag -> Essentials flag. Most entries are standard Essentials flags.
# Kicking, Hammer, Piercing and Wing are not: they are custom flags, written because
# ported mechanics read them (striker, martialartist, sledgehammer, hammerfist,
# impale; mjolnir NV-7; updraft, NV-9). Essentials keeps a move's Flags as free
# strings ("*s" in the PBS schema) and only tests the ones it knows, so a game
# without those ports simply ignores them. Ballistic is Essentials' own Bomb (True
# Shot, NV-25; every Ruleset move Nova marks Bomb is ballistic in the Ruleset, so
# reconciling it only adds the flag). Bone is custom too (Bone Breaker, NV-30).
_FLAG = {
    "contact": "Contact",
    "punching": "Punching",
    "biting": "Biting",
    "sound": "Sound",
    "slicing": "Slicing",
    "wind": "Wind",
    "pulse": "Pulse",
    "high_crit": "HighCriticalHitRate",
    "kicking": "Kicking",
    "hammer": "Hammer",
    "piercing": "Piercing",
    "wing": "Wing",
    "ballistic": "Bomb",
    "bone": "Bone",
}

# The Essentials flag names the Ruleset models. When move_apply reconciles an
# existing move's Flags line it touches only these, leaving the engine's own
# unmodeled flags (CanProtect, CanMirrorMove, HighCriticalHitRate, …) intact.
MODELED_FLAG_NAMES: frozenset[str] = frozenset(_FLAG.values())

# Neutral PRIMARY effect -> Essentials FunctionCode. These are standard moves whose
# mechanic exists natively in both engines under different names, so they port as
# data. Names are taken from Maruno17's PBS. An effect with no native Essentials
# equivalent (e.g. super_effective_on_arg) is deliberately absent -> resolves to None
# and is carried by a behavior spec instead.
_PRIMARY_FUNCTION_CODE = {
    "multi_hit": "HitTwoToFiveTimes",
    "ohko": "OHKO",
    "confuse": "ConfuseTarget",
    "triple_kick": "HitThreeTimesPowersUpWithEachHit",
    "low_kick": "PowerHigherWithTargetWeight",
    "heat_crash": "PowerHigherWithUserHeavierThanTarget",
    "brick_break": "RemoveScreens",
    "recoil_if_miss": "CrashDamageIfFailsUnusableInGravity",
    "first_turn_only": "FlinchTargetFailsIfNotUserFirstTurn",
    "u-turn": "SwitchOutUserDamagingMove",
}

# Neutral secondary effect -> Essentials FunctionCode for a damaging move that
# also applies that effect. Kept to the confidently-correct status effects; an
# unknown effect resolves to None.
_ADDITIONAL_FUNCTION_CODE = {
    "burn": "BurnTarget",
    "poison": "PoisonTarget",
    "paralysis": "ParalyzeTarget",
    "flinch": "FlinchTarget",
    "frostbite": "FreezeTarget",
    "confusion": "ConfuseTarget",
}

# Neutral move target -> Essentials Target. Defaults to NearOther (standard single
# target) for anything unmapped, which is the right default for invented moves.
_TARGET = {
    "selected": "NearOther",
    "user": "User",
    "both": "AllNearFoes",
    "foes_and_ally": "AllNearOthers",
    "opponents_field": "FoeSide",
    "users_field": "UserSide",
    "entire_field": "BothSides",
    "all_battlers": "AllBattlers",
}

# Neutral weather -> the Essentials 21 battle weathers that count as it, for ported
# mechanics that test `battler.effectiveWeather` (which already drops sun and rain
# for a Utility Umbrella holder). The first entry is what a lab self-test sets.
# Hail includes :Snowstorm because Nova registers that weather and treats it as hail
# everywhere ([:Hail, :Snowstorm].include?(effectiveWeather)); in a game without
# it the extra symbol never matches.
_WEATHER = {
    "rain": ("Rain", "HeavyRain"),
    "sun": ("Sun", "HarshSun"),
    "sand": ("Sandstorm",),
    "hail": ("Hail", "Snowstorm"),
}

# Neutral terrain -> the Essentials 21 field terrain (`battle.field.terrain`).
_TERRAIN = {"grassy": "Grassy", "electric": "Electric", "psychic": "Psychic", "misty": "Misty"}


def internal_name(name: str) -> str:
    """A display name as an Essentials INTERNAL name: `Mr Mime` -> `MRMIME`,
    `Poison Heal` -> `POISONHEAL`. Used to construct symbols absent an `aka` hint."""
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def type_internal(name: str) -> str:
    return internal_name(name)


def category(neutral: str) -> str:
    return _CATEGORY.get(neutral, "Physical")


def flag(neutral: str) -> Optional[str]:
    return _FLAG.get(neutral)


def weathers(neutral: str) -> Optional[tuple[str, ...]]:
    return _WEATHER.get(neutral)


def terrain(neutral: str) -> Optional[str]:
    return _TERRAIN.get(neutral)


def function_code(primary_effect: str) -> Optional[str]:
    """A plain `hit` is `FunctionCode = None`; a standard effect maps to its named
    Essentials FunctionCode; a scripted/parameterized effect with no native
    equivalent returns None so the caller marks it unresolved (a behavior spec
    carries it instead)."""
    if primary_effect == "hit":
        return NO_FUNCTION_CODE
    return _PRIMARY_FUNCTION_CODE.get(primary_effect)


def additional_function_code(effect: str) -> Optional[str]:
    return _ADDITIONAL_FUNCTION_CODE.get(effect)


def target(neutral: str) -> str:
    return _TARGET.get(neutral, "NearOther")
