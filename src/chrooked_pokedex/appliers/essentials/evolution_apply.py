"""Apply evolution Overrides into a species' `Evolution` lines in `pokemon.txt`.

The neutral schema stores an evolution as a backward pointer: species X carries
`evolution.from = Y`, meaning Y evolves into X. Both pokeemerald and Essentials store
it the other way — forward, on the pre-evolution Y — and Essentials writes one
`Evolution = SPECIES,METHOD,PARAM` line per branch (Eevee has ten). So this applier
collects every backward pointer, groups them by pre-evolution, and replaces that
source's whole set of `Evolution` lines at once. The whole-set replace is what stops
a branching pre-evolution (Eevee -> Vaporeon and Eevee -> Jolteon) from clobbering
itself one line at a time.

Honesty over guessing: a source the resmap cannot resolve, or a method the vocab
cannot render, is reported (blocked/partial), never written as a token Essentials
would reject. When a source has *no* renderable line at all, its existing lines are
left intact (not wiped to empty) and the miss is reported partial.

Runs alongside the other tiers; it owns `pokemon.txt`'s `Evolution` lines only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Optional

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from ...seed.neutralize import slug
from . import pbs_edit, vocab
from .resolution import ResolutionMap


def apply_evolutions(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    path = target / "PBS" / "pokemon.txt"
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    original = text

    groups = _group_by_source(ruleset, resmap, report)
    for source_symbol in sorted(groups):
        lines, partial = groups[source_symbol]
        if pbs_edit.find_section(text, source_symbol) is None:
            report.add(ReportEntry(
                status="blocked", category="evolution", chrooked_id=source_symbol,
                symbol=source_symbol, reason="pre-evolution species not found",
            ))
            continue
        # Only write when we have at least one renderable line. A source with nothing
        # renderable keeps its current lines rather than being wiped to empty.
        wrote = False
        if lines:
            text, wrote = pbs_edit.set_section_lines(text, source_symbol, "Evolution", lines)
        # Report a line only when something actually changed or a branch was flagged —
        # an already-matching source produces no write and no report line (no churn),
        # so "applied" in the report always means the file was modified.
        if wrote or partial:
            report.add(ReportEntry(
                status="partial" if partial else "applied", category="evolution",
                chrooked_id=source_symbol, symbol=source_symbol,
                reason="some branches not rendered" if partial else "",
                partial_fields=tuple(partial),
            ))

    if text != original:
        path.write_text(text, encoding="utf-8")
        return {path}
    return set()


def _group_by_source(
    ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> dict[str, tuple[list[str], list[str]]]:
    """Build `{source_symbol: (rendered_lines, unresolved_notes)}` from every backward
    `evolution.from` pointer. A source that only had unrenderable methods still gets an
    entry (empty lines, partial notes) so it is reported, never silently dropped."""
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
            # Also flag the source so its whole-set entry reads partial, not applied —
            # one of its intended branches did not make it into the written set.
            partials.setdefault(source_symbol, []).append(f"{chrooked_id}:unresolved_target")
            continue

        line = _render_line(evo.method, target_symbol)
        if line is None:
            partials.setdefault(source_symbol, []).append(f"{chrooked_id}:method")
            continue
        by_source.setdefault(source_symbol, []).append(line)

    groups: dict[str, tuple[list[str], list[str]]] = {}
    for source_symbol, lines in by_source.items():
        groups[source_symbol] = (lines, partials.get(source_symbol, []))
    for source_symbol, notes in partials.items():
        if source_symbol not in groups:
            groups[source_symbol] = ([], notes)
    return groups


def _resolve_source(
    from_species: str, ruleset: Ruleset, resmap: ResolutionMap
) -> Optional[str]:
    """The pre-evolution's INTERNAL name. Prefer its own Ruleset entry's `aka`; else
    fall back to a name-derived INTERNAL — `find_section` validates it really exists."""
    source_id = slug(from_species)
    source = ruleset.species.get(source_id)
    if source is not None:
        return resmap.species(source_id, dict(source.aka))
    return vocab.internal_name(from_species)


def _render_line(method: Mapping[str, object], target_internal: str) -> Optional[str]:
    """Render one `SPECIES,METHOD,PARAM` line, or None for an unrenderable method.

    `level` and `item` are the clean, common methods; anything else is carried by an
    explicit `essentials:` hint (with an optional `param:`) so the ~40 engine-specific
    methods round-trip exactly without being modeled one by one. A method with none of
    these keys returns None and is reported partial.
    """
    if "level" in method:
        return f"{target_internal},Level,{method['level']}"
    if "item" in method:
        return f"{target_internal},Item,{vocab.internal_name(str(method['item']))}"
    if "essentials" in method:
        name = method["essentials"]
        param = method.get("param")
        if param is not None:
            return f"{target_internal},{name},{param}"
        return f"{target_internal},{name}"
    return None
