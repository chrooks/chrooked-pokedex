"""Apply species scalar Overrides (types, stats, abilities) into a target's
`PBS/pokemon.txt`.

Each overridden field is written into the species' `[INTERNAL_NAME]` section with
whole-field replacement. Base stats are positional in Essentials
(`BaseStats = HP,ATK,DEF,SPEED,SPATK,SPDEF`), so a single stat Override rewrites
just its index. Abilities span two lines — `Abilities` (primary, secondary) and
`HiddenAbilities` — and only the changed slots are overlaid.

Nothing is silently dropped: a species the target lacks is reported blocked; an
ability name that does not resolve leaves that slot and reports the species partial.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...model.schema import SpeciesOverride
from ...report import ApplyReport, ReportEntry
from . import pbs_edit
from .resolution import ResolutionMap

# Essentials BaseStats order is HP, Attack, Defense, Speed, Sp.Atk, Sp.Def.
_STAT_KEY_TO_INDEX = {"hp": 0, "atk": 1, "def": 2, "spe": 3, "spa": 4, "spd": 5}
_ABILITY_SLOTS = ("primary", "secondary")


def apply_species(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    path = target / "PBS" / "pokemon.txt"
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    original = text

    for chrooked_id in sorted(ruleset.species):
        override = ruleset.species[chrooked_id]
        if not (override.types or override.abilities or override.stats):
            continue
        symbol = resmap.species(chrooked_id, dict(override.aka))
        if symbol is None:
            report.add(ReportEntry(
                status="blocked", category="species", chrooked_id=chrooked_id,
                reason="no species symbol resolved",
            ))
            continue
        if pbs_edit.find_section(text, symbol) is None:
            report.add(ReportEntry(
                status="blocked", category="species", chrooked_id=chrooked_id,
                symbol=symbol, reason="species section not found",
            ))
            continue

        text, unresolved = _apply_fields(text, symbol, override, resmap)
        if unresolved:
            report.add(ReportEntry(
                status="partial", category="species", chrooked_id=chrooked_id,
                symbol=symbol, reason="some fields not applied",
                partial_fields=tuple(unresolved),
            ))
        else:
            report.add(ReportEntry(
                status="applied", category="species", chrooked_id=chrooked_id,
                symbol=symbol,
            ))

    if text != original:
        path.write_text(text, encoding="utf-8")
        return {path}
    return set()


def _apply_fields(
    text: str, symbol: str, override: SpeciesOverride, resmap: ResolutionMap
) -> tuple[str, list[str]]:
    unresolved: list[str] = []

    if override.types:
        symbols = [resmap.type(name) for name in override.types]
        if all(symbols):
            text = pbs_edit.set_section_field(text, symbol, "Types", ",".join(symbols))
        else:
            unresolved.append("types")

    if override.stats:
        for key, value in override.stats.items():
            index = _STAT_KEY_TO_INDEX.get(key)
            if index is None:
                unresolved.append(f"stat:{key}")
                continue
            text, applied = pbs_edit.set_comma_index(
                text, symbol, "BaseStats", index, str(value)
            )
            if not applied:
                unresolved.append(f"stat:{key}")

    if override.abilities:
        text, ability_unresolved = _apply_abilities(text, symbol, override, resmap)
        unresolved.extend(ability_unresolved)

    return text, unresolved


def _apply_abilities(
    text: str, symbol: str, override: SpeciesOverride, resmap: ResolutionMap
) -> tuple[str, list[str]]:
    unresolved: list[str] = []
    span = pbs_edit.find_section(text, symbol)
    block = text[span[0]:span[1]]

    current = pbs_edit.get_field(block, "Abilities") or ""
    slots = [a.strip() for a in current.split(",") if a.strip()]
    for index, slot in enumerate(_ABILITY_SLOTS):
        name = getattr(override.abilities, slot)
        if name is None:
            continue
        resolved = resmap.ability(name)
        if resolved is None:
            unresolved.append(f"ability:{name}")
            continue
        while len(slots) <= index:
            slots.append("")
        slots[index] = resolved
    slots = [s for s in slots if s]
    if slots:
        text = pbs_edit.set_section_field(text, symbol, "Abilities", ",".join(slots))

    if override.abilities.hidden is not None:
        resolved = resmap.ability(override.abilities.hidden)
        if resolved is None:
            unresolved.append(f"ability:{override.abilities.hidden}")
        else:
            text = pbs_edit.set_section_field(text, symbol, "HiddenAbilities", resolved)

    return text, unresolved
