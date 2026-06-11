"""Apply evolution Overrides into species_info `.evolutions` entries.

The neutral schema stores an evolution as a backward pointer: species X carries
`evolution.from = Y`, meaning Y evolves into X. pokeemerald stores it forward, on
the pre-evolution, so this rewrites Y's `.evolutions` field to evolve into X.

The real seeded Ruleset carries no evolution data (Milestone 2 deferred it), so
this fires only on Rulesets that hand-author evolutions. It supports the common
EVO_LEVEL and EVO_ITEM methods; anything else is reported partial rather than
guessed.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from ...seed.neutralize import slug
from . import c_edit


def apply_evolutions(target: Path, ruleset: Ruleset, report: ApplyReport) -> set[Path]:
    files = _species_info_files(target)
    texts: dict[Path, str] = {path: path.read_text(encoding="utf-8") for path in files}
    changed: set[Path] = set()

    for chrooked_id in sorted(ruleset.species):
        override = ruleset.species[chrooked_id]
        if override.evolution is None or not override.evolution.from_species:
            continue

        this_symbol = (override.aka or {}).get("pokeemerald") or (
            "SPECIES_" + chrooked_id.upper()
        )
        pre_symbol = "SPECIES_" + slug(override.evolution.from_species).upper()
        rendered = _render_evolution(override.evolution.method, this_symbol)
        if rendered is None:
            report.add(ReportEntry(
                status="partial", category="evolution", chrooked_id=chrooked_id,
                reason="unsupported evolution method",
            ))
            continue

        located = _locate(texts, pre_symbol)
        if located is None:
            report.add(ReportEntry(
                status="blocked", category="evolution", chrooked_id=chrooked_id,
                symbol=pre_symbol, reason="pre-evolution species not found",
            ))
            continue

        path, span = located
        body = texts[path][span[0] + 1 : span[1]]
        new_body = c_edit.set_field(body, "evolutions", rendered)
        new_text = c_edit.replace_entry_body(texts[path], span, new_body)
        if new_text != texts[path]:
            texts[path] = new_text
            changed.add(path)
        report.add(ReportEntry(
            status="applied", category="evolution", chrooked_id=chrooked_id,
            symbol=pre_symbol,
        ))

    for path in changed:
        path.write_text(texts[path], encoding="utf-8")
    return changed


def _render_evolution(method: dict, target_symbol: str) -> str | None:
    if "level" in method:
        return f"EVOLUTION({{EVO_LEVEL, {method['level']}, {target_symbol}}})"
    if "item" in method:
        item = "ITEM_" + slug(str(method["item"])).upper()
        return f"EVOLUTION({{EVO_ITEM, {item}, {target_symbol}}})"
    return None


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


def _locate(texts: dict[Path, str], symbol: str):
    for path, text in texts.items():
        span = c_edit.find_species_entry(text, symbol)
        if span is not None:
            return path, span
    return None
