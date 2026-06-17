"""Apply evolution Overrides into a 16.2 species' flat `Evolutions=` line.

The 16.2 analogue of `appliers/essentials/evolution_apply.py`, with one format
difference: 16.2 stores ALL of a pre-evolution's branches on ONE flat line,
`Evolutions=SPECIES,Method,Param,SPECIES2,Method2,Param2,...` (comma-grouped triples),
where v21 writes one `Evolution=` line per branch.

The neutral schema stores an evolution as a backward pointer: species X carries
`evolution.from = Y`, meaning Y evolves into X. 16.2 stores it forward, on the
pre-evolution Y. So this applier collects every backward pointer, groups them by
pre-evolution, and rebuilds that source's whole `Evolutions=` line at once — the
whole-set replace is what stops a branching pre-evolution from clobbering itself.

Honesty over guessing: a source the resmap cannot resolve, or a method the vocab
cannot render, is reported (blocked/partial), never written as a token Essentials
would reject. A source with no renderable branch keeps its current line intact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Optional

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from ...seed.neutralize import slug
from ..essentials import vocab
from . import pbs_io, section_edit, section_read
from .resolution import ResolutionMap


def apply_evolutions(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    path = target / "PBS" / "pokemon.txt"
    if not path.exists():
        return set()
    text, had_bom = pbs_io.read(path)
    original = text

    existing = section_read.internal_names(text)
    groups = _group_by_source(ruleset, resmap, report, existing)
    for source_symbol in sorted(groups):
        triples, partial = groups[source_symbol]
        if section_edit.find_section_by_internalname(text, source_symbol) is None:
            report.add(ReportEntry(
                status="blocked", category="evolution", chrooked_id=source_symbol,
                symbol=source_symbol, reason="pre-evolution species not found",
            ))
            continue
        wrote = False
        if triples:
            line = ",".join(triples)
            span = section_edit.find_section_by_internalname(text, source_symbol)
            current = section_edit.get_field(text[span[0]:span[1]], "Evolutions")
            if current != line:
                text, _ = section_edit.set_section_field(
                    text, source_symbol, "Evolutions", line
                )
                wrote = True
        if wrote or partial:
            report.add(ReportEntry(
                status="partial" if partial else "applied", category="evolution",
                chrooked_id=source_symbol, symbol=source_symbol,
                reason="some branches not rendered" if partial else "",
                partial_fields=tuple(partial),
            ))

    if text != original:
        pbs_io.write(path, text, had_bom)
        return {path}
    return set()


def _group_by_source(
    ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport, existing: set[str]
) -> dict[str, tuple[list[str], list[str]]]:
    """Build `{source_symbol: (triple_tokens, unresolved_notes)}` from every backward
    `evolution.from` pointer. Each branch contributes a flat `SPECIES,Method,Param`
    triple; the source's line is the comma-join of its triples."""
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
            partials.setdefault(source_symbol, []).append(f"{chrooked_id}:unresolved_target")
            continue
        if target_symbol not in existing:
            # Target species absent from THIS game (e.g. a Galarian form like
            # WEEZINGGALAR that Africanus lacks). Writing the evolution would
            # reference an undefined PBSpecies and break compilation — drop the
            # branch and report it instead.
            report.add(ReportEntry(
                status="partial", category="evolution", chrooked_id=chrooked_id,
                symbol=target_symbol, reason="evolution target species not in target",
            ))
            partials.setdefault(source_symbol, []).append(f"{chrooked_id}:target_absent")
            continue

        triple = _render_triple(evo.method, target_symbol)
        if triple is None:
            partials.setdefault(source_symbol, []).append(f"{chrooked_id}:method")
            continue
        by_source.setdefault(source_symbol, []).extend(triple)

    groups: dict[str, tuple[list[str], list[str]]] = {}
    for source_symbol, triples in by_source.items():
        groups[source_symbol] = (triples, partials.get(source_symbol, []))
    for source_symbol, notes in partials.items():
        if source_symbol not in groups:
            groups[source_symbol] = ([], notes)
    return groups


def _resolve_source(
    from_species: str, ruleset: Ruleset, resmap: ResolutionMap
) -> Optional[str]:
    """The pre-evolution's INTERNAL name. Prefer its own Ruleset entry's `aka`; else a
    name-derived INTERNAL (the caller validates it really exists in the file)."""
    source_id = slug(from_species)
    source = ruleset.species.get(source_id)
    if source is not None:
        return resmap.species(source_id, dict(source.aka))
    return vocab.internal_name(from_species)


def _render_triple(method: Mapping[str, object], target_internal: str) -> Optional[list[str]]:
    """Render one branch as a flat `[SPECIES, Method, Param]` token list (joined into the
    source's `Evolutions=` line), or None for an unrenderable method.

    `level` and `item` are the clean common methods; anything else is carried by an
    explicit `essentials:` hint (with optional `param:`) so the ~40 engine-specific
    methods round-trip exactly. A method with none of these keys returns None (partial).
    """
    if "level" in method:
        return [target_internal, "Level", str(method["level"])]
    if "item" in method:
        return [target_internal, "Item", vocab.internal_name(str(method["item"]))]
    if "essentials" in method:
        name = str(method["essentials"])
        param = method.get("param")
        # Always emit a 3-token triple to keep the comma-grouped Evolutions= line
        # aligned. A param-less method writes an EMPTY param (trailing comma) —
        # matching the real 16.2 format, e.g. `BRAMBLEGHAST,Happiness,`.
        return [target_internal, name, "" if param is None else str(param)]
    return None
