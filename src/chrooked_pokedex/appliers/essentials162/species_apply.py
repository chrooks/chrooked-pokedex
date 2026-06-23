"""Apply species scalar Overrides into an Essentials 16.2 `PBS/pokemon.txt`.

The 16.2 analogue of `appliers/essentials/species_apply.py`, built on the
`section_edit` I/O and the 16.2 format rules:

  * Types are TWO fields, `Type1=`/`Type2=` (not a v21 `Types=` comma list). A
    mono-type Override writes `Type1` and DROPS `Type2` entirely via
    `remove_section_field` — 16.2 has no blank `Type2=` line.
  * `BaseStats=` is positional HP,Atk,Def,**Spe**,SpA,SpD — Speed at index 3 — so a
    single stat Override rewrites just its index with `set_comma_index`.
  * Abilities split across `Abilities=` (comma list) and `HiddenAbility=` (SINGULAR,
    one value, never a comma list — note the v21 plural `HiddenAbilities` differs).

A species absent from the target is created (a new `[N]` section) when the Override
carries enough to form a valid row (types + a full stat block); a partial Override on
an absent species is reported blocked rather than written as an invalid section.
Nothing is silently dropped: an ability name that does not resolve leaves that slot
and reports the species partial.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...model.schema import SpeciesOverride
from ...report import ApplyReport, ReportEntry
from ..essentials import vocab
from . import pbs_io, section_edit, section_read
from .resolution import ResolutionMap

# 16.2 BaseStats order is HP, Attack, Defense, Speed, Sp.Atk, Sp.Def — Speed at index 3.
_STAT_KEY_TO_INDEX = {"hp": 0, "atk": 1, "def": 2, "spe": 3, "spa": 4, "spd": 5}
_ABILITY_SLOTS = ("primary", "secondary")
_STAT_ORDER = ("hp", "atk", "def", "spe", "spa", "spd")


def apply_species(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport,
    skip: set[str] | None = None,
) -> set[Path]:
    """Apply species scalar Overrides into `pokemon.txt`.

    `skip` names chrooked_ids already claimed by `forms_apply` (alt-forms that live in
    `pokemonforms.txt`); they are passed over here so a form is never double-reported
    as both applied-in-forms and blocked-in-species.
    """
    skip = skip or set()
    path = target / "PBS" / "pokemon.txt"
    if not path.exists():
        return set()
    text, had_bom = pbs_io.read(path)
    original = text

    for chrooked_id in sorted(ruleset.species):
        if chrooked_id in skip:
            continue
        override = ruleset.species[chrooked_id]
        if not (override.types or override.abilities or override.stats):
            continue
        symbol = resmap.species(chrooked_id, dict(override.aka))
        present = symbol is not None and (
            section_edit.find_section_by_internalname(text, symbol) is not None
        )

        if present:
            text = _apply_existing(text, symbol, override, resmap, report, chrooked_id)
        else:
            text = _create_or_block(text, override, resmap, report, chrooked_id)

    if text != original:
        pbs_io.write(path, text, had_bom)
        return {path}
    return set()


def _apply_existing(
    text: str, symbol: str, override: SpeciesOverride, resmap: ResolutionMap,
    report: ApplyReport, chrooked_id: str,
) -> str:
    text, unresolved = _apply_fields(text, symbol, override, resmap)
    if unresolved:
        report.add(ReportEntry(
            status="partial", category="species", chrooked_id=chrooked_id,
            symbol=symbol, reason="some fields not applied",
            partial_fields=tuple(unresolved),
        ))
    else:
        report.add(ReportEntry(
            status="applied", category="species", chrooked_id=chrooked_id, symbol=symbol,
        ))
    return text


def _create_or_block(
    text: str, override: SpeciesOverride, resmap: ResolutionMap,
    report: ApplyReport, chrooked_id: str,
) -> str:
    """Create a new `[N]` section for an absent species, or block a partial Override.

    A creatable Override carries types AND a full six-stat block — enough to emit a
    valid 16.2 section. Anything less (e.g. a lone stat tweak aimed at a species the
    target lacks) is reported blocked, never written as a broken section. Every
    referenced type must also resolve: creating a section with a silently-dropped
    type would give the new species the WRONG typing, so an unresolved type blocks
    creation rather than fabricating a mono-type section.
    """
    type_symbols = [resmap.type(name) for name in (override.types or ())]
    types_resolve = bool(override.types) and all(type_symbols)
    has_full_stats = bool(override.stats) and all(
        key in override.stats for key in _STAT_ORDER
    )
    if not (types_resolve and has_full_stats):
        reason = "species section not found and Override insufficient to create"
        if override.types and not types_resolve:
            missing = [n for n, s in zip(override.types, type_symbols) if not s]
            reason = (
                "species section not found; cannot create with an unresolved "
                f"type {missing!r} (would mis-type the new species)"
            )
        report.add(ReportEntry(
            status="blocked", category="species", chrooked_id=chrooked_id,
            reason=reason,
        ))
        return text

    block_body, unresolved = _render_new_block(override, resmap)
    next_index = section_read.max_index(text) + 1
    text = section_edit.append_section(text, next_index, block_body)
    status = "partial" if unresolved else "applied"
    report.add(ReportEntry(
        status=status, category="species", chrooked_id=chrooked_id,
        symbol=_internal_of(override, resmap),
        reason="created new species" + (" (some fields unresolved)" if unresolved else ""),
        partial_fields=tuple(unresolved),
    ))
    return text


def _render_new_block(
    override: SpeciesOverride, resmap: ResolutionMap
) -> tuple[str, list[str]]:
    internal = _internal_of(override, resmap)
    unresolved: list[str] = []

    type_symbols = [resmap.type(name) or "" for name in override.types]
    if not all(type_symbols):
        unresolved.append("types")
        type_symbols = [s for s in type_symbols if s] or ["NORMAL"]

    stats = ",".join(str(override.stats[key]) for key in _STAT_ORDER)

    lines = [
        f"Name={override.name}",
        f"InternalName={internal}",
        f"Type1={type_symbols[0]}",
    ]
    if len(type_symbols) > 1:
        lines.append(f"Type2={type_symbols[1]}")
    lines.append(f"BaseStats={stats}")
    return "\n".join(lines), unresolved


def _internal_of(override: SpeciesOverride, resmap: ResolutionMap) -> str:
    hint = (override.aka or {}).get("essentials")
    return str(hint) if hint else vocab.internal_name(override.name)


def _apply_fields(
    text: str, symbol: str, override: SpeciesOverride, resmap: ResolutionMap
) -> tuple[str, list[str]]:
    unresolved: list[str] = []

    if override.types:
        text, type_unresolved = _apply_types(text, symbol, override, resmap)
        unresolved.extend(type_unresolved)

    if override.stats:
        for key, value in override.stats.items():
            index = _STAT_KEY_TO_INDEX.get(key)
            if index is None:
                unresolved.append(f"stat:{key}")
                continue
            text, applied = section_edit.set_comma_index(
                text, symbol, "BaseStats", index, str(value)
            )
            if not applied:
                unresolved.append(f"stat:{key}")

    if override.abilities:
        text, ability_unresolved = _apply_abilities(text, symbol, override, resmap)
        unresolved.extend(ability_unresolved)

    return text, unresolved


def _apply_types(
    text: str, symbol: str, override: SpeciesOverride, resmap: ResolutionMap
) -> tuple[str, list[str]]:
    symbols = [resmap.type(name) for name in override.types]
    if not all(symbols):
        return text, ["types"]
    text, _ = section_edit.set_section_field(text, symbol, "Type1", symbols[0])
    if len(symbols) > 1:
        text, _ = section_edit.set_section_field(text, symbol, "Type2", symbols[1])
    else:
        # mono-type: 16.2 drops Type2 entirely, never leaves a blank `Type2=`.
        text, _ = section_edit.remove_section_field(text, symbol, "Type2")
    return text, []


def _apply_abilities(
    text: str, symbol: str, override: SpeciesOverride, resmap: ResolutionMap
) -> tuple[str, list[str]]:
    unresolved: list[str] = []
    span = section_edit.find_section_by_internalname(text, symbol)
    block = text[span[0]:span[1]]

    current = section_edit.get_field(block, "Abilities") or ""
    slots = [a.strip() for a in current.split(",") if a.strip()]
    wrote_slot = False
    for index, slot in enumerate(_ABILITY_SLOTS):
        name = getattr(override.abilities, slot)
        if name is None:
            continue
        resolved = resmap.ability(name)
        if resolved is None:
            # Ability not defined in the target's abilities.txt (e.g. a custom
            # ability like CHLOROPLAST). Do NOT fabricate and write an undefined
            # reference — Essentials refuses to compile it. Report and skip; #23
            # will define custom abilities so they resolve here.
            unresolved.append(f"ability:{name}")
            continue
        while len(slots) <= index:
            slots.append("")
        slots[index] = resolved
        wrote_slot = True
    slots = [s for s in slots if s]
    if wrote_slot and slots:
        text, _ = section_edit.set_section_field(text, symbol, "Abilities", ",".join(slots))

    if override.abilities.hidden is not None:
        # HiddenAbility is SINGULAR in 16.2 — one value, never a comma list.
        resolved = resmap.ability(override.abilities.hidden)
        if resolved is None:
            unresolved.append(f"hidden-ability:{override.abilities.hidden}")
        else:
            text, _ = section_edit.set_section_field(text, symbol, "HiddenAbility", resolved)

    return text, unresolved
