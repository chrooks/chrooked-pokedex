"""Apply species scalar Overrides (types, abilities, stats) into a target fork.

Each overridden field is rendered to C and written into the target's
`[SPECIES_X] = { ... }` entry with whole-field replacement. Abilities are an
array field: the override carries only the changed slots, so the current array
is read and the changed slots overlaid before the whole array is re-rendered —
this computes a new value, it does not merge token-by-token.

Nothing is silently dropped: a missing species, a macro-form entry, or an
unresolved ability is recorded in the Apply Report as blocked or partial.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...model.schema import SpeciesOverride
from ...report import ApplyReport, ReportEntry
from ...seed.neutralize import extract_ability_constants
from . import c_edit
from .resolution import ResolutionMap

_STAT_KEY_TO_FIELD = {
    "hp": "baseHP",
    "atk": "baseAttack",
    "def": "baseDefense",
    "spa": "baseSpAttack",
    "spd": "baseSpDefense",
    "spe": "baseSpeed",
}
_ABILITY_SLOTS = ("primary", "secondary", "hidden")


def _species_info_files(target: Path) -> list[Path]:
    pokemon_dir = target / "src" / "data" / "pokemon"
    files: list[Path] = []
    flat = pokemon_dir / "species_info.h"
    if flat.exists():
        files.append(flat)
    split_dir = pokemon_dir / "species_info"
    if split_dir.exists():
        files.extend(sorted(split_dir.glob("*.h")))
    return files


def apply_species(
    target: Path,
    ruleset: Ruleset,
    resmap: ResolutionMap,
    report: ApplyReport,
) -> set[Path]:
    """Apply every species Override; return the set of files actually changed."""
    files = _species_info_files(target)
    texts: dict[Path, str] = {path: path.read_text(encoding="utf-8") for path in files}
    changed: set[Path] = set()

    for chrooked_id in sorted(ruleset.species):
        override = ruleset.species[chrooked_id]
        # Identity / evolution-only entries carry no scalar fields for this tier;
        # skip them silently — they exist for resolution, not species edits.
        if not (override.types or override.abilities or override.stats):
            continue
        symbol = resmap.species(chrooked_id, dict(override.aka))
        if symbol is None:
            report.add(ReportEntry(
                status="blocked", category="species", chrooked_id=chrooked_id,
                reason="no species symbol resolved",
            ))
            continue

        located = _locate(texts, symbol)
        if located is None:
            report.add(ReportEntry(
                status="blocked", category="species", chrooked_id=chrooked_id,
                symbol=symbol, reason="species not found or macro-form entry",
            ))
            continue

        path, span = located
        dialect = _detect_types_dialect(texts[path])
        body = texts[path][span[0] + 1 : span[1]]
        new_body, unresolved = _render_fields(body, override, resmap, dialect)
        new_text = c_edit.replace_entry_body(texts[path], span, new_body)
        if new_text != texts[path]:
            texts[path] = new_text
            changed.add(path)

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

    for path in changed:
        path.write_text(texts[path], encoding="utf-8")
    return changed


def _locate(texts: dict[Path, str], symbol: str):
    for path, text in texts.items():
        span = c_edit.find_species_entry(text, symbol)
        if span is not None:
            return path, span
    return None


def _detect_types_dialect(text: str) -> str:
    """Return "macro" if this species file already uses MON_TYPES(...), else
    "brace" — matching this specific file's own native .types convention.
    Detected per-file since a split-layout target can mix dialects across files."""
    if "MON_TYPES(" in text:
        return "macro"
    return "brace"


def _render_fields(
    body: str, override: SpeciesOverride, resmap: ResolutionMap, dialect: str
) -> tuple[str, list[str]]:
    unresolved: list[str] = []

    if override.types:
        symbols = [resmap.type(name) for name in override.types]
        if all(symbols):
            body = c_edit.set_field_all(body, "types", _render_types(symbols, dialect))
        else:
            unresolved.append("types")

    if override.stats:
        for key, value in override.stats.items():
            field = _STAT_KEY_TO_FIELD.get(key)
            if field is not None:
                # A stat may be gated per generation; every branch gets the value.
                body = c_edit.set_field_all(body, field, str(value))

    if override.abilities:
        body, ability_unresolved = _apply_abilities(body, override, resmap)
        unresolved.extend(ability_unresolved)

    return body, unresolved


def _render_types(symbols: list[str], dialect: str) -> str:
    assert dialect in ("brace", "macro"), dialect
    if dialect == "brace":
        first = symbols[0]
        second = symbols[1] if len(symbols) > 1 else symbols[0]
        return "{ " + first + ", " + second + " }"
    return "MON_TYPES(" + ", ".join(symbols) + ")"


def _apply_abilities(body: str, override: SpeciesOverride, resmap: ResolutionMap):
    """Overlay the Override's changed ability slots onto every `.abilities`
    occurrence, preserving each branch's own values for the unchanged slots."""
    unresolved: list[str] = []
    resolved_slots: dict[int, str] = {}
    for index, slot in enumerate(_ABILITY_SLOTS):
        name = getattr(override.abilities, slot)
        if name is None:
            continue
        symbol = resmap.ability(name)
        if symbol is None:
            unresolved.append(f"ability:{name}")
            continue
        resolved_slots[index] = symbol

    if not resolved_slots:
        return body, unresolved

    def render(current_value: str) -> str:
        current = list(extract_ability_constants(current_value))
        while len(current) < 3:
            current.append("ABILITY_NONE")
        for index, symbol in resolved_slots.items():
            current[index] = symbol
        return "{" + ", ".join(current[:3]) + "}"

    return c_edit.set_field_per_occurrence(body, "abilities", render), unresolved
