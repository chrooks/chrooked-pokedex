"""Abilities category: per-species slots plus ability name/description edits.

Slot reassignment rewrites only the `abilities_for SPECIES, PRIMARY,
SECONDARY, HIDDEN` line in data/pokemon/base_stats/<species>.asm (the
non-faithful line when FAITHFUL-wrapped). AbilityDef overrides rewrite the
`rawchar` name line in data/abilities/names.asm and the text block under the
ability's label in descriptions.asm. New abilities are blocked — their
mechanics are engine code (the behaviors-packet Boundary).
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from .asm_edit import FAITHFUL, classify_lines, splice_args
from .resolution import ResolutionMap

_BASE_STATS_DIR = Path("data") / "pokemon" / "base_stats"
_NAMES_FILE = Path("data") / "abilities" / "names.asm"
_DESCS_FILE = Path("data") / "abilities" / "descriptions.asm"

# Game Boy textbox line width the description text/next lines must fit.
_DESC_WIDTH = 18

# AbilitiesOverride slot -> 1-indexed abilities_for macro arg.
_SLOT_ARGS = {"primary": 2, "secondary": 3, "hidden": 4}


def apply_abilities(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> list[Path]:
    """Apply species ability slots and AbilityDef overrides; return changed files."""
    changed: list[Path] = []
    changed += _apply_species_slots(Path(target), ruleset, resmap, report)
    changed += _apply_ability_defs(Path(target), ruleset, resmap, report)
    return changed


def _apply_species_slots(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> list[Path]:
    changed = []
    referenced: frozenset[str] | None = None  # lazy one-time target scan
    for chrooked_id, override in sorted(ruleset.species.items()):
        if override.abilities is None:
            continue
        if referenced is None:
            referenced = _referenced_abil_symbols(target)
        label = resmap.species_label(override.name, dict(override.aka))
        path = _base_stats_path(target, label)
        if path is None:
            report.add(ReportEntry(
                status="blocked", category="abilities", chrooked_id=chrooked_id,
                reason=f"no base_stats file for {label} in target",
            ))
            continue

        slots = {
            slot: getattr(override.abilities, slot)
            for slot in _SLOT_ARGS
            if getattr(override.abilities, slot) is not None
        }
        replacements = {}
        unresolved = []
        for slot, ability_name in slots.items():
            symbol = resmap.ability(ability_name, {})
            if symbol is None:
                unresolved.append(ability_name)
            else:
                replacements[_SLOT_ARGS[slot]] = symbol
        if unresolved:
            report.add(ReportEntry(
                status="blocked", category="abilities", chrooked_id=chrooked_id,
                symbol=label,
                reason="unresolvable ability(ies): " + ", ".join(unresolved),
            ))
            continue

        lines = path.read_text(encoding="utf-8").splitlines()
        index = _find_abilities_line(lines)
        if index is None:
            report.add(ReportEntry(
                status="blocked", category="abilities", chrooked_id=chrooked_id,
                symbol=label, reason="no abilities_for line in base_stats file",
            ))
            continue

        # The abilities_for macro DEFINES ABIL_<SPECIES>_<ABILITY> symbols that
        # trainer/battle-tower data references by name. Swapping out an ability
        # something references would undefine its symbol and break the link —
        # keep that slot, write the rest, and say so.
        kept = _conflicting_slots(lines[index], replacements, referenced)
        for slot in kept:
            del replacements[_SLOT_ARGS[slot]]

        new_line = splice_args(lines[index], replacements) if replacements else lines[index]
        if new_line != lines[index]:
            lines[index] = new_line
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            changed.append(path)
        if kept:
            report.add(ReportEntry(
                status="partial", category="abilities", chrooked_id=chrooked_id,
                symbol=label,
                reason="kept slot(s) whose ability is referenced by target data: "
                + ", ".join(kept[slot] for slot in kept),
                partial_fields=tuple(kept),
            ))
        else:
            report.add(ReportEntry(
                status="applied", category="abilities", chrooked_id=chrooked_id, symbol=label,
            ))
    return changed


def _referenced_abil_symbols(target: Path) -> frozenset[str]:
    """All ABIL_* symbols referenced anywhere in the target's asm sources.

    Two reference shapes exist: literal tokens (db ABIL_SCYTHER_TECHNICIAN | ...)
    and macro-composed ones — `tr_extra STEADFAST` under `tr_mon 30, GENGAR ...`
    expands to ABIL_GENGAR_STEADFAST. Non-ability tr_extra args (SHINY, natures)
    compose symbols no abilities_for line ever defines, so over-collecting them
    is harmless. Definition sites (`ABIL_\\1_\\2` in the macro body) never match
    the literal pattern, so no exclusions are needed.
    """
    token = re.compile(r"\bABIL_[A-Z0-9_]+")
    tr_mon = re.compile(r"\s*tr_mon\s+[^,]+,\s*([A-Z0-9_]+)")
    tr_extra = re.compile(r"\s*tr_extra\s+(.+)")
    found: set[str] = set()
    for path in Path(target).rglob("*.asm"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        found.update(token.findall(text))
        if "tr_extra" not in text:
            continue
        species = None
        for line in text.splitlines():
            mon = tr_mon.match(line)
            if mon:
                species = mon.group(1)
                continue
            extra = tr_extra.match(line)
            if extra and species:
                for arg in extra.group(1).split(","):
                    found.add(f"ABIL_{species}_{arg.strip()}")
    return frozenset(found)


def _conflicting_slots(
    line: str, replacements: dict[int, str], referenced: frozenset[str]
) -> dict[str, str]:
    """Slots whose outgoing ability is referenced: {slot_name: ABIL_ symbol}."""
    args = [part.strip() for part in line.split(",")]
    species_const = args[0].split()[-1]  # "\tabilities_for BULBASAUR" -> BULBASAUR
    conflicts: dict[str, str] = {}
    for slot, argnum in _SLOT_ARGS.items():
        if argnum not in replacements or argnum - 1 >= len(args):
            continue
        outgoing = args[argnum - 1]
        symbol = f"ABIL_{species_const}_{outgoing}"
        if outgoing != replacements[argnum] and symbol in referenced:
            conflicts[slot] = symbol
    return conflicts


def _apply_ability_defs(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> list[Path]:
    changed = []
    names_path = target / _NAMES_FILE
    descs_path = target / _DESCS_FILE
    for chrooked_id, ability in sorted(ruleset.abilities.items()):
        symbol = resmap.ability(chrooked_id, dict(ability.aka), name=ability.name)
        if symbol is None:
            report.add(ReportEntry(
                status="blocked", category="ability", chrooked_id=chrooked_id,
                reason="no such ability in target; mechanics need engine code",
            ))
            continue

        label = _symbol_to_camel(symbol)
        name_result = _rewrite_name(names_path, label, ability.name)
        desc_result = "clean"
        if ability.description:
            desc_result = _rewrite_description(descs_path, label, ability.description)
        if name_result == "changed":
            changed.append(names_path)
        if desc_result == "changed":
            changed.append(descs_path)

        missing = [
            what for what, result in (("name", name_result), ("description", desc_result))
            if result == "missing"
        ]
        if missing:
            report.add(ReportEntry(
                status="partial", category="ability", chrooked_id=chrooked_id,
                symbol=symbol,
                reason=f"no {' / '.join(missing)} label for {label} in target files",
                partial_fields=tuple(missing),
            ))
        else:
            report.add(ReportEntry(
                status="applied", category="ability", chrooked_id=chrooked_id, symbol=symbol,
            ))
    return list(dict.fromkeys(changed))


def _find_abilities_line(lines: list[str]) -> int | None:
    labels = classify_lines(lines)
    for index, line in enumerate(lines):
        if line.startswith("\tabilities_for ") and labels[index] != FAITHFUL:
            return index
    return None


def _rewrite_name(path: Path, label: str, new_name: str) -> str:
    """Rewrite the `Label: rawchar "...@"` line; 'changed' / 'clean' / 'missing'."""
    lines = path.read_text(encoding="utf-8").splitlines()
    pattern = re.compile(rf'^({re.escape(label)}:\s*rawchar ")[^"]*(@")')
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match is None:
            continue
        replaced = match.group(1) + new_name + match.group(2) + line[match.end():]
        if replaced == line:
            return "clean"
        lines[index] = replaced
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return "changed"
    return "missing"


def _rewrite_description(path: Path, label: str, description: str) -> str:
    """Rewrite the text block under `LabelDescription:`; 'changed' / 'clean' / 'missing'."""
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index(f"{label}Description:") + 1
    except ValueError:
        return "missing"
    end = start
    while end < len(lines) and lines[end].strip() != "done":
        end += 1
    # RGBDS string literals cannot carry embedded double quotes.
    safe = description.replace('"', "'")
    wrapped = textwrap.wrap(safe, _DESC_WIDTH) or [""]
    new_lines = [f'\ttext "{wrapped[0]}"'] + [f'\tnext "{part}"' for part in wrapped[1:]]
    if lines[start:end] == new_lines:
        return "clean"
    lines[start:end] = new_lines
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "changed"


def _base_stats_path(target: Path, label: str) -> Path | None:
    """Find the species' base_stats file by normalized name match.

    Filenames are not mechanically derivable from labels (MrMimePlain lives in
    mr__mime_plain.asm — double underscore), so compare with all separators
    stripped: mrmimeplain == mrmimeplain.
    """
    want = re.sub(r"[^a-z0-9]", "", label.lower())
    for path in sorted((target / _BASE_STATS_DIR).glob("*.asm")):
        if re.sub(r"[^a-z0-9]", "", path.stem) == want:
            return path
    return None


def _symbol_to_camel(symbol: str) -> str:
    return "".join(part.capitalize() for part in symbol.split("_"))
