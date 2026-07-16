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

    # Symbols the Ruleset will make exist (base ∪ owned) — used to resolve species
    # slots/learnset entries that point at a brand-new Ruleset ability or move.
    known_abilities = set(resolution.ability_syms) | {
        resolution.ability_symbol(a.name) for a in ruleset.abilities.values()
    }
    known_moves = set(resolution.move_syms) | {
        resolution.move_symbol(m.name) for m in ruleset.moves.values()
    }

    defs_dir = target / "patch" / "Definitions"

    if "abilities" in categories:
        text = _build_abiltext(ruleset, resolution, report)
        written.add(_write(defs_dir / "abiltext.rb", text))

    if "moves" in categories:
        text = _build_movetext(ruleset, resolution, report)
        written.add(_write(defs_dir / "movetext.rb", text))

    if "species" in categories:
        text = _build_montext(ruleset, resolution, known_abilities, known_moves, report)
        written.add(_write(defs_dir / "montext.rb", text))

    if "behaviors" in categories:
        rows = behavior_triage.triage(ruleset, resolution)
        _write(target / "rejuv-behavior-triage.md", behavior_triage.render_markdown(rows))

    # The compiler writes patch/Data/*.dat on boot; create the folder now so the
    # first compile has somewhere to land (the Init script also self-heals it).
    (target / "patch" / "Data").mkdir(parents=True, exist_ok=True)

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
    known_moves: set[str],
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
        base_form = resolution.monhash[key][0]
        stmts, unresolved = _species_lines(
            species, key, form, base_form, resolution, known_abilities, known_moves
        )
        if not stmts:
            continue  # nothing to change for this species
        assignments.append((key, form, stmts))
        report.add(ReportEntry(
            status="partial" if unresolved else "applied",
            category="species", chrooked_id=species.chrooked_id, symbol=f"{key}::{form}",
            partial_fields=tuple(unresolved),
        ))
    return montext_delta(assignments)


def _species_lines(
    species, key, form, base_form, resolution, known_abilities, known_moves
) -> tuple[list[str], list[str]]:
    """Full Ruby statements for one resolved species/form.

    Per-INDEX assignments (``[:BaseStats][i]``, ``[:Abilities][i]``) target arrays
    that a non-base form may not carry — it inherits them from ``base_form`` at
    compile. Seeding the array from the base form with ``||=`` before indexing
    avoids a ``nil[]=`` crash and preserves the untouched slots. Whole-value
    assignments (``[:Type1]``, ``[:HiddenAbility]``, ``[:Moveset]``) create the key
    outright and need no seed.
    """
    ref = f'MONHASH[:{key}]["{form}"]'
    base_ref = f'MONHASH[:{key}]["{base_form}"]'
    stmts: list[str] = []
    unresolved: list[str] = []

    if species.stats:
        stmts.append(f"{ref}[:BaseStats] ||= {base_ref}[:BaseStats].dup")
        for stat, value in species.stats.items():
            stmts.append(f"{ref}[:BaseStats][{_STAT_INDEX[stat]}] = {value}")

    if species.types:
        stmts.append(f"{ref}[:Type1] = {to_ruby(Sym(_type_sym(species.types[0])))}")
        second = species.types[1] if len(species.types) > 1 else None
        stmts.append(f"{ref}[:Type2] = {to_ruby(Sym(_type_sym(second)) if second else None)}")

    if species.abilities:
        ability_slots = [
            (idx, getattr(species.abilities, attr))
            for idx, attr in ((0, "primary"), (1, "secondary"))
        ]
        if any(name for _, name in ability_slots):
            stmts.append(f"{ref}[:Abilities] ||= {base_ref}[:Abilities].dup")
        for slot_idx, name in ability_slots:
            if not name:
                continue
            sym = resolution.ability_symbol(name)
            if sym in known_abilities:
                stmts.append(f"{ref}[:Abilities][{slot_idx}] = :{sym}")
            else:
                unresolved.append(f"ability:{name}")
        if species.abilities.hidden:
            sym = resolution.ability_symbol(species.abilities.hidden)
            if sym in known_abilities:
                stmts.append(f"{ref}[:HiddenAbility] = :{sym}")
            else:
                unresolved.append(f"hidden:{species.abilities.hidden}")

    if species.learnset:
        pairs = []
        for lm in species.learnset:
            sym = resolution.move_symbol(lm.move)
            if sym not in known_moves:
                unresolved.append(f"move:{lm.move}")
                continue
            pairs.append([lm.level, Sym(sym)])
        stmts.append(f"{ref}[:Moveset] = {to_ruby(pairs)}")

    return stmts, unresolved


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

