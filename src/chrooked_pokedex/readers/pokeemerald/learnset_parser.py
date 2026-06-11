from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LearnsetEntry:
    move: str
    level: int


_LEARNSET_ARRAY_PATTERN = re.compile(
    r"static\s+const\s+(?:struct\s+LevelUpMove|u16)\s+"
    r"(s\w+LevelUpLearnset)\s*\[\s*\]\s*=\s*\{",
)

_MOVE_ENTRY_PATTERN = re.compile(
    r"LEVEL_UP_MOVE\(\s*(\d+)\s*,\s*(MOVE_\w+)\s*\)",
)

_LEARNSET_END_PATTERN = re.compile(r"LEVEL_UP_END\b")

_POINTER_TABLE_ENTRY = re.compile(
    r"\[\s*(SPECIES_\w+)\s*\]\s*=\s*(s\w+LevelUpLearnset)\s*,",
)

_SPECIES_INFO_LEARNSET_REF = re.compile(
    r"\[\s*(SPECIES_\w+)\s*\]\s*=",
)

_LEARNSET_FIELD_REF = re.compile(
    r"\.levelUpLearnset\s*=\s*(s\w+LevelUpLearnset)\s*,",
)


def parse_learnsets(repo_path: Path) -> dict[str, list[LearnsetEntry]]:
    learnset_files = _find_learnset_files(repo_path)
    variable_learnsets = _parse_learnset_arrays(learnset_files)
    species_to_variable = _build_species_to_variable_map(repo_path)

    result: dict[str, list[LearnsetEntry]] = {}
    for species, variable_name in species_to_variable.items():
        if variable_name in variable_learnsets:
            result[species] = variable_learnsets[variable_name]

    return result


def _find_learnset_files(repo_path: Path) -> list[Path]:
    pokemon_dir = repo_path / "src" / "data" / "pokemon"
    paths: list[Path] = []

    flat = pokemon_dir / "level_up_learnsets.h"
    if flat.exists():
        paths.append(flat)

    split_dir = pokemon_dir / "level_up_learnsets"
    if split_dir.exists():
        paths.extend(sorted(split_dir.glob("*.h")))

    return paths


def _parse_learnset_arrays(
    files: list[Path],
) -> dict[str, list[LearnsetEntry]]:
    result: dict[str, list[LearnsetEntry]] = {}

    for path in files:
        text = path.read_text(encoding="utf-8")
        for match in _LEARNSET_ARRAY_PATTERN.finditer(text):
            variable_name = match.group(1)
            array_start = match.end()

            entries: list[LearnsetEntry] = []
            pos = array_start
            while pos < len(text):
                end_match = _LEARNSET_END_PATTERN.search(text, pos)
                move_match = _MOVE_ENTRY_PATTERN.search(text, pos)

                if end_match and (not move_match or end_match.start() < move_match.start()):
                    break

                if not move_match:
                    break

                level = int(move_match.group(1))
                move = move_match.group(2)
                entries.append(LearnsetEntry(move=move, level=level))
                pos = move_match.end()

            result[variable_name] = entries

    return result


def _build_species_to_variable_map(repo_path: Path) -> dict[str, str]:
    pokemon_dir = repo_path / "src" / "data" / "pokemon"

    pointer_table = pokemon_dir / "level_up_learnset_pointers.h"
    if pointer_table.exists():
        return _parse_pointer_table(pointer_table)

    return _parse_species_info_learnset_refs(repo_path)


def _parse_pointer_table(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    result: dict[str, str] = {}
    for match in _POINTER_TABLE_ENTRY.finditer(text):
        species = match.group(1)
        variable = match.group(2)
        if species != "SPECIES_NONE":
            result[species] = variable
    return result


def _parse_species_info_learnset_refs(repo_path: Path) -> dict[str, str]:
    pokemon_dir = repo_path / "src" / "data" / "pokemon"
    result: dict[str, str] = {}

    species_info_paths: list[Path] = []
    flat = pokemon_dir / "species_info.h"
    if flat.exists():
        species_info_paths.append(flat)
    split_dir = pokemon_dir / "species_info"
    if split_dir.exists():
        species_info_paths.extend(sorted(split_dir.glob("*.h")))

    for path in species_info_paths:
        text = path.read_text(encoding="utf-8")
        current_species: str | None = None

        for line in text.splitlines():
            species_match = _SPECIES_INFO_LEARNSET_REF.search(line)
            if species_match:
                current_species = species_match.group(1)
                continue

            if current_species:
                ref_match = _LEARNSET_FIELD_REF.search(line)
                if ref_match:
                    result[current_species] = ref_match.group(1)
                    current_species = None

    return result
