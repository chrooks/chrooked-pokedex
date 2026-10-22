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
  type_conversion    {type, multiplier=1.2, control?}         {move, converted, hp?}
  flag_boost         {flags, multiplier, control?}            {move, result, hp?, holder?}
  conditional_boost  {weather | terrain, multiplier,          {move, result, hp?, field?,
                      moves=all|higher_stat, control?}         item?, airborne?, stats?}
  stab_grant         {types | all, multiplier=1.5, control?}  {move, result, hp?, types?}

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
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping, Optional, Protocol

from ..appliers.essentials import vocab
from ..model.behavior_spec import BehaviorSpec, BehaviorTemplate
from ..model.schema import MOVE_FLAGS

SHAPES = ("type_boost", "type_conversion", "flag_boost", "conditional_boost", "stab_grant")

# shape -> (required params, optional params with their defaults)
_PARAMS: dict[str, tuple[frozenset[str], dict[str, object]]] = {
    "type_boost": (frozenset({"type", "multiplier"}), {"pinch": False, "control": None}),
    "type_conversion": (frozenset({"type"}), {"multiplier": 1.2, "control": None}),
    "flag_boost": (frozenset({"flags", "multiplier"}), {"control": None}),
    "conditional_boost": (frozenset({"multiplier"}),
                          {"weather": None, "terrain": None, "moves": "all", "control": None}),
    "stab_grant": (frozenset({"types"}), {"multiplier": 1.5, "control": None}),
}
# The probe field that states the expected outcome, per shape.
_OUTCOME = {"type_boost": "result", "type_conversion": "converted", "flag_boost": "result",
            "conditional_boost": "result", "stab_grant": "result"}
# The shapes whose self-test entries carry a setup hash (the self-test's `arrange`).
_SCENE_SHAPES = ("conditional_boost", "stab_grant")
# Moves Essentials builds in code, with no PBS section to resolve them by.
_BUILTIN_MOVES = {"struggle": "STRUGGLE"}
_RESULTS = ("boosted", "normal")
_WEATHERS = ("rain", "sun", "sand", "hail")
_TERRAINS = ("grassy", "electric", "psychic", "misty")
_MOVE_SETS = ("all", "higher_stat")
_STATS = ("physical", "special")
_INTERNAL = re.compile(r"^[A-Z][A-Z0-9_]*$")

# The self-test's battlers. Fixed, because neutral mode (both battlers typed ???)
# makes the measured ratio the ability's effect alone, whatever the species.
_SELFTEST_USER = "NUMEL"
_SELFTEST_FOE = "SNORLAX"
_FIGHT_MOVES = 4  # a Pokemon knows at most four


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
    if len(spec.effects) != 1:
        summaries = "; ".join(e.summary for e in spec.effects) or "none"
        raise TemplateError(
            f"{where}: a template generates exactly one effect, and this spec has {len(spec.effects)} "
            f"({summaries}); give it a hand-written port, or a shape that covers every effect")
    validate(spec.template, len(spec.test_cases), where)


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
    if template.shape == "conditional_boost":
        _validate_condition(params, where)
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


def _validate_probe(probe: Mapping[str, object], template: BehaviorTemplate, at: str) -> None:
    shape, params = template.shape, template.params
    outcome = _OUTCOME[shape]
    allowed = {"move", outcome, "hp"}
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
    unknown = sorted(set(probe) - allowed)
    if unknown:
        raise TemplateError(f"{at}: unknown fields {', '.join(unknown)} (takes {', '.join(sorted(allowed))})")
    if not _is_text(probe.get("move")):
        raise TemplateError(f"{at}: needs a move name, e.g. {{move: Tackle, ...}}")
    value = probe.get(outcome)
    if outcome == "result" and value not in _RESULTS:
        raise TemplateError(f"{at}: result must be boosted or normal, not {value!r}")
    if outcome == "converted" and not isinstance(value, bool):
        raise TemplateError(f"{at}: converted must be true or false, not {value!r}")
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
    if higher_stat and probe.get("stats") not in _STATS:
        raise TemplateError(f"{at}: needs stats: physical or special (which of Attack and Sp. Atk is higher)")
    holder = probe.get("holder", True)
    if not holder and value != "normal":
        raise TemplateError(f"{at}: a Pokemon without the ability cannot be boosted; use result: normal")
    if not holder and "hp" in probe:
        raise TemplateError(f"{at}: hp applies to the ability's holder; drop it from a holder: false probe")


