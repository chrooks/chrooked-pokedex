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
from . import behavior_install, behavior_triage
from .emit import (
    Sym, abiltext_delta, montext_delta, movetext_delta, to_ruby, typetext_delta,
)
from .init_script import INIT_SCRIPT
from .resolution import RejuvResolution

# Species scalars first, then learnset — parity with the other engines' tier order.
_CATEGORIES = ("abilities", "moves", "species", "type-chart", "behaviors")
_STAT_INDEX = {k: i for i, k in enumerate(STAT_KEYS)}


def apply_rejuv(
    target: Path,
    ruleset: Ruleset,
    report: ApplyReport,
    *,
    category: str = "all",
    behavior_source_dir: Path | None = None,
) -> set[Path]:
    """Write the patch/ delta files and return the set of paths written."""
    resolution = RejuvResolution.build(target)
    categories = _CATEGORIES if category == "all" else (category,)
    written: set[Path] = set()

    # Which behaviors will genuinely install battle code this run — abiltext may
    # only drop its DATA ONLY warning for these (honesty Invariant). A
    # category-limited run that skips "behaviors" installs nothing, so nothing
    # counts as implemented.
    implemented: set[str] = set()
    if "behaviors" in categories:
        implemented = {
            cid for cid in ruleset.behaviors
            if behavior_install.has_implementation(cid, behavior_source_dir)
        }

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
        text = _build_abiltext(ruleset, resolution, report, implemented)
        written.add(_write(defs_dir / "abiltext.rb", text))

    if "moves" in categories:
        text = _build_movetext(ruleset, resolution, report, implemented)
        written.add(_write(defs_dir / "movetext.rb", text))

    if "species" in categories:
        text = _build_montext(ruleset, resolution, known_abilities, known_moves, report)
        written.add(_write(defs_dir / "montext.rb", text))

    if "type-chart" in categories:
        text = _build_typetext(ruleset, report)
        written.add(_write(defs_dir / "typetext.rb", text))

    if "behaviors" in categories:
        rows = behavior_triage.triage(ruleset, resolution, implemented)
        _write(target / "rejuv-behavior-triage.md", behavior_triage.render_markdown(rows))
        written |= behavior_install.install_behaviors(
            target, ruleset, report, source_dir=behavior_source_dir
        )

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


# --- typetext ----------------------------------------------------------------

# multiplier -> which TYPEHASH bucket on the DEFENDER lists the attacker type.
_CHART_BUCKETS = {2: ":weaknesses", 0.5: ":resistances", 0: ":immunities"}


def _build_typetext(ruleset: Ruleset, report: ApplyReport) -> str:
    blocks: list[str] = []
    for override in ruleset.type_chart:
        atk = _type_sym(override.attacker)
        dfn = _type_sym(override.defender)
        mult = override.multiplier
        bucket = _CHART_BUCKETS.get(mult)
        if bucket is None and mult != 1:
            report.add(ReportEntry(
                status="blocked", category="type-chart",
                chrooked_id=f"{override.attacker}-vs-{override.defender}",
                reason=f"unsupported multiplier {mult} (chart holds 0/0.5/1/2 only)",
            ))
            continue
        blocks.append(
            f"[:weaknesses, :resistances, :immunities].each "
            f"{{ |k| TYPEHASH[:{dfn}][k]&.delete(:{atk}) }}"
        )
        if bucket:
            blocks.append(f"(TYPEHASH[:{dfn}][{bucket}] ||= []) << :{atk}")
        report.add(ReportEntry(
            status="applied", category="type-chart",
            chrooked_id=f"{override.attacker}-vs-{override.defender}",
            symbol=f"{atk}->{dfn} x{mult}",
        ))
    return typetext_delta(blocks)


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

# Vanilla function codes for full effect-set combos (Bite 0x00F, Fire Fang
# 0x00B, Ice Fang 0x00E, Thunder Fang 0x009). Keyed on the full
# additional-effect set with a single shared chance.
_FLINCH_COMBOS = {
    frozenset({"flinch"}): 0x00F,
    frozenset({"burn", "flinch"}): 0x00B,
    frozenset({"freeze", "flinch"}): 0x00E,
    frozenset({"paralysis", "flinch"}): 0x009,
}
# Primary `effect:` values that map onto a vanilla function code for EXISTING
# moves, with the :effect chance the code expects (Fake Out is 0x012:
# first-turn-only + guaranteed flinch, chance lives in :effect).
_PRIMARY_EFFECT_CODES = {"first_turn_only": (0x012, 100)}

# Vanilla function codes for one single secondary effect at :effect chance
# (Ember, Poison Sting, Thunder Shock, Ice Beam, Aurora Beam, Crush Claw,
# Moonblast, Acid/Psychic, Mud-Slap, Confusion).
_SINGLE_EFFECT_CODES = {
    "burn": 0x00A, "poison": 0x005, "paralysis": 0x007, "freeze": 0x00C,
    "flinch": 0x00F, "atk_minus_1": 0x042, "def_minus_1": 0x043,
    "sp_atk_minus_1": 0x045, "sp_def_minus_1": 0x046, "acc_minus_1": 0x047,
    "confusion": 0x013,
}


# The stat-drop fangs whose flinch leftover is the fangflinch behavior's job
# (see ruleset/behaviors/fangflinch.yaml).
_FANGFLINCH_MOVES = {"draconicfang", "lithicfang", "metallicfang", "tectonicfang", "lovelybite"}


