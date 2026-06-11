from __future__ import annotations

import re
from pathlib import Path

_DEFINE_ABILITY = re.compile(
    r"^#define\s+(ABILITY_\w+)\s+(\d+)",
    re.MULTILINE,
)

_ENUM_ENTRY = re.compile(
    r"(ABILITY_\w+)\s*(?:=\s*(\d+))?\s*[,}]",
)

# --- Ability text patterns ---

# Chrooked: gAbilityNames array — [ABILITY_X] = _("Name")
_NAME_ARRAY_ENTRY = re.compile(
    r"\[(ABILITY_\w+)\]\s*=\s*_\(\"([^\"]+)\"\)",
)

# Chrooked: description constants — static const u8 sXDescription[] = _("...");
_DESCRIPTION_CONST = re.compile(
    r"static\s+const\s+u8\s+s(\w+)Description\[\]\s*=\s*_\(\"([^\"]+)\"\)",
)

# Chrooked: description pointer table — [ABILITY_X] = sXDescription
_DESCRIPTION_POINTER = re.compile(
    r"\[(ABILITY_\w+)\]\s*=\s*s(\w+)Description",
)

# Pokeemerald: struct entry — [ABILITY_X] = { .name = _("X"), .description = COMPOUND_STRING("...") }
_STRUCT_ABILITY_ENTRY = re.compile(
    r"\[(ABILITY_\w+)\]\s*=",
)
_STRUCT_NAME = re.compile(r'\.name\s*=\s*_\("([^"]+)"\)')
_STRUCT_DESCRIPTION = re.compile(r'\.description\s*=\s*COMPOUND_STRING\("([^"]+)"\)')

_SKIP_PREFIXES = ("ABILITIES_COUNT",)
_SKIP_CONSTANTS = {"ABILITY_NONE"}


def _should_skip(name: str) -> bool:
    if name in _SKIP_CONSTANTS:
        return True
    return name.startswith(_SKIP_PREFIXES)


def parse_ability_constants(repo_path: Path) -> dict[str, int]:
    abilities_path = repo_path / "include" / "constants" / "abilities.h"
    if not abilities_path.exists():
        return {}

    text = abilities_path.read_text(encoding="utf-8")
    result: dict[str, int] = {}

    # Try #define format first
    for match in _DEFINE_ABILITY.finditer(text):
        name = match.group(1)
        if _should_skip(name):
            continue
        result[name] = int(match.group(2))

    if result:
        return result

    # Fall back to enum format
    counter = 0
    for match in _ENUM_ENTRY.finditer(text):
        name = match.group(1)
        if match.group(2) is not None:
            counter = int(match.group(2))
        if not _should_skip(name):
            result[name] = counter
        counter += 1

    return result


def parse_ability_text(repo_path: Path) -> dict[str, tuple[str, str]]:
    """Return {ABILITY_X: (name, description)} from either format."""
    # Try Pokeemerald struct format: src/data/abilities.h
    struct_path = repo_path / "src" / "data" / "abilities.h"
    if struct_path.exists():
        return _parse_struct_ability_text(struct_path)

    # Try Chrooked separate arrays: src/data/text/abilities.h
    text_path = repo_path / "src" / "data" / "text" / "abilities.h"
    if text_path.exists():
        return _parse_separate_ability_text(text_path)

    return {}


