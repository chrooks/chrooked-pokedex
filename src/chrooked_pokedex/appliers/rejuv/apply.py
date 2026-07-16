"""Emit the Rejuvenation ``patch/`` from the Ruleset.

Data flows one way: Ruleset -> delta Ruby files under ``<target>/patch/``. Nothing
outside ``patch/`` (game data) is touched; uninstall is ``rm -rf patch/``. A
behavior triage report is written at the target root next to the Apply Report as
a meta artifact.

Everything that cannot resolve becomes an Apply Report entry (blocked/partial),
never a crash and never a fabricated symbol.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...model.schema import STAT_KEYS
from ...report import ApplyReport, ReportEntry
from . import behavior_triage
from .emit import Sym, abiltext_delta, montext_delta, movetext_delta, to_ruby
from .init_script import INIT_SCRIPT
from .resolution import RejuvResolution

# Species scalars first, then learnset — parity with the other engines' tier order.
_CATEGORIES = ("abilities", "moves", "species", "behaviors")
_STAT_INDEX = {k: i for i, k in enumerate(STAT_KEYS)}


def apply_rejuv(
    target: Path,
    ruleset: Ruleset,
    report: ApplyReport,
    *,
    category: str = "all",
) -> set[Path]:
    """Write the patch/ delta files and return the set of paths written."""
    resolution = RejuvResolution.build(target)
    categories = _CATEGORIES if category == "all" else (category,)
    written: set[Path] = set()

    # Ability symbols the Ruleset will make exist (base ∪ owned) — used to resolve
    # species ability slots that point at a brand-new Ruleset ability.
    known_abilities = set(resolution.ability_syms) | {
        resolution.ability_symbol(a.name) for a in ruleset.abilities.values()
    }

    defs_dir = target / "patch" / "Definitions"

    if "abilities" in categories:
        text = _build_abiltext(ruleset, resolution, report)
        written.add(_write(defs_dir / "abiltext.rb", text))

    if "moves" in categories:
        text = _build_movetext(ruleset, resolution, report)
        written.add(_write(defs_dir / "movetext.rb", text))

    if "species" in categories:
        text = _build_montext(ruleset, resolution, known_abilities, report)
        written.add(_write(defs_dir / "montext.rb", text))

    if "behaviors" in categories:
        rows = behavior_triage.triage(ruleset, resolution)
        _write(target / "rejuv-behavior-triage.md", behavior_triage.render_markdown(rows))

    # The Init compile trigger — always written so a category-limited run still
    # recompiles whatever delta it produced.
    written.add(_write(target / "patch" / "Init" / "chrooked_compile.rb", INIT_SCRIPT))
    return written


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- montext -----------------------------------------------------------------

def _build_montext(
    ruleset: Ruleset,
    resolution: RejuvResolution,
    known_abilities: set[str],
    report: ApplyReport,
) -> str:
    assignments: list[tuple[str, str, list[str]]] = []
    for species in ruleset.species.values():
        resolved = resolution.species(species.chrooked_id, species.aka)
        if resolved is None:
            report.add(ReportEntry(
                status="blocked", category="species", chrooked_id=species.chrooked_id,
                reason="no MONHASH key/form (preexisting mon only; add an aka.rejuv hint to rescue)",
            ))
            continue
        key, form = resolved
        lines, unresolved = _species_lines(species, resolution, known_abilities)
        if not lines:
            continue  # nothing to change for this species
        assignments.append((key, form, lines))
        report.add(ReportEntry(
            status="partial" if unresolved else "applied",
            category="species", chrooked_id=species.chrooked_id, symbol=f"{key}::{form}",
            partial_fields=tuple(unresolved),
        ))
    return montext_delta(assignments)


def _species_lines(species, resolution, known_abilities) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    unresolved: list[str] = []

    if species.stats:
        for stat, value in species.stats.items():
            lines.append(f"[:BaseStats][{_STAT_INDEX[stat]}] = {value}")

    if species.types:
        lines.append(f"[:Type1] = {to_ruby(Sym(_type_sym(species.types[0])))}")
        second = species.types[1] if len(species.types) > 1 else None
        lines.append(f"[:Type2] = {to_ruby(Sym(_type_sym(second)) if second else None)}")

    if species.abilities:
        for slot_idx, attr in ((0, "primary"), (1, "secondary")):
            name = getattr(species.abilities, attr)
            if name:
                sym = resolution.ability_symbol(name)
                if sym in known_abilities:
                    lines.append(f"[:Abilities][{slot_idx}] = :{sym}")
                else:
                    unresolved.append(f"ability:{name}")
        if species.abilities.hidden:
            sym = resolution.ability_symbol(species.abilities.hidden)
            if sym in known_abilities:
                lines.append(f"[:HiddenAbility] = :{sym}")
            else:
                unresolved.append(f"hidden:{species.abilities.hidden}")

    if species.learnset:
        pairs = []
        for lm in species.learnset:
            sym = resolution.move(lm.move)
            if sym is None:
                unresolved.append(f"move:{lm.move}")
                continue
            pairs.append([lm.level, Sym(sym)])
        lines.append(f"[:Moveset] = {to_ruby(pairs)}")

    return lines, unresolved


def _type_sym(name: str) -> str:
    from ...seed.neutralize import slug
    return slug(name).upper()


# --- movetext ----------------------------------------------------------------

_MOVE_SCALARS: tuple[tuple[str, str], ...] = (
    ("power", "basedamage"),
    ("accuracy", "accuracy"),
    ("pp", "maxpp"),
    ("description", "desc"),
)


def _build_movetext(ruleset: Ruleset, resolution: RejuvResolution, report: ApplyReport) -> str:
    blocks: list[str] = []
    for move in ruleset.moves.values():
        sym = resolution.move(move.name)
        if sym is None:
            report.add(ReportEntry(
                status="blocked", category="move", chrooked_id=move.chrooked_id,
                reason="move not in base MOVEHASH (creating new moves is out of scope)",
            ))
            continue
        lines = [f"MOVEHASH[:{sym}][:type] = :{_type_sym(move.type)}"]
        lines.append(f"MOVEHASH[:{sym}][:category] = :{move.category}")
        for attr, field in _MOVE_SCALARS:
            value = getattr(move, attr)
            if value is not None and value != "":
                lines.append(f"MOVEHASH[:{sym}][:{field}] = {to_ruby(value)}")
        blocks.extend(lines)
        report.add(ReportEntry(status="applied", category="move",
                               chrooked_id=move.chrooked_id, symbol=sym))
    return movetext_delta(blocks)


# --- abiltext ----------------------------------------------------------------

def _build_abiltext(ruleset: Ruleset, resolution: RejuvResolution, report: ApplyReport) -> str:
    next_id = resolution.max_ability_id + 1
    blocks: list[str] = []
    for ability in ruleset.abilities.values():
        sym = resolution.ability_symbol(ability.name)
        if sym in resolution.ability_syms:
            # Existing ability — patch its text only.
            blocks.append(f"ABILHASH[:{sym}][:name] = {to_ruby(ability.name)}")
            if ability.description:
                blocks.append(f"ABILHASH[:{sym}][:desc] = {to_ruby(ability.description)}")
            report.add(ReportEntry(status="applied", category="ability",
                                   chrooked_id=ability.chrooked_id, symbol=sym))
        else:
            # New ability — data-only (its mechanic still needs battle code).
            blocks.append(
                f"ABILHASH[:{sym}] = {{ :ID => {next_id}, "
                f":name => {to_ruby(ability.name)}, "
                f":desc => {to_ruby(ability.description)} }}"
            )
            next_id += 1
            report.add(ReportEntry(status="applied", category="ability",
                                   chrooked_id=ability.chrooked_id, symbol=sym,
                                   reason="DATA ONLY (new ability; mechanic needs battle code)"))
    return abiltext_delta(blocks)
