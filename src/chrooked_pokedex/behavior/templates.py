"""Behavior templates: a port generated from its spec instead of written by hand.

Many of the Ruleset's ability mechanics are one of a few shapes the dex has already
proven on a real engine: "moves of this type hit harder" (Blaze's shape), "Normal moves
become type X and hit harder" (Aerilate's), "moves with this flag hit harder" (Iron
Fist's), "hit harder while a weather or terrain is up" (Sand Force's and Solar
Power's). A behavior spec that is one of those says so in a `template:` block:

    template:
      shape: flag_boost
      params: {flags: [kicking], multiplier: 1.3}
      probes:
        - {move: High Jump Kick, result: boosted}
        - {move: Tackle, result: normal}
        - {move: High Jump Kick, result: normal, holder: false}

`params` configure the shape; `probes` hold one machine-checkable probe per entry of
the spec's `test_cases`, in the same order. From that block this module emits, for an
Essentials 21 target (mjolnir NV-8, NV-9):

  * the port, `chrooked_<id>.rb`: one handler-registry entry, the same Ruby a person
    would write for that shape;
  * the port's own case for the lab's headless self-test, registered at load in
    `$chrooked_selftest_cases`, so the self-test needs no edit per mechanic;
  * the harness checks, one per probe, which score the port's OBS lines against the
    spec's test cases.

Specs stay engine-neutral (move, type and item names, Ruleset move flags, neutral
weathers and terrains). The target's own PBS turns them into INTERNAL names through a
resolver, the Essentials `ResolutionMap`, which never guesses: a name the target lacks
fails the render and says which. Every shape generates exactly one effect, so a spec
with more effects is refused (`validate_spec`) rather than ported half-way; a mechanic
that fits no shape keeps a hand-written port in references/essentials21-harness/.

Shapes, their params, and the probe fields each accepts:

  type_boost         {type, multiplier, pinch?, control?}     {move, result, hp?, holder?}
  type_conversion    {type, multiplier=1.2, from=normal|any,  {move, converted, hp?}
                      flags?, control?}
  flag_boost         {flags, multiplier, control?}            {move, result, hp?, holder?}
  conditional_boost  {weather | terrain, multiplier,          {move, result, hp?, field?,
                      moves=all|higher_stat, control?}         item?, airborne?, stats?}
  stab_grant         {types | all, multiplier=1.5, control?}  {move, result, hp?, types?}
  hit_status         {status, chance, type | flags}           {move, inflicts, target_types?}
  type_immunity      {type}                                   {move, immune}
  hit_drain          {fraction, moves=contact|non_contact}    {move, drain, ooze?}
  ko_effect          {heal | stat}                            {kos, effect, hp?, stage?}
  priority_boost     {type, full_hp?}                         {move, result, hp?}
  type_resist        {type, multiplier}                       {move, applies}
  keeps              {}                                       {measure, status?}  (blocks only)

`result` is `boosted` or `normal`; `converted` is true or false. `pinch: true` limits a
type boost to HP at or below 1/3, Blaze's threshold, and a probe's `hp` sets the
holder's HP fraction first. `holder: false` probes a Pokemon WITHOUT the ability, a
case the port can never log because it only runs for its holder; the self-test
measures that case itself. `control` is a vanilla ability, by INTERNAL name, that the
self-test measures beside the port for comparison (BLAZE beside a type boost, say).

A conditional boost holds while its `weather` (rain, sun, sand, hail) affects the user
or its `terrain` (grassy, electric, psychic, misty) is up and the user is grounded.
`moves: all` boosts every move's power, as Nova's Sand Force does; `moves:
higher_stat` boosts the attacking stat behind the user's higher one (physical moves
when Attack >= Sp. Atk, special otherwise), as Solar Power does. Its probes set the
scene: `field: false` (no weather or terrain), `item` (a held item, weather only, e.g.
Utility Umbrella), `airborne: true` (terrain only), and `stats: physical|special`
(which attacking stat is higher; required for higher_stat).

A STAB grant gives moves of `types` (a list of type names, or `all`) the same-type
bonus without the type (NV-10): the same 1.5x on final damage that Nova's own STAB
applies, and only when the user lacks the type, so STAB never doubles; a typeless
move (Struggle) gets none, as in Nova. A probe's `types` sets the user's types
first (a list of type names; without it the user is the neutral ??? type).

A type conversion takes Normal-type moves by default (`from: normal`, Aerilate's
shape); `from: any` takes every move, as Normalize does, and `flags` limits either to
moves carrying one of those flags (NV-13: Arctic Ariette's Normal sound moves, Sacred
Toll's sound moves of any type).

A hit status (NV-13) gives the user's damaging hits a `chance` percent roll to inflict
`status` (burn, poison, paralysis) when the move, as used, is of `type` or carries one
of `flags`: Nova's Poison Touch shape. A probe says whether the roll can land
(`inflicts`), and `target_types` sets the target's types first (a Fire type cannot be
burned). The lab self-test measures the rate over seeded rolls, so these checks score
the self-test's own lines (source=selftest).

A type immunity (NV-13) blocks every move of `type` aimed at the holder, status moves
included: Nova's Bulletproof shape, keyed on the type. A probe says whether its move
is blocked (`immune`).

A hit drain (NV-14) heals the user `fraction` of the HP each hit took, through Nova's
own drain path (Big Root, Heal Block and a Liquid Ooze target all apply), on contact
moves or on non-contact ones. A probe's `drain` is healed, none or reversed, and
`ooze: true` puts Liquid Ooze on the target.

A knockout effect (NV-14) fires when the user's move knocks out foes: a `heal` of a
fraction of max HP while the user can heal (Carnivore), or a `stat` raised one stage
per foe knocked out (Moxie). A probe names no move: `kos` foes fell (0 for a hit that
knocked nothing out), and `effect` says whether anything happened, with the user's
`hp` (heal) or its `stage` in that stat (stat) set first.

A priority boost (NV-14) gives moves of `type` +1 priority, only at full HP when
`full_hp` is true: Nova's Gale Wings, which reads the move's own type. A probe's `hp`
sets the user's HP fraction first.

A type resist (NV-18) multiplies the damage the holder TAKES from moves of `type`
(Hydrophyte halves Fire): Nova's Thick Fat shape on DamageCalcFromTarget. A probe's
`applies` says whether the multiplier applies to its move. A type immunity's probe
may set `mold_breaker: true`: the attacker's Mold Breaker lifts the immunity.

Blocks (NV-18). A spec whose effects are several shapes lists blocks instead of one
template: each names the `effects` it generates and the `cases` its probes cover.
Each block is its own registry entry (two blocks on one registry are refused), and
its log lines carry `block=<n>`. A `keeps` block generates nothing: the game's own
ability of that name already does the effect (vanilla Immunity cannot be poisoned),
and its probes measure the ability against none (`measure: status|eor_status`,
`status`), so a port that replaces the ability's other handlers is seen to keep it.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Mapping, Optional, Protocol

from ..appliers.essentials import vocab
from ..model.behavior_spec import BehaviorSpec, BehaviorTemplate
from ..model.schema import MOVE_FLAGS

SHAPES = ("type_boost", "type_conversion", "flag_boost", "conditional_boost", "stab_grant",
          "hit_status", "type_immunity", "hit_drain", "ko_effect", "priority_boost",
          "type_resist", "keeps", "struck_status", "damage_taken", "type_absorb", "stat_swap",
          "crit_condition", "absent", "drops")
# The shapes that only stand in a block beside one that generates an effect.
_BLOCK_ONLY = ("keeps", "absent")

# shape -> (required params, optional params with their defaults)
_PARAMS: dict[str, tuple[frozenset[str], dict[str, object]]] = {
    "type_boost": (frozenset({"type", "multiplier"}), {"pinch": False, "control": None}),
    "type_conversion": (frozenset({"type"}),
                        {"multiplier": 1.2, "from": "normal", "flags": None, "control": None}),
    "flag_boost": (frozenset({"flags", "multiplier"}), {"control": None}),
    "conditional_boost": (frozenset({"multiplier"}),
                          {"weather": None, "terrain": None, "moves": "all", "control": None}),
    "stab_grant": (frozenset({"types"}), {"multiplier": 1.5, "control": None}),
    "hit_status": (frozenset({"status", "chance"}), {"type": None, "flags": None, "contact": None}),
    "struck_status": (frozenset({"status", "chance"}), {}),
    "damage_taken": (frozenset({"rules"}), {}),
    "type_absorb": (frozenset({"type"}), {"heal": None, "stats": None}),
    "stat_swap": (frozenset({"attack"}), {"defense": None, "moves": "damaging", "flags": None, "contact": None,
                                          "burn": None}),
    "crit_condition": (frozenset({"when"}), {}),
    "type_immunity": (frozenset({"type"}), {}),
    "hit_drain": (frozenset({"fraction", "moves"}), {}),
    "ko_effect": (frozenset(), {"heal": None, "stat": None}),
    "priority_boost": (frozenset({"type"}), {"full_hp": False}),
    "type_resist": (frozenset({"type", "multiplier"}), {}),
    "keeps": (frozenset(), {}),
    "absent": (frozenset({"reason"}), {}),
    "drops": (frozenset({"registry"}), {}),
}
# The probe field that states the expected outcome, per shape.
_OUTCOME = {"type_boost": "result", "type_conversion": "converted", "flag_boost": "result",
            "conditional_boost": "result", "stab_grant": "result",
            "hit_status": "inflicts", "type_immunity": "immune", "hit_drain": "drain",
            "ko_effect": "effect", "priority_boost": "result", "type_resist": "applies",
            "keeps": "measure", "struck_status": "inflicts", "damage_taken": "factor",
            "type_absorb": "absorbed", "stat_swap": "uses", "crit_condition": "crit",
            "absent": "absent", "drops": "measure"}
# The shapes whose self-test entries carry a setup hash (the self-test's `arrange`).
_SCENE_SHAPES = ("conditional_boost", "stab_grant")
# Moves Essentials builds in code, with no PBS section to resolve them by.
_BUILTIN_MOVES = {"struggle": "STRUGGLE"}
_RESULTS = ("boosted", "normal")
_WEATHERS = ("rain", "sun", "sand", "hail")
_TERRAINS = ("grassy", "electric", "psychic", "misty")
_MOVE_SETS = ("all", "higher_stat")
_STATS = ("physical", "special")
_CONVERT_FROM = ("normal", "any")
# The shapes that never scale damage: no calc entry.
_NON_DAMAGE_SHAPES = ("hit_status", "type_immunity", "hit_drain", "ko_effect", "priority_boost",
                      "type_resist", "keeps", "struck_status", "damage_taken", "type_absorb", "stat_swap",
                      "crit_condition", "absent", "drops")
# What a keeps (or drops) probe measures, the ability against none (the self-test's keeps
# phase): whether a foe can give the holder `status`, the HP its status changes at end of
# round, or the HP the end of a round in `weather` changes (NV-25).
_KEEP_MEASURES = ("status", "eor_status", "eor_weather")
# The registries a drops block may remove the game's own handler from (NV-25).
_DROPPABLE = ("EndOfRoundWeather",)
# The registries each shape's port adds to: two blocks of one spec may not share one.
_REGISTRIES = {
    "type_boost": ("DamageCalcFromUser",), "flag_boost": ("DamageCalcFromUser",),
    "conditional_boost": ("DamageCalcFromUser",), "stab_grant": ("DamageCalcFromUser",),
    "type_conversion": ("ModifyMoveBaseType", "DamageCalcFromUser"),
    "hit_status": ("OnDealingHit",), "hit_drain": ("OnDealingHit",), "type_immunity": ("MoveImmunity",),
    "ko_effect": ("OnEndOfUsingMove",), "priority_boost": ("PriorityChange",),
    "type_resist": ("DamageCalcFromTarget",), "keeps": (), "struck_status": ("OnBeingHit",),
    "damage_taken": ("DamageCalcFromTarget",), "type_absorb": ("MoveImmunity",),
    # Method wrappers, not registries: one per spec, each its own alias names.
    "stat_swap": ("pbGetAttackStats",),
    "crit_condition": ("CriticalCalcFromUser",),
    "absent": (), "drops": ("EndOfRoundWeather",),
}
# What a crit_condition's `when` forces a critical hit on (Ruby on `target`).
_CRIT_WHEN = {
    # Elite Redux's impaired: poisoned (either), paralyzed, or slowed (a Speed stage below 0).
    "impaired": "target.poisoned? || target.paralyzed? || target.stages[:SPEED] < 0",
}
_SWAP_ATTACK = ("attack", "special_attack", "higher")
_SWAP_MOVES = ("physical", "special", "damaging")
_SWAP_USES = ("attack", "special_attack", "status_move", "blocked")
_DRAINS = ("healed", "none", "reversed")
_CONTACT = ("contact", "non_contact")
# Ruleset stat -> (Essentials stat, its name in stage text)
_STAT_NAMES = {
    "attack": ("ATTACK", "Attack"), "defense": ("DEFENSE", "Defense"),
    "special_attack": ("SPECIAL_ATTACK", "Sp. Atk"), "special_defense": ("SPECIAL_DEFENSE", "Sp. Def"),
    "speed": ("SPEED", "Speed"),
}
_MAX_STAGE = 6
# status -> (Essentials status, the Battler method stem of pbCan<Stem>? and pb<Stem>,
# Nova's own message for an ability inflicting it, as its Poison Touch and Static use)
_STATUSES = {
    "burn": ("BURN", "Burn", "{1} {2} burned {3}!"),
    "poison": ("POISON", "Poison", "{1} {2} poisoned {3}!"),
    "paralysis": ("PARALYSIS", "Paralyze", "{1} {2} paralyzed {3}! It may be unable to move!"),
    # Nova's freeze is the Ruleset's frostbite (chrooked_frostbite.rb, NV-12).
    "frostbite": ("FROZEN", "Freeze", "{1} {2} frostbit {3}!"),
}
_INTERNAL = re.compile(r"^[A-Z][A-Z0-9_]*$")

# The self-test's battlers. Fixed, because neutral mode (both battlers typed ???)
# makes the measured ratio the ability's effect alone, whatever the species.
_SELFTEST_USER = "NUMEL"
_SELFTEST_FOE = "SNORLAX"
FIGHT_MOVES = 4  # a Pokemon knows at most four


class TemplateError(ValueError):
    """A template block that cannot be generated: bad shape, params, probes or names."""


class Names(Protocol):
    """Neutral name -> the target's INTERNAL name, or None when the target lacks it.
    The Essentials `ResolutionMap` is one."""

    def move(self, name: str) -> Optional[str]: ...
    def type(self, name: str) -> Optional[str]: ...
    def ability(self, name: str) -> Optional[str]: ...
    def item(self, name: str) -> Optional[str]: ...


def validate_spec(spec: BehaviorSpec) -> None:
    """Everything that makes a templated spec generatable, short of the target's names.

    It must apply to an ability, and it must have exactly one effect: every shape
    generates one, so a spec with more (a boost AND a burn chance, say) would be
    marked installed while half of it is missing. Then the template itself must
    validate. Raises TemplateError naming the first problem.
    """
    where = f"{spec.chrooked_id}.yaml:template"
    if spec.template is None:
        raise TemplateError(f"{spec.chrooked_id}: no template block")
    if spec.applies_to != "ability":
        raise TemplateError(f"{where}: templates generate ability ports; this spec applies to a {spec.applies_to}")
    if spec.template.shape == "blocks":
        _validate_blocks(spec, where)
        return
    if spec.template.shape in (*_BLOCK_ONLY, "drops"):
        raise TemplateError(f"{where}: {spec.template.shape} belongs in a block beside one that generates an effect")
    if len(spec.effects) != 1:
        summaries = "; ".join(e.summary for e in spec.effects) or "none"
        raise TemplateError(
            f"{where}: a template generates exactly one effect, and this spec has {len(spec.effects)} "
            f"({summaries}); give it a hand-written port, or a shape that covers every effect")
    validate(spec.template, len(spec.test_cases), where)


def _validate_blocks(spec: BehaviorSpec, where: str) -> None:
    template = spec.template
    assert template is not None
    effects: list[int] = []
    cases: list[int] = []
    used: dict[str, int] = {}
    for n, block in enumerate(template.blocks, start=1):
        at = f"{where}[{n}]"
        if block.shape == "blocks":
            raise TemplateError(f"{at}: blocks do not nest")
        validate(block, len(block.cases), at)
        if block.shape == "absent":
            # A case this game cannot have (a field Nova lacks): no effect of its own.
            if block.effects:
                raise TemplateError(f"{at}: an absent block generates nothing; give it effects: []")
        elif any(not 1 <= e <= len(spec.effects) for e in block.effects) or not block.effects:
            raise TemplateError(f"{at}: effects must number the spec's effects, 1 to {len(spec.effects)}")
        effects += block.effects
        cases += block.cases
        for registry in _REGISTRIES[block.shape]:
            if registry in used:
                raise TemplateError(f"{at}: {block.shape} adds to {registry}, as block {used[registry]} does; "
                                    "blocks of one spec may not share a registry")
            used[registry] = n
    if sorted(effects) != list(range(1, len(spec.effects) + 1)):
        raise TemplateError(f"{where}: the blocks must generate each of the {len(spec.effects)} effects exactly "
                            f"once (got {sorted(effects)})")
    if sorted(cases) != list(range(1, len(spec.test_cases) + 1)):
        raise TemplateError(f"{where}: the blocks' cases must cover each of the {len(spec.test_cases)} test "
                            f"cases exactly once (got {sorted(cases)})")
    if all(block.shape in _BLOCK_ONLY for block in template.blocks):
        raise TemplateError(f"{where}: every block keeps the game's own ability; there is nothing to port")


def validate(template: BehaviorTemplate, n_test_cases: int, where: str = "template") -> None:
    """Check a template block makes sense for its shape, without touching any game.

    The loader already enforces the layout (a mapping, one probe per test case); this
    is the per-shape check: known shape, the params that shape takes, the probe
    fields it reads. Raises TemplateError naming the first problem.
    """
    if template.shape not in SHAPES:
        raise TemplateError(f"{where}: unknown shape {template.shape!r}; known shapes: {', '.join(SHAPES)}")
    required, optional = _PARAMS[template.shape]
    params = dict(template.params)
    missing = sorted(required - params.keys())
    if missing:
        raise TemplateError(f"{where}: {template.shape} needs params {', '.join(missing)}")
    unknown = sorted(params.keys() - required - optional.keys())
    if unknown:
        raise TemplateError(
            f"{where}: unknown params {', '.join(unknown)} for {template.shape} "
            f"(takes {', '.join(sorted(required | optional.keys()))})")
    if "type" in params and not _is_text(params["type"]):
        raise TemplateError(f"{where}: params.type must be a type name, e.g. Fire")
    if "multiplier" in params and not _is_positive_number(params["multiplier"]):
        raise TemplateError(f"{where}: params.multiplier must be a positive number, e.g. 1.5")
    if "pinch" in params and not isinstance(params["pinch"], bool):
        raise TemplateError(f"{where}: params.pinch must be true or false")
    control = params.get("control")
    if control is not None and not (isinstance(control, str) and _INTERNAL.match(control)):
        raise TemplateError(f"{where}: params.control must be an INTERNAL ability name such as BLAZE, not {control!r}")
    if "flags" in params:
        flags = params["flags"]
        if not isinstance(flags, list) or not flags or not all(isinstance(f, str) for f in flags):
            raise TemplateError(f"{where}: params.flags must be a non-empty list of move flags")
        bad = [f for f in flags if f not in MOVE_FLAGS]
        if bad:
            raise TemplateError(
                f"{where}: unknown move flags {', '.join(bad)}; known: {', '.join(sorted(MOVE_FLAGS))}")
    if "from" in params and params["from"] not in _CONVERT_FROM:
        raise TemplateError(f"{where}: params.from must be one of {', '.join(_CONVERT_FROM)}, not {params['from']!r}")
    if template.shape == "conditional_boost":
        _validate_condition(params, where)
    if template.shape == "damage_taken":
        _validate_rules(params, where)
    if template.shape == "absent" and not _is_text(params["reason"]):
        raise TemplateError(f"{where}: params.reason says why this game cannot have the case")
    if template.shape == "drops" and params["registry"] not in _DROPPABLE:
        raise TemplateError(f"{where}: params.registry must be one of {', '.join(_DROPPABLE)}")
    if template.shape == "crit_condition" and params["when"] not in _CRIT_WHEN:
        raise TemplateError(f"{where}: params.when must be one of {', '.join(_CRIT_WHEN)}")
    if template.shape == "crit_condition":
        for at, probe in enumerate(template.probes, start=1):
            status = probe.get("target_status")
            if status is not None and status not in (*_STATUSES, "toxic"):
                raise TemplateError(f"{where}: probe {at} target_status must be one of "
                                    f"{', '.join((*_STATUSES, 'toxic'))}, not {status!r}")
    if template.shape == "stat_swap":
        if params["attack"] not in _SWAP_ATTACK:
            raise TemplateError(f"{where}: params.attack must be one of {', '.join(_SWAP_ATTACK)}")
        if params.get("defense") not in (None, "defense"):
            raise TemplateError(f"{where}: params.defense is defense (the target's Defense), or left out")
        if params.get("moves", "damaging") not in _SWAP_MOVES:
            raise TemplateError(f"{where}: params.moves must be one of {', '.join(_SWAP_MOVES)}")
        if params.get("burn") not in (None, "ignore", "physical"):
            raise TemplateError(f"{where}: params.burn is ignore (no halving) or physical (halved as physical)")
        if "contact" in params and params["contact"] is not True:
            raise TemplateError(f"{where}: params.contact gates on contact moves; give true or leave it out")
    if template.shape == "type_absorb":
        if (params.get("heal") is None) == (params.get("stats") is None):
            raise TemplateError(f"{where}: type_absorb needs exactly one of params.heal or params.stats")
        if params.get("heal") is not None and params["heal"] is not True:
            raise TemplateError(f"{where}: params.heal is true (a quarter of max HP, as Volt Absorb)")
        stats = params.get("stats")
        if stats is not None and (not isinstance(stats, list) or not stats
                                  or any(st not in _STAT_NAMES for st in stats)):
            raise TemplateError(f"{where}: params.stats must be a list of {', '.join(_STAT_NAMES)}")
    if template.shape in ("hit_status", "struck_status"):
        _validate_hit_status(params, where, gated=template.shape == "hit_status")
    if template.shape == "hit_drain":
        if not (_is_positive_number(params["fraction"]) and params["fraction"] <= 1):  # type: ignore[operator]
            raise TemplateError(f"{where}: params.fraction must be a fraction of the damage in (0, 1], e.g. 0.25")
        if params["moves"] not in _CONTACT:
            raise TemplateError(f"{where}: params.moves must be one of {', '.join(_CONTACT)}, not {params['moves']!r}")
    if template.shape == "ko_effect":
        heal, stat = params.get("heal"), params.get("stat")
        if (heal is None) == (stat is None):
            raise TemplateError(f"{where}: ko_effect needs exactly one of params.heal or params.stat")
        if heal is not None and not (_is_positive_number(heal) and heal <= 1):  # type: ignore[operator]
            raise TemplateError(f"{where}: params.heal must be a fraction of max HP in (0, 1], e.g. 0.25")
        if stat is not None and stat not in _STAT_NAMES:
            raise TemplateError(f"{where}: params.stat must be one of {', '.join(_STAT_NAMES)}, not {stat!r}")
    if "full_hp" in params and not isinstance(params["full_hp"], bool):
        raise TemplateError(f"{where}: params.full_hp must be true or false")
    if template.shape == "stab_grant" and params["types"] != "all" and not _is_type_list(params["types"]):
        raise TemplateError(f"{where}: params.types must be all, or a non-empty list of type names, e.g. [Dark, Fairy]")
    if len(template.probes) != n_test_cases:
        raise TemplateError(
            f"{where}: {len(template.probes)} probes for {n_test_cases} test_cases; keep them aligned 1:1")
    for index, probe in enumerate(template.probes, start=1):
        _validate_probe(probe, template, f"{where}: probe {index}")


def _validate_condition(params: Mapping[str, object], where: str) -> None:
    weather, terrain = params.get("weather"), params.get("terrain")
    if (weather is None) == (terrain is None):
        raise TemplateError(f"{where}: conditional_boost needs exactly one of params.weather or params.terrain")
    if weather is not None and weather not in _WEATHERS:
        raise TemplateError(f"{where}: params.weather must be one of {', '.join(_WEATHERS)}, not {weather!r}")
    if terrain is not None and terrain not in _TERRAINS:
        raise TemplateError(f"{where}: params.terrain must be one of {', '.join(_TERRAINS)}, not {terrain!r}")
    moves = params.get("moves", "all")
    if moves not in _MOVE_SETS:
        raise TemplateError(f"{where}: params.moves must be one of {', '.join(_MOVE_SETS)}, not {moves!r}")


def _fraction(value: object) -> Optional[Fraction]:
    """A positive number, or a fraction written "1/3": exact where a decimal is not."""
    if isinstance(value, bool):
        return None
    try:
        number = Fraction(str(value)) if isinstance(value, str) else Fraction(value)  # type: ignore[arg-type]
    except (ValueError, TypeError, ZeroDivisionError):
        return None
    return number if number > 0 else None


def _validate_rules(params: Mapping[str, object], where: str) -> None:
    rules = params.get("rules")
    if not isinstance(rules, list) or not rules or not all(isinstance(r, dict) for r in rules):
        raise TemplateError(f"{where}: params.rules must be a list of {{multiplier, type?, contact?, super_effective?}}")
    for index, rule in enumerate(rules, start=1):
        unknown = sorted(set(rule) - {"multiplier", "type", "contact", "super_effective"})
        if unknown:
            raise TemplateError(f"{where}: rule {index}: unknown keys {', '.join(unknown)}")
        if _fraction(rule.get("multiplier")) is None:
            raise TemplateError(f"{where}: rule {index}: multiplier must be a positive number or a fraction (1/3)")
        if "type" not in rule and rule.get("contact") is not True and rule.get("super_effective") is not True:
            raise TemplateError(f"{where}: rule {index}: needs a type, contact: true or super_effective: true")


def _validate_hit_status(params: Mapping[str, object], where: str, gated: bool = True) -> None:
    if params["status"] not in _STATUSES:
        raise TemplateError(f"{where}: params.status must be one of {', '.join(_STATUSES)}, not {params['status']!r}")
    chance = params["chance"]
    if not (isinstance(chance, int) and not isinstance(chance, bool) and 0 < chance <= 100):
        raise TemplateError(f"{where}: params.chance must be a whole percent from 1 to 100, e.g. 30")
    if not gated:
        return  # struck_status: a contact move, always
    if "contact" in params and params["contact"] is not True:
        raise TemplateError(f"{where}: params.contact gates on contact moves; give true or leave it out")
    if sum(params.get(key) is not None for key in ("type", "flags", "contact")) != 1:
        raise TemplateError(f"{where}: hit_status needs exactly one of params.type, params.flags or params.contact")


def _validate_probe(probe: Mapping[str, object], template: BehaviorTemplate, at: str) -> None:
    shape, params = template.shape, template.params
    outcome = _OUTCOME[shape]
    allowed = {outcome} if shape in ("ko_effect", "keeps", "absent", "drops") else {"move", outcome}
    if shape not in _NON_DAMAGE_SHAPES or shape == "priority_boost":
        allowed.add("hp")
    if shape == "hit_drain":
        allowed.add("ooze")
    if shape == "type_immunity":
        allowed.add("mold_breaker")
    if shape in ("keeps", "drops"):
        allowed |= {"status", "weather"}
    if shape == "ko_effect":
        allowed |= {"kos", "hp"} if params.get("heal") is not None else {"kos", "stage"}
    # A Pokemon without the ability is only measurable as "boosted or not", and the
    # self-test measures it on a bare field, so holder: false belongs to the
    # unconditional result shapes.
    if shape in ("type_boost", "flag_boost"):
        allowed.add("holder")
    higher_stat = shape == "conditional_boost" and params.get("moves", "all") == "higher_stat"
    if shape == "conditional_boost":
        allowed.add("field")
        allowed |= {"item"} if params.get("weather") is not None else {"airborne"}
        if higher_stat:
            allowed.add("stats")
    if shape == "stab_grant":
        allowed.add("types")
    if shape == "hit_status":
        allowed.add("target_types")
    if shape == "struck_status":
        allowed.add("attacker_types")
    if shape == "type_absorb":
        allowed |= {"hp", "stage"}
    if shape == "damage_taken":
        allowed.add("types")  # the holder's types first (a super-effective hit)
    if shape == "stat_swap":
        allowed |= {"attack", "special_attack", "stages", "burned", "blocked_by"}
    if shape == "crit_condition":
        allowed |= {"target_status", "target_speed", "target_ability"}
    unknown = sorted(set(probe) - allowed)
    if unknown:
        raise TemplateError(f"{at}: unknown fields {', '.join(unknown)} (takes {', '.join(sorted(allowed))})")
    if shape not in ("ko_effect", "keeps", "absent", "drops") and not _is_text(probe.get("move")):
        raise TemplateError(f"{at}: needs a move name, e.g. {{move: Tackle, ...}}")
    value = probe.get(outcome)
    if outcome == "result" and value not in _RESULTS:
        raise TemplateError(f"{at}: result must be boosted or normal, not {value!r}")
    if outcome == "drain" and value not in _DRAINS:
        raise TemplateError(f"{at}: drain must be one of {', '.join(_DRAINS)}, not {value!r}")
    if outcome == "uses" and value not in _SWAP_USES:
        raise TemplateError(f"{at}: uses must be one of {', '.join(_SWAP_USES)}, not {value!r}")
    if outcome == "uses" and (value == "blocked") != ("blocked_by" in probe):
        raise TemplateError(f"{at}: uses: blocked goes with blocked_by (the foe's ability)")
    if outcome == "factor" and _fraction(value) is None:
        raise TemplateError(f"{at}: factor must be the multiplier the ability gives its move (0.5, 1/3, 2)")
    if outcome == "measure":
        if value not in _KEEP_MEASURES:
            raise TemplateError(f"{at}: measure must be one of {', '.join(_KEEP_MEASURES)}, not {value!r}")
        if value == "eor_weather":
            if probe.get("weather") not in _WEATHERS or "status" in probe:
                raise TemplateError(f"{at}: eor_weather takes weather: one of {', '.join(_WEATHERS)}")
        elif probe.get("status") not in _STATUSES or "weather" in probe:
            raise TemplateError(f"{at}: status must be one of {', '.join(_STATUSES)}")
    if outcome == "absent" and value is not True:
        raise TemplateError(f"{at}: an absent probe is {{absent: true}}")
    if outcome not in ("result", "drain", "measure", "factor", "uses") and not isinstance(value, bool):
        raise TemplateError(f"{at}: {outcome} must be true or false, not {value!r}")
    hp = probe.get("hp", 1.0)
    if not (_is_positive_number(hp) and hp <= 1):  # type: ignore[operator]
        raise TemplateError(f"{at}: hp must be a fraction of max HP in (0, 1], not {hp!r}")
    for flag in ("holder", "field", "airborne"):
        if flag in probe and not isinstance(probe[flag], bool):
            raise TemplateError(f"{at}: {flag} must be true or false")
    if "item" in probe and not _is_text(probe["item"]):
        raise TemplateError(f"{at}: item must be an item name, e.g. Utility Umbrella")
    if "types" in probe and not _is_type_list(probe["types"]):
        raise TemplateError(f"{at}: types must be a non-empty list of type names, e.g. [Water, Dragon]")
    if "attacker_types" in probe and not _is_type_list(probe["attacker_types"]):
        raise TemplateError(f"{at}: attacker_types must be a non-empty list of type names, e.g. [Ice]")
    if "target_types" in probe and not _is_type_list(probe["target_types"]):
        raise TemplateError(f"{at}: target_types must be a non-empty list of type names, e.g. [Fire]")
    if higher_stat and probe.get("stats") not in _STATS:
        raise TemplateError(f"{at}: needs stats: physical or special (which of Attack and Sp. Atk is higher)")
    if "mold_breaker" in probe and not isinstance(probe["mold_breaker"], bool):
        raise TemplateError(f"{at}: mold_breaker must be true or false")
    if probe.get("mold_breaker") and value:
        raise TemplateError(f"{at}: Mold Breaker lifts the immunity; use immune: false")
    if "ooze" in probe and not isinstance(probe["ooze"], bool):
        raise TemplateError(f"{at}: ooze must be true or false")
    if probe.get("ooze") and value == "healed":
        raise TemplateError(f"{at}: a Liquid Ooze target reverses the drain; use drain: reversed")
    if shape == "ko_effect":
        _validate_ko_probe(probe, params, at)
    holder = probe.get("holder", True)
    if not holder and value != "normal":
        raise TemplateError(f"{at}: a Pokemon without the ability cannot be boosted; use result: normal")
    if not holder and "hp" in probe:
        raise TemplateError(f"{at}: hp applies to the ability's holder; drop it from a holder: false probe")


def _validate_ko_probe(probe: Mapping[str, object], params: Mapping[str, object], at: str) -> None:
    kos, effect = probe.get("kos"), probe.get("effect")
    if not (isinstance(kos, int) and not isinstance(kos, bool) and 0 <= kos <= 3):
        raise TemplateError(f"{at}: kos must be how many foes the move knocked out, 0 to 3")
    stage = probe.get("stage", 0)
    if not (isinstance(stage, int) and not isinstance(stage, bool) and -_MAX_STAGE <= stage <= _MAX_STAGE):
        raise TemplateError(f"{at}: stage must be a stat stage from -6 to 6")
    if effect and kos == 0:
        raise TemplateError(f"{at}: nothing happens without a knockout; use effect: false")
    if effect and float(probe.get("hp", 1.0)) >= 1:  # type: ignore[arg-type]
        if params.get("heal") is not None:
            raise TemplateError(f"{at}: a user at full HP cannot heal; set hp below 1 or use effect: false")
    if effect and stage == _MAX_STAGE:
        raise TemplateError(f"{at}: the stat is already at +6; use effect: false")


def render_essentials21(spec: BehaviorSpec, names: Names) -> str:
    """The Essentials 21 port for a templated spec: `chrooked_<id>.rb`'s full text."""
    if spec.template is not None and spec.template.shape == "blocks":
        return _render_blocks(spec, names)
    port = _resolve(spec, names)
    return _fill(_PORT, {
        "HEADER": _header(spec, port),
        "LOG": _CHROOKED_LOG,
        "BODY": _body(spec, port, _selftest_case(spec, port)),
    })


