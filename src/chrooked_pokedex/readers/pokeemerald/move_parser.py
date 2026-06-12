from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MoveInfo:
    constant: str
    name: str
    type: str
    category: str
    power: int | None
    accuracy: int | None
    pp: int | None
    description: str
    effect: str = "EFFECT_HIT"          # raw engine token
    argument: str | None = None         # raw inner text of `.argument = { ... }`
    additional_effects: tuple[tuple[str, int], ...] = ()  # (MOVE_EFFECT_* token, chance)
    flags: tuple[str, ...] = ()          # raw camelCase flag names set TRUE
    priority: int = 0
    target: str = "MOVE_TARGET_SELECTED"  # raw engine token


_MOVE_ENTRY = re.compile(r"\[\s*(MOVE_\w+)\s*\]\s*=\s*\{")

_FIELD_NAME = re.compile(r'\.name\s*=\s*COMPOUND_STRING\("([^"]+)"\)')
_FIELD_TYPE = re.compile(r"\.type\s*=\s*(TYPE_\w+)")
_FIELD_CATEGORY = re.compile(r"\.category\s*=\s*(DAMAGE_CATEGORY_\w+)")
_FIELD_POWER = re.compile(r"\.power\s*=\s*(\d+)")
_FIELD_ACCURACY = re.compile(r"\.accuracy\s*=\s*(\d+)")
_FIELD_PP = re.compile(r"\.pp\s*=\s*(\d+)")
_FIELD_DESC = re.compile(r'\.description\s*=\s*(?:COMPOUND_STRING|s\w+Description)\s*\(\s*"(.+?)"\s*\)', re.DOTALL)
_FIELD_EFFECT = re.compile(r"\.effect\s*=\s*(EFFECT_\w+)")
_FIELD_PRIORITY = re.compile(r"\.priority\s*=\s*(-?\d+)")
_FIELD_TARGET = re.compile(r"\.target\s*=\s*(MOVE_TARGET_\w+)")
_FIELD_ARGUMENT = re.compile(r"\.argument\s*=\s*\{([^}]*)\}")
# Balance one level of nested parens so a macro chance like PERCENT(10) inside the
# block does not truncate the capture at the first ')'.
_FIELD_ADDL = re.compile(
    r"\.additionalEffects\s*=\s*ADDITIONAL_EFFECTS\(((?:[^()]|\([^()]*\))*)\)", re.DOTALL
)
_ADDL_ENTRY = re.compile(r"\.moveEffect\s*=\s*(MOVE_EFFECT_\w+).*?\.chance\s*=\s*(\d+)", re.DOTALL)
# Boolean flag fields the Ruleset models (abilities key off several of these).
_FLAG_FIELDS = (
    "makesContact", "punchingMove", "bitingMove", "soundMove", "slicingMove",
    "windMove", "wingMove", "kickingMove", "piercingMove", "boneMove",
    "hammerMove", "ballisticMove",
)

_SKIP_MOVES = {"MOVE_NONE", "MOVE_COUNT", "MOVE_UNAVAILABLE"}


def _parse_flags(body: str) -> tuple[str, ...]:
    return tuple(
        flag for flag in _FLAG_FIELDS
        if re.search(r"\." + flag + r"\s*=\s*TRUE", body)
    )


def _parse_additional_effects(body: str) -> tuple[tuple[str, int], ...]:
    block = _FIELD_ADDL.search(body)
    if not block:
        return ()
    return tuple(
        (effect, int(chance)) for effect, chance in _ADDL_ENTRY.findall(block.group(1))
    )


def parse_moves(repo_path: Path) -> dict[str, MoveInfo]:
    moves_path = repo_path / "src" / "data" / "moves_info.h"
    if not moves_path.exists():
        return {}

    text = moves_path.read_text(encoding="utf-8")
    result: dict[str, MoveInfo] = {}

    entries = list(_MOVE_ENTRY.finditer(text))

    for i, entry_match in enumerate(entries):
        constant = entry_match.group(1)
        if constant in _SKIP_MOVES:
            continue

        start = entry_match.end()
        end = entries[i + 1].start() if i + 1 < len(entries) else len(text)
        body = text[start:end]

        name_m = _FIELD_NAME.search(body)
        type_m = _FIELD_TYPE.search(body)
        cat_m = _FIELD_CATEGORY.search(body)
        power_m = _FIELD_POWER.search(body)
        acc_m = _FIELD_ACCURACY.search(body)
        pp_m = _FIELD_PP.search(body)
        desc_m = _FIELD_DESC.search(body)

        if not name_m:
            continue

        description = ""
        if desc_m:
            description = desc_m.group(1)
            description = re.sub(r'"\s*"', "", description)
            description = description.replace("\\n", " ").replace("\n", " ")
            description = re.sub(r"\s+", " ", description).strip()

        effect_m = _FIELD_EFFECT.search(body)
        priority_m = _FIELD_PRIORITY.search(body)
        target_m = _FIELD_TARGET.search(body)
        argument_m = _FIELD_ARGUMENT.search(body)

        result[constant] = MoveInfo(
            constant=constant,
            name=name_m.group(1),
            type=type_m.group(1) if type_m else "",
            category=cat_m.group(1).removeprefix("DAMAGE_CATEGORY_") if cat_m else "",
            power=int(power_m.group(1)) if power_m else None,
            accuracy=int(acc_m.group(1)) if acc_m else None,
            pp=int(pp_m.group(1)) if pp_m else None,
            description=description,
            effect=effect_m.group(1) if effect_m else "EFFECT_HIT",
            argument=argument_m.group(1).strip() if argument_m else None,
            additional_effects=_parse_additional_effects(body),
            flags=_parse_flags(body),
            priority=int(priority_m.group(1)) if priority_m else 0,
            target=target_m.group(1) if target_m else "MOVE_TARGET_SELECTED",
        )

    return result
