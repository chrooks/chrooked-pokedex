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
from ...model.schema import DEFAULT_EFFECT, STAT_KEYS
from ...report import ApplyReport, ReportEntry
from . import behavior_install, compose, behavior_triage
from ...model.schema import composed_behaviors, is_composed
from .emit import (
    Sym, abiltext_delta, itemtext_delta, montext_delta, movetext_delta, ruby_sym,
    to_ruby, typetext_delta,
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
        # A COMPOSED ability is implemented by its parts, not by a mod of its
        # own — chrooked_zz_zcompose.rb makes the holder a set, so the parts'
        # vanilla checks and chrooked tables both fire. Counting it as DATA ONLY
        # would cry wolf on every combo, and this warning only works if it is
        # never wrong. The honesty Invariant still holds: a part that is itself
        # a Ruleset behavior must have a real implementation, so a combo built
        # on an uninstalled mechanic still warns.
        for ability in ruleset.abilities.values():
            if not is_composed(ability):
                continue
            parts = composed_behaviors(ability)
            if all(
                part not in ruleset.behaviors or part in implemented
                for part in parts
            ):
                implemented.add(ability.chrooked_id)

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
        text, evo_items = _build_montext(
            ruleset, resolution, known_abilities, known_moves, report
        )
        written.add(_write(defs_dir / "montext.rb", text))
        # Item evolutions need the item usable from the bag: clear :noUse in the
        # item data, and register it as an evolution stone (EVOSTONES membership
        # + the Fire Stone UseOnPokemon handler) via a generated mod. Both files
        # are always written so removing the last item evolution self-heals.
        written.add(_write(defs_dir / "itemtext.rb", _build_itemtext(evo_items)))
        written.add(_write(
            target / "patch" / "Mods" / "chrooked_zz_evoitems.rb",
            _build_evoitem_mod(evo_items),
        ))

    if "type-chart" in categories:
        text = _build_typetext(ruleset, report)
        written.add(_write(defs_dir / "typetext.rb", text))

    if "behaviors" in categories:
        rows = behavior_triage.triage(ruleset, resolution, implemented)
        _write(target / "rejuv-behavior-triage.md", behavior_triage.render_markdown(rows))
        written |= behavior_install.install_behaviors(
            target, ruleset, report, source_dir=behavior_source_dir
        )
        # Abilities built from several behaviors. Written even when the table is
        # empty so a target cannot keep a stale one — apply never prunes mods.
        written.add(_write(
            target / "patch" / "Mods" / compose.MOD_NAME,
            compose.render_compose_mod(ruleset),
        ))

    # Static mods (chrooked_zz_*.rb) — self-contained UI/mechanic tweaks that are
    # not Ruleset behaviors, so they install unconditionally on every apply.
    written |= _install_static_mods(target, behavior_source_dir)

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


def _install_static_mods(target: Path, source_dir: Path | None) -> set[Path]:
    """Copy every chrooked_zz_*.rb into patch/Mods/ verbatim.

    These are self-contained script mods (no dependency on the behavior core),
    unlike behavior files which need chrooked_00_core.rb's tables.
    """
    src_root = source_dir or behavior_install._DEFAULT_SOURCE_DIR
    mods_dir = target / "patch" / "Mods"
    written: set[Path] = set()
    for src in sorted(src_root.glob("chrooked_zz_*.rb")):
        dest = mods_dir / src.name
        mods_dir.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        written.add(dest)
    return written


# --- montext -----------------------------------------------------------------

def _build_montext(
    ruleset: Ruleset,
    resolution: RejuvResolution,
    known_abilities: set[str],
    known_moves: set[str],
    report: ApplyReport,
) -> tuple[str, set[str]]:
    """(montext delta text, item symbols used by applied item evolutions)."""
    # Evolutions are keyed by the PRE-evolution, which is usually a different
    # species from the one carrying the Override — collect them up front so each
    # source's statements ride inside its own dig guard below.
    evo_stmts, evo_items = _evolution_statements(ruleset, resolution, report)

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
        # This species may also be some other species' pre-evolution; fold those
        # statements in here so the pair shares one dig guard.
        stmts = stmts + evo_stmts.pop((key, form), [])
        if not stmts:
            continue  # nothing to change for this species
        assignments.append((key, form, stmts))
        report.add(ReportEntry(
            status="partial" if unresolved else "applied",
            category="species", chrooked_id=species.chrooked_id, symbol=f"{key}::{form}",
            partial_fields=tuple(unresolved),
        ))

    # A pre-evolution with no Override of its own still needs its block emitted.
    for (key, form), stmts in evo_stmts.items():
        assignments.append((key, form, stmts))
    return montext_delta(assignments), evo_items


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
    ref = f'MONHASH[{ruby_sym(key)}]["{form}"]'
    base_ref = f'MONHASH[{ruby_sym(key)}]["{base_form}"]'
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
                stmts.append(f"{ref}[:Abilities][{slot_idx}] = {ruby_sym(sym)}")
            else:
                unresolved.append(f"ability:{name}")
        if species.abilities.hidden:
            sym = resolution.ability_symbol(species.abilities.hidden)
            if sym in known_abilities:
                stmts.append(f"{ref}[:HiddenAbility] = {ruby_sym(sym)}")
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


def _evolution_statements(
    ruleset: Ruleset, resolution: RejuvResolution, report: ApplyReport
) -> tuple[dict[tuple[str, str], list[str]], set[str]]:
    """Ruby statements that write each evolution onto its PRE-evolution's entry.

    The neutral schema points backward (species X carries ``evolution.from = Y``)
    while Rejuv stores the edge forward, in Y's ``:evolutions`` array — so every
    statement here targets the source, not the species that owns the Override.

    Each statement rewrites only its own branch: it rejects any existing entry
    aimed at the same target species, then appends ours. A pre-evolution that
    branches (Eevee) keeps the branches the Ruleset never mentions, including
    ones that exist only in the base game and are therefore invisible to us.
    """
    from ...model import evolution_methods

    stmts: dict[tuple[str, str], list[str]] = {}
    item_syms: set[str] = set()
    for chrooked_id in sorted(ruleset.species):
        species = ruleset.species[chrooked_id]
        evo = species.evolution
        if evo is None or not evo.from_species:
            continue

        target = resolution.species(chrooked_id, species.aka)
        if target is None:
            report.add(ReportEntry(
                status="blocked", category="evolution", chrooked_id=chrooked_id,
                reason="no MONHASH key/form for the evolved species",
            ))
            continue

        source_id = _slug(evo.from_species)
        source_aka = ruleset.species[source_id].aka if source_id in ruleset.species else {}
        source = resolution.species(source_id, source_aka)
        if source is None:
            report.add(ReportEntry(
                status="blocked", category="evolution", chrooked_id=chrooked_id,
                reason=f"unresolved pre-evolution {evo.from_species!r}",
            ))
            continue

        target_form = resolution.monhash[target[0]].index(target[1])
        rendered, item_sym = _render_evolution(
            evo.method, target[0], target_form, resolution, evolution_methods
        )
        if rendered is None:
            report.add(ReportEntry(
                status="blocked", category="evolution", chrooked_id=chrooked_id,
                symbol=f"{source[0]}::{source[1]}",
                reason=f"evolution method not renderable for rejuv: {dict(evo.method)}",
            ))
            continue

        # Rejuv keys a branch by (species, form): Rockruff carries three separate
        # edges to LYCANROC forms 0/1/2, Petilil two to LILLIGANT 0/1. Rejecting
        # on the species symbol alone would collapse every sibling branch into
        # ours, silently deleting the regional/alternate-form evolutions.
        ref = f'MONHASH[{ruby_sym(source[0])}]["{source[1]}"][:evolutions]'
        stmts.setdefault(source, []).append(
            f"{ref} = ({ref} || []).reject {{ |e| "
            f"e[:species] == :{target[0]} && (e[:form] || 0) == {target_form} }}"
            f" + [{rendered}]"
        )
        if item_sym is not None:
            item_syms.add(item_sym)
        report.add(ReportEntry(
            status="applied", category="evolution", chrooked_id=chrooked_id,
            symbol=f"{source[0]}::{source[1]}",
        ))
    return stmts, item_syms


def _render_evolution(
    method, target_symbol: str, target_form: int, resolution, evolution_methods
) -> tuple[str | None, str | None]:
    """(Ruby hash literal or None, evolution item symbol or None).

    The rendered literal is None when the method has no Rejuv rendering. The
    item symbol is set only for item-use methods, so the caller can make that
    item bag-usable (clear :noUse + register the evolution-stone handler).

    Rejuv is Essentials-derived, so the canonical vocabulary's ``essentials``
    token is the right one. A method carrying only a ``pokeemerald:`` hint has no
    Rejuv equivalent — it returns None and the caller reports it blocked rather
    than guessing a token.

    ``form:`` is always written, matching the reject predicate that pairs with it.
    ponytail: the base game omits ``form:`` on some edges, which makes them
    form-inheriting (Mega Absol's edge lands on Mega Charizard X). Ours are
    explicit instead, because we know the exact target form — an Override that
    wants inheriting behavior would need a new method flag.
    """
    head = f"{{ species: :{target_symbol}, form: {target_form}, method: "
    if "level" in method:
        return f"{head}:Level, parameter: {int(method['level'])} }}", None
    if "item" in method:
        sym = _type_sym(str(method["item"]))
        return f"{head}:Item, parameter: {ruby_sym(sym)} }}", sym

    canonical = evolution_methods.to_engine(method, "essentials")
    if canonical is None:
        return None, None
    token, value_kind, raw = canonical
    if value_kind == "none":
        return f"{head}:{token} }}", None
    if value_kind == "level":
        return f"{head}:{token}, parameter: {int(raw)} }}", None
    if value_kind == "move":
        return f"{head}:{token}, parameter: :{resolution.move_symbol(str(raw))} }}", None
    if value_kind == "item":
        sym = _type_sym(str(raw))
        item_use = token == "Item"
        return f"{head}:{token}, parameter: {ruby_sym(sym)} }}", (sym if item_use else None)
    return None, None


def _slug(name: str) -> str:
    from ...seed.neutralize import slug
    return slug(name)


def _build_itemtext(item_syms: set[str]) -> str:
    """Clear ``:noUse`` on every applied evolution item so the bag offers Use.

    Trade-evolution items (Sachet, Whipped Dream, ...) ship with ``:noUse``
    because the base game only holds them; an Item-method evolution needs them
    usable on a Pokémon.
    """
    blocks = [
        f"ITEMHASH[{ruby_sym(sym)}].delete(:noUse) if ITEMHASH[{ruby_sym(sym)}]"
        for sym in sorted(item_syms)
    ]
    return itemtext_delta(blocks)


def _build_evoitem_mod(item_syms: set[str]) -> str:
    """The ``patch/Mods`` script that makes evolution items act like stones.

    The bag's use path only evolves via items in the hardcoded ``EVOSTONES``
    list, which also carries the shared ``UseOnPokemon`` handler (see the
    game's ``ItemEffects.rb``). Mods load after ItemEffects, so appending here
    picks up both the handler copy and the Able/Not Able party annotations.

    The items.dat recompile also lives here rather than in the Init script:
    ``compileItems`` references ``PBStats``, which only exists once the main
    game scripts have loaded — Init runs before them, Mods run after (and
    still before the cache first reads items.dat).
    """
    items = ", ".join(ruby_sym(sym) for sym in sorted(item_syms))
    return (
        "# Generated by chrooked-pokedex — do not hand-edit.\n"
        "# Register Ruleset evolution items as bag-usable evolution stones.\n"
        f"[{items}].each do |item|\n"
        "  next if EVOSTONES.include?(item)\n"
        "  EVOSTONES.push(item)\n"
        "  ItemHandlers::UseOnPokemon.copy(:FIRESTONE, item)\n"
        "end\n"
        "\n"
        "# Recompile items.dat when the patched item definitions are newer.\n"
        "# Runs here (not patch/Init) because compileItems needs PBStats,\n"
        "# which the main scripts define after Init but before Mods.\n"
        "begin\n"
        '  defn = "patch/Definitions/itemtext.rb"\n'
        '  dat = "patch/Data/items.dat"\n'
        "  if File.exist?(defn) && (!File.exist?(dat) || File.mtime(defn) > File.mtime(dat))\n"
        '    Dir.mkdir("patch/Data") unless File.directory?("patch/Data")\n'
        "    compileItems\n"
        "  end\n"
        "rescue => e\n"
        '  dp("chrooked item compile failed: #{e.message}") if defined?(dp)\n'
        "end\n"
    )


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
_TARGET = {"selected": "SingleNonUser", "user": "User", "both": "AllOpposing",
           # Boomburst's target — hits both foes AND your own ally. Missing here
           # meant every foes_and_ally move degraded to single-target silently.
           # PLURAL: Battler.rb#pbTargets cases on :AllNonUsers, and an unknown
           # symbol falls out of that case with an EMPTY target list — the move
           # deals no damage while its function code still fires.
           "foes_and_ally": "AllNonUsers"}
# Neutral move flag -> Rejuv bool key. Flags with no Rejuv counterpart (hammer,
# bone, wing, piercing) are simply not set — they carry no standard Rejuv flag.
_FLAG = {
    "contact": "contact", "punching": "punchmove", "biting": "bitingmove",
    "sound": "soundmove", "slicing": "sharpmove", "wind": "windmove",
    "ballistic": "ballmove", "kicking": "kickmove", "pulse": "pulsemove",
    "high_crit": "highcrit",
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
    frozenset({"frostbite", "flinch"}): 0x00E,
    frozenset({"paralysis", "flinch"}): 0x009,
}
# Primary `effect:` values that map onto a vanilla function code, with the
# :effect chance the code expects (Fake Out is 0x012: first-turn-only +
# guaranteed flinch, chance lives in :effect; None means no :effect field).
# Consulted for existing-move patches AND new-move creation.
_PRIMARY_EFFECT_CODES = {
    "first_turn_only": (0x012, 100),
    "u-turn": (0x0EE, None),
    "triple_kick": (0x0BF, None),
    # HP-drain move: heals the user half the damage dealt (0x0DD). A
    # quarter-drain variant (Reap/Siphon) keeps this funccode and halves the
    # heal via the chrooked_quarterdrain behavior (CHROOKED_MOVE_ABSORB_MODS).
    "absorb": (0x0DD, None),
    # Protect-family shield (0x140 = Spiky Shield). Taken for its fail-on-repeat
    # gate only; a shield whose block differs from Spiky Shield's (Root Shelter
    # halves instead of blocking) replaces pbEffect in its own behavior.
    "shield": (0x140, None),
    # "this move is now plain damage" — the ONLY way to move an edited move OFF
    # an engine funccode it should no longer have. The applier rewrites :function
    # solely when an effect maps, so a move redesigned away from a special code
    # (Fissure and Guillotine off OHKO 0x070) otherwise keeps every behavior of
    # the old one. It has to be opt-in: `effect` defaults to "hit" on 155 of the
    # 207 overrides, so mapping "hit" itself would reset 155 engine funccodes.
    "plain_damage": (0x000, None),
    # Sleep-gated attack that does NOT wake the user, with a flinch chance
    # (0x011 = Snore; Battle_MoveEffects.rb gates it on attacker.isSleeping?).
    # The chance rides :effect, so 30 reproduces Snore's roll on any BP.
    # Comatose satisfies the gate permanently (Battler.rb#isSleeping?).
    "sleep_gated": (0x011, 30),
}

# Vanilla function codes for one single secondary effect at :effect chance
# (Ember, Poison Sting, Thunder Shock, Ice Beam, Aurora Beam, Crush Claw,
# Moonblast, Acid/Psychic, Mud-Slap, Confusion).
_SINGLE_EFFECT_CODES = {
    "burn": 0x00A, "poison": 0x005, "paralysis": 0x007, "frostbite": 0x00C,
    "flinch": 0x00F, "atk_minus_1": 0x042, "def_minus_1": 0x043,
    "sp_atk_minus_1": 0x045, "sp_def_minus_1": 0x046, "acc_minus_1": 0x047,
    "spd_minus_1": 0x044, "confusion": 0x013,
    # The >110 special drawback: user's Sp. Atk falls two steps after use
    # (Overheat / Draco Meteor / Leaf Storm all share 0x03F, :effect 100).
    "sp_atk_minus_2": 0x03F,
    # Self stat-raise secondaries. Cribbed from Battle_MoveEffects.rb, whose
    # own class comments name the move we are writing:
    #   0x01D "(Harden, Steel Wing, Withdraw, Psyshield Bash)"
    #   0x01F "(Flame Charge / Esper Wing / Aqua Step / Trailblaze)"
    #   0x020 "(Charge Beam, Fiery Dance, Mystical Power, Torch Song)"
    "def_plus_1": 0x01D, "spd_plus_1": 0x01F, "sp_atk_plus_1": 0x020,
    # Rejuv swaps freeze for frostbite behind the NeverMeltIce gate, so the
    # freeze secondary and the frostbite secondary are the same 0x00C class
    # (Battle_MoveEffects.rb: "Freezes the target. (Ice Beam / Ice Punch /
    # Powder Snow / Freeze-Dry / Freezing Glare)").
    "freeze_or_frostbite": 0x00C,
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
            # Existing move — patch its scalars in place. One `ref` per move so
            # a symbol needing quotes (a chrooked_id that opens with a digit) is
            # rendered once, correctly, for every field line below.
            ref = f"MOVEHASH[{ruby_sym(sym)}]"
            lines = [f"{ref}[:type] = :{_type_sym(move.type)}",
                     f"{ref}[:category] = :{move.category}"]
            if move.recoil:
                # Rejuv reads :recoil as a fraction of damage dealt
                # (Battle_Move.rb: @recoil = @data.checkFlag?(:recoil, 0)).
                lines.append(f"{ref}[:recoil] = {move.recoil}")
            if move.second_type:
                # Dual-damage-type (Flying Press): pure data, the engine reads
                # :secondtype in its type-mod calc.
                lines.append(
                    f"{ref}[:secondtype] = :{_type_sym(move.second_type)}")
            for attr, field in _MOVE_SCALARS:
                value = getattr(move, attr)
                if value is not None and value != "":
                    lines.append(f"{ref}[:{field}] = {to_ruby(value)}")
            # Target is emitted only when it is NOT the "selected" default.
            # 191 of 207 overrides sit on that default without meaning it, so
            # writing it unconditionally would turn every base spread move the
            # Ruleset touches for power into a single-target move.
            if move.target and move.target != "selected":
                if (tsym := _TARGET.get(move.target)):
                    lines.append(f"{ref}[:target] = :{tsym}")
            # ponytail: priority 0 is indistinguishable from "unset" in a
            # MoveDef, so only a nonzero priority is written.
            if move.priority:
                lines.append(f"{ref}[:priority] = {move.priority}")
            # ponytail: additive only — sets modeled flags the Ruleset declares,
            # never clears one the engine already has.
            for flag in move.flags:
                if (key := _FLAG.get(flag)):
                    lines.append(f"{ref}[:{key}] = true")
            reason = ""
            covered = False
            if move.effect in _PRIMARY_EFFECT_CODES:
                code, chance = _PRIMARY_EFFECT_CODES[move.effect]
                lines.append(f"{ref}[:function] = 0x{code:03X}")
                if chance is not None:
                    lines.append(f"{ref}[:effect] = {chance}")
            elif move.additional_effects:
                # Retuned secondary (Muddy Water's speed drop): swap the
                # funccode + :effect chance; anything unmapped is reported,
                # never silently dropped.
                function, chance, leftover = _function_for(move)
                if function:
                    lines.append(f"{ref}[:function] = 0x{function:03X}")
                    if chance is not None:
                        lines.append(f"{ref}[:effect] = {chance}")
                if leftover:
                    # A move behavior sharing the move's chrooked_id owns what
                    # the funccode can't express — same rule the create branch
                    # below applies. Without this an edited move with a shipped
                    # mechanic reports DATA ONLY while its mod sits installed.
                    if move.chrooked_id in implemented:
                        covered = True
                        reason = (f"{move.chrooked_id} mechanic "
                                  f"({', '.join(leftover)})")
                    else:
                        reason = f"DATA ONLY: {', '.join(leftover)}"
            blocks.extend(lines)
            report.add(ReportEntry(
                status="applied" if covered or not reason else "partial",
                category="move",
                chrooked_id=move.chrooked_id, symbol=sym, reason=reason))
        else:
            # New move — create a full MOVEHASH entry. Flinch combos map onto a
            # vanilla :function code (pure data); anything the code doesn't cover
            # stays honestly DATA ONLY.
            sym = resolution.move_symbol(move.name)
            function, chance, leftover = _function_for(move)
            # The primary effect: takes the function slot when the additional
            # effects left it free; otherwise it joins the leftover so it is
            # reported, never silently dropped (Bail Out shipped as plain 0x000).
            primary = move.effect if move.effect != DEFAULT_EFFECT else ""
            if primary == "recoil":
                # The >110 physical drawback rides the :recoil data field the
                # engine already reads (Double-Edge carries :recoil => 0.33), not
                # a :function code — emitted in _new_move_block, not a leftover.
                primary = ""
            elif primary:
                primary_code = _PRIMARY_EFFECT_CODES.get(primary)
                if primary_code is not None and function == 0x000:
                    function, chance = primary_code
                else:
                    leftover = sorted(leftover + [primary])
            blocks.append(_new_move_block(move, sym, next_id, function, chance))
            next_id += 1
            # A move behavior sharing the move's chrooked_id owns whatever the
            # funccode can't express, so the leftover is implemented, not missing.
            own_behavior = move.chrooked_id in implemented
            if not move.additional_effects and not primary:
                reason = ""
            elif not leftover:
                reason = f"effects mapped to :function 0x{function:03X}"
            elif own_behavior and function:
                reason = (f"effects mapped to :function 0x{function:03X} "
                          f"+ {move.chrooked_id} mechanic ({', '.join(leftover)})")
            elif own_behavior:
                reason = f"{move.chrooked_id} mechanic ({', '.join(leftover)})"
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
        *([f":secondtype => :{_type_sym(move.second_type)}"] if move.second_type else []),
        f":category => :{move.category}",
        f":basedamage => {move.power if move.power is not None else _CREATE_DEFAULTS['basedamage']}",
        f":accuracy => {move.accuracy if move.accuracy is not None else _CREATE_DEFAULTS['accuracy']}",
        f":maxpp => {move.pp if move.pp is not None else _CREATE_DEFAULTS['maxpp']}",
        f":target => :{_TARGET.get(move.target, 'SingleNonUser')}",
        # ponytail: priority 0 is the engine default, so only a nonzero one is
        # written — same rule the existing-move patch above follows.
        *([f":priority => {move.priority}"] if move.priority else []),
    ]
    if effect_chance is not None:
        fields.append(f":effect => {effect_chance}")
    if move.effect == "recoil":
        # >110 physical drawback: 1/3 recoil (D3), the field the engine reads.
        fields.append(":recoil => 0.33")
    for flag in move.flags:
        key = _FLAG.get(flag)
        if key:
            fields.append(f":{key} => true")
    return f"MOVEHASH[{ruby_sym(sym)}] = {{ {', '.join(fields)} }}"


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
            blocks.append(f"ABILHASH[{ruby_sym(sym)}][:name] = {to_ruby(ability.name)}")
            if ability.description:
                blocks.append(f"ABILHASH[{ruby_sym(sym)}][:desc] = {to_ruby(ability.description)}")
            report.add(ReportEntry(status="applied", category="ability",
                                   chrooked_id=ability.chrooked_id, symbol=sym))
        else:
            # New ability — DATA ONLY unless its mechanic installs this run.
            blocks.append(
                f"ABILHASH[{ruby_sym(sym)}] = {{ :ID => {next_id}, "
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