def _body(spec: BehaviorSpec, port: _Port, selftest: str) -> str:
    """One shape's registry entries, its self-test registration inside."""
    values = {
        "ID": spec.chrooked_id,
        "ABILITY": port.ability,
        "SELFTEST": selftest,
    }
    if "multiplier" in port.params:
        values["MULTIPLIER"] = _ruby_float(port.params["multiplier"])
    if port.shape == "type_boost":
        if port.params["pinch"]:
            values["CONDITION"] = (
                "      hp_low  = user.hp <= user.totalhp / 3\n"
                f"      boosted = hp_low && type == :{port.type}")
            values["HP_FIELD"] = "hp_low=#{hp_low} "
        else:
            values["CONDITION"] = f"      boosted = (type == :{port.type})"
            values["HP_FIELD"] = ""
        body = _TYPE_BOOST
    elif port.shape == "type_conversion":
        values["TYPE"] = port.type
        values["GATE"] = _conversion_gate(port)
        body = _TYPE_CONVERSION
    elif port.shape == "flag_boost":
        values["FLAGS"] = "|".join(port.flags)
        body = _FLAG_BOOST
    elif port.shape == "conditional_boost":
        values.update(_conditional_ruby(port))
        body = _CONDITIONAL_BOOST
    elif port.shape == "hit_status":
        _, stem, message = _STATUSES[str(port.params["status"])]
        values.update({"GATE": _hit_gate(port), "CHANCE": str(port.params["chance"]),
                       "STEM": stem, "MESSAGE": message})
        body = _HIT_STATUS
    elif port.shape == "type_immunity":
        values["TYPE"] = port.type
        body = _TYPE_IMMUNITY
    elif port.shape == "hit_drain":
        contact = "move.pbContactMove?(user)"
        values["GATE"] = contact if port.params["moves"] == "contact" else f"!{contact}"
        values["FRACTION"] = _ruby_float(port.params["fraction"])
        body = _HIT_DRAIN
    elif port.shape == "ko_effect" and port.params["heal"] is not None:
        values["FRACTION"] = _ruby_float(port.params["heal"])
        body = _KO_HEAL
    elif port.shape == "ko_effect":
        values["STAT"] = _STAT_NAMES[str(port.params["stat"])][0]
        body = _KO_STAT
    elif port.shape == "priority_boost":
        gate = f"move.type == :{port.type}"
        values["CONDITION"] = f"hp_full && {gate}" if port.params["full_hp"] else gate
        body = _PRIORITY_BOOST
    elif port.shape == "type_resist":
        values["TYPE"] = port.type
        body = _TYPE_RESIST
    elif port.shape == "damage_taken":
        lines = []
        for multiplier, rule_type, contact, super_effective in port.rules:
            gate = " && ".join(([] if not contact else ["contact"]) + ([f"type == :{rule_type}"] if rule_type else [])
                               + (["Effectiveness.super_effective?(target.damageState.typeMod)"] if super_effective else []))
            lines.append(f"      factor *= {_ruby_fraction(multiplier)} if {gate}")
        values["RULES"] = "\n".join(lines)
        body = _DAMAGE_TAKEN
    elif port.shape == "type_absorb":
        values["TYPE"] = port.type
        values["EFFECT"] = _absorb_effect(port)
        body = _TYPE_ABSORB
    elif port.shape == "stat_swap":
        values.update({k: v.replace("{{ID}}", spec.chrooked_id) for k, v in _swap_ruby(port).items()})
        body = _STAT_SWAP
    elif port.shape == "crit_condition":
        values["WHEN"] = _CRIT_WHEN[str(port.params["when"])]
        body = _CRIT_CONDITION
    elif port.shape == "struck_status":
        _, stem, message = _STATUSES[str(port.params["status"])]
        values.update({"CHANCE": str(port.params["chance"]), "STEM": stem, "MESSAGE": message})
        body = _STRUCK_STATUS
    else:
        values["TYPE_GATE"] = (
            "" if port.grant_types is None
            else f" && [{', '.join(':' + t for t in port.grant_types)}].include?(type)")
        body = _STAB_GRANT
    return _fill(body, values)