def _build_movetext(
    ruleset: Ruleset,
    resolution: RejuvResolution,
    report: ApplyReport,
    implemented: set[str] = frozenset(),
) -> str:
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
            # ponytail: priority 0 is indistinguishable from "unset" in a
            # MoveDef, so only a nonzero priority is written.
            if move.priority:
                lines.append(f"MOVEHASH[:{sym}][:priority] = {move.priority}")
            if move.effect in _PRIMARY_EFFECT_CODES:
                code, chance = _PRIMARY_EFFECT_CODES[move.effect]
                lines.append(f"MOVEHASH[:{sym}][:function] = 0x{code:03X}")
                lines.append(f"MOVEHASH[:{sym}][:effect] = {chance}")
            blocks.extend(lines)
            report.add(ReportEntry(status="applied", category="move",
                                   chrooked_id=move.chrooked_id, symbol=sym))
        else:
            # New move — create a full MOVEHASH entry. Flinch combos map onto a
            # vanilla :function code (pure data); anything the code doesn't cover
            # stays honestly DATA ONLY.
            sym = resolution.move_symbol(move.name)
            function, chance, leftover = _function_for(move)
            blocks.append(_new_move_block(move, sym, next_id, function, chance))
            next_id += 1
            if not move.additional_effects:
                reason = None
            elif not leftover:
                reason = f"effects mapped to :function 0x{function:03X}"
            elif (leftover == ["flinch"] and "fangflinch" in implemented
                  and move.chrooked_id in _FANGFLINCH_MOVES):
                reason = (f"effects mapped to :function 0x{function:03X} "
                          "+ fangflinch mechanic (flinch)")
            elif function:
                reason = (f"partial via :function 0x{function:03X}; "
                          f"DATA ONLY: {', '.join(leftover)}")
            else:
                reason = f"DATA ONLY (effects need battle code: {', '.join(leftover)})"
            report.add(ReportEntry(status="applied", category="move",
                                   chrooked_id=move.chrooked_id, symbol=sym,
                                   reason=reason))
    return movetext_delta(blocks)


def _function_for(move) -> tuple[int, int | None, list[str]]:
    """(function code, :effect chance, effect names NOT covered by the code).

    A function code carries ONE shared chance, so a combo code only applies
    when every effect rolls at the same chance. A stat-drop+flinch pair (the
    chrooked fangs) takes the stat-drop code — the flinch leftover is the
    fangflinch behavior's job. Any other flinch pair keeps flinch (0x00F) and
    names the leftover.
    """
    names = frozenset(e.effect for e in move.additional_effects)
    chances = {e.chance for e in move.additional_effects}
    code = _FLINCH_COMBOS.get(names)
    if code is not None and len(chances) <= 1:
        return code, move.additional_effects[0].chance, []
    if len(names) == 1 and (only := next(iter(names))) in _SINGLE_EFFECT_CODES:
        return _SINGLE_EFFECT_CODES[only], move.additional_effects[0].chance, []
    if "flinch" in names:
        others = names - {"flinch"}
        mapped = [n for n in sorted(others) if n in _SINGLE_EFFECT_CODES]
        if len(others) == 1 and mapped:
            effect = next(e for e in move.additional_effects if e.effect == mapped[0])
            return _SINGLE_EFFECT_CODES[mapped[0]], effect.chance, ["flinch"]
        flinch = next(e for e in move.additional_effects if e.effect == "flinch")
        return 0x00F, flinch.chance, sorted(others)
    return 0x000, None, sorted(names)


def _new_move_block(
    move, sym: str, move_id: int, function: int = 0x000, effect_chance: int | None = None
) -> str:
    fields = [
        f":ID => {move_id}",
        f":name => {to_ruby(move.name)}",
        f":desc => {to_ruby(move.description or move.name)}",
        f":function => 0x{function:03X}",
        f":type => :{_type_sym(move.type)}",
        f":category => :{move.category}",
        f":basedamage => {move.power if move.power is not None else _CREATE_DEFAULTS['basedamage']}",
        f":accuracy => {move.accuracy if move.accuracy is not None else _CREATE_DEFAULTS['accuracy']}",
        f":maxpp => {move.pp if move.pp is not None else _CREATE_DEFAULTS['maxpp']}",
        f":target => :{_TARGET.get(move.target, 'SingleNonUser')}",
    ]
    if effect_chance is not None:
        fields.append(f":effect => {effect_chance}")
    for flag in move.flags:
        key = _FLAG.get(flag)
        if key:
            fields.append(f":{key} => true")
    return f"MOVEHASH[:{sym}] = {{ {', '.join(fields)} }}"


# --- abiltext ----------------------------------------------------------------

def _build_abiltext(
    ruleset: Ruleset,
    resolution: RejuvResolution,
    report: ApplyReport,
    implemented: set[str] = frozenset(),
) -> str:
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
            # New ability — DATA ONLY unless its mechanic installs this run.
            blocks.append(
                f"ABILHASH[:{sym}] = {{ :ID => {next_id}, "
                f":name => {to_ruby(ability.name)}, "
                f":desc => {to_ruby(ability.description)} }}"
            )
            next_id += 1
            reason = (
                "mechanic implemented (patch/Mods)"
                if ability.chrooked_id in implemented
                else "DATA ONLY (new ability; mechanic needs battle code)"
            )
            report.add(ReportEntry(status="applied", category="ability",
                                   chrooked_id=ability.chrooked_id, symbol=sym,
                                   reason=reason))
    return abiltext_delta(blocks)
