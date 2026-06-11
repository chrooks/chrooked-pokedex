from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SPECIES_PROFILE_FIELDS: tuple[str, ...] = (
    "baseHP",
    "baseAttack",
    "baseDefense",
    "baseSpeed",
    "baseSpAttack",
    "baseSpDefense",
    "types",
    "catchRate",
    "expYield",
    "evYield_HP",
    "evYield_Attack",
    "evYield_Defense",
    "evYield_Speed",
    "evYield_SpAttack",
    "evYield_SpDefense",
    "itemCommon",
    "itemRare",
    "genderRatio",
    "eggCycles",
    "friendship",
    "growthRate",
    "eggGroups",
    "abilities",
    "safariZoneFleeRate",
    "bodyColor",
    "natDexNum",
)

IMPLICIT_SPECIES_PROFILE_DEFAULTS: dict[str, str] = {
    "evYield_HP": "0",
    "evYield_Attack": "0",
    "evYield_Defense": "0",
    "evYield_Speed": "0",
    "evYield_SpAttack": "0",
    "evYield_SpDefense": "0",
    "itemCommon": "ITEM_NONE",
    "itemRare": "ITEM_NONE",
    "safariZoneFleeRate": "0",
}

_ALLOWED_FIELDS = set(SPECIES_PROFILE_FIELDS)
_SPECIES_ENTRY_PATTERN = re.compile(r"\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*")
_FUNCTION_MACRO_PATTERN = re.compile(
    r"^\s*#define\s+([A-Z][A-Z0-9_]*)\s*\(([^)]*)\)\s*(.*?)\s*$"
)
_MACRO_CALL_PATTERN = re.compile(r"([A-Z][A-Z0-9_]*)\s*\(")
_FIELD_PATTERN = re.compile(r"\.([A-Za-z_][A-Za-z0-9_]*)\s*=")


@dataclass(frozen=True)
class SpeciesProfile:
    species: str
    fields: dict[str, str]


@dataclass(frozen=True)
class _FunctionMacro:
    parameters: tuple[str, ...]
    body: str


def get_species_profile_value(profile: SpeciesProfile, field: str) -> str | None:
    return profile.fields.get(field, IMPLICIT_SPECIES_PROFILE_DEFAULTS.get(field))


def parse_species_profiles(repo_path: Path) -> dict[str, SpeciesProfile]:
    profiles: dict[str, SpeciesProfile] = {}
    for header_path in _species_info_headers(repo_path):
        text = _strip_c_comments(header_path.read_text(encoding="utf-8"))
        macros = _parse_function_macros(text)
        for species, body in _iter_species_entry_bodies(text, macros):
            fields = _parse_fields(body)
            if fields:
                profiles[species] = SpeciesProfile(species=species, fields=fields)
    return profiles


def _species_info_headers(repo_path: Path) -> list[Path]:
    pokemon_dir = repo_path / "src" / "data" / "pokemon"
    headers: list[Path] = []

    flat_header = pokemon_dir / "species_info.h"
    if flat_header.exists():
        headers.append(flat_header)

    split_dir = pokemon_dir / "species_info"
    if split_dir.exists():
        headers.extend(sorted(split_dir.glob("*.h")))

    return headers


def _iter_species_entry_bodies(
    text: str,
    macros: dict[str, _FunctionMacro],
) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    search_pos = 0

    while match := _SPECIES_ENTRY_PATTERN.search(text, search_pos):
        species = match.group(1)
        value_start = _skip_whitespace(text, match.end())
        if value_start >= len(text):
            break

        if text[value_start] == "{":
            opening_brace = value_start
            closing_brace = _find_matching_brace(text, opening_brace)
            if closing_brace is None:
                search_pos = match.end()
                continue

            entries.append((species, text[opening_brace + 1 : closing_brace]))
            search_pos = closing_brace + 1
            continue

        macro_match = _MACRO_CALL_PATTERN.match(text, value_start)
        if macro_match is None:
            search_pos = match.end()
            continue

        macro_name = macro_match.group(1)
        macro = macros.get(macro_name)
        opening_paren = value_start + macro_match.group(0).rfind("(")
        closing_paren = _find_matching_paren(text, opening_paren)
        if macro is None or closing_paren is None:
            search_pos = match.end()
            continue

        arguments = _split_arguments(text[opening_paren + 1 : closing_paren])
        entries.append((species, _expand_function_macro(macro, arguments)))
        search_pos = closing_paren + 1

    return entries


def _parse_function_macros(text: str) -> dict[str, _FunctionMacro]:
    macros: dict[str, _FunctionMacro] = {}
    for line in _logical_preprocessor_lines(text):
        match = _FUNCTION_MACRO_PATTERN.match(line)
        if match is None:
            continue

        name = match.group(1)
        parameters = tuple(
            parameter.strip()
            for parameter in match.group(2).split(",")
            if parameter.strip()
        )
        macros[name] = _FunctionMacro(parameters=parameters, body=match.group(3))
    return macros


