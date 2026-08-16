"""Apply learnsets by replacing a species' whole level-up list outright.

This is the fix for v1's duplicate-move bug. v1 merged the Ruleset's moves into
the target's existing list, so a move present in both appeared twice. Here the
Ruleset owns the entire list: the target's array body is discarded and re-rendered
from the Ruleset, so a move can appear at most as many times as the Ruleset lists it.

pokeemerald-expansion defines the same learnset array (e.g. `sGoodraLevelUpLearnset`)
once per generation, each guarded by a `#if P_GEN_X` block. Only one is active at
compile time, but which one depends on the target's build config. To make the
Ruleset's list win regardless, every definition of the variable is replaced.

Moves the target lacks are not written (that would not compile). They are recorded
as partial; when a missing move is Ruleset-owned it is created in a later milestone,
after which a re-apply includes it.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...model import Ruleset
from ...model.holds import HoldSet
from ...report import ApplyReport, ReportEntry
from ...readers.pokeemerald.learnset_parser import _build_species_to_variable_map
from .resolution import ResolutionMap

_INDENT = "    "


def _learnset_files(target: Path) -> list[Path]:
    pokemon_dir = target / "src" / "data" / "pokemon"
    files: list[Path] = []
    flat = pokemon_dir / "level_up_learnsets.h"
    if flat.exists():
        files.append(flat)
    split_dir = pokemon_dir / "level_up_learnsets"
    if split_dir.exists():
        files.extend(sorted(split_dir.glob("*.h")))
    return files


def apply_learnsets(
    target: Path,
    ruleset: Ruleset,
    resmap: ResolutionMap,
    report: ApplyReport,
    holds: HoldSet | None = None,
) -> set[Path]:
    holds = holds or HoldSet()
    files = _learnset_files(target)
    texts: dict[Path, str] = {path: path.read_text(encoding="utf-8") for path in files}
    species_to_variable = _build_species_to_variable_map(target)
    changed: set[Path] = set()

    for chrooked_id in sorted(ruleset.species):
        override = ruleset.species[chrooked_id]
        if override.learnset is None:
            continue
        if holds.is_held(chrooked_id, "learnset"):
            report.add(ReportEntry(
                status="held", category="learnset", chrooked_id=chrooked_id,
                reason="target-pinned",
            ))
            continue

        symbol = resmap.species(chrooked_id, dict(override.aka))
        if symbol is None:
            report.add(ReportEntry(
                status="blocked", category="learnset", chrooked_id=chrooked_id,
                reason="no species symbol resolved",
            ))
            continue

        variable = species_to_variable.get(symbol)
        if variable is None:
            report.add(ReportEntry(
                status="blocked", category="learnset", chrooked_id=chrooked_id,
                symbol=symbol, reason="no learnset array for species",
            ))
            continue

        body, unresolved = _render_list(override.learnset, ruleset, resmap)
        for path in files:
            new_text = _replace_arrays(texts[path], variable, body)
            if new_text != texts[path]:
                texts[path] = new_text
                changed.add(path)

        if unresolved:
            report.add(ReportEntry(
                status="partial", category="learnset", chrooked_id=chrooked_id,
                symbol=symbol, reason="some moves not yet in target",
                partial_fields=tuple(unresolved),
            ))
        else:
            report.add(ReportEntry(
                status="applied", category="learnset", chrooked_id=chrooked_id,
                symbol=symbol,
            ))

    for path in changed:
        path.write_text(texts[path], encoding="utf-8")
    return changed


def _render_list(learnset, ruleset: Ruleset, resmap: ResolutionMap) -> tuple[str, list[str]]:
    lines: list[str] = []
    unresolved: list[str] = []
    for entry in learnset:
        symbol = resmap.move(entry.move)
        if symbol is None:
            owned = ruleset.owned_move(entry.move) is not None
            tag = "owned" if owned else "unknown"
            unresolved.append(f"move:{entry.move}({tag})")
            continue
        lines.append(f"{_INDENT}LEVEL_UP_MOVE({entry.level}, {symbol}),")
    lines.append(f"{_INDENT}LEVEL_UP_END")
    return "\n" + "\n".join(lines) + "\n", unresolved


def _replace_arrays(text: str, variable: str, new_body: str) -> str:
    """Replace the body of every `<variable>[] = { ... }` definition in text."""
    pattern = re.compile(re.escape(variable) + r"\s*\[\s*\]\s*=\s*\{")
    spans: list[tuple[int, int]] = []
    for match in pattern.finditer(text):
        open_brace = match.end() - 1
        close_brace = _find_matching_brace(text, open_brace)
        if close_brace is not None:
            spans.append((open_brace, close_brace))
    # Replace right-to-left so earlier indices stay valid.
    for open_brace, close_brace in reversed(spans):
        text = text[: open_brace + 1] + new_body + text[close_brace:]
    return text


def _find_matching_brace(text: str, open_index: int):
    depth = 0
    for pos in range(open_index, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return pos
    return None