def _parse_struct_ability_text(path: Path) -> dict[str, tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    result: dict[str, tuple[str, str]] = {}

    current_ability: str | None = None
    current_name: str | None = None
    current_desc: str | None = None

    for line in text.splitlines():
        entry_match = _STRUCT_ABILITY_ENTRY.search(line)
        if entry_match:
            if current_ability and current_name and current_desc:
                result[current_ability] = (current_name, current_desc)
            current_ability = entry_match.group(1)
            current_name = None
            current_desc = None

        if current_ability:
            name_match = _STRUCT_NAME.search(line)
            if name_match:
                current_name = name_match.group(1)
            desc_match = _STRUCT_DESCRIPTION.search(line)
            if desc_match:
                current_desc = desc_match.group(1)

    if current_ability and current_name and current_desc:
        result[current_ability] = (current_name, current_desc)

    result.pop("ABILITY_NONE", None)
    return result


def _parse_separate_ability_text(path: Path) -> dict[str, tuple[str, str]]:
    text = path.read_text(encoding="utf-8")

    # Parse name array
    names: dict[str, str] = {}
    for match in _NAME_ARRAY_ENTRY.finditer(text):
        ability = match.group(1)
        if ability != "ABILITY_NONE":
            names[ability] = match.group(2)

    # Parse description constants
    desc_by_label: dict[str, str] = {}
    for match in _DESCRIPTION_CONST.finditer(text):
        desc_by_label[match.group(1)] = match.group(2)

    # Parse pointer table to map ABILITY_X → description label
    descriptions: dict[str, str] = {}
    for match in _DESCRIPTION_POINTER.finditer(text):
        ability = match.group(1)
        label = match.group(2)
        if ability != "ABILITY_NONE" and label in desc_by_label:
            descriptions[ability] = desc_by_label[label]

    result: dict[str, tuple[str, str]] = {}
    for ability in names:
        if ability in descriptions:
            result[ability] = (names[ability], descriptions[ability])

    return result


_CASE_ABILITY = re.compile(r"^\s*case\s+(ABILITY_\w+)\s*:", re.MULTILINE)

_BATTLE_LOGIC_FILES = (
    "src/battle_util.c",
)


def find_ability_battle_logic(
    repo_path: Path, ability_constant: str,
) -> tuple[str, int] | None:
    """Find where an ability's battle logic is implemented.

    Returns (relative_file_path, line_count) or None if not found.
    """
    for rel_path in _BATTLE_LOGIC_FILES:
        full_path = repo_path / rel_path
        if not full_path.exists():
            continue

        lines = full_path.read_text(encoding="utf-8").splitlines()
        block_lines = _count_case_block_lines(lines, ability_constant)
        if block_lines is not None:
            return (rel_path, block_lines)

    return None


def _count_case_block_lines(lines: list[str], ability_constant: str) -> int | None:
    """Count lines in a case block for the given ability constant.

    Tracks brace depth so nested if/for blocks don't end the count early.
    Returns partial count if file ends while still in block.
    """
    in_block = False
    count = 0
    depth = 0

    for line in lines:
        if in_block:
            stripped = line.strip()
            if stripped.startswith("case ") and depth == 0:
                return count
            depth += line.count("{") - line.count("}")
            if depth < 0:
                return count
            count += 1
        elif f"case {ability_constant}:" in line:
            in_block = True
            count = 1
            depth = line.count("{") - line.count("}")

    return count if in_block else None


_SPECIES_HEADER = re.compile(r"\[\s*(SPECIES_\w+)\s*\]\s*=")
_ABILITIES_FIELD = re.compile(r"\.abilities\s*=\s*\{([^}]+)\}")


def find_ability_species(
    repo_path: Path, ability_constant: str,
) -> tuple[str, ...]:
    """Find all species that reference the given ability in species_info."""
    pokemon_dir = repo_path / "src" / "data" / "pokemon"

    paths: list[Path] = []
    flat = pokemon_dir / "species_info.h"
    if flat.exists():
        paths.append(flat)
    split_dir = pokemon_dir / "species_info"
    if split_dir.exists():
        paths.extend(sorted(split_dir.glob("*.h")))

    result: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        current_species: str | None = None

        for line in text.splitlines():
            species_match = _SPECIES_HEADER.search(line)
            if species_match:
                current_species = species_match.group(1)

            if current_species:
                abilities_match = _ABILITIES_FIELD.search(line)
                if abilities_match:
                    abilities_text = abilities_match.group(1)
                    if ability_constant in abilities_text:
                        result.append(current_species)

    return tuple(sorted(set(result)))
