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


_MOVE_ENTRY = re.compile(r"\[\s*(MOVE_\w+)\s*\]\s*=\s*\{")

_FIELD_NAME = re.compile(r'\.name\s*=\s*COMPOUND_STRING\("([^"]+)"\)')
_FIELD_TYPE = re.compile(r"\.type\s*=\s*(TYPE_\w+)")
_FIELD_CATEGORY = re.compile(r"\.category\s*=\s*(DAMAGE_CATEGORY_\w+)")
_FIELD_POWER = re.compile(r"\.power\s*=\s*(\d+)")
_FIELD_ACCURACY = re.compile(r"\.accuracy\s*=\s*(\d+)")
_FIELD_PP = re.compile(r"\.pp\s*=\s*(\d+)")
_FIELD_DESC = re.compile(r'\.description\s*=\s*(?:COMPOUND_STRING|s\w+Description)\s*\(\s*"(.+?)"\s*\)', re.DOTALL)

_SKIP_MOVES = {"MOVE_NONE", "MOVE_COUNT", "MOVE_UNAVAILABLE"}


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

        result[constant] = MoveInfo(
            constant=constant,
            name=name_m.group(1),
            type=type_m.group(1) if type_m else "",
            category=cat_m.group(1).removeprefix("DAMAGE_CATEGORY_") if cat_m else "",
            power=int(power_m.group(1)) if power_m else None,
            accuracy=int(acc_m.group(1)) if acc_m else None,
            pp=int(pp_m.group(1)) if pp_m else None,
            description=description,
        )

    return result
