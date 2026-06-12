"""Create Ruleset-owned content the target lacks: abilities and moves.

When the Ruleset owns the full definition of a move or ability (e.g. Excalibur),
and the target does not have it, the applier creates it rather than skipping. It
appends a new `#define MOVE_X N` / `#define ABILITY_X N` constant (bumping the
relevant `*_COUNT_GEN9` sentinel that `MOVES_COUNT`/`ABILITIES_COUNT` alias) and a
data-table entry. Z-moves and Max-moves are defined relative to `MOVES_COUNT`, so
inserting before the sentinel shifts them consistently.

There are no Ruleset-owned *types*: the neutral schema models only type-chart
multiplier overrides, never new type definitions, so the type tier is empty.

Creation is idempotent: a constant that already exists is left alone.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...model import Ruleset
from ...model.schema import AbilityDef, MoveDef
from ...report import ApplyReport, ReportEntry
from ...seed import neutralize as nz
from ...seed.neutralize import normalize_description
from .resolution import ResolutionMap

_CATEGORY_TO_SYMBOL = {
    "physical": "DAMAGE_CATEGORY_PHYSICAL",
    "special": "DAMAGE_CATEGORY_SPECIAL",
    "status": "DAMAGE_CATEGORY_STATUS",
}


def create_owned_content(
    target: Path,
    ruleset: Ruleset,
    resmap: ResolutionMap,
    report: ApplyReport,
) -> set[Path]:
    """Create owned abilities then moves the target lacks; return changed files."""
    changed: set[Path] = set()
    changed |= _create_abilities(target, ruleset, resmap, report)
    changed |= _create_moves(target, ruleset, resmap, report)
    return changed


def _create_abilities(target, ruleset, resmap, report) -> set[Path]:
    constants_path = target / "include" / "constants" / "abilities.h"
    data_path = target / "src" / "data" / "abilities.h"
    changed: set[Path] = set()
    for chrooked_id in sorted(ruleset.abilities):
        ability = ruleset.abilities[chrooked_id]
        if resmap.ability(ability.name) is not None:
            continue  # already present in target
        symbol = _symbol(ability.aka, "pokeemerald", "ABILITY_", chrooked_id)
        ok = _insert_constant(constants_path, "ABILITIES_COUNT", symbol)
        if not ok:
            report.add(ReportEntry(
                status="blocked", category="ability", chrooked_id=chrooked_id,
                symbol=symbol, reason="could not place ability constant",
            ))
            continue
        _insert_entry(data_path, "gAbilitiesInfo", _ability_entry(symbol, ability))
        changed.update({constants_path, data_path})
        resmap.ability_by_name[ability.name.lower()] = symbol
        report.add(ReportEntry(
            status="applied", category="ability", chrooked_id=chrooked_id,
            symbol=symbol, reason=_creation_reason(ruleset, ability.name),
        ))
    return changed


def _creation_reason(ruleset: Ruleset, name: str) -> str:
    """Created abilities are DATA ONLY: the applier writes the name + description but
    never the battle mechanic. If the Ruleset carries a behavior spec for this ability,
    say so loudly so the silent-inert-ability trap stays visible in the Apply Report."""
    if ruleset.behavior_for(name) is not None:
        return "created — DATA ONLY: implement mechanic (behavior spec exists)"
    return "created"


def _create_moves(target, ruleset, resmap, report) -> set[Path]:
    constants_path = target / "include" / "constants" / "moves.h"
    data_path = target / "src" / "data" / "moves_info.h"
    changed: set[Path] = set()
    for chrooked_id in sorted(ruleset.moves):
        move = ruleset.moves[chrooked_id]
        if resmap.move(move.name) is not None:
            continue
        symbol = _symbol(move.aka, "pokeemerald", "MOVE_", chrooked_id)
        ok = _insert_constant(constants_path, "MOVES_COUNT", symbol)
        if not ok:
            report.add(ReportEntry(
                status="blocked", category="move", chrooked_id=chrooked_id,
                symbol=symbol, reason="could not place move constant",
            ))
            continue
        _insert_entry(data_path, "gMovesInfo", _move_entry(symbol, move, resmap))
        changed.update({constants_path, data_path})
        resmap.move_by_name[move.name.lower()] = symbol
        report.add(ReportEntry(
            status="applied", category="move", chrooked_id=chrooked_id,
            symbol=symbol, reason="created",
        ))
    return changed


def _symbol(aka, key: str, prefix: str, chrooked_id: str) -> str:
    if aka and aka.get(key):
        return str(aka[key])
    return prefix + chrooked_id.upper()


def _insert_constant(path: Path, count_alias: str, symbol: str) -> bool:
    """Insert `#define <symbol> N` before the sentinel `<count_alias>` aliases,
    bumping that sentinel by one. Idempotent: returns True if already present."""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if re.search(r"#define\s+" + re.escape(symbol) + r"\b", text):
        return True

    sentinel = _resolve_count_sentinel(text, count_alias)
    if sentinel is None:
        return False
    sentinel_name, value = sentinel
    pattern = re.compile(r"(#define\s+" + re.escape(sentinel_name) + r"\s+)(\d+)")

    def bump(match: re.Match) -> str:
        return f"#define {symbol} {value}\n{match.group(1)}{value + 1}"

    new_text = pattern.sub(bump, text, count=1)
    path.write_text(new_text, encoding="utf-8")
    return True


def _resolve_count_sentinel(text: str, count_alias: str):
    """Return (sentinel_define_name, int_value). `MOVES_COUNT` may alias
    `MOVES_COUNT_GEN9`, which holds the literal; follow one level of aliasing."""
    alias = re.search(r"#define\s+" + re.escape(count_alias) + r"\s+(\w+)", text)
    if alias is None:
        return None
    target_name = alias.group(1)
    if target_name.isdigit():
        return (count_alias, int(target_name))
    literal = re.search(r"#define\s+" + re.escape(target_name) + r"\s+(\d+)", text)
    if literal is None:
        return None
    return (target_name, int(literal.group(1)))


def _insert_entry(path: Path, array_var: str, entry_text: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    open_brace = _array_open_brace(text, array_var)
    if open_brace is None:
        return
    close_brace = _find_matching_brace(text, open_brace)
    if close_brace is None:
        return
    new_text = text[:close_brace] + entry_text + text[close_brace:]
    path.write_text(new_text, encoding="utf-8")


def _array_open_brace(text: str, array_var: str):
    match = re.search(re.escape(array_var) + r"\s*\[[^\]]*\]\s*=\s*\{", text)
    if match is None:
        return None
    return match.end() - 1


def _ability_entry(symbol: str, ability: AbilityDef) -> str:
    description = normalize_description(ability.description or ability.name)
    return (
        f"    [{symbol}] =\n"
        f"    {{\n"
        f'        .name = _("{ability.name}"),\n'
        f'        .description = COMPOUND_STRING("{_escape(description)}"),\n'
        f"    }},\n"
    )


def _move_entry(symbol: str, move: MoveDef, resmap: ResolutionMap) -> str:
    type_symbol = resmap.type(move.type) or ("TYPE_" + move.type.upper())
    category = _CATEGORY_TO_SYMBOL.get(move.category, "DAMAGE_CATEGORY_PHYSICAL")
    lines = [
        f"    [{symbol}] =",
        "    {",
        f'        .name = COMPOUND_STRING("{move.name}"),',
    ]
    if move.description:
        safe = normalize_description(move.description)
        lines.append(f'        .description = COMPOUND_STRING("{_escape(safe)}"),')
    lines.append(f"        .effect = {nz.primary_effect_symbol(move.effect)},")
    lines.append(f"        .type = {type_symbol},")
    lines.append(f"        .category = {category},")
    if move.power is not None:
        lines.append(f"        .power = {move.power},")
    if move.accuracy is not None:
        lines.append(f"        .accuracy = {move.accuracy},")
    if move.pp is not None:
        lines.append(f"        .pp = {move.pp},")
    if move.priority:
        lines.append(f"        .priority = {move.priority},")
    lines.append(f"        .target = {nz.move_target_symbol(move.target)},")
    if move.argument:
        lines.append(f"        .argument = {{ {_render_argument(move.argument, resmap)} }},")
    for flag in move.flags:
        symbol_flag = nz.move_flag_symbol(flag)
        if symbol_flag is not None:
            lines.append(f"        .{symbol_flag} = TRUE,")
    if move.additional_effects:
        lines.append("        .additionalEffects = ADDITIONAL_EFFECTS(")
        rendered = [
            "            { .moveEffect = "
            + nz.move_effect_symbol(ae.effect)
            + f", .chance = {ae.chance} }}"
            for ae in move.additional_effects
        ]
        lines.append(",\n".join(rendered))
        lines.append("        ),")
    lines.append("    },")
    return "\n".join(lines) + "\n"


def _render_argument(argument, resmap: ResolutionMap) -> str:
    """Render a neutral argument map back to C, e.g. {'type': 'Dragon'} ->
    `.type = TYPE_DRAGON`; `{'absorb_percentage': 50}` -> `.absorbPercentage = 50`."""
    parts = []
    for field, value in argument.items():
        camel = nz.snake_to_camel(field)
        if isinstance(value, int):
            rendered = str(value)
        else:  # a string argument is a type in practice (e.g. super-effective-on-type)
            rendered = resmap.type(value) or ("TYPE_" + str(value).upper().replace(" ", "_"))
        parts.append(f".{camel} = {rendered}")
    return ", ".join(parts)


def _escape(text: str) -> str:
    """Escape a Python string for a C string literal. A real newline becomes the
    two characters backslash-n: a bare newline inside `"..."` is invalid C, and it
    would also split the value across lines so the readers could not round-trip it."""
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _find_matching_brace(text: str, open_index: int):
    depth = 0
    for pos in range(open_index, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return pos
    return None
