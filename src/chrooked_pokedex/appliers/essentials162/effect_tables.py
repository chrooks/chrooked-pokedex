"""Resolve a MoveDef's BEHAVIOR into Essentials 16.2 moves.txt columns.

The scalar applier (#21) writes a move's *numbers* (power/type/accuracy/pp) but
leaves the behavior columns at safe placeholders, so a custom move lands inert:
right stats, but it doesn't burn, flinch, drop a stat, hit twice, or OHKO. This
module fills those columns — funccode (col 3), effectchance (col 9), target
(col 10), flags (col 12) — for moves whose effect ALREADY exists in this game.

**Crib provenance (the locked sourcing decision).** Every funccode here is COPIED
from a vanilla move in this exact game's `PBS/moves.txt` that already implements the
effect — never authored from scratch. Correctness is inherited from a shipping,
working move and is verifiable against the file. Each row cites the move(s) it was
cribbed from. A code's meaning was confirmed against >=2 moves that share it (and
triangulated across the whole file for the stat-direction codes, where a single
move's name is misleading — e.g. BUBBLEBEAM `044` lowers SPEED, not SpAtk).

**Exact-match, else unresolved (the locked collapse decision).** A move resolves
only when its FULL effect signature matches one existing funccode exactly:
  - plain `hit`, no secondary                  -> `000` / `0`        (plain damage)
  - `hit` + exactly ONE secondary@chance       -> SECONDARY code + that chance
  - a non-`hit` primary, no secondary           -> the PRIMARY code
Any other shape (a primary effect plus a secondary, or two-or-more secondaries, or
an unmapped effect) returns ``None`` -> reported UNRESOLVED and handed to the #12
mechanic-porting loop, with the move kept at its safe plain-hit defaults. We NEVER
approximate by dropping part of an effect: a wrong funccode ships a broken move,
which is worse than a missing one.

This is the 16.2 analogue of pokeemerald's `move_render.py` + the `neutralize`
tables, but where pokeemerald emits C `EFFECT_*` symbols, 16.2 emits a 3-digit HEX
funccode + a hex target + a letter-flag string into a flat CSV row.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...model.schema import DEFAULT_EFFECT, MoveDef

# Safe plain-hit defaults — identical to move_apply's placeholders. A resolved
# plain-damage move emits exactly these; an unresolved move keeps them untouched.
PLAIN_FUNCCODE = "000"
PLAIN_EFFECTCHANCE = "0"
DEFAULT_TARGET_HEX = "00"


# --- PRIMARY effect -> funccode --------------------------------------------------
#
# A non-`hit` primary effect IS the move's mechanic; the funccode encodes it whole.
# Each code verified against >=2 vanilla moves that share it (where >=2 exist).
EFFECT_TO_FUNCCODE: dict[str, str] = {
    "absorb": "0DD",          # verified via ABSORB, MEGADRAIN, GIGADRAIN (drain HP)
    "triple_kick": "0BF",     # verified via TRIPLEKICK, TRIPLEAXEL (3 hits, ramping)
    "multi_hit": "0C0",       # verified via DOUBLESLAP, FURYSWIPES, PINMISSILE (2-5 hits)
    "ohko": "070",            # verified via FISSURE, HORNDRILL, GUILLOTINE (one-hit KO)
    "brick_break": "10A",     # verified via BRICKBREAK (breaks screens)
    "low_kick": "09A",        # verified via LOWKICK (power scales with target weight)
    "heat_crash": "09B",      # verified via HEATCRASH, HEAVYSLAM (power by weight ratio)
    "belch": "158",           # verified via BELCH (requires a held Berry eaten)
    "rage": "093",            # verified via RAGE (Attack rises when hit)
    "roar": "0EB",            # verified via ROAR, WHIRLWIND (force-switch the target)
    "first_turn_only": "012",  # verified via FAKEOUT (flinch, usable only turn 1)
    # NOTE: 012 reads col 9 (effectchance) as its flinch probability — see
    # EFFECT_DEFAULT_EFFECTCHANCE below, which gives first_turn_only its 100% flinch.
    "recoil_if_miss": "10B",  # verified via JUMPKICK, HIGHJUMPKICK (crash damage on miss)
    "confuse": "013",         # verified via CONFUSION, SIGNALBEAM (damage + may confuse)
    "curse": "10D",           # verified via CURSE (Ghost: cut HP, curse; else raise Atk/Def)
    "moonlight": "0D8",       # verified via MOONLIGHT, MORNINGSUN, SYNTHESIS (weather heal)
    "attack_down_2": "04B",   # verified via CHARM, FEATHERDANCE (lower target Attack by 2)
}

# A few primary-effect funccodes use col 9 (effectchance) as a probability the effect
# implies, so they cannot default to "0" or the effect never fires. Fake Out (012) always
# flinches. An effect not listed keeps PLAIN_EFFECTCHANCE ("0").
EFFECT_DEFAULT_EFFECTCHANCE: dict[str, str] = {
    "first_turn_only": "100",  # FAKEOUT always flinches
}

# `absorb` is fraction-specific in 16.2: the funccode encodes HOW MUCH HP is drained.
# The neutral `argument.absorb_percentage` picks the right code; an unmapped fraction
# stays unresolved rather than defaulting to the wrong drain amount.
ABSORB_PERCENT_TO_FUNCCODE: dict[int, str] = {
    50: "0DD",   # verified via ABSORB, MEGADRAIN, GIGADRAIN (drain 50%)
    75: "14F",   # verified via DRAININGKISS, OBLIVIONWING (drain 75%)
}
_DEFAULT_ABSORB_PERCENT = 50

# `semi_invulnerable` is PER-MOVE in 16.2 (Fly/Dig/Dive/Bounce each have their own
# code), so it cannot map from the neutral name alone. We disambiguate by the move's
# `aka.essentials`/`aka.pokeemerald` hint; an unrecognized one stays unresolved.
SEMI_INVULNERABLE_BY_INTERNAL: dict[str, str] = {
    "FLY": "0C9",      # verified via FLY (up turn 1, strike turn 2)
    "DIG": "0CA",      # verified via DIG (underground turn 1)
    "DIVE": "0CB",     # verified via DIVE (underwater turn 1)
    "BOUNCE": "0CC",   # verified via BOUNCE (up turn 1, may paralyze)
}


# --- SECONDARY (additional_effect) -> funccode -----------------------------------
#
# In 16.2 a `hit + ONE secondary@chance` move collapses to a damaging funccode whose
# MEANING is the secondary; the percent comes from the model (-> col 9). One code per
# effect-type; the chance is data. Verified against >=2 moves; the stat-direction
# codes were triangulated across the whole file (a single move's name lies).
SECONDARY_TO_FUNCCODE: dict[str, str] = {
    "burn": "00A",            # verified via EMBER, FLAMETHROWER (may burn)
    "paralysis": "007",       # verified via THUNDERBOLT(10%), BODYSLAM(30%) — code, %=data
    "poison": "005",          # verified via POISONSTING, SLUDGEBOMB (may poison)
    "freeze": "00C",          # verified via ICEBEAM, ICEPUNCH, POWDERSNOW (may freeze)
    "flinch": "00F",          # verified via ROCKSLIDE, AIRSLASH, IRONHEAD (may flinch)
    "confusion": "013",       # verified via CONFUSION (may confuse) — shares the primary code
    "atk_minus_1": "042",     # verified via GROWL, AURORABEAM, PLAYROUGH, TROPKICK (lower Atk)
    "def_minus_1": "043",     # verified via CRUNCH, ROCKSMASH (lower Def)
    "sp_atk_minus_1": "045",  # verified via STRUGGLEBUG, SNARL, MOONBLAST, MISTBALL (lower SpAtk)
    "sp_def_minus_1": "046",  # verified via PSYCHIC, SHADOWBALL, BUGBUZZ (lower SpDef)
    "spd_minus_1": "044",     # verified via ELECTROWEB, LOWSWEEP, ICYWIND, BUBBLEBEAM (lower Speed)
    "acc_minus_1": "047",     # verified via MUDSLAP (lower Accuracy)
    "def_plus_1": "01D",      # verified via STEELWING (damaging, raises user Def; HARDEN status shares it)
    "spd_plus_1": "01F",      # verified via FLAMECHARGE, ESPERWING, AQUASTEP, TRAILBLAZE (raise user Speed)
}
# A biting move that applies BOTH a status AND a flinch (Fire/Thunder Fang) collapses to
# ONE dedicated funccode that bundles both — distinct from the status-only secondary codes
# above. Cribbed from each fang's own row; the status chance carries to col 9 (safe whether
# the code reads it or hardcodes 10/10). `freeze_or_frostbite` is deliberately absent — only
# plain `freeze` exists here, and the Ice Fang naming would mask the dropped frostbite half.
STATUS_FLINCH_TO_FUNCCODE: dict[str, str] = {
    "burn": "00B",       # verified via FIREFANG (may burn + may flinch)
    "paralysis": "009",  # verified via THUNDERFANG (may paralyze + may flinch)
    "freeze": "00E",     # verified via ICEFANG (may freeze + may flinch) — plain freeze
}

# Deliberately NOT mapped (resolve unresolved -> #12):
#   freeze_or_frostbite — this Ruby-1.x 16.2 engine has no distinct "frostbite"
#     effect (that is a gen9 concept); only plain `freeze` (00C) exists. Mapping it to
#     freeze would silently drop the frostbite half, so we leave it unresolved.


# --- Flag-letter legend ----------------------------------------------------------
#
# 16.2 flags are a letter string in col 12. Only letters this game actually uses for
# a given neutral flag are mapped (verified by >=2 moves carrying that letter with
# that semantic). The b/e/f letters (protect / mirror-move / flinch-eligible) are
# engine defaults, NOT neutral-flag-driven, so we never fabricate them.
#
# Neutral flags with no letter in this engine (slicing, wind, wing, bone, hammer,
# kicking, piercing) are DROPPED + noted by the caller — exactly as pokeemerald
# drops an unmodeled flag. (This Ruby-1.x engine predates per-flag letters for them;
# `l` is the POWDER flag, not kicking — verified via SPORE/STUNSPORE/SLEEPPOWDER.)
FLAG_TO_LETTER: dict[str, str] = {
    "contact": "a",     # verified via TACKLE, BODYSLAM, every physical-contact move
    "biting": "i",      # verified via BITE, CRUNCH, ICEFANG, FIREFANG
    "punching": "j",    # verified via ICEPUNCH, MACHPUNCH, FIREPUNCH
    "sound": "k",       # verified via HYPERVOICE, SNARL, BUGBUZZ
    "ballistic": "n",   # verified via SLUDGEBOMB, SHADOWBALL, ENERGYBALL
}


# --- Target-hex legend -----------------------------------------------------------
#
# 16.2 targets are a hex bitcode in col 10. The Ruleset uses only `selected` and
# `both`; both verified against this game's usage.
TARGET_TO_HEX: dict[str, str] = {
    "selected": "00",   # verified via MEGAHORN (single chosen foe — the engine default)
    "both": "04",       # verified via TWISTER, STRUGGLEBUG, SNARL (all opposing foes)
}

# A NAMED-target PBS variant (e.g. Infinite Fusion 2) spells col 10 as an engine
# constant name instead of a hex bitcode. Same two neutral targets the Ruleset uses.
# Detected per-file by `move_apply._uses_named_targets`; an unknown neutral target
# falls back to the single-foe default.
TARGET_TO_NAME: dict[str, str] = {
    "selected": "NearOther",   # single adjacent target — the engine default
    "both": "AllNearFoes",     # all adjacent foes
}
DEFAULT_TARGET_NAME = "NearOther"


@dataclass(frozen=True)
class Behavior:
    """The four moves.txt behavior columns a resolved move writes.

    `funccode` -> col 3, `effectchance` -> col 9, `target` -> col 10, `flags` -> col 12.
    """

    funccode: str
    effectchance: str
    target: str
    flags: str


def _internal_hint(move: MoveDef) -> str | None:
    """The engine internal name a move points at, for per-move generics, if any."""
    hint = (move.aka or {}).get("essentials") or (move.aka or {}).get("pokeemerald")
    if not hint:
        return None
    text = str(hint).upper()
    # A pokeemerald hint is `MOVE_FLY`; strip the prefix to match the internal name.
    return text.removeprefix("MOVE_").replace("_", "")


def _render_target(move: MoveDef, named: bool) -> str:
    if named:
        return TARGET_TO_NAME.get(move.target, DEFAULT_TARGET_NAME)
    return TARGET_TO_HEX.get(move.target, DEFAULT_TARGET_HEX)


def merge_flags(existing: str, add: str) -> str:
    """Union the modeled flag letters onto a row's existing flags, stably ordered.

    Additive only: every letter already on the row survives (engine-default letters the
    Ruleset doesn't model — protect `b` / mirror-move `e` / flinch-eligible `f` — are
    preserved), and the modeled letters are added. Flag REMOVAL is not expressed: the
    neutral schema has no negative-flag intent, so a wholesale replace would silently
    wipe those defaults (the IF2 regression this fixes). Alphabetical order matches the
    engine's own convention (`abef`, `befk`).
    """
    return "".join(sorted(set(existing) | set(add)))


def _render_flags(move: MoveDef) -> tuple[str, list[str]]:
    """The flag-letter string + the list of neutral flags that had no engine letter.

    Letters are emitted in the legend's declared order so the result is stable.
    """
    mapped: list[str] = []
    dropped: list[str] = []
    for flag in move.flags:
        letter = FLAG_TO_LETTER.get(flag)
        if letter is None:
            dropped.append(flag)
        else:
            mapped.append(letter)
    # Stable order: follow the legend's key order, not the move's flag order.
    ordered = [
        letter for flag, letter in FLAG_TO_LETTER.items() if letter in set(mapped)
    ]
    return "".join(ordered), dropped


def _resolve_funccode(move: MoveDef) -> tuple[str, str] | None:
    """`(funccode, effectchance)` for the move's effect signature, or None.

    None means the signature has no single existing 16.2 code (a primary+secondary
    combo, two-or-more secondaries, or an unmapped effect) -> unresolved -> #12.
    """
    is_plain = move.effect == DEFAULT_EFFECT
    additionals = move.additional_effects

    # semi_invulnerable resolves by per-move code FIRST, with or without a secondary: the
    # move's own code (FLY/DIG/DIVE/BOUNCE) already bundles its secondary, so a Bounce
    # paralysis must not block resolution — its chance just carries to col 9.
    if move.effect == "semi_invulnerable":
        internal = _internal_hint(move)
        code = SEMI_INVULNERABLE_BY_INTERNAL.get(internal) if internal else None
        if code is None:
            return None
        # the per-move code bundles at most ONE secondary; 2+ would be an approximation.
        if len(additionals) > 1:
            return None
        chance = str(additionals[0].chance) if additionals else PLAIN_EFFECTCHANCE
        return code, chance

    if is_plain and not additionals:
        return PLAIN_FUNCCODE, PLAIN_EFFECTCHANCE

    if is_plain and len(additionals) == 1:
        secondary = additionals[0]
        code = SECONDARY_TO_FUNCCODE.get(secondary.effect)
        if code is None:
            return None
        return code, str(secondary.chance)

    # A BITING move's `status + flinch` pair collapses to its bundled fang code; the
    # status chance carries to col 9. The biting flag is required — the fang codes are
    # the engine's fang functions, so a non-biting burn+flinch move must not borrow one.
    # Any other two-secondary combo stays unresolved.
    if is_plain and len(additionals) == 2 and "biting" in move.flags:
        effects = {a.effect for a in additionals}
        # need exactly {flinch, <one distinct status>}; a duplicate pair collapses the
        # set to <2 and is not a fang combo -> unresolved.
        if len(effects) != 2 or "flinch" not in effects:
            return None
        (status,) = effects - {"flinch"}
        code = STATUS_FLINCH_TO_FUNCCODE.get(status)
        if code is not None:
            chance = next(str(a.chance) for a in additionals if a.effect == status)
            return code, chance
        # No bundled status+flinch code, but if the non-flinch half is a STAT-DROP the
        # engine handles natively, emit that code and let the chrooked_fangflinch plugin
        # add the flinch (see deferred_effects). The stat-drop chance carries to col 9.
        if _is_statdrop_secondary(status):
            chance = next(str(a.chance) for a in additionals if a.effect == status)
            return SECONDARY_TO_FUNCCODE[status], chance
        return None

    if not is_plain and not additionals:
        if move.effect == "absorb":
            percent = (move.argument or {}).get("absorb_percentage", _DEFAULT_ABSORB_PERCENT)
            code = ABSORB_PERCENT_TO_FUNCCODE.get(percent)
            return (code, PLAIN_EFFECTCHANCE) if code else None
        code = EFFECT_TO_FUNCCODE.get(move.effect)
        if code is None:
            return None
        chance = EFFECT_DEFAULT_EFFECTCHANCE.get(move.effect, PLAIN_EFFECTCHANCE)
        return code, chance

    # Any other combo (primary effect + secondary, or >=2 secondaries) -> unresolved.
    return None


def resolve_behavior(move: MoveDef, named: bool = False) -> Behavior | None:
    """Resolve a move's behavior to its four 16.2 columns, or None when unresolved.

    None = the effect signature has no exact existing 16.2 funccode; the caller keeps
    the safe plain-hit defaults and reports it unresolved for the #12 loop. (Target
    and flags resolve cleanly even for an unmapped-funccode move, but without a real
    funccode the move would behave wrong, so an unresolvable signature blocks the
    whole behavior write — honesty over a half-right row.)

    `named` selects the col-10 target representation: a name (`NearOther`) for a
    named-target PBS, else the hex bitcode (`00`).
    """
    resolved = _resolve_funccode(move)
    if resolved is None:
        return None
    funccode, effectchance = resolved
    flags, _dropped = _render_flags(move)
    return Behavior(
        funccode=funccode,
        effectchance=effectchance,
        target=_render_target(move, named),
        flags=flags,
    )


def _is_statdrop_secondary(effect: str) -> bool:
    """A single-stage stat-drop secondary the engine handles natively (042/043/...)."""
    return effect.endswith("_minus_1") and effect in SECONDARY_TO_FUNCCODE


def deferred_effects(move: MoveDef) -> list[str]:
    """Effect parts intentionally handed to a plugin, not the funccode (for reporting).

    A biting stat-drop + flinch move resolves to its stat-drop code (the engine lowers
    the stat); the flinch is added by the `chrooked_fangflinch` plugin, so it is reported
    deferred rather than silently absent. Keep the plugin's gated move list in sync with
    this shape — a new biting stat-drop+flinch move needs adding to the plugin too.
    """
    # Mirror _resolve_funccode's stat-drop branch EXACTLY — including its is_plain gate —
    # so a note is emitted only for a move that actually resolved to a stat-drop code.
    if move.effect != DEFAULT_EFFECT:
        return []
    additionals = move.additional_effects
    if "biting" not in move.flags or len(additionals) != 2:
        return []
    effects = {a.effect for a in additionals}
    if len(effects) != 2 or "flinch" not in effects:
        return []
    (status,) = effects - {"flinch"}
    if status in STATUS_FLINCH_TO_FUNCCODE or not _is_statdrop_secondary(status):
        return []
    return ["flinch -> chrooked_fangflinch plugin"]


def dropped_flags(move: MoveDef) -> list[str]:
    """Neutral flags on this move that have no 16.2 letter (for caller reporting)."""
    return _render_flags(move)[1]


def specifies_effect(move: MoveDef) -> bool:
    """Whether the move carries EFFECT intent: a non-default primary or any secondary.

    Distinct from `specifies_behavior` (which also fires on flag/target intent): a move
    that only retunes flags or target has NO effect intent, so its funccode/effectchance
    columns must be left alone. Writing a plain `000` there would silently flatten an
    existing engine funccode the Ruleset never meant to touch — recoil (Brave Bird `0FB`),
    charge, etc. The neutral schema can't express "remove an effect", so an unspecified
    effect means "no opinion, keep the engine's code", mirroring how target/flags default.
    """
    return move.effect != DEFAULT_EFFECT or bool(move.additional_effects)


def specifies_behavior(move: MoveDef) -> bool:
    """Whether the Ruleset move carries ANY behavior intent worth writing.

    A plain `hit` move with no secondary, no flags, and the default target specifies
    no behavior — so the EDIT path leaves the target's existing behavior columns
    (which may belong to a known vanilla move) untouched rather than blanking them.
    The CREATE path always writes a full row regardless, since a brand-new move has
    no existing columns to preserve.
    """
    return bool(
        move.effect != DEFAULT_EFFECT
        or move.additional_effects
        or move.flags
        or move.target != "selected"
    )
