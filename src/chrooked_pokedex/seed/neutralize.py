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


# pokeemerald flavor text uses backslash control codes (\n new line, \l scroll,
# \p new paragraph) for textbox layout. The GBA charmap has no glyph for a literal
# backslash, so any backslash that survives into an emitted C string breaks the
# build's charmap preprocessor. Descriptions are flavor text, so we flatten these
# control codes to a single space when a value enters the Ruleset.
_CONTROL_ESCAPE = re.compile(r"\\[nlp]")
_STRAY_BACKSLASH = re.compile(r"\\")


def normalize_description(text: str) -> str:
    """Flatten textbox control codes and drop stray backslashes from flavor text."""
    text = _CONTROL_ESCAPE.sub(" ", text)
    text = _STRAY_BACKSLASH.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def type_name(constant: str) -> str:
    return type_constant_to_name(constant)


# --- Move behavior fields: neutral <-> engine token translation ----------------
#
# Primary effects, secondary (additional) effects, and targets neutralize
# generically by stripping the engine prefix and lowercasing — a clean bijection
# that covers every value, not just the ones seen so far. Move flags are the one
# exception: they are camelCase booleans (`makesContact`, `bitingMove`), so they
# need an explicit map. Keeping these here means the seed (engine -> neutral) and
# the applier (neutral -> engine) share one source of truth.

# camelCase C flag <-> neutral name.
MOVE_FLAG_TO_NEUTRAL: dict[str, str] = {
    "makesContact": "contact",
    "punchingMove": "punching",
    "bitingMove": "biting",
    "soundMove": "sound",
    "slicingMove": "slicing",
    "windMove": "wind",
    "wingMove": "wing",
    "kickingMove": "kicking",
    "piercingMove": "piercing",
    "boneMove": "bone",
    "hammerMove": "hammer",
    "ballisticMove": "ballistic",
}
NEUTRAL_TO_MOVE_FLAG: dict[str, str] = {v: k for k, v in MOVE_FLAG_TO_NEUTRAL.items()}


def primary_effect_name(token: str) -> str:
    """`EFFECT_SUPER_EFFECTIVE_ON_ARG` -> `super_effective_on_arg`."""
    return token.removeprefix("EFFECT_").lower()


def primary_effect_symbol(name: str) -> str:
    return "EFFECT_" + _c_identifier(name)


def move_effect_name(token: str) -> str:
    """`MOVE_EFFECT_BURN` -> `burn`."""
    return token.removeprefix("MOVE_EFFECT_").lower()


def move_effect_symbol(name: str) -> str:
    return "MOVE_EFFECT_" + _c_identifier(name)


def move_target_name(token: str) -> str:
    """`MOVE_TARGET_BOTH` -> `both`."""
    return token.removeprefix("MOVE_TARGET_").lower()


def move_target_symbol(name: str) -> str:
    return "MOVE_TARGET_" + _c_identifier(name)


def _c_identifier(name: str) -> str:
    """A neutral id as a C symbol chunk: `u-turn` -> `U_TURN` (hyphens and spaces
    are legal in neutral names but never in a C identifier)."""
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


def move_flag_name(token: str) -> str | None:
    return MOVE_FLAG_TO_NEUTRAL.get(token)


def move_flag_symbol(name: str) -> str | None:
    return NEUTRAL_TO_MOVE_FLAG.get(name)


def _camel_to_snake(text: str) -> str:
    return re.sub(r"([A-Z])", r"_\1", text).lower()


def snake_to_camel(text: str) -> str:
    head, *tail = text.split("_")
    return head + "".join(part.capitalize() for part in tail)


def neutralize_argument(inner: str) -> dict[str, object]:
    """`.type = TYPE_DRAGON` -> {'type': 'Dragon'}; `.absorbPercentage = 50` ->
    {'absorb_percentage': 50}. The inner text is the body between the argument's
    braces. Type values become plain type names; integers stay integers."""
    result: dict[str, object] = {}
    for field, raw in re.findall(r"\.(\w+)\s*=\s*([^,}]+)", inner):
        value = raw.strip()
        if _TYPE_TOKEN.fullmatch(value):
            result[_camel_to_snake(field)] = type_name(value)
        elif re.fullmatch(r"-?\d+", value):
            result[_camel_to_snake(field)] = int(value)
        else:
            result[_camel_to_snake(field)] = value
    return result


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


def item_name(constant: str) -> str:
    """`ITEM_LEAF_STONE` -> `Leaf Stone`."""
    return constant.removeprefix("ITEM_").replace("_", " ").title()


def item_symbol(name: str) -> str:
    """`Leaf Stone` -> `ITEM_LEAF_STONE` (round-trips standard items)."""
    return "ITEM_" + name.strip().upper().replace(" ", "_")


def move_symbol(name: str) -> str:
    """`Dragon Breath` -> `MOVE_DRAGON_BREATH` (mirror of item_symbol for the
    pokeemerald `knows_move` evolution param)."""
    return "MOVE_" + name.strip().upper().replace(" ", "_")


def neutralize_evolution_method(method_token: str, param: str) -> dict:
    """Turn a pokeemerald (EVO_*, param) pair into a neutral method dict.

    The two clean, common methods become plain keys; everything else is kept as a
    faithful passthrough (`pokeemerald` + `param`) so it round-trips exactly even
    though there are ~40 engine-specific methods we do not model individually.
    """
    if method_token == "EVO_LEVEL" and param.isdigit():
        return {"level": int(param)}
    if method_token == "EVO_ITEM" and param.startswith("ITEM_"):
        return {"item": item_name(param)}
    return {"pokeemerald": method_token, "param": param}