def _ruby_fraction(value: Fraction) -> str:
    """An exact Ruby float for a multiplier: 0.5, or (1.0 / 3) where no decimal is exact."""
    if value.denominator in (1, 2, 4, 5, 8, 10, 20, 25, 40, 50, 100):
        return _ruby_float(float(value))
    return f"({float(value.numerator)} / {value.denominator})"


def _swap_ruby(port: _Port) -> dict[str, str]:
    """The gate, the attacking stat and the optional defense and burn wrappers of a
    stat swap (NV-23)."""
    gate = {"physical": " && physicalMove?", "special": " && specialMove?", "damaging": ""}[str(port.params["moves"])]
    if port.params.get("contact"):
        gate += " && pbContactMove?(user)"
    if port.flags:
        gate += f" && @flags.any? {{ |f| f[/^({'|'.join(port.flags)})$/i] }}"
    attack = {
        "attack": '[user.attack, user.stages[:ATTACK] + 6, "ATTACK"]',
        "special_attack": '[user.spatk, user.stages[:SPECIAL_ATTACK] + 6, "SPECIAL_ATTACK"]',
        "higher": "chrooked_{{ID}}_higher(user)",
    }[str(port.params["attack"])]
    defense = ""
    if port.params.get("defense"):
        defense = "\n".join([
            "      alias_method :chrooked_{{ID}}_defense_stats, :pbGetDefenseStats",
            "      def pbGetDefenseStats(user, target)",
            "        return chrooked_{{ID}}_defense_stats(user, target) if !chrooked_{{ID}}_takes?(user)",
            "        return target.defense, target.stages[:DEFENSE] + Battle::Battler::STAT_STAGE_MAXIMUM",
            "      end",
            ""])
    burn = ""
    if port.params.get("burn"):
        fix = ("multipliers[:final_damage_multiplier] *= 2 if halves   # the swapped stat is no Attack"
               if port.params["burn"] == "ignore" else
               "multipliers[:final_damage_multiplier] /= 2 if halves   # halved as a physical move")
        test = ("physicalMove? && " if port.params["burn"] == "ignore" else "!physicalMove? && ")
        burn = "\n".join([
            "      alias_method :chrooked_{{ID}}_status_mults, :pbCalcDamageMultipliersStatusConditions",
            "      def pbCalcDamageMultipliersStatusConditions(user, target, numTargets, type, baseDmg, multipliers)",
            "        chrooked_{{ID}}_status_mults(user, target, numTargets, type, baseDmg, multipliers)",
            "        return if !chrooked_{{ID}}_takes?(user) || user.status != :BURN",
            f"        halves = {test}damageReducedByBurn? && !user.hasActiveAbility?([:GUTS, :QUICKFEET])",
            f"        {fix}",
            '        ChrookedLog.line("[chrooked:{{ID}}] OBS move=#{@id} ability=true burn_check=true halves=#{'
            + ("!halves" if port.params["burn"] == "ignore" else "halves") + '}")',
            "      end",
            ""])
    return {"GATE": gate, "ATTACK": attack, "DEFENSE_WRAP": defense, "BURN_WRAP": burn,
            "DEFENSE_NAME": '"DEFENSE"' if port.params.get("defense") else '(specialMove? ? "SPECIAL_DEFENSE" : "DEFENSE")'}