# Neutral move target -> Rejuv :target symbol. "both" means both foes (Overdrive,
# Twister). Anything unlisted falls back to :SingleNonUser.
_TARGET = {"selected": "SingleNonUser", "user": "User", "both": "AllOpposing"}
# Neutral move flag -> Rejuv bool key. Flags with no Rejuv counterpart (hammer,
# bone, wing, piercing) are simply not set — they carry no standard Rejuv flag.
_FLAG = {
    "contact": "contact", "punching": "punchmove", "biting": "bitingmove",
    "sound": "soundmove", "slicing": "sharpmove", "wind": "windmove",
    "ballistic": "ballmove", "kicking": "kickmove",
}
# Creation defaults for a scalar a MoveDef leaves as None (all 23 current
# creation moves carry full numbers; these guard a future sparse def).
# ponytail: flat defaults — tune in the Ruleset if a created move needs otherwise.
_CREATE_DEFAULTS = {"basedamage": 0, "accuracy": 100, "maxpp": 5}


def _build_movetext(ruleset: Ruleset, resolution: RejuvResolution, report: ApplyReport) -> str:
    next_id = resolution.max_move_id + 1
    blocks: list[str] = []
    for move in ruleset.moves.values():
        sym = resolution.move(move.name)
        if sym is not None:
            # Existing move — patch its scalars in place.
            lines = [f"MOVEHASH[:{sym}][:type] = :{_type_sym(move.type)}",
                     f"MOVEHASH[:{sym}][:category] = :{move.category}"]
            for attr, field in _MOVE_SCALARS:
                value = getattr(move, attr)
                if value is not None and value != "":
                    lines.append(f"MOVEHASH[:{sym}][:{field}] = {to_ruby(value)}")
            blocks.extend(lines)
            report.add(ReportEntry(status="applied", category="move",
                                   chrooked_id=move.chrooked_id, symbol=sym))
        else:
            # New move — create a full MOVEHASH entry with :function 0x000 (plain
            # damage). Its scripted effect, if any, is DATA ONLY until behavior code
            # lands (phase 3).
            sym = resolution.move_symbol(move.name)
            blocks.append(_new_move_block(move, sym, next_id))
            next_id += 1
            report.add(ReportEntry(status="applied", category="move",
                                   chrooked_id=move.chrooked_id, symbol=sym,
                                   reason="DATA ONLY (new move; :function 0x000, effect needs battle code)"))
    return movetext_delta(blocks)


def _new_move_block(move, sym: str, move_id: int) -> str:
    fields = [
        f":ID => {move_id}",
        f":name => {to_ruby(move.name)}",
        f":desc => {to_ruby(move.description or move.name)}",
        ":function => 0x000",
        f":type => :{_type_sym(move.type)}",
        f":category => :{move.category}",
        f":basedamage => {move.power if move.power is not None else _CREATE_DEFAULTS['basedamage']}",
        f":accuracy => {move.accuracy if move.accuracy is not None else _CREATE_DEFAULTS['accuracy']}",
        f":maxpp => {move.pp if move.pp is not None else _CREATE_DEFAULTS['maxpp']}",
        f":target => :{_TARGET.get(move.target, 'SingleNonUser')}",
    ]
    for flag in move.flags:
        key = _FLAG.get(flag)
        if key:
            fields.append(f":{key} => true")
    return f"MOVEHASH[:{sym}] = {{ {', '.join(fields)} }}"


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
