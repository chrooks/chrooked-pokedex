"""Create Ruleset-owned content the target lacks: abilities and moves.

When the Ruleset owns a full move or ability (e.g. Excalibur) and the target does
not have it, the Applier appends a new `[INTERNAL_NAME]` section to the relevant
PBS file rather than skipping. Creation is idempotent: an internal name already in
the file is left alone.

Honesty over silent inertness:
  * A created ability is DATA ONLY — its name and description are written, never the
    battle mechanic. If the Ruleset carries a behavior spec for it, the Apply Report
    says so loudly.
  * A move field the vocab cannot faithfully translate (a scripted primary effect, a
    flag with no Essentials counterpart) is left out and reported as unresolved,
    never written as a token Essentials would reject.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...model.schema import AbilityDef, MoveDef
from ...report import ApplyReport, ReportEntry
from ...seed.neutralize import normalize_description
from . import pbs_edit, pbs_read, vocab
from .resolution import ResolutionMap


def create_owned_content(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    changed: set[Path] = set()
    changed |= _create_abilities(target, ruleset, resmap, report)
    changed |= _create_moves(target, ruleset, resmap, report)
    return changed


def _create_abilities(target, ruleset, resmap, report) -> set[Path]:
    path = target / "PBS" / "abilities.txt"
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    existing = pbs_read.section_headers(text)
    changed = False

    for chrooked_id in sorted(ruleset.abilities):
        ability = ruleset.abilities[chrooked_id]
        if resmap.ability(ability.name) is not None:
            continue
        internal = _internal(ability.aka, "essentials", ability.name)
        if internal in existing:
            resmap.ability_by_name[ability.name.lower()] = internal
            continue
        text = pbs_edit.append_section(text, _ability_block(internal, ability))
        existing.add(internal)
        resmap.ability_by_name[ability.name.lower()] = internal
        changed = True
        report.add(ReportEntry(
            status="applied", category="ability", chrooked_id=chrooked_id,
            symbol=internal, reason=_creation_reason(ruleset, ability.name),
        ))

    if changed:
        path.write_text(text, encoding="utf-8")
        return {path}
    return set()


def _create_moves(target, ruleset, resmap, report) -> set[Path]:
    path = target / "PBS" / "moves.txt"
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    existing = pbs_read.section_headers(text)
    changed = False

    for chrooked_id in sorted(ruleset.moves):
        move = ruleset.moves[chrooked_id]
        if resmap.move(move.name) is not None:
            continue
        internal = _internal(move.aka, "essentials", move.name)
        if internal in existing:
            resmap.move_by_name[move.name.lower()] = internal
            continue
        block, unresolved = _move_block(internal, move, resmap)
        text = pbs_edit.append_section(text, block)
        existing.add(internal)
        resmap.move_by_name[move.name.lower()] = internal
        changed = True
        status = "partial" if unresolved else "applied"
        report.add(ReportEntry(
            status=status, category="move", chrooked_id=chrooked_id, symbol=internal,
            reason="created" if not unresolved else "created; some fields not ported",
            partial_fields=tuple(unresolved),
        ))

    if changed:
        path.write_text(text, encoding="utf-8")
        return {path}
    return set()


def _creation_reason(ruleset: Ruleset, name: str) -> str:
    if ruleset.behavior_for(name) is not None:
        return "created — DATA ONLY: implement mechanic (behavior spec exists)"
    return "created — DATA ONLY"


def _ability_block(internal: str, ability: AbilityDef) -> str:
    description = normalize_description(ability.description or ability.name)
    return f"[{internal}]\nName = {ability.name}\nDescription = {description}\n"


def _move_block(internal: str, move: MoveDef, resmap: ResolutionMap) -> tuple[str, list[str]]:
    unresolved: list[str] = []
    function_code, effect_chance = _function_code(move, unresolved)

    lines = [
        f"[{internal}]",
        f"Name = {move.name}",
        f"Type = {resmap.type(move.type)}",
        f"Category = {vocab.category(move.category)}",
        f"Power = {move.power if move.power is not None else 0}",
        f"Accuracy = {move.accuracy if move.accuracy is not None else 100}",
        f"TotalPP = {move.pp if move.pp is not None else 5}",
        f"Target = {vocab.target(move.target)}",
        f"FunctionCode = {function_code}",
    ]
    if move.priority:
        lines.append(f"Priority = {move.priority}")

    flags = _flags(move, unresolved)
    if flags:
        lines.append(f"Flags = {','.join(flags)}")
    if effect_chance is not None:
        lines.append(f"EffectChance = {effect_chance}")
    if move.description:
        lines.append(f"Description = {normalize_description(move.description)}")

    return "\n".join(lines) + "\n", unresolved


def _function_code(move: MoveDef, unresolved: list[str]) -> tuple[str, int | None]:
    """Resolve a move's effect to an Essentials FunctionCode + EffectChance.

    Essentials carries one FunctionCode per move, so a plain `hit` becomes `None`
    and a single secondary effect (burn, paralysis, ...) becomes its named code with
    a chance. A scripted primary effect, or anything beyond one mappable secondary,
    is noted unresolved and left as `None` rather than mistranslated."""
    base = vocab.function_code(move.effect)
    if base is None:
        unresolved.append(f"effect:{move.effect}")
        base = vocab.NO_FUNCTION_CODE

    effect_chance: int | None = None
    if move.additional_effects:
        first = move.additional_effects[0]
        code = vocab.additional_function_code(first.effect)
        if code is not None and base == vocab.NO_FUNCTION_CODE:
            base = code
            effect_chance = first.chance
        else:
            unresolved.append(f"effect:{first.effect}")
        for extra in move.additional_effects[1:]:
            unresolved.append(f"effect:{extra.effect}(extra)")

    return base, effect_chance


def _flags(move: MoveDef, unresolved: list[str]) -> list[str]:
    flags: list[str] = []
    for flag in move.flags:
        mapped = vocab.flag(flag)
        if mapped is None:
            unresolved.append(f"flag:{flag}")
        else:
            flags.append(mapped)
    return flags


def _internal(aka, key: str, name: str) -> str:
    if aka and aka.get(key):
        return str(aka[key])
    return vocab.internal_name(name)