def render_essentials21(spec: BehaviorSpec, names: Names) -> str:
    """The Essentials 21 port for a templated spec: `chrooked_<id>.rb`'s full text."""
    port = _resolve(spec, names)
    values = {
        "ID": spec.chrooked_id,
        "ABILITY": port.ability,
        "MULTIPLIER": _ruby_float(port.params["multiplier"]),
        "SELFTEST": _selftest_case(spec, port),
    }
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
        body = _TYPE_CONVERSION
    elif port.shape == "flag_boost":
        values["FLAGS"] = "|".join(port.flags)
        body = _FLAG_BOOST
    elif port.shape == "conditional_boost":
        values.update(_conditional_ruby(port))
        body = _CONDITIONAL_BOOST
    else:
        values["TYPE_GATE"] = (
            "" if port.grant_types is None
            else f" && [{', '.join(':' + t for t in port.grant_types)}].include?(type)")
        body = _STAB_GRANT
    return _fill(_PORT, {
        "HEADER": _header(spec, port),
        "LOG": _CHROOKED_LOG,
        "BODY": _fill(body, values),
    })


def harness_checks(spec: BehaviorSpec, names: Names) -> list[dict[str, object]]:
    """One harness check per probe, aligned with the spec's test_cases.

    Each check selects the port's OBS line for the probe's move and holder (plus the
    HP side of a pinch, or the scene a conditional boost was measured in) and
    expects the probe's outcome, in the keys the generated port logs. Values are
    strings, as the harness compares them.
    """
    port = _resolve(spec, names)
    pinch = port.shape == "type_boost" and bool(port.params["pinch"])
    checks: list[dict[str, object]] = []
    for probe in port.probes:
        select: dict[str, object] = {"move": probe.move, "ability": _flag(probe.holder)}
        if pinch and probe.holder:
            select["hp_low"] = _flag(probe.hp * 3 <= 1)  # the port's user.hp <= user.totalhp / 3
        if port.shape in _SCENE_SHAPES:
            select.update(_scene(port, probe))
        if port.shape == "type_conversion":
            expect = {"converted": port.type if probe.outcome else "none", "boosted": _flag(bool(probe.outcome))}
        else:
            expect = {"result": str(probe.outcome).upper()}
        checks.append({"stage": _stage(spec.name, probe, pinch, port), "select": select, "expect": expect})
    return checks


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

    grant_types = None
    if template.shape == "stab_grant" and params["types"] != "all":
        grant_types = resolve_types(params["types"])
    outcome = _OUTCOME[template.shape]
    probes: list[_Probe] = []
    for probe in template.probes:
        move = names.move(str(probe["move"])) or _BUILTIN_MOVES.get(str(probe["move"]).lower())
        if move is None:
            missing.append(f"move {probe['move']!r}")
        item = None
        if "item" in probe:
            item = names.item(str(probe["item"]))
            if item is None:
                missing.append(f"item {probe['item']!r}")
        probes.append(_Probe(
            name=str(probe["move"]), move=move or "", outcome=probe[outcome],
            hp=float(probe.get("hp", 1.0)), holder=bool(probe.get("holder", True)),  # type: ignore[arg-type]
            field=bool(probe.get("field", True)), item=item,
            item_name=str(probe["item"]) if "item" in probe else None,
            airborne=bool(probe.get("airborne", False)),
            stats=str(probe["stats"]) if "stats" in probe else None,
            types=resolve_types(probe.get("types") or ()),
            type_names=tuple(str(t) for t in probe.get("types") or ()),  # type: ignore[union-attr]
        ))
    if missing:
        raise TemplateError(f"{where}: the target has no {', '.join(dict.fromkeys(missing))}")
    return _Port(shape=template.shape, params=params, ability=ability or "", type=type_,
                 flags=tuple(flags), probes=tuple(probes), weathers=weathers, terrain=terrain,
                 grant_types=grant_types)


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
    multiplier = _ruby_float(port.params["multiplier"])
    seam = "Battle::AbilityEffects::DamageCalcFromUser"
    if port.shape == "type_boost":
        pinch = bool(port.params["pinch"])
        note = (f"Nova's Blaze handler{'' if pinch else ' minus its HP check'}, for {port.params['type']}: an "
                f"attack-stat multiplier ({multiplier}x)"
                f"{' at or below 1/3 max HP (user.hp <= user.totalhp / 3)' if pinch else ''}, so tiny "
                f"hits land a little under {multiplier}x (the damage formula's flat +2 is never scaled).")
        obs = "move=<ID> type=<TYPE> ability=true " + ("hp_low=<true|false> " if pinch else "") + "result=<BOOSTED|NORMAL>"
    elif port.shape == "type_conversion":
        seam = "Battle::AbilityEffects::ModifyMoveBaseType (the conversion) plus DamageCalcFromUser (the rider)"
        note = (f"The pair Nova's own Aerilate and Dragonize use: Normal moves become {port.params['type']} and set "
                f"move.powerBoost, and the {multiplier}x power rider reads that flag, so moves that compute "
                "their own type (Weather Ball, Judgment, Struggle, ...) are never converted.")
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
        f"#     [chrooked:{spec.chrooked_id}] OBS {obs}   a real hit",
        f"#     [chrooked:{spec.chrooked_id}] EST ...   an AI estimate, never scored",
        _RULE,
    ]
    return "\n".join(lines)


