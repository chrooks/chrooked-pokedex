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

import re
from dataclasses import dataclass
from pathlib import Path

from ...model import Ruleset, evolution_methods
from ...model.schema import SpeciesOverride
from ...report import ApplyReport, ReportEntry
from ...seed.neutralize import item_symbol, move_symbol, slug
from . import c_edit
from .resolution import ResolutionMap


@dataclass(frozen=True)
class _EvoDialect:
    """What the target's evolution layer declares. Forks prune EVO_* methods
    (soulgold keeps 9 of expansion's ~30) and item constants must be the target's
    own — writing an undeclared token breaks the ROM build, not just the apply."""

    # None = constants file not found, don't validate.
    known_methods: frozenset[str] | None = None
    # normalized ("LEAFSTONE") -> declared symbol ("ITEM_LEAF_STONE"); None = no file.
    items_normalized: dict[str, str] | None = None

    def supports_method(self, token: str) -> bool:
        return self.known_methods is None or token in self.known_methods

    def resolve_item(self, name: str) -> str | None:
        """Neutral item name -> the target's declared ITEM_* symbol (underscore- and
        space-insensitive), or the constructed symbol when no item table was found."""
        constructed = item_symbol(name)
        if self.items_normalized is None:
            return constructed
        return self.items_normalized.get(_squash(constructed.removeprefix("ITEM_")))


def _squash(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _detect_evo_dialect(target: Path) -> _EvoDialect:
    known_methods = None
    constants = target / "include" / "constants" / "pokemon.h"
    if constants.exists():
        text = constants.read_text(encoding="utf-8", errors="replace")
        tokens = frozenset(
            t for t in re.findall(r"\bEVO_[A-Z0-9_]+\b", text)
            if not t.startswith("EVO_MODE_")
        )
        known_methods = tokens or None
    items_normalized = None
    items_h = target / "include" / "constants" / "items.h"
    if items_h.exists():
        text = items_h.read_text(encoding="utf-8", errors="replace")
        items_normalized = {
            _squash(sym.removeprefix("ITEM_")): sym
            for sym in sorted(set(re.findall(r"\bITEM_[A-Z0-9_]+\b", text)))
        }
    return _EvoDialect(known_methods=known_methods, items_normalized=items_normalized)


def apply_evolutions(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    dialect = _detect_evo_dialect(target)
    groups, blocked = _group_by_source(ruleset, resmap, report, dialect)

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


def _group_by_source(
    ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport,
    dialect: _EvoDialect | None = None,
):
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

        rendered = _render_triple(evo.method, target_symbol, dialect or _EvoDialect())
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


def _render_triple(
    method: dict, target_symbol: str, dialect: _EvoDialect = _EvoDialect()
) -> str | None:
    if "level" in method:
        return f"{{EVO_LEVEL, {method['level']}, {target_symbol}}}"
    if "item" in method:
        item = dialect.resolve_item(str(method["item"]))
        if item is None or not dialect.supports_method("EVO_ITEM"):
            return None
        return f"{{EVO_ITEM, {item}, {target_symbol}}}"
    canonical = evolution_methods.to_engine(method, "pokeemerald")
    if canonical is not None:
        token, value_kind, raw = canonical
        if not dialect.supports_method(token):
            return None
        param = _pe_param(value_kind, raw, dialect)
        if param is None:
            return None
        return f"{{{token}, {param}, {target_symbol}}}"
    if "pokeemerald" in method:
        if not dialect.supports_method(str(method["pokeemerald"])):
            return None
        param = method.get("param", "0")
        return f"{{{method['pokeemerald']}, {param}, {target_symbol}}}"
    return None


def _pe_param(value_kind: str, raw: str, dialect: _EvoDialect) -> str | None:
    """Render a canonical method's param as a pokeemerald token; None = the
    target cannot express it (unknown item)."""
    if value_kind == "none":
        return "0"
    if value_kind == "item":
        return dialect.resolve_item(raw)
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
