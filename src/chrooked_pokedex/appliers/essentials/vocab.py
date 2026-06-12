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

# Neutral move flag -> Essentials flag. Only the flags with a real, standard
# Essentials counterpart are listed; the rest (wing, kicking, piercing, bone,
# hammer, ballistic) have no stable equivalent and resolve to None.
_FLAG = {
    "contact": "Contact",
    "punching": "Punching",
    "biting": "Biting",
    "sound": "Sound",
    "slicing": "Slicing",
    "wind": "Wind",
}

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
}

# Neutral secondary effect -> Essentials FunctionCode for a damaging move that
# also applies that effect. Kept to the confidently-correct status effects; an
# unknown effect resolves to None.
_ADDITIONAL_FUNCTION_CODE = {
    "burn": "BurnTarget",
    "poison": "PoisonTarget",
    "paralysis": "ParalyzeTarget",
    "flinch": "FlinchTarget",
    "freeze": "FreezeTarget",
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