def _selftest_case(spec: BehaviorSpec, port: _Port) -> str:
    """The `$chrooked_selftest_cases` entry: what the lab self-test measures.

    calc: the holder probes, once per (move, HP, scene); without: the holder: false
    moves; fight: the holder's distinct moves, at most four, for one AI-vs-AI battle.
    A conditional boost's entries carry a setup hash (the self-test's `arrange`).
    """
    calc: list[str] = []
    for probe in port.probes:
        setup = f", {_setup(port, probe)}" if port.shape in _SCENE_SHAPES else ""
        entry = f"[:{probe.move}, {_ruby_float(probe.hp)}{setup}]"
        if probe.holder and entry not in calc:
            calc.append(entry)
    without = list(dict.fromkeys(f":{p.move}" for p in port.probes if not p.holder))
    # A built-in move (Struggle) cannot be learned, so it never joins the fight.
    learnable = [p for p in port.probes if p.holder and p.move.lower() not in _BUILTIN_MOVES]
    fight = list(dict.fromkeys(f":{p.move}" for p in learnable))[:_FIGHT_MOVES]
    control = port.params.get("control")
    return _fill(_SELFTEST, {
        "ID": spec.chrooked_id,
        "ABILITY": port.ability,
        "CONTROL": f":{control}" if control else "nil",
        "USER": _SELFTEST_USER,
        "FOE": _SELFTEST_FOE,
        "CALC": ", ".join(calc),
        "WITHOUT": ", ".join(without),
        "FIGHT": ", ".join(fight),
    })


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
# chrooked_forestry.rb). `{{KEY}}` is filled by _fill; everything else is literal
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
      next if type != :NORMAL || !GameData::Type.exists?(:{{TYPE}})
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

# Registered at load, so the lab self-test (which runs later, at GameData.load_all)
# finds every installed port's case without a table of its own. Inert on a played
# copy: one hash in a global, read only when chrooked-selftest.on arms the self-test.
_SELFTEST = """\
  ($chrooked_selftest_cases ||= {})["{{ID}}"] = {
    ability: :{{ABILITY}}, control: {{CONTROL}}, user: :{{USER}}, foe: :{{FOE}}, neutral: true,
    calc: [{{CALC}}],
    without: [{{WITHOUT}}],
    fight: [{{FIGHT}}]
  }"""
