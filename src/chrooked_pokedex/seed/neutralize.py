"""Turn engine-specific C symbols into the Ruleset's plain neutral names.

The seed reads pokeemerald C (symbols like `TYPE_WATER`, `ABILITY_POISON_HEAL`,
`MOVE_DRAGON_BREATH`) and must emit plain names (`Water`, `Poison Heal`,
`Dragon Breath`). These helpers do that translation and mint `chrooked_id`
slugs.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..readers.pokeemerald.ability_parser import parse_ability_text
from ..readers.pokeemerald.move_parser import parse_moves
from ..readers.pokeemerald.type_chart_parser import type_constant_to_name

# Base-stat C field name -> neutral stat key.
STAT_FIELD_TO_KEY: dict[str, str] = {
    "baseHP": "hp",
    "baseAttack": "atk",
    "baseDefense": "def",
    "baseSpAttack": "spa",
    "baseSpDefense": "spd",
    "baseSpeed": "spe",
}

_TYPE_TOKEN = re.compile(r"TYPE_\w+")
_ABILITY_TOKEN = re.compile(r"ABILITY_\w+")
_MOVE_TOKEN = re.compile(r"MOVE_\w+")


def slug(name: str) -> str:
    """Mint a `chrooked_id`: lowercase, strip everything but a-z0-9."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def type_name(constant: str) -> str:
    return type_constant_to_name(constant)


def extract_types(field_value: str | None) -> tuple[str, ...]:
    """`MON_TYPES(TYPE_FIRE, TYPE_FLYING)` -> ('Fire', 'Flying').

    A mono-type written as a duplicate (`{TYPE_X, TYPE_X}`) collapses to one.
    """
    if not field_value:
        return ()
    constants = _TYPE_TOKEN.findall(field_value)
    names = [type_name(c) for c in constants]
    if len(names) == 2 and names[0] == names[1]:
        return (names[0],)
    return tuple(names)


def extract_ability_constants(field_value: str | None) -> tuple[str, ...]:
    """`{ABILITY_BLAZE, ABILITY_NONE, ABILITY_SOLAR_POWER}` -> the three tokens."""
    if not field_value:
        return ()
    return tuple(_ABILITY_TOKEN.findall(field_value))


def build_ability_name_map(repo: Path) -> dict[str, str]:
    """{ABILITY_X: display name} from a repo's ability text."""
    return {const: name for const, (name, _desc) in parse_ability_text(repo).items()}


def build_move_name_map(repo: Path) -> dict[str, str]:
    """{MOVE_X: display name} from a repo's move table."""
    return {const: info.name for const, info in parse_moves(repo).items()}


def move_name(constant: str, move_names: dict[str, str]) -> str:
    """Resolve MOVE_X to a display name, falling back to a title-cased token."""
    if constant in move_names:
        return move_names[constant]
    return constant.removeprefix("MOVE_").replace("_", " ").title()


def ability_name(constant: str, ability_names: dict[str, str]) -> str:
    if constant in ability_names:
        return ability_names[constant]
    return constant.removeprefix("ABILITY_").replace("_", " ").title()


def species_display_name(constant: str) -> str:
    """`SPECIES_MR_MIME` -> `Mr Mime`. Deterministic; aka keeps the exact symbol."""
    return constant.removeprefix("SPECIES_").replace("_", " ").title()
