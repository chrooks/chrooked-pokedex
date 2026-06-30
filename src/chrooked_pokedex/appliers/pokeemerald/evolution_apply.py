"""Apply evolution Overrides into species_info `.evolutions` entries.

The neutral schema stores an evolution as a backward pointer: species X carries
`evolution.from = Y`, meaning Y evolves into X. pokeemerald stores it forward, on
the pre-evolution Y, and Y may evolve into several species. So the applier collects
every backward pointer, groups them by pre-evolution, and writes that source's
WHOLE `.evolutions` list at once — the same whole-list replace that learnsets use,
which is what stops a branching pre-evolution (e.g. Cubone -> Marowak and
Marowak-Alola) from clobbering itself one target at a time.

The pre-evolution `from` is matched to its Ruleset entry by slug, and that entry's
`aka` gives the exact symbol — so forms resolve correctly. A source the Ruleset
cannot resolve, or a method it cannot render, is reported (blocked/partial), never
guessed.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset, evolution_methods
from ...model.schema import SpeciesOverride
from ...report import ApplyReport, ReportEntry
from ...seed.neutralize import item_symbol, move_symbol, slug
from . import c_edit
from .resolution import ResolutionMap


def apply_evolutions(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    groups, blocked = _group_by_source(ruleset, resmap, report)

    files = _species_info_files(target)
    texts: dict[Path, str] = {path: path.read_text(encoding="utf-8") for path in files}
    changed: set[Path] = set()

    for source_symbol in sorted(groups):
        rendered, partial = groups[source_symbol]
        located = _locate(texts, source_symbol)
        if located is None:
            report.add(ReportEntry(
                status="blocked", category="evolution", chrooked_id=source_symbol,
                symbol=source_symbol, reason="pre-evolution species not found",
            ))
            continue
        path, span = located
        body = texts[path][span[0] + 1 : span[1]]
        new_body = c_edit.set_field_all(body, "evolutions", rendered)
        new_text = c_edit.replace_entry_body(texts[path], span, new_body)
        if new_text != texts[path]:
            texts[path] = new_text
            changed.add(path)
        status = "partial" if partial else "applied"
        report.add(ReportEntry(
            status=status, category="evolution", chrooked_id=source_symbol,
            symbol=source_symbol,
            reason="some methods/targets not rendered" if partial else "",
            partial_fields=tuple(partial),
        ))

    for path in changed:
        path.write_text(texts[path], encoding="utf-8")
    return changed


def _group_by_source(ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport):
    """Build {source_symbol: (rendered_EVOLUTION_text, unresolved_notes)}."""
    by_source: dict[str, list[str]] = {}
    partials: dict[str, list[str]] = {}

    for chrooked_id in sorted(ruleset.species):
        override = ruleset.species[chrooked_id]
        evo = override.evolution
        if evo is None or not evo.from_species:
            continue

        target_symbol = resmap.species(chrooked_id, dict(override.aka))
        source_symbol = _resolve_source(evo.from_species, ruleset, resmap)
        if source_symbol is None:
            report.add(ReportEntry(
                status="blocked", category="evolution", chrooked_id=chrooked_id,
                reason=f"unresolved pre-evolution {evo.from_species!r}",
            ))
            continue
        if target_symbol is None:
            report.add(ReportEntry(
                status="blocked", category="evolution", chrooked_id=chrooked_id,
                reason="unresolved evolved species symbol",
            ))
            continue

        rendered = _render_triple(evo.method, target_symbol)
        if rendered is None:
            partials.setdefault(source_symbol, []).append(f"{chrooked_id}:method")
            continue
        by_source.setdefault(source_symbol, []).append(rendered)

    groups: dict[str, tuple[str, list[str]]] = {}
    for source_symbol, triples in by_source.items():
        text = "EVOLUTION(" + ", ".join(triples) + ")"
        groups[source_symbol] = (text, partials.get(source_symbol, []))
    return groups, partials


def _resolve_source(from_species: str, ruleset: Ruleset, resmap: ResolutionMap):
    source_id = slug(from_species)
    source = ruleset.species.get(source_id)
    if source is not None:
        return resmap.species(source_id, dict(source.aka))
    return resmap.species_by_id.get(source_id)


def _render_triple(method: dict, target_symbol: str) -> str | None:
    if "level" in method:
        return f"{{EVO_LEVEL, {method['level']}, {target_symbol}}}"
    if "item" in method:
        return f"{{EVO_ITEM, {item_symbol(str(method['item']))}, {target_symbol}}}"
    canonical = evolution_methods.to_engine(method, "pokeemerald")
    if canonical is not None:
        token, value_kind, raw = canonical
        param = _pe_param(value_kind, raw)
        return f"{{{token}, {param}, {target_symbol}}}"
    if "pokeemerald" in method:
        param = method.get("param", "0")
        return f"{{{method['pokeemerald']}, {param}, {target_symbol}}}"
    return None


def _pe_param(value_kind: str, raw: str) -> str:
    """Render a canonical method's param as a pokeemerald token."""
    if value_kind == "none":
        return "0"
    if value_kind == "item":
        return item_symbol(raw)
    if value_kind == "move":
        return move_symbol(raw)
    if value_kind == "map":
        return raw.upper()
    return raw  # level: the integer as-is


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