def _absorb_effect(port: _Port) -> str:
    """What absorbing does: Volt Absorb's quarter heal or Sap Sipper's stat, through
    Nova's own battler helpers; several stats in turn, as those helpers would."""
    if port.params.get("heal"):
        return f"      next target.pbMoveImmunityHealingAbility(user, move, type, :{port.type}, show_message)"
    stats = [_STAT_NAMES[str(st)][0] for st in port.params["stats"]]  # type: ignore[union-attr]
    if len(stats) == 1:
        return (f"      next target.pbMoveImmunityStatRaisingAbility(user, move, type, :{port.type}, "
                f":{stats[0]}, 1, show_message)")
    return "\n".join([
        "      if show_message",
        "        battle.pbShowAbilitySplash(target)",
        "        raised = false",
        f"        [{', '.join(':' + st for st in stats)}].each do |stat|",
        "          next if !target.pbCanRaiseStatStage?(stat, target)",
        "          if Battle::Scene::USE_ABILITY_SPLASH",
        "            target.pbRaiseStatStage(stat, 1, target)",
        "          else",
        "            target.pbRaiseStatStageByCause(stat, 1, target, target.abilityName)",
        "          end",
        "          raised = true",
        "        end",
        "        if !raised",
        "          battle.pbDisplay(_INTL(\"It doesn't affect {1}...\", target.pbThis(true)))",
        "        end",
        "        battle.pbHideAbilitySplash(target)",
        "      end",
        "      next true",
    ])


def _block_spec(spec: BehaviorSpec, block: BehaviorTemplate) -> BehaviorSpec:
    """One block as a one-effect spec of its own: its shape, its first effect, its cases."""
    return replace(spec, template=BehaviorTemplate(shape=block.shape, params=block.params, probes=block.probes),
                   effects=(spec.effects[block.effects[0] - 1],),
                   test_cases=tuple(spec.test_cases[c - 1] for c in block.cases))


def _render_blocks(spec: BehaviorSpec, names: Names) -> str:
    validate_spec(spec)
    assert spec.template is not None
    bodies: list[str] = []
    ability = ""
    for n, block in enumerate(spec.template.blocks, start=1):
        if block.shape in _BLOCK_ONLY:
            continue
        if block.shape == "drops":
            ability = names.ability(spec.name) or ""
            if not ability:
                raise TemplateError(f"{spec.chrooked_id}.yaml:template: ability {spec.name!r} does not resolve")
            bodies.append(_fill(_DROPS, {"ID": spec.chrooked_id, "ABILITY": ability, "N": str(n),
                                         "REGISTRY": str(block.params["registry"])}))
            continue
        part = _block_spec(spec, block)
        port = _resolve(part, names)
        ability = port.ability
        body = _body(part, port, "").replace('\n\n  ChrookedLog.line("[chrooked:', '\n  ChrookedLog.line("[chrooked:')
        bodies.append(body.replace(" ability=true", f" ability=true block={n}"))
    tail = "\n".join([
        "begin",
        render_selftest_case(spec.chrooked_id, ability, selftest_case(spec, names)),
        f'  ChrookedLog.line("[chrooked:{spec.chrooked_id}] installed: {len(bodies)} block{"s" if len(bodies) != 1 else ""}")',
        "rescue StandardError => e",
        f'  ChrookedLog.error("[chrooked:{spec.chrooked_id}] ERROR #{{e.class}}: #{{e.message}}")',
        "end",
        "",
    ])
    return _fill(_PORT, {"HEADER": _blocks_header(spec), "LOG": _CHROOKED_LOG, "BODY": "".join(bodies) + tail})


def _weather_symbol(neutral: str) -> str:
    """The Essentials weather a neutral name sets (sand -> Sandstorm)."""
    weathers = vocab.weathers(neutral)
    if not weathers:
        raise TemplateError(f"no Essentials weather for {neutral!r}")
    return weathers[0]


def _blocks_header(spec: BehaviorSpec) -> str:
    assert spec.template is not None
    summary = " ".join(" ".join(e.summary.split()) for e in spec.effects)
    listed = "; ".join(
        f"block {n}, effects {', '.join(map(str, b.effects))}: "
        + (f"kept by the game's own {spec.name}" if b.shape == "keeps"
           else f"not in this game ({b.params['reason']})" if b.shape == "absent"
           else f"drops the game's own {spec.name} handler from {b.params['registry']}" if b.shape == "drops"
           else f"{b.shape} on {' and '.join(_REGISTRIES[b.shape])}")
        for n, b in enumerate(spec.template.blocks, start=1))
    return "\n".join([
        f"# chrooked:{spec.chrooked_id}",
        _RULE,
        f"# GENERATED by chrooked-pokedex from ruleset/behaviors/{spec.chrooked_id}.yaml",
        "# (template: blocks). Do not edit this file: change the spec and run apply.",
        "#",
        *_comment(f'Ruleset behavior "{spec.chrooked_id}": {summary}'),
        "#",
        *_comment(f"BLOCKS (mjolnir NV-18), each its own registry entry, its log lines marked block=<n>: "
                  f"{listed}. A kept effect is the game's own ability's, which this port leaves in place."),
        "#",
        *_comment("Install, load order, the marker-gated oracle, the OBS/EST split and the "
                  "self-test registration at the end are explained once, in "
                  "references/essentials21-harness/README.md."),
        _RULE,
    ])


def harness_checks(spec: BehaviorSpec, names: Names) -> list[dict[str, object]]:
    """One harness check per probe, aligned with the spec's test_cases.

    Each check selects the port's OBS line for the probe's move and holder (plus the
    HP side of a pinch, or the scene a conditional boost was measured in) and
    expects the probe's outcome, in the keys the generated port logs. Values are
    strings, as the harness compares them.
    """
    if spec.template is not None and spec.template.shape == "blocks":
        return _blocks_checks(spec, names)
    port = _resolve(spec, names)
    pinch = port.shape == "type_boost" and bool(port.params["pinch"])
    checks: list[dict[str, object]] = []
    for probe in port.probes:
        if port.shape == "struck_status":
            checks.append({"stage": _stage(spec.name, probe, pinch, port), "select": {
                "move": probe.move, "ability": "true", "source": "selftest", "side": "struck",
                "attacker_types": "/".join(probe.attacker_types) or "QMARKS",
            }, "expect": {"status_ok": "true"}})
            continue
        if port.shape == "hit_status":
            # The rate is the self-test's to measure: its own line, per target typing.
            checks.append({"stage": _stage(spec.name, probe, pinch, port), "select": {
                "move": probe.move, "ability": "true", "source": "selftest",
                "target_types": "/".join(probe.target_types) or "QMARKS",
            }, "expect": {"damage": "NORMAL", "status_ok": "true", "flinch_ok": "true"}})
            continue
        if port.shape in ("hit_drain", "ko_effect", "priority_boost"):
            state_select, state_expect = _state_check(port, probe)
            checks.append({"stage": _stage(spec.name, probe, pinch, port),
                           "select": state_select, "expect": state_expect})
            continue
        select: dict[str, object] = {"move": probe.move, "ability": _flag(probe.holder)}
        if pinch and probe.holder:
            select["hp_low"] = _flag(probe.hp * 3 <= 1)  # the port's user.hp <= user.totalhp / 3
        if port.shape in _SCENE_SHAPES:
            select.update(_scene(port, probe))
        if port.shape == "type_conversion":
            expect = {"converted": port.type if probe.outcome else "none", "boosted": _flag(bool(probe.outcome))}
        elif port.shape == "type_immunity" and probe.mold_breaker:
            # Mold Breaker skips the handler, so the self-test's own line says it.
            select.update({"source": "selftest", "mold_breaker": "true"})
            expect = {"immune": _flag(bool(probe.outcome))}
        elif port.shape == "type_immunity":
            expect = {"result": "IMMUNE" if probe.outcome else "NORMAL"}
        elif port.shape == "type_resist":
            expect = {"result": "APPLIED" if probe.outcome else "NORMAL"}
        elif port.shape == "damage_taken":
            expect = {"factor": f"{float(_fraction(probe.outcome) or 1):.3f}"}
        elif port.shape == "stat_swap":
            select, expect = _swap_check(port, probe, select)
        elif port.shape == "crit_condition":
            label = f"p{port.probes.index(probe) + 1}"
            select = {"case": "crit", "label": label, "source": "selftest"}
            expect = {"forced": _flag(bool(probe.outcome))}
        elif port.shape == "type_absorb":
            # Absorbing heals or raises inside the handler, so the self-test's own line says it.
            select.update({"source": "selftest", "mold_breaker": "false", "hp_set": _ruby_float(probe.hp),
                           "stages_set": _stages_set(port, probe)})
            effect = "NONE"
            if probe.outcome and port.params.get("heal") and probe.hp < 1:
                effect = "HEALED"
            elif probe.outcome and port.params.get("stats") and probe.stage < _MAX_STAGE:
                effect = "RAISED"
            expect = {"immune": _flag(bool(probe.outcome)), "effect": effect}
        else:
            expect = {"result": str(probe.outcome).upper()}
        checks.append({"stage": _stage(spec.name, probe, pinch, port), "select": select, "expect": expect})
    return checks


