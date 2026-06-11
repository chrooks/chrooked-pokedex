from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvolutionEntry:
    method: str
    param: str
    target_species: str


_TABLE_SPECIES_PATTERN = re.compile(
    r"\[\s*(SPECIES_\w+)\s*\]\s*=\s*\{",
)

_EVOLUTION_TUPLE = re.compile(
    r"\{\s*(EVO_\w+)\s*,\s*(\w+)\s*,\s*(SPECIES_\w+)\s*\}",
)

_INLINE_SPECIES_PATTERN = re.compile(
    r"\[\s*(SPECIES_\w+)\s*\]\s*=",
)

_INLINE_EVOLUTIONS_PATTERN = re.compile(
    r"\.evolutions\s*=\s*EVOLUTION\((.+?)\)\s*,",
    re.DOTALL,
)


def parse_evolutions(repo_path: Path) -> dict[str, list[EvolutionEntry]]:
    pokemon_dir = repo_path / "src" / "data" / "pokemon"

    table_file = pokemon_dir / "evolution.h"
    if table_file.exists():
        return _parse_evolution_table(table_file)

    return _parse_inline_evolutions(repo_path)


def _parse_evolution_table(path: Path) -> dict[str, list[EvolutionEntry]]:
    text = path.read_text(encoding="utf-8")
    result: dict[str, list[EvolutionEntry]] = {}

    for species_match in _TABLE_SPECIES_PATTERN.finditer(text):
        species = species_match.group(1)
        if species == "SPECIES_NONE":
            continue

        start = species_match.end()
        next_species = _TABLE_SPECIES_PATTERN.search(text, start)
        end = next_species.start() if next_species else len(text)
        block = text[start:end]

        entries = _extract_evolution_tuples(block)
        if entries:
            result[species] = entries

    return result


def _parse_inline_evolutions(repo_path: Path) -> dict[str, list[EvolutionEntry]]:
    pokemon_dir = repo_path / "src" / "data" / "pokemon"
    result: dict[str, list[EvolutionEntry]] = {}

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

        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]

            species_match = _INLINE_SPECIES_PATTERN.search(line)
            if species_match:
                current_species = species_match.group(1)

            if current_species and ".evolutions" in line:
                evo_text = line
                while "EVOLUTION(" in evo_text and evo_text.count("(") > evo_text.count(")"):
                    i += 1
                    if i < len(lines):
                        evo_text += "\n" + lines[i]

                entries = _extract_evolution_tuples(evo_text)
                if entries:
                    result[current_species] = entries
                current_species = None

            i += 1

    return result


def _extract_evolution_tuples(text: str) -> list[EvolutionEntry]:
    entries: list[EvolutionEntry] = []
    for match in _EVOLUTION_TUPLE.finditer(text):
        entries.append(
            EvolutionEntry(
                method=match.group(1),
                param=match.group(2),
                target_species=match.group(3),
            )
        )
    return entries