def _logical_preprocessor_lines(text: str) -> list[str]:
    lines: list[str] = []
    pending: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not pending and not line.lstrip().startswith("#define"):
            continue

        if line.endswith("\\"):
            pending.append(line[:-1].strip())
            continue

        pending.append(line.strip())
        lines.append(" ".join(pending))
        pending = []

    if pending:
        lines.append(" ".join(pending))

    return lines


def _expand_function_macro(macro: _FunctionMacro, arguments: list[str]) -> str:
    body = macro.body
    for parameter, argument in zip(macro.parameters, arguments, strict=False):
        body = re.sub(rf"\b{re.escape(parameter)}\b", argument.strip(), body)

    body = re.sub(r"\s*##\s*", "", body)
    body = body.strip()
    if body.startswith("{"):
        closing_brace = _find_matching_brace(body, 0)
        if closing_brace is not None:
            return body[1:closing_brace]
    return body


def _parse_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    pos = 0
    brace_depth = 0
    paren_depth = 0
    bracket_depth = 0

    while pos < len(body):
        char = body[pos]
        if char == "{":
            brace_depth += 1
            pos += 1
            continue
        if char == "}":
            brace_depth = max(0, brace_depth - 1)
            pos += 1
            continue
        if char == "(":
            paren_depth += 1
            pos += 1
            continue
        if char == ")":
            paren_depth = max(0, paren_depth - 1)
            pos += 1
            continue
        if char == "[":
            bracket_depth += 1
            pos += 1
            continue
        if char == "]":
            bracket_depth = max(0, bracket_depth - 1)
            pos += 1
            continue

        if brace_depth == paren_depth == bracket_depth == 0 and char == ".":
            match = _FIELD_PATTERN.match(body, pos)
            if match:
                field_name = match.group(1)
                expression_start = match.end()
                expression_end = _find_expression_end(body, expression_start)
                if _should_keep_field(field_name):
                    fields[field_name] = _normalize_expression(
                        body[expression_start:expression_end]
                    )
                pos = expression_end + 1
                continue

        pos += 1

    return fields


def _should_keep_field(field_name: str) -> bool:
    if field_name.endswith(("_old", "_new")):
        return False
    if field_name == "catchRate_hard":
        return False
    return field_name in _ALLOWED_FIELDS


def _find_expression_end(text: str, start: int) -> int:
    brace_depth = 0
    paren_depth = 0
    bracket_depth = 0
    pos = start

    while pos < len(text):
        char = text[pos]
        if char == "{":
            brace_depth += 1
        elif char == "}":
            if brace_depth == 0 and paren_depth == 0 and bracket_depth == 0:
                return pos
            brace_depth = max(0, brace_depth - 1)
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif char == "," and brace_depth == paren_depth == bracket_depth == 0:
            return pos
        pos += 1

    return pos


def _skip_whitespace(text: str, start: int) -> int:
    pos = start
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def _find_matching_brace(text: str, opening_brace: int) -> int | None:
    depth = 0
    for pos in range(opening_brace, len(text)):
        char = text[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return pos
    return None


def _find_matching_paren(text: str, opening_paren: int) -> int | None:
    depth = 0
    for pos in range(opening_paren, len(text)):
        char = text[pos]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return pos
    return None


def _split_arguments(text: str) -> list[str]:
    arguments: list[str] = []
    start = 0
    brace_depth = 0
    paren_depth = 0
    bracket_depth = 0

    for pos, char in enumerate(text):
        if char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif char == "," and brace_depth == paren_depth == bracket_depth == 0:
            arguments.append(text[start:pos].strip())
            start = pos + 1

    tail = text[start:].strip()
    if tail:
        arguments.append(tail)
    return arguments


def _normalize_expression(expression: str) -> str:
    value = re.sub(r"\s+", " ", expression).strip()
    value = re.sub(r"\s*,\s*", ", ", value)
    value = re.sub(r"\{\s*", "{ ", value)
    value = re.sub(r"\s*\}", " }", value)
    value = re.sub(r"\(\s*", "(", value)
    value = re.sub(r"\s*\)", ")", value)
    return value


def _strip_c_comments(text: str) -> str:
    result: list[str] = []
    pos = 0
    in_string = False
    in_char = False

    while pos < len(text):
        char = text[pos]
        next_char = text[pos + 1] if pos + 1 < len(text) else ""

        if in_string:
            result.append(char)
            if char == "\\" and next_char:
                result.append(next_char)
                pos += 2
                continue
            if char == '"':
                in_string = False
            pos += 1
            continue

        if in_char:
            result.append(char)
            if char == "\\" and next_char:
                result.append(next_char)
                pos += 2
                continue
            if char == "'":
                in_char = False
            pos += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            pos += 1
            continue

        if char == "'":
            in_char = True
            result.append(char)
            pos += 1
            continue

        if char == "/" and next_char == "/":
            pos += 2
            while pos < len(text) and text[pos] != "\n":
                pos += 1
            result.append("\n")
            continue

        if char == "/" and next_char == "*":
            pos += 2
            while pos + 1 < len(text) and not (
                text[pos] == "*" and text[pos + 1] == "/"
            ):
                result.append("\n" if text[pos] == "\n" else " ")
                pos += 1
            pos += 2
            continue

        result.append(char)
        pos += 1

    return "".join(result)