def _swap_check(port: _Port, probe: _Probe,
                select: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    """A stat swap's check: the port's line for the scene the probe set (its stats and
    stages), or for a burned probe its burn line; a status move or a blocked move is
    the self-test's own line."""
    if probe.outcome == "status_move":
        return {"case": "category", "move": probe.move, "source": "selftest"}, {"status": "true"}
    if probe.outcome == "blocked":
        return ({"case": "blocked", "move": probe.move, "foe_ability": probe.blocked_by, "source": "selftest"},
                {"immune": "true"})
    if probe.burned:
        halves = port.params["burn"] == "physical"
        return {**select, "burn_check": "true"}, {"halves": _flag(halves)}
    values = dict(probe.stat_values)
    stages = dict(probe.stat_stages)
    if "ATTACK" in values:
        select["atk"] = str(values["ATTACK"])
    if "SPECIAL_ATTACK" in values:
        select["spatk"] = str(values["SPECIAL_ATTACK"])
    select["atk_stage"] = str(stages.get("ATTACK", 0))
    select["spatk_stage"] = str(stages.get("SPECIAL_ATTACK", 0))
    expect: dict[str, object] = {"attack_stat": str(probe.outcome).upper()}
    if port.params.get("defense"):
        expect["defense_stat"] = "DEFENSE"
    return select, expect


def _stages_set(port: _Port, probe: _Probe) -> str:
    """The stages a type_absorb probe sets on the holder first, as the self-test logs them."""
    if not probe.stage or not port.params.get("stats"):
        return "none"
    return "/".join(f"{_STAT_NAMES[str(st)][0]}:{probe.stage}" for st in port.params["stats"])  # type: ignore[union-attr]


def _blocks_checks(spec: BehaviorSpec, names: Names) -> list[dict[str, object]]:
    """Each block's checks, in test-case order; one on a port line also selects its
    block, and a keeps block's read the self-test's comparison with no ability."""
    validate_spec(spec)
    assert spec.template is not None
    by_case: dict[int, dict[str, object]] = {}
    for n, block in enumerate(spec.template.blocks, start=1):
        if block.shape == "absent":
            for case in block.cases:
                reason = str(block.params["reason"])
                by_case[case] = {"stage": f"Not in this game: {reason}", "absent": reason,
                                 "select": {}, "expect": {}}
            continue
        if block.shape in ("keeps", "drops"):
            for case, probe in zip(block.cases, block.probes):
                select = {"case": "keeps", "kind": str(probe["measure"]), "source": "selftest"}
                if "weather" in probe:
                    select["weather"] = _weather_symbol(str(probe["weather"]))
                    scene = f"in {probe['weather']}"
                else:
                    select["status"] = _STATUSES[str(probe["status"])][0]
                    scene = f"with {probe['status']}"
                # keeps: the game's own ability still differs from none; drops: it no longer does.
                kept = block.shape == "keeps"
                by_case[case] = {"stage": f"Measured by the self-test: {spec.name}'s own {probe['measure']} "
                                          f"{scene}{'' if kept else ', dropped'}.",
                                 "select": select, "expect": {"changed": _flag(kept)}}
            continue
        for case, check in zip(block.cases, harness_checks(_block_spec(spec, block), names)):
            select = dict(check["select"])  # type: ignore[call-overload]
            if select.get("ability") == "true" and select.get("source") != "selftest":
                select["block"] = str(n)
            by_case[case] = {**check, "select": select}
    return [by_case[case] for case in sorted(by_case)]


def _state_check(port: _Port, probe: _Probe) -> tuple[dict[str, object], dict[str, object]]:
    """A check on a port that logs the state deciding its outcome (NV-14): select that
    state, so the first matching line is the one the probe describes."""
    if port.shape == "hit_drain":
        select: dict[str, object] = {"move": probe.move, "ability": "true", "ooze": _flag(probe.ooze)}
        if probe.outcome == "healed":
            select["can_heal"] = "true"
        return select, {"result": str(probe.outcome).upper()}
    if port.shape == "priority_boost":
        select = {"move": probe.move, "ability": "true", "hp_full": _flag(probe.hp >= 1)}
        return select, {"result": "BOOSTED" if probe.outcome == "boosted" else "NORMAL"}
    select = {"ability": "true", "kos": str(probe.kos)}
    if port.params["heal"] is not None:
        select["hp_full"] = _flag(probe.hp >= 1)
        return select, {"result": "HEALED" if probe.outcome else "NONE"}
    select["stage"] = str(probe.stage)
    if not probe.outcome:
        return select, {"result": "NONE"}
    return select, {"result": "RAISED", "change": str(min(probe.kos, _MAX_STAGE - probe.stage))}


# --- resolution ------------------------------------------------------------------


@dataclass(frozen=True)
class _Probe:
    name: str      # the neutral move name, for stage text
    move: str      # the target's INTERNAL move name
    outcome: object  # "boosted" / "normal", or a bool for type_conversion
    hp: float
    holder: bool
    field: bool = True               # conditional_boost: the weather or terrain is up
    item: Optional[str] = None       # INTERNAL held item
    item_name: Optional[str] = None  # its neutral name, for stage text
    airborne: bool = False
    stats: Optional[str] = None      # "physical" / "special": the higher attacking stat
    types: tuple[str, ...] = ()      # INTERNAL types to give the user (stab_grant)
    type_names: tuple[str, ...] = ()  # their neutral names, for stage text
    target_types: tuple[str, ...] = ()       # INTERNAL types to give the target (hit_status)
    target_type_names: tuple[str, ...] = ()  # their neutral names, for stage text
    ooze: bool = False   # hit_drain: the target holds Liquid Ooze
    kos: int = 0         # ko_effect: foes the move knocked out
    stage: int = 0       # ko_effect: the user's stage in the raised stat
    mold_breaker: bool = False  # type_immunity: the attacker breaks the mold
    attacker_types: tuple[str, ...] = ()  # struck_status: INTERNAL types to give the attacker
    stat_values: tuple[tuple[str, int], ...] = ()  # stat_swap: (STAT, value) set first
    stat_stages: tuple[tuple[str, int], ...] = ()  # stat_swap: (STAT, stage) set first
    burned: bool = False                            # stat_swap: the user is burned first
    blocked_by: Optional[str] = None                # stat_swap: INTERNAL ability of the foe
    target_status: Optional[str] = None             # crit_condition: Essentials status of the target
    target_speed: int = 0                           # crit_condition: the target's Speed stage
    target_ability: Optional[str] = None            # crit_condition: INTERNAL ability of the target


@dataclass(frozen=True)
class _Port:
    shape: str
    params: dict[str, object]   # with defaults filled in
    ability: str
    type: Optional[str]         # INTERNAL, for the type shapes
    flags: tuple[str, ...]      # Essentials flag names, for flag_boost
    probes: tuple[_Probe, ...]
    weathers: tuple[str, ...] = ()  # Essentials weathers that count, for a weather boost
    terrain: Optional[str] = None   # Essentials terrain, for a terrain boost
    grant_types: Optional[tuple[str, ...]] = None  # stab_grant: INTERNAL types, None = all
    rules: tuple[tuple[Fraction, Optional[str], bool, bool], ...] = ()  # damage_taken: (multiplier, type, contact, SE)


def _resolve(spec: BehaviorSpec, names: Names) -> _Port:
    """Validate the spec and its template and turn every neutral name into the target's own."""
    validate_spec(spec)
    template = spec.template
    assert template is not None  # validate_spec refuses a spec without one
    where = f"{spec.chrooked_id}.yaml:template"
    params = {**_PARAMS[template.shape][1], **template.params}

    missing: list[str] = []
    ability = names.ability(spec.name)
    if ability is None:
        missing.append(f"ability {spec.name!r}")
    type_ = None
    if "type" in template.params:
        type_ = names.type(str(params["type"]))
        if type_ is None:
            missing.append(f"type {params['type']!r}")
    flags: list[str] = []
    for neutral in params.get("flags") or ():  # type: ignore[union-attr]
        flag = vocab.flag(neutral)
        if flag is None:
            missing.append(f"Essentials flag for move flag {neutral!r}")
        else:
            flags.append(flag)
    weathers: tuple[str, ...] = ()
    if params.get("weather") is not None:
        weathers = vocab.weathers(str(params["weather"])) or ()
    terrain = vocab.terrain(str(params["terrain"])) if params.get("terrain") is not None else None

    def resolve_types(type_names: object) -> tuple[str, ...]:
        resolved = []
        for type_name in type_names:  # type: ignore[union-attr]
            internal = names.type(str(type_name))
            if internal is None:
                missing.append(f"type {type_name!r}")
            resolved.append(internal or "")
        return tuple(resolved)

    rules: list[tuple[Fraction, Optional[str], bool, bool]] = []
    for rule in params.get("rules") or ():  # type: ignore[union-attr]
        rule_type = None
        if "type" in rule:
            rule_type = names.type(str(rule["type"]))
            if rule_type is None:
                missing.append(f"type {rule['type']!r}")
        rules.append((_fraction(rule["multiplier"]) or Fraction(1), rule_type, bool(rule.get("contact")),
                      bool(rule.get("super_effective"))))
    def resolve_ability(name: object) -> Optional[str]:
        if name is None:
            return None
        internal = names.ability(str(name))
        if internal is None:
            missing.append(f"ability {name!r}")
        return internal

    grant_types = None
    if template.shape == "stab_grant" and params["types"] != "all":
        grant_types = resolve_types(params["types"])
    outcome = _OUTCOME[template.shape]
    probes: list[_Probe] = []
    for probe in template.probes:
        move = None
        if template.shape != "ko_effect":
            move = names.move(str(probe["move"])) or _BUILTIN_MOVES.get(str(probe["move"]).lower())
            if move is None:
                missing.append(f"move {probe['move']!r}")
        item = None
        if "item" in probe:
            item = names.item(str(probe["item"]))
            if item is None:
                missing.append(f"item {probe['item']!r}")
        probes.append(_Probe(
            name=str(probe.get("move", "")), move=move or "", outcome=probe[outcome],
            hp=float(probe.get("hp", 1.0)), holder=bool(probe.get("holder", True)),  # type: ignore[arg-type]
            field=bool(probe.get("field", True)), item=item,
            item_name=str(probe["item"]) if "item" in probe else None,
            airborne=bool(probe.get("airborne", False)),
            stats=str(probe["stats"]) if "stats" in probe else None,
            types=resolve_types(probe.get("types") or ()),
            type_names=tuple(str(t) for t in probe.get("types") or ()),  # type: ignore[union-attr]
            target_types=resolve_types(probe.get("target_types") or ()),
            target_type_names=tuple(str(t) for t in probe.get("target_types") or ()),  # type: ignore[union-attr]
            ooze=bool(probe.get("ooze", False)), kos=int(probe.get("kos", 0)),  # type: ignore[call-overload]
            stage=int(probe.get("stage", 0)),  # type: ignore[call-overload]
            mold_breaker=bool(probe.get("mold_breaker", False)),
            attacker_types=resolve_types(probe.get("attacker_types") or ()),
            stat_values=tuple((_STAT_NAMES[k][0], int(v)) for k, v in probe.items()  # type: ignore[call-overload]
                              if k in ("attack", "special_attack")),
            stat_stages=tuple((_STAT_NAMES[str(k)][0], int(v))  # type: ignore[call-overload]
                              for k, v in (probe.get("stages") or {}).items()),  # type: ignore[union-attr]
            burned=bool(probe.get("burned", False)),
            blocked_by=resolve_ability(probe.get("blocked_by")),
            target_status=str(probe["target_status"]) if probe.get("target_status") else None,
            target_speed=int(probe.get("target_speed", 0)),  # type: ignore[call-overload]
            target_ability=resolve_ability(probe.get("target_ability")),
        ))
    if template.shape == "hit_drain" and any(p.get("ooze") for p in template.probes) \
            and names.ability("Liquid Ooze") is None:
        missing.append("ability 'Liquid Ooze'")
    if missing:
        raise TemplateError(f"{where}: the target has no {', '.join(dict.fromkeys(missing))}")
    return _Port(shape=template.shape, params=params, ability=ability or "", type=type_,
                 flags=tuple(flags), probes=tuple(probes), weathers=weathers, terrain=terrain,
                 grant_types=grant_types, rules=tuple(rules))


# --- rendering -------------------------------------------------------------------

_PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
_RULE = "# " + "-" * 75


def _fill(text: str, values: Mapping[str, str]) -> str:
    """Replace every `{{KEY}}` in one pass. Values are never re-scanned, and a key
    with no value is an error, so nothing is left half-filled."""
    def value(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise TemplateError(f"internal: no value for placeholder {{{{{key}}}}}")
        return values[key]
    return _PLACEHOLDER.sub(value, text)


def _flag_test(port: _Port) -> str:
    """Nova's flag test, as its Iron Fist and Liquid Voice read flags."""
    return f"move.flags.any? {{ |f| f[/^({'|'.join(port.flags)})$/i] }}"


def _conversion_gate(port: _Port) -> str:
    """The moves a type conversion takes: Normal ones, or any, and only flagged ones
    when it names flags."""
    if port.params["from"] == "normal":
        lines = [f"      next if type != :NORMAL || !GameData::Type.exists?(:{port.type})"]
    else:
        lines = [f"      next if !GameData::Type.exists?(:{port.type})"]
    if port.flags:
        lines.append(f"      next if !{_flag_test(port)}")
    return "\n".join(lines)


def _hit_gate(port: _Port) -> str:
    """The hits a status chance rides on: the move's type as used, or its flags."""
    if port.type is not None:
        return f"      next if move.calcType != :{port.type}"
    if port.params.get("contact"):
        return "      next if !move.pbContactMove?(user)"
    return f"      next if !{_flag_test(port)}"


def _conditional_ruby(port: _Port) -> dict[str, str]:
    """The gate, the multiplier and the logged fields of a conditional boost.

    The terrain gate is Nova's own test for Grassy Terrain's healing; the weather
    gate reads `effectiveWeather`, which already clears sun and rain for a Utility
    Umbrella holder and every weather under Air Lock or Cloud Nine.
    """
    higher_stat = port.params["moves"] == "higher_stat"
    if port.weathers:
        lines = [("weather", "user.battle.pbWeather")]
        gate = f"[{', '.join(':' + w for w in port.weathers)}].include?(user.effectiveWeather)"
        fields_a, fields_b = "weather=#{weather} item=#{user.item_id || 'none'} ", ""
    else:
        lines = [("terrain", "user.battle.field.terrain"), ("grounded", "user.affectedByTerrain?")]
        gate = f"terrain == :{port.terrain} && grounded"
        fields_a, fields_b = "terrain=#{terrain} ", "grounded=#{grounded} "
    if higher_stat:
        lines.append(("higher", "(user.attack >= user.spatk) ? :physical : :special"))
        fields_b += "higher=#{higher} "
    width = max(len(name) for name, _ in lines + [("boosted", "")])
    code = [f"      {name:<{width}} = {expr}" for name, expr in lines]
    if higher_stat:
        code.append(f"      {'boosted':<{width}} = {gate} &&")
        code.append(" " * (6 + width + 3) + "(higher == :physical ? move.physicalMove? : move.specialMove?)")
    else:
        code.append(f"      {'boosted':<{width}} = {gate}")
    return {
        "CONDITION": "\n".join(code),
        # Sand Force raises power; Solar Power, which picks a stat, raises that stat.
        "MULT_KIND": "attack" if higher_stat else "power",
        "FIELDS_A": fields_a,
        "FIELDS_B": fields_b,
    }


def _header(spec: BehaviorSpec, port: _Port) -> str:
    multiplier = _ruby_float(port.params["multiplier"]) if "multiplier" in port.params else ""
    seam = "Battle::AbilityEffects::DamageCalcFromUser"
    when_logged, estimates = "a real hit", True
    if port.shape == "type_boost":
        pinch = bool(port.params["pinch"])
        note = (f"Nova's Blaze handler{'' if pinch else ' minus its HP check'}, for {port.params['type']}: an "
                f"attack-stat multiplier ({multiplier}x)"
                f"{' at or below 1/3 max HP (user.hp <= user.totalhp / 3)' if pinch else ''}, so tiny "
                f"hits land a little under {multiplier}x (the damage formula's flat +2 is never scaled).")
        obs = "move=<ID> type=<TYPE> ability=true " + ("hp_low=<true|false> " if pinch else "") + "result=<BOOSTED|NORMAL>"
    elif port.shape == "type_conversion":
        seam = "Battle::AbilityEffects::ModifyMoveBaseType (the conversion) plus DamageCalcFromUser (the rider)"
        flags = " or ".join(port.flags)
        if port.params["from"] == "normal" and not port.flags:
            note = (f"The pair Nova's own Aerilate and Dragonize use: Normal moves become {port.params['type']} and set "
                    f"move.powerBoost, and the {multiplier}x power rider reads that flag, so moves that compute "
                    "their own type (Weather Ball, Judgment, Struggle, ...) are never converted.")
        elif port.params["from"] == "normal":
            note = (f"Nova's Aerilate pair with one more gate, the move's {flags} flag (read as Nova's Liquid "
                    f"Voice reads Sound): Normal-type {flags} moves become {port.params['type']} and set "
                    f"move.powerBoost, and the {multiplier}x power rider reads that flag.")
        else:
            which = f"{flags} moves of any type" if port.flags else "every move"
            note = (f"{which[0].upper() + which[1:]} become {port.params['type']} (Nova's Normalize shape"
                    f"{', gated on the flag as its Liquid Voice is' if port.flags else ''}) and set "
                    f"move.powerBoost, and the {multiplier}x power rider reads that flag.")
        obs = "move=<ID> ability=true converted=<TYPE|none> boosted=<true|false>"
    elif port.shape == "flag_boost":
        note = (f"Nova's Iron Fist shape: a {multiplier}x power multiplier when the move carries a "
                f"{' or '.join(port.flags)} flag. Kicking, Hammer, Piercing and Wing are custom flags the dex "
                "writes into the game's move data (appliers/essentials/vocab.py); without the flag in "
                "the data this port never fires.")
        obs = "move=<ID> ability=true category=<flag|none> result=<BOOSTED|NORMAL>"
    elif port.shape == "stab_grant":
        which = ("every move with a type" if port.grant_types is None
                 else f"{' and '.join(str(t) for t in port.params['types'])}-type moves")
        note = (f"Nova's own STAB (Battle::Move#pbCalcDamageMultipliersSTAB) multiplies final damage by "
                f"1.5 when `type && user.pbHasType?(type)`. This grants {which} the same factor "
                f"({multiplier}x) in the same slot, only when the user LACKS the type, so STAB never "
                "doubles; Struggle (type nil) gets none, as in Nova's STAB. Modelled on the hand-written "
                "Full Moon port (mjolnir NV-10).")
        obs = "move=<ID> type=<TYPE> ability=true user_types=<T/T> own=<true|false> result=<BOOSTED|NORMAL>"
    elif port.shape == "hit_status":
        seam = "Battle::AbilityEffects::OnDealingHit"
        verb = {"burn": "burn", "poison": "poison", "paralysis": "paralyze"}[str(port.params["status"])]
        gate = (f"is {port.params['type']}-type as used (move.calcType)" if port.type is not None
                else "makes contact (pbContactMove?)" if port.params.get("contact")
                else f"carries a {' or '.join(port.flags)} flag")
        note = (f"Nova's Poison Touch shape: Nova fires this registry for the user's ability only after a "
                f"hit that dealt damage and missed any substitute; when the move {gate}, a "
                f"{port.params['chance']}% roll to {verb} the target. Never through Shield Dust or on a "
                f"target unaffected by additional effects, and pbCan{_STATUSES[str(port.params['status'])][1]}? "
                "is asked before the roll. The lab self-test measures the rate over seeded rolls and logs "
                "it on this mechanic's behalf with source=selftest.")
        obs = "move=<ID> type=<TYPE> ability=true hit=true can_inflict=<bool> inflicted=<bool>"
        when_logged, estimates = "after a gated hit", False
    elif port.shape == "type_immunity":
        seam = "Battle::AbilityEffects::MoveImmunity"
        note = (f"Nova's Bulletproof shape, keyed on the type: Nova asks this registry from "
                f"pbImmunityByAbility for every move aimed at the holder (status moves included) with the "
                f"move's type as used, unless Mold Breaker bypasses it, so {_a(str(port.params['type']))}-type move "
                "deals no damage and lands no secondary effect. Like Nova's own type immunities (Volt "
                "Absorb, Flash Fire) it never blocks a move the holder aims at itself.")
        obs = "move=<ID> type=<TYPE> ability=true result=<IMMUNE|NORMAL>"
        when_logged = "a move aimed at the holder"
    elif port.shape == "struck_status":
        seam = "Battle::AbilityEffects::OnBeingHit"
        stem = _STATUSES[str(port.params["status"])][1]
        note = (f"Nova's Flame Body shape: after a contact move that dealt damage to the holder (and missed any "
                f"substitute), a {port.params['chance']}% roll to give the ATTACKER {port.params['status']}, "
                f"unless Protective Pads or the like spare it (affectedByContactEffect?); pbCan{stem}? is "
                "asked before the roll. The lab self-test measures the rate over seeded rolls (source=selftest, "
                "side=struck).")
        obs = "move=<ID> type=<TYPE> ability=true struck=true can_inflict=<bool> inflicted=<bool>"
        when_logged, estimates = "after a contact hit on the holder", False
    elif port.shape == "hit_drain":
        seam = "Battle::AbilityEffects::OnDealingHit"
        which = "makes contact" if port.params["moves"] == "contact" else "does not make contact"
        note = (f"Nova fires this registry for the user's ability only after a hit that dealt damage and "
                f"missed any substitute. When the move {which} (pbContactMove?, as Nova's Poison Touch asks), "
                f"the user heals round({port.params['fraction']} x the HP the target lost) through Nova's own "
                "drain path, Battle::Battler#pbRecoverHPFromDrain, as its drain moves do: Big Root adds 30%, "
                "Heal Block and full HP stop it, and a Liquid Ooze target reverses it. Silent when the user "
                "could not heal and the target has no Liquid Ooze. Modelled on the hand-written Vampiric "
                "(mjolnir NV-14).")
        obs = ("move=<ID> ability=true contact=<bool> ooze=<bool> can_heal=<bool> hp_lost=<n> change=<n> "
               "result=<HEALED|REVERSED|NONE>")
        when_logged, estimates = "after a hit", False
    elif port.shape == "ko_effect":
        seam = "Battle::AbilityEffects::OnEndOfUsingMove"
        if port.params["heal"] is not None:
            what = (f"heals {port.params['heal']} of max HP (floored) while the user can heal (alive, below "
                    "full HP, no Heal Block), with Nova's Ice Body message; one heal however many foes fell. "
                    "Modelled on the hand-written Carnivore (mjolnir NV-14)")
            obs = "move=<ID> ability=true kos=<n> hp_full=<bool> change=<n> result=<HEALED|NONE>"
        else:
            stat = _STAT_NAMES[str(port.params["stat"])][1]
            what = f"raises {stat} one stage per foe knocked out, as Moxie raises Attack"
            obs = "move=<ID> ability=true kos=<n> stage=<n> change=<n> result=<RAISED|NONE>"
        note = (f"Nova's Moxie shape: after each move the holder uses, a target counts when its damage state "
                f"says it fainted, and nothing happens if the knockout ended the battle. The port {what}.")
        when_logged, estimates = "after each move the holder uses", False
    elif port.shape == "priority_boost":
        seam = "Battle::AbilityEffects::PriorityChange"
        hp = " while the holder is at full HP (battler.hp == battler.totalhp)" if port.params["full_hp"] else ""
        note = (f"Nova's Gale Wings for {port.params['type']}: +1 priority for moves whose own type "
                f"(move.type, as Gale Wings reads it) is {port.params['type']}{hp}. pbCalculatePriority asks "
                "it each round for the holder's chosen move; the AI asks it too. Modelled on the "
                "hand-written Rapid Combustion (mjolnir NV-14).")
        obs = "move=<ID> type=<TYPE> ability=true hp_full=<bool> priority=<n> result=<BOOSTED|NORMAL>"
        when_logged = "each round's priority"
    elif port.shape == "crit_condition":
        seam = "Battle::AbilityEffects::CriticalCalcFromUser"
        note = ("Nova's Merciless shape, widened: the handler returns 99 when the target is "
                f"{port.params['when']} ({_CRIT_WHEN[str(port.params['when'])]}), and pbIsCritical? takes any "
                "stage above 50 as a certain critical hit. It asks the user's handler first, so the target's "
                "Battle Armor or Shell Armor (CriticalCalcFromTarget, -1) and Lucky Chant still deny it, as "
                "they deny Merciless.")
        obs = "move=<ID> ability=true result=<FORCED|NORMAL>"
        when_logged = "each critical-hit check"
    else:
        higher_stat = port.params["moves"] == "higher_stat"
        if higher_stat:
            what = (f"Nova's Solar Power shape: a {multiplier}x attack-stat multiplier on the moves of the "
                    "user's higher attacking stat (physical when Attack >= Sp. Atk, special otherwise)")
        else:
            what = f"Nova's Sand Force shape: a {multiplier}x power multiplier on every move"
        if port.weathers:
            umbrella = port.params["weather"] in ("rain", "sun")
            when = (f"while user.effectiveWeather is {' or '.join(':' + w for w in port.weathers)}"
                    f"{' (a Utility Umbrella clears it for its holder; Air Lock and Cloud Nine clear it for all)' if umbrella else ' (Air Lock and Cloud Nine clear it)'}")
            obs = "move=<ID> ability=true weather=<WEATHER> item=<ITEM|none> "
        else:
            when = (f"while the field's terrain is :{port.terrain} and the user is affected by terrain "
                    "(grounded and not semi-invulnerable), Nova's own test for Grassy Terrain's healing")
            obs = "move=<ID> ability=true terrain=<TERRAIN> grounded=<true|false> "
        note = f"{what}, {when}."
        obs += ("higher=<physical|special> " if higher_stat else "") + "result=<BOOSTED|NORMAL>"
    summary = " ".join(spec.effects[0].summary.split()) if spec.effects else spec.name
    lines = [
        f"# chrooked:{spec.chrooked_id}",
        _RULE,
        f"# GENERATED by chrooked-pokedex from ruleset/behaviors/{spec.chrooked_id}.yaml",
        f"# (template: {port.shape}). Do not edit this file: change the spec and run apply.",
        "#",
        *_comment(f'Ruleset behavior "{spec.chrooked_id}": {summary}'),
        "#",
        *_comment(f"Essentials 21 Seam: {seam}. {note}"),
        "#",
        *_comment("Install, load order, the marker-gated oracle, the OBS/EST split and the "
                  "self-test registration at the end are explained once, in "
                  "references/essentials21-harness/README.md."),
        f"#     [chrooked:{spec.chrooked_id}] OBS {obs}   {when_logged}",
        *([f"#     [chrooked:{spec.chrooked_id}] EST ...   an AI estimate, never scored"] if estimates else []),
        _RULE,
    ]
    return "\n".join(lines)


@dataclass(frozen=True)
class SelftestCase:
    """What the lab self-test measures for one port, as Ruby fragments, before they
    are written into its `$chrooked_selftest_cases` entry. A composed ability merges
    its parts' cases into one (behavior/compose.py).

    calc: the holder probes, once per (move, HP, scene); phases: the measurement
    phases a non-damage shape adds after calc, (key, entries) in order; without: the
    holder: false moves; fight: the holder's distinct moves, at most four, for one
    AI-vs-AI battle. A conditional boost's entries carry a setup hash (the
    self-test's `arrange`).
    """

    control: Optional[str]  # INTERNAL comparison ability, or None
    calc: tuple[str, ...]
    phases: tuple[tuple[str, tuple[str, ...]], ...]
    without: tuple[str, ...]
    fight: tuple[str, ...]


def selftest_case(spec: BehaviorSpec, names: Names) -> SelftestCase:
    """A templated spec's self-test case, resolved against the target's names; a
    spec in blocks merges its blocks' cases."""
    if spec.template is None or spec.template.shape != "blocks":
        return _case(_resolve(spec, names))
    cases = []
    keeps: list[str] = []
    for block in spec.template.blocks:
        if block.shape == "absent":
            continue
        if block.shape in ("keeps", "drops"):
            keeps += [f"[:{p['measure']}, {{weather: :{_weather_symbol(str(p['weather']))}}}]" if "weather" in p
                      else f"[:{p['measure']}, {{status: :{_STATUSES[str(p['status'])][0]}}}]" for p in block.probes]
        else:
            cases.append(_case(_resolve(_block_spec(spec, block), names)))
    return merge_cases(cases, extra=(("keeps", tuple(keeps)),) if keeps else ())


def merge_cases(cases: list[SelftestCase], extra: tuple[tuple[str, tuple[str, ...]], ...] = (),
                fight: tuple[str, ...] = ()) -> SelftestCase:
    """Several ports' cases as one: the first control, every calc entry and phase
    entry once, at most four fight moves."""
    control: Optional[str] = None
    calc: list[str] = []
    phases: dict[str, list[str]] = {}
    without: list[str] = []
    moves: list[str] = []
    for case in cases:
        control = control or case.control
        calc += case.calc
        for key, entries in case.phases:
            phases.setdefault(key, []).extend(entries)
        without += case.without
        moves += case.fight
    for key, entries in extra:
        phases.setdefault(key, []).extend(entries)
    moves += fight
    return SelftestCase(
        control=control, calc=tuple(dict.fromkeys(calc)),
        phases=tuple((key, tuple(dict.fromkeys(entries))) for key, entries in phases.items()),
        without=tuple(dict.fromkeys(without)), fight=tuple(dict.fromkeys(moves))[:FIGHT_MOVES])


def render_selftest_case(chrooked_id: str, ability: str, case: SelftestCase) -> str:
    """The `$chrooked_selftest_cases["<id>"] = {...}` registration for a port."""
    return _fill(_SELFTEST, {
        "ID": chrooked_id,
        "ABILITY": ability,
        "CONTROL": f":{case.control}" if case.control else "nil",
        "USER": _SELFTEST_USER,
        "FOE": _SELFTEST_FOE,
        "CALC": ", ".join(case.calc),
        "PHASES": "".join(_render_phase(key, entries) for key, entries in case.phases),
        "WITHOUT": ", ".join(case.without),
        "FIGHT": ", ".join(case.fight),
    })


def _selftest_case(spec: BehaviorSpec, port: _Port) -> str:
    return render_selftest_case(spec.chrooked_id, port.ability, _case(port))


def _case(port: _Port) -> SelftestCase:
    calc: list[str] = []
    for probe in port.probes:
        setup = f", {_setup(port, probe)}" if port.shape in _SCENE_SHAPES else ""
        entry = f"[:{probe.move}, {_ruby_float(probe.hp)}{setup}]"
        if port.shape not in _NON_DAMAGE_SHAPES and probe.holder and entry not in calc:
            calc.append(entry)
    without = list(dict.fromkeys(f":{p.move}" for p in port.probes if not p.holder))
    # A built-in move (Struggle) cannot be learned, so it never joins the fight.
    learnable = [p for p in port.probes if p.holder and p.move.lower() not in _BUILTIN_MOVES]
    fight = list(dict.fromkeys(f":{p.move}" for p in learnable))[:FIGHT_MOVES]
    if port.shape in ("type_immunity", "type_resist", "struck_status", "damage_taken", "type_absorb"):
        fight = []
    if port.shape == "stat_swap":
        fight = list(dict.fromkeys(f":{p.move}" for p in port.probes if p.outcome in ("attack", "special_attack")))[:FIGHT_MOVES]  # the moves are the foe's to use; the defend and taken phases measure them
    if port.shape == "ko_effect":
        fight = [":TACKLE"]  # its probes name no move; one, so the real path runs in the AI battle
    control = port.params.get("control")
    return SelftestCase(control=str(control) if control else None, calc=tuple(calc),
                        phases=_phases(port), without=tuple(without), fight=tuple(fight))


def _phases(port: _Port) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """The self-test phases a non-damage shape adds after calc: chance, defend, ..."""
    if port.shape == "hit_status":
        status = _STATUSES[str(port.params["status"])][0]
        entries: list[str] = []
        for probe in port.probes:
            rate = repr(int(port.params["chance"]) / 100) if probe.outcome else "0"  # type: ignore[call-overload]
            setup = (f", setup: {{target_types: [{', '.join(':' + t for t in probe.target_types)}]}}"
                     if probe.target_types else "")
            entry = f"[:{probe.move}, {{status: :{status}, status_rate: {rate}, flinch_rate: 0{setup}}}]"
            if entry not in entries:
                entries.append(entry)
        return (("chance", tuple(entries)),)
    if port.shape == "type_immunity":
        entries = [f"[:{p.move}, {{mold_breaker: true}}]" if p.mold_breaker else f":{p.move}" for p in port.probes]
        return (("defend", tuple(dict.fromkeys(entries))),)
    if port.shape in ("type_resist", "damage_taken"):
        entries = [f"[:{p.move}, {{types: [{', '.join(':' + t for t in p.types)}]}}]" if p.types else f":{p.move}"
                   for p in port.probes]
        return (("taken", tuple(dict.fromkeys(entries))),)
    if port.shape == "crit_condition":
        entries = []
        for index, probe in enumerate(port.probes, start=1):
            opts = []
            if probe.target_status == "toxic":
                opts.append("status: :POISON, toxic: true")   # bad poison: a poison with a toxic count
            elif probe.target_status:
                opts.append(f"status: :{_STATUSES[probe.target_status][0]}")
            if probe.target_speed:
                opts.append(f"speed: {probe.target_speed}")
            if probe.target_ability:
                opts.append(f"ability: :{probe.target_ability}")
            entries.append(f'["p{index}", :{probe.move}, {{{", ".join(opts)}}}]')
        return (("crit", tuple(entries)),)
    if port.shape == "stat_swap":
        calc, category, blocked = [], [], []
        for probe in port.probes:
            if probe.outcome == "status_move":
                category.append(f":{probe.move}")
                continue
            if probe.outcome == "blocked":
                blocked.append(f"[:{probe.move}, :{probe.blocked_by}]")
                continue
            setup = []
            if probe.stat_values:
                setup.append("stat_values: {" + ", ".join(f"{k}: {v}" for k, v in probe.stat_values) + "}")
            if probe.stat_stages:
                setup.append("stages: {" + ", ".join(f"{k}: {v}" for k, v in probe.stat_stages) + "}")
            if probe.burned:
                setup.append("status: :BURN")
            calc.append(f"[:{probe.move}, 1.0, {{{', '.join(setup)}}}]")
        phases = [("swap", tuple(dict.fromkeys(calc)))]
        if category:
            phases.append(("category", tuple(dict.fromkeys(category))))
        if blocked:
            phases.append(("blocked", tuple(dict.fromkeys(blocked))))
        return tuple(phases)
    if port.shape == "type_absorb":
        entries = []
        for probe in port.probes:
            opts = [f"hp: {_ruby_float(probe.hp)}"]
            if probe.stage and port.params.get("stats"):
                stats = ", ".join(f"{_STAT_NAMES[str(st)][0]}: {probe.stage}" for st in port.params["stats"])  # type: ignore[union-attr]
                opts.append(f"stages: {{{stats}}}")
            entries.append(f"[:{probe.move}, {{{', '.join(opts)}}}]")
        return (("defend", tuple(dict.fromkeys(entries))),)
    if port.shape == "struck_status":
        status = _STATUSES[str(port.params["status"])][0]
        entries = []
        for probe in port.probes:
            rate = repr(int(port.params["chance"]) / 100) if probe.outcome else "0"  # type: ignore[call-overload]
            setup = (f", setup: {{types: [{', '.join(':' + t for t in probe.attacker_types)}]}}"
                     if probe.attacker_types else "")
            entries.append(f"[:{probe.move}, {{status: :{status}, status_rate: {rate}{setup}}}]")
        return (("struck", tuple(dict.fromkeys(entries))),)
    if port.shape == "hit_drain":
        entries = [f"[:{p.move}, {{hp_lost: 100{', target_ability: :LIQUIDOOZE' if p.ooze else ''}}}]"
                   for p in port.probes]
        return (("drain", tuple(dict.fromkeys(entries))),)
    if port.shape == "ko_effect":
        if port.params["heal"] is not None:
            entries = [f"{{kos: {p.kos}, hp: {_ruby_float(p.hp)}}}" for p in port.probes]
        else:
            stat = _STAT_NAMES[str(port.params["stat"])][0]
            entries = [f"{{kos: {p.kos}, stages: {{{stat}: {p.stage}}}}}" for p in port.probes]
        return (("ko", tuple(dict.fromkeys(entries))),)
    if port.shape == "priority_boost":
        entries = [f"[:{p.move}, {_ruby_float(p.hp)}]" for p in port.probes]
        return (("priority", tuple(dict.fromkeys(entries))),)
    return ()


def _render_phase(key: str, entries: tuple[str, ...]) -> str:
    """One phase line of a case; chance entries are long, so one per line."""
    if key == "chance":
        return "    chance: [\n" + ",\n".join("      " + e for e in entries) + "\n    ],\n"
    return f"    {key}: [{', '.join(entries)}],\n"


def _setup(port: _Port, probe: _Probe) -> str:
    """The Ruby setup hash the self-test's `arrange` applies before measuring a probe."""
    parts = []
    if probe.field and port.weathers:
        parts.append(f"weather: :{port.weathers[0]}")
    if probe.field and port.terrain:
        parts.append(f"terrain: :{port.terrain}")
    if probe.item:
        parts.append(f"item: :{probe.item}")
    if probe.airborne:
        parts.append("airborne: true")
    if probe.stats:
        parts.append(f"stats: :{probe.stats}")
    if probe.types:
        parts.append(f"types: [{', '.join(':' + t for t in probe.types)}]")
    return "{" + ", ".join(parts) + "}"


def _scene(port: _Port, probe: _Probe) -> dict[str, object]:
    """The OBS keys a scene shape's check selects on: the scene the self-test set."""
    scene: dict[str, object] = {}
    if port.shape == "stab_grant":
        # Without probe types the self-test leaves the user neutral: ??? is QMARKS.
        scene["user_types"] = "/".join(probe.types) if probe.types else "QMARKS"
        return scene
    if port.weathers:
        scene["weather"] = port.weathers[0] if probe.field else "None"
        scene["item"] = probe.item or "none"
    else:
        scene["terrain"] = port.terrain if probe.field else "None"
        scene["grounded"] = _flag(not probe.airborne)
    if probe.stats:
        scene["higher"] = probe.stats
    return scene


def _stage(name: str, probe: _Probe, pinch: bool, port: _Port) -> str:
    """The in-game action for a played battle (the harness prints it on `stage`)."""
    if port.shape == "hit_status":
        foe = f"{_a('/'.join(probe.target_type_names))}-type foe" if probe.target_type_names else "the foe"
        return f"With your {name} user, use {probe.name} on {foe}, many times."
    if port.shape == "type_immunity":
        return f"Have the foe use {probe.name} on your {name} Pokemon."
    if port.shape in ("damage_taken", "type_absorb"):
        return f"Have the foe use {probe.name} on your {name} Pokemon."
    if port.shape == "stat_swap":
        return f"With your {name} user, use {probe.name} on the foe."
    if port.shape == "crit_condition":
        state = []
        if probe.target_status:
            state.append({"toxic": "badly poisoned", "poison": "poisoned", "paralysis": "paralyzed",
                          "burn": "burned", "frostbite": "frostbitten"}[probe.target_status])
        if probe.target_speed:
            state.append(f"at {probe.target_speed:+d} Speed")
        if probe.target_ability:
            state.append(f"with {probe.target_ability}")
        return f"With your {name} user, use {probe.name} on a foe {' and '.join(state) or 'in no state'}."
    if port.shape == "struck_status":
        foe = f"{_a('/'.join(probe.attacker_types))}-type foe" if probe.attacker_types else "the foe"
        return f"Have {foe} hit your {name} Pokemon with {probe.name}, many times."
    if port.shape == "hit_drain":
        foe = "a Liquid Ooze foe" if probe.ooze else "a foe"
        return f"With your {name} user below full HP, hit {foe} with {probe.name}."
    if port.shape == "ko_effect":
        if port.params["heal"] is not None:
            who = f"With your {name} user at {_hp_text(probe.hp)}"
        else:
            stat = _STAT_NAMES[str(port.params["stat"])][1]
            who = f"With your {name} user" + (f" at {probe.stage:+d} {stat}" if probe.stage else "")
        if probe.kos == 0:
            return f"{who}, hit a foe without knocking it out."
        foes = "a foe" if probe.kos == 1 else f"{probe.kos} foes at once"
        return f"{who}, knock out {foes}."
    if port.shape == "priority_boost":
        return f"With your {name} user at {_hp_text(probe.hp)}, use {probe.name}."
    if not probe.holder:
        return f"With a Pokemon WITHOUT {name}, use {probe.name} on the foe."
    hp = ""
    if probe.hp < 1:
        hp = f" at {Fraction(probe.hp).limit_denominator(12)} max HP"
    elif pinch:
        hp = " at full HP"
    extras: list[str] = []
    if probe.stats:
        extras.append("higher stat " + ("Attack" if probe.stats == "physical" else "Sp. Atk"))
    if probe.airborne:
        extras.append("airborne")
    if probe.item_name:
        extras.append(f"holding {probe.item_name}")
    if probe.type_names:
        extras.append(f"{'/'.join(probe.type_names)} type")
    who = f"With your {name} user" + (f" ({', '.join(extras)})" if extras else "")
    where = ""
    if port.shape == "conditional_boost" and port.weathers:
        where = f" in {port.params['weather']}" if probe.field else " with no weather"
    elif port.shape == "conditional_boost":
        where = f" on {str(port.params['terrain']).title()} Terrain" if probe.field else " with no terrain"
    return f"{who}{hp}{where}, use {probe.name} on the foe."


def _hp_text(hp: float) -> str:
    return "full HP" if hp >= 1 else f"{Fraction(hp).limit_denominator(12)} max HP"


def _a(word: str) -> str:
    """The word with its indefinite article: a Fire, an Ice."""
    return f"{'an' if word[:1].lower() in 'aeiou' else 'a'} {word}"


def _comment(text: str) -> list[str]:
    return ["# " + line for line in textwrap.wrap(text, width=84, break_on_hyphens=False, break_long_words=False)]


def _ruby_float(value: object) -> str:
    return repr(float(value))  # type: ignore[arg-type]


def _flag(value: bool) -> str:
    return "true" if value else "false"


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _is_type_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_text(t) for t in value)


# --- Ruby ------------------------------------------------------------------------
# The shapes' Ruby, as proven by hand in NV-5..NV-9 (chrooked_kindle.rb,
# chrooked_overcharge.rb, chrooked_chitinize.rb, chrooked_martialartist.rb,
# chrooked_forestry.rb; NV-13's chrooked_pyre.rb, chrooked_nocturnal.rb and
# chrooked_arcticariette.rb; NV-14's chrooked_vampiric.rb, chrooked_carnivore.rb and
# chrooked_rapidcombustion.rb). `{{KEY}}` is filled by _fill; everything else is literal
# Ruby, `#{...}` interpolation included.

_PORT = """\
{{HEADER}}

{{LOG}}
{{BODY}}"""

# Copied verbatim from the hand-written chrooked_kindle.rb: every port carries it,
# guarded, so each file stands alone and the first one loaded defines it.
_CHROOKED_LOG = """\
unless defined?(ChrookedLog)
  module ChrookedLog
    # Resolved once, at load, while the working directory is the game folder.
    LOG     = File.expand_path("chrooked_load.log")
    ENABLED = File.exist?(File.expand_path("chrooked-oracle.on"))

    def self.line(msg)
      write(msg) if ENABLED
    end

    def self.error(msg)
      write(msg)
    end

    def self.write(msg)
      File.open(LOG, "a") { |f| f.puts(msg) }
    rescue StandardError
      nil
    end
  end
end
"""

_TYPE_BOOST = """\
begin
  chrooked_table = Battle::AbilityEffects::DamageCalcFromUser
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=#{!chrooked_table[:{{ABILITY}}].nil?}")
  chrooked_table.add(:{{ABILITY}},
    proc { |ability, user, target, move, mults, power, type|
{{CONDITION}}
      mults[:attack_multiplier] *= {{MULTIPLIER}} if boosted
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:{{ID}}] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \\
                         "{{HP_FIELD}}result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on Battle::AbilityEffects::DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_TYPE_CONVERSION = """\
begin
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=" \\
                   "#{!Battle::AbilityEffects::ModifyMoveBaseType[:{{ABILITY}}].nil?}")
  Battle::AbilityEffects::ModifyMoveBaseType.add(:{{ABILITY}},
    proc { |ability, user, move, type|
{{GATE}}
      move.powerBoost = true
      next :{{TYPE}}
    }
  )
  Battle::AbilityEffects::DamageCalcFromUser.add(:{{ABILITY}},
    proc { |ability, user, target, move, mults, power, type|
      mults[:power_multiplier] *= {{MULTIPLIER}} if move.powerBoost
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:{{ID}}] #{tag} move=#{move.id} ability=true " \\
                         "converted=#{move.powerBoost ? type : 'none'} boosted=#{move.powerBoost}")
      end
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on ModifyMoveBaseType and DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_FLAG_BOOST = """\
begin
  chrooked_table = Battle::AbilityEffects::DamageCalcFromUser
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=#{!chrooked_table[:{{ABILITY}}].nil?}")
  chrooked_table.add(:{{ABILITY}},
    proc { |ability, user, target, move, mults, power, type|
      category = move.flags.find { |f| f[/^({{FLAGS}})$/i] }
      mults[:power_multiplier] *= {{MULTIPLIER}} if category
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:{{ID}}] #{tag} move=#{move.id} ability=true category=#{category || 'none'} " \\
                         "result=#{category ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on Battle::AbilityEffects::DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_CONDITIONAL_BOOST = """\
begin
  chrooked_table = Battle::AbilityEffects::DamageCalcFromUser
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=#{!chrooked_table[:{{ABILITY}}].nil?}")
  chrooked_table.add(:{{ABILITY}},
    proc { |ability, user, target, move, mults, power, type|
{{CONDITION}}
      mults[:{{MULT_KIND}}_multiplier] *= {{MULTIPLIER}} if boosted
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:{{ID}}] #{tag} move=#{move.id} ability=true {{FIELDS_A}}" \\
                         "{{FIELDS_B}}result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on Battle::AbilityEffects::DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_STAB_GRANT = """\
begin
  chrooked_table = Battle::AbilityEffects::DamageCalcFromUser
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=#{!chrooked_table[:{{ABILITY}}].nil?}")
  chrooked_table.add(:{{ABILITY}},
    proc { |ability, user, target, move, mults, power, type|
      own     = !type.nil? && user.pbHasType?(type)
      boosted = !type.nil? && !own{{TYPE_GATE}}
      mults[:final_damage_multiplier] *= {{MULTIPLIER}} if boosted
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:{{ID}}] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \\
                         "user_types=#{user.pbTypes.join('/')} own=#{own} result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on Battle::AbilityEffects::DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_HIT_STATUS = """\
begin
  ChrookedLog.line("[chrooked:{{ID}}] load prior_on_hit=#{!Battle::AbilityEffects::OnDealingHit[:{{ABILITY}}].nil?}")
  Battle::AbilityEffects::OnDealingHit.add(:{{ABILITY}},
    proc { |ability, user, target, move, battle|
{{GATE}}
      next if !target.affectedByAdditionalEffects?
      next if target.hasActiveAbility?(:SHIELDDUST) && !target.beingMoldBroken?
      can_inflict = target.pbCan{{STEM}}?(user, false)
      inflicted = false
      if can_inflict && battle.pbRandom(100) < {{CHANCE}}
        battle.pbShowAbilitySplash(user)
        msg = nil
        if !Battle::Scene::USE_ABILITY_SPLASH
          msg = _INTL("{{MESSAGE}}", user.pbOfThis, user.abilityName, target.pbThis(true))
        end
        target.pb{{STEM}}(user, msg)
        battle.pbHideAbilitySplash(user)
        inflicted = true
      end
      ChrookedLog.line("[chrooked:{{ID}}] OBS move=#{move.id} type=#{move.calcType} ability=true hit=true " \\
                       "can_inflict=#{can_inflict} inflicted=#{inflicted}")
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on OnDealingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_TYPE_IMMUNITY = """\
begin
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=#{!Battle::AbilityEffects::MoveImmunity[:{{ABILITY}}].nil?}")
  Battle::AbilityEffects::MoveImmunity.add(:{{ABILITY}},
    proc { |ability, user, target, move, type, battle, show_message|
      immune = type == :{{TYPE}} && user.index != target.index
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s =~ /AI[ _]?Move/ } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:{{ID}}] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \\
                         "result=#{immune ? 'IMMUNE' : 'NORMAL'}")
      end
      next false if !immune
      if show_message
        battle.pbShowAbilitySplash(target)
        if Battle::Scene::USE_ABILITY_SPLASH
          battle.pbDisplay(_INTL("It doesn't affect {1}...", target.pbThis(true)))
        else
          battle.pbDisplay(_INTL("{1} {2} made {3} ineffective!",
                                 target.pbOfThis, target.abilityName, move.name))
        end
        battle.pbHideAbilitySplash(target)
      end
      next true
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on MoveImmunity")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_HIT_DRAIN = """\
begin
  ChrookedLog.line("[chrooked:{{ID}}] load prior_on_hit=#{!Battle::AbilityEffects::OnDealingHit[:{{ABILITY}}].nil?}")
  Battle::AbilityEffects::OnDealingHit.add(:{{ABILITY}},
    proc { |ability, user, target, move, battle|
      gated    = {{GATE}}
      ooze     = target.hasActiveAbility?(:LIQUIDOOZE, true)
      can_heal = user.canHeal?
      amount   = (target.damageState.hpLost * {{FRACTION}}).round
      before   = user.hp
      if gated && amount > 0 && !user.fainted? && (can_heal || ooze)
        battle.pbShowAbilitySplash(user)
        user.pbRecoverHPFromDrain(amount, target)
        battle.pbHideAbilitySplash(user)
      end
      change = user.hp - before
      ChrookedLog.line("[chrooked:{{ID}}] OBS move=#{move.id} ability=true contact=#{move.pbContactMove?(user)} " \\
                       "ooze=#{ooze} can_heal=#{can_heal} hp_lost=#{target.damageState.hpLost} change=#{change} " \\
                       "result=#{change > 0 ? 'HEALED' : (change < 0 ? 'REVERSED' : 'NONE')}")
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on OnDealingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_KO_HEAL = """\
begin
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=" \\
                   "#{!Battle::AbilityEffects::OnEndOfUsingMove[:{{ABILITY}}].nil?}")
  Battle::AbilityEffects::OnEndOfUsingMove.add(:{{ABILITY}},
    proc { |ability, user, targets, move, battle|
      kos     = targets.count { |b| b.damageState.fainted }
      hp_full = user.hp >= user.totalhp
      before  = user.hp
      if kos > 0 && !battle.pbAllFainted?(user.idxOpposingSide) && user.canHeal?
        battle.pbShowAbilitySplash(user)
        user.pbRecoverHP((user.totalhp * {{FRACTION}}).floor)
        if Battle::Scene::USE_ABILITY_SPLASH
          battle.pbDisplay(_INTL("{1}'s HP was restored.", user.pbThis))
        else
          battle.pbDisplay(_INTL("{1} {2} restored its HP.", user.pbOfThis, user.abilityName))
        end
        battle.pbHideAbilitySplash(user)
      end
      change = user.hp - before
      ChrookedLog.line("[chrooked:{{ID}}] OBS move=#{move.id} ability=true kos=#{kos} hp_full=#{hp_full} " \\
                       "change=#{change} result=#{change > 0 ? 'HEALED' : 'NONE'}")
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on OnEndOfUsingMove")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_KO_STAT = """\
begin
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=" \\
                   "#{!Battle::AbilityEffects::OnEndOfUsingMove[:{{ABILITY}}].nil?}")
  Battle::AbilityEffects::OnEndOfUsingMove.add(:{{ABILITY}},
    proc { |ability, user, targets, move, battle|
      kos   = targets.count { |b| b.damageState.fainted }
      stage = user.stages[:{{STAT}}]
      if kos > 0 && !battle.pbAllFainted?(user.idxOpposingSide) && user.pbCanRaiseStatStage?(:{{STAT}}, user)
        user.pbRaiseStatStageByAbility(:{{STAT}}, kos, user)
      end
      change = user.stages[:{{STAT}}] - stage
      ChrookedLog.line("[chrooked:{{ID}}] OBS move=#{move.id} ability=true kos=#{kos} stage=#{stage} " \\
                       "change=#{change} result=#{change > 0 ? 'RAISED' : 'NONE'}")
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on OnEndOfUsingMove")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_PRIORITY_BOOST = """\
begin
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=" \\
                   "#{!Battle::AbilityEffects::PriorityChange[:{{ABILITY}}].nil?}")
  Battle::AbilityEffects::PriorityChange.add(:{{ABILITY}},
    proc { |ability, battler, move, pri|
      hp_full = battler.hp == battler.totalhp
      boosted = {{CONDITION}}
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s =~ /AI[ _]?Move/ } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:{{ID}}] #{tag} move=#{move.id} type=#{move.type} ability=true " \\
                         "hp_full=#{hp_full} priority=#{boosted ? pri + 1 : pri} " \\
                         "result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
      next pri + 1 if boosted
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on PriorityChange")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_DROPS = """\
begin
  chrooked_table = Battle::AbilityEffects::{{REGISTRY}}
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=#{!chrooked_table[:{{ABILITY}}].nil?}")
  chrooked_table.remove(:{{ABILITY}})   # the spec removes this effect of the game's own ability
  ChrookedLog.line("[chrooked:{{ID}}] dropped from {{REGISTRY}} block={{N}}")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_CRIT_CONDITION = """\
begin
  chrooked_table = Battle::AbilityEffects::CriticalCalcFromUser
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=#{!chrooked_table[:{{ABILITY}}].nil?}")
  chrooked_table.add(:{{ABILITY}},
    proc { |ability, user, target, move, c|
      forced = {{WHEN}}
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:{{ID}}] #{tag} move=#{move.id} ability=true " \\
                         "result=#{forced ? 'FORCED' : 'NORMAL'}")
      end
      next 99 if forced   # pbIsCritical? takes any stage above 50 as certain, as Merciless's 99
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on CriticalCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_STAT_SWAP = """\
begin
  ChrookedLog.line("[chrooked:{{ID}}] load wrapped=#{Battle::Move.method_defined?(:chrooked_{{ID}}_attack_stats)}")
  class Battle::Move
    unless method_defined?(:chrooked_{{ID}}_attack_stats)
      # The holder's moves this ability takes; the holder's own name, so a composed
      # ability that lists this one takes them too.
      def chrooked_{{ID}}_takes?(user)
        user.hasActiveAbility?(:{{ABILITY}}) && damagingMove?{{GATE}}
      end

      # The higher of Attack and Sp. Atk after their stages (Attack on a tie).
      def chrooked_{{ID}}_higher(user)
        mul, div = Battle::Battler::STAT_STAGE_MULTIPLIERS, Battle::Battler::STAT_STAGE_DIVISORS
        atk   = user.attack * mul[user.stages[:ATTACK] + 6] / div[user.stages[:ATTACK] + 6]
        spatk = user.spatk * mul[user.stages[:SPECIAL_ATTACK] + 6] / div[user.stages[:SPECIAL_ATTACK] + 6]
        return [user.spatk, user.stages[:SPECIAL_ATTACK] + 6, "SPECIAL_ATTACK"] if spatk > atk
        [user.attack, user.stages[:ATTACK] + 6, "ATTACK"]
      end

      alias_method :chrooked_{{ID}}_attack_stats, :pbGetAttackStats
      def pbGetAttackStats(user, target)
        return chrooked_{{ID}}_attack_stats(user, target) if !user.hasActiveAbility?(:{{ABILITY}})
        takes = chrooked_{{ID}}_takes?(user)
        if takes
          stat, stage, name = {{ATTACK}}
        else
          stat, stage = chrooked_{{ID}}_attack_stats(user, target)
          name = specialMove? ? "SPECIAL_ATTACK" : "ATTACK"
        end
        if ChrookedLog::ENABLED
          tag = caller_locations(1, 8).any? { |l| l.path.to_s =~ /AI[ _]?Move/ } ? "EST" : "OBS"
          # A composed holder answers to this ability's name (NV-16): log as the composed
          # ability, with part=, as its registry parts are re-tagged.
          own  = user.ability_id == :{{ABILITY}}
          as   = own ? "{{ID}}" : (defined?(ChrookedCompose) && ChrookedCompose.tag_of(user.ability_id)) || "{{ID}}"
          part = own ? "" : " part={{ID}}"
          ChrookedLog.line("[chrooked:#{as}] #{tag} move=#{@id} ability=true takes=#{takes} atk=#{user.attack} " \\
                           "spatk=#{user.spatk} atk_stage=#{user.stages[:ATTACK]} " \\
                           "spatk_stage=#{user.stages[:SPECIAL_ATTACK]} attack_stat=#{name} " \\
                           "defense_stat=#{takes ? {{DEFENSE_NAME}} : (specialMove? ? 'SPECIAL_DEFENSE' : 'DEFENSE')}#{part}")
        end
        return stat, stage
      end
{{DEFENSE_WRAP}}{{BURN_WRAP}}    end
  end
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on Battle::Move#pbGetAttackStats")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_DAMAGE_TAKEN = """\
begin
  chrooked_table = Battle::AbilityEffects::DamageCalcFromTarget
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=#{!chrooked_table[:{{ABILITY}}].nil?}")
  chrooked_table.add(:{{ABILITY}},
    proc { |ability, user, target, move, mults, power, type|
      contact = move.pbContactMove?(user)
      factor  = 1.0
{{RULES}}
      mults[:final_damage_multiplier] *= factor
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:{{ID}}] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \\
                         "contact=#{contact} factor=#{format('%.3f', factor)}")
      end
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on Battle::AbilityEffects::DamageCalcFromTarget")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_TYPE_ABSORB = """\
begin
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=#{!Battle::AbilityEffects::MoveImmunity[:{{ABILITY}}].nil?}")
  Battle::AbilityEffects::MoveImmunity.add(:{{ABILITY}},
    proc { |ability, user, target, move, type, battle, show_message|
      absorbed = type == :{{TYPE}} && user.index != target.index
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s =~ /AI[ _]?Move/ } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:{{ID}}] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \\
                         "result=#{absorbed ? 'ABSORBED' : 'NORMAL'}")
      end
      next false if !absorbed
{{EFFECT}}
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on MoveImmunity")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_STRUCK_STATUS = """\
begin
  ChrookedLog.line("[chrooked:{{ID}}] load prior_on_being_hit=#{!Battle::AbilityEffects::OnBeingHit[:{{ABILITY}}].nil?}")
  Battle::AbilityEffects::OnBeingHit.add(:{{ABILITY}},
    proc { |ability, user, target, move, battle|
      next if !move.pbContactMove?(user) || !user.affectedByContactEffect?
      can_inflict = user.pbCan{{STEM}}?(target, false)
      inflicted = false
      if can_inflict && battle.pbRandom(100) < {{CHANCE}}
        battle.pbShowAbilitySplash(target)
        msg = nil
        if !Battle::Scene::USE_ABILITY_SPLASH
          msg = _INTL("{{MESSAGE}}", target.pbOfThis, target.abilityName, user.pbThis(true))
        end
        user.pb{{STEM}}(target, msg)
        battle.pbHideAbilitySplash(target)
        inflicted = true
      end
      ChrookedLog.line("[chrooked:{{ID}}] OBS move=#{move.id} type=#{move.calcType} ability=true struck=true " \\
                       "can_inflict=#{can_inflict} inflicted=#{inflicted}")
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on OnBeingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

_TYPE_RESIST = """\
begin
  chrooked_table = Battle::AbilityEffects::DamageCalcFromTarget
  ChrookedLog.line("[chrooked:{{ID}}] load prior_handler=#{!chrooked_table[:{{ABILITY}}].nil?}")
  chrooked_table.add(:{{ABILITY}},
    proc { |ability, user, target, move, mults, power, type|
      applies = (type == :{{TYPE}})
      mults[:final_damage_multiplier] *= {{MULTIPLIER}} if applies
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:{{ID}}] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \\
                         "result=#{applies ? 'APPLIED' : 'NORMAL'}")
      end
    }
  )
{{SELFTEST}}
  ChrookedLog.line("[chrooked:{{ID}}] installed on Battle::AbilityEffects::DamageCalcFromTarget")
rescue StandardError => e
  ChrookedLog.error("[chrooked:{{ID}}] ERROR #{e.class}: #{e.message}")
end
"""

# Registered at load, so the lab self-test (which runs later, at GameData.load_all)
# finds every installed port's case without a table of its own. Inert on a played
# copy: one hash in a global, read only when chrooked-selftest.on arms the self-test.
_SELFTEST = """\
  ($chrooked_selftest_cases ||= {})["{{ID}}"] = {
    ability: :{{ABILITY}}, control: {{CONTROL}}, user: :{{USER}}, foe: :{{FOE}}, neutral: true,
    calc: [{{CALC}}],
{{PHASES}}    without: [{{WITHOUT}}],
    fight: [{{FIGHT}}]
  }"""
