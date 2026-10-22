"""Behavior templates: a port generated from its spec instead of written by hand.

Many of the Ruleset's ability mechanics are one of a few shapes the dex has already
proven on a real engine: "moves of this type hit harder" (Blaze's shape), "Normal moves
become type X and hit harder" (Aerilate's), "moves with this flag hit harder" (Iron
Fist's). A behavior spec that is one of those says so in a `template:` block:

    template:
      shape: flag_boost
      params: {flags: [kicking], multiplier: 1.3}
      probes:
        - {move: High Jump Kick, result: boosted}
        - {move: Tackle, result: normal}
        - {move: High Jump Kick, result: normal, holder: false}

`params` configure the shape; `probes` hold one machine-checkable probe per entry of
the spec's `test_cases`, in the same order. From that block this module emits, for an
Essentials 21 target (mjolnir NV-8):

  * the port, `chrooked_<id>.rb`: one handler-registry entry, the same Ruby a person
    would write for that shape;
  * the port's own case for the lab's headless self-test, registered at load in
    `$chrooked_selftest_cases`, so the self-test needs no edit per mechanic;
  * the harness checks, one per probe, which score the port's OBS lines against the
    spec's test cases.

Specs stay engine-neutral (move and type names, Ruleset move flags). The target's own
PBS turns them into INTERNAL names through a resolver, the Essentials `ResolutionMap`,
which never guesses: a name the target lacks fails the render and says which. A
mechanic that fits no shape keeps a hand-written port in references/essentials21-harness/.

Shapes, their params, and the probe fields each accepts:

  type_boost       {type, multiplier, pinch?, control?}   {move, result, hp?, holder?}
  type_conversion  {type, multiplier=1.2, control?}       {move, converted, hp?}
  flag_boost       {flags, multiplier, control?}          {move, result, hp?, holder?}

`result` is `boosted` or `normal`; `converted` is true or false. `pinch: true` limits a
type boost to HP at or below 1/3, Blaze's threshold, and a probe's `hp` sets the
holder's HP fraction first. `holder: false` probes a Pokemon WITHOUT the ability, a
case the port can never log because it only runs for its holder; the self-test
measures that case itself. `control` is a vanilla ability, by INTERNAL name, that the
self-test measures beside the port for comparison (BLAZE beside a type boost, say).
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

SHAPES = ("type_boost", "type_conversion", "flag_boost")

# shape -> (required params, optional params with their defaults)
_PARAMS: dict[str, tuple[frozenset[str], dict[str, object]]] = {
    "type_boost": (frozenset({"type", "multiplier"}), {"pinch": False, "control": None}),
    "type_conversion": (frozenset({"type"}), {"multiplier": 1.2, "control": None}),
    "flag_boost": (frozenset({"flags", "multiplier"}), {"control": None}),
}
# The probe field that states the expected outcome, per shape.
_OUTCOME = {"type_boost": "result", "type_conversion": "converted", "flag_boost": "result"}
_RESULTS = ("boosted", "normal")
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
    if len(template.probes) != n_test_cases:
        raise TemplateError(
            f"{where}: {len(template.probes)} probes for {n_test_cases} test_cases; keep them aligned 1:1")
    for index, probe in enumerate(template.probes, start=1):
        _validate_probe(probe, template.shape, f"{where}: probe {index}")


def _validate_probe(probe: Mapping[str, object], shape: str, at: str) -> None:
    outcome = _OUTCOME[shape]
    # A Pokemon without the ability is only measurable as "boosted or not", so
    # holder: false belongs to the shapes whose outcome is a result.
    allowed = {"move", outcome, "hp"} | ({"holder"} if outcome == "result" else set())
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
    holder = probe.get("holder", True)
    if not isinstance(holder, bool):
        raise TemplateError(f"{at}: holder must be true or false")
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
    else:
        values["FLAGS"] = "|".join(port.flags)
        body = _FLAG_BOOST
    return _fill(_PORT, {
        "HEADER": _header(spec, port),
        "LOG": _CHROOKED_LOG,
        "BODY": _fill(body, values),
    })


def harness_checks(spec: BehaviorSpec, names: Names) -> list[dict[str, object]]:
    """One harness check per probe, aligned with the spec's test_cases.

    Each check selects the port's OBS line for the probe's move and holder (plus the
    HP side of a pinch) and expects the probe's outcome, in the keys the generated
    port logs. Values are strings, as the harness compares them.
    """
    port = _resolve(spec, names)
    pinch = port.shape == "type_boost" and bool(port.params["pinch"])
    checks: list[dict[str, object]] = []
    for probe in port.probes:
        select: dict[str, object] = {"move": probe.move, "ability": _flag(probe.holder)}
        if pinch and probe.holder:
            select["hp_low"] = _flag(probe.hp * 3 <= 1)  # the port's user.hp <= user.totalhp / 3
        if port.shape == "type_conversion":
            expect = {"converted": port.type if probe.outcome else "none", "boosted": _flag(bool(probe.outcome))}
        else:
            expect = {"result": str(probe.outcome).upper()}
        checks.append({"stage": _stage(spec.name, probe, pinch), "select": select, "expect": expect})
    return checks


# --- resolution ------------------------------------------------------------------


@dataclass(frozen=True)
class _Probe:
    name: str      # the neutral move name, for stage text
    move: str      # the target's INTERNAL move name
    outcome: object  # "boosted" / "normal", or a bool for type_conversion
    hp: float
    holder: bool


@dataclass(frozen=True)
class _Port:
    shape: str
    params: dict[str, object]   # with defaults filled in
    ability: str
    type: Optional[str]         # INTERNAL, for the type shapes
    flags: tuple[str, ...]      # Essentials flag names, for flag_boost
    probes: tuple[_Probe, ...]


def _resolve(spec: BehaviorSpec, names: Names) -> _Port:
    """Validate the spec's template and turn every neutral name into the target's own."""
    where = f"{spec.chrooked_id}.yaml:template"
    template = spec.template
    if template is None:
        raise TemplateError(f"{spec.chrooked_id}: no template block")
    if spec.applies_to != "ability":
        raise TemplateError(f"{where}: templates generate ability ports; this spec applies to a {spec.applies_to}")
    validate(template, len(spec.test_cases), where)
    params = {**_PARAMS[template.shape][1], **template.params}

    missing: list[str] = []
    ability = names.ability(spec.name)
    if ability is None:
        missing.append(f"ability {spec.name!r}")
    type_ = None
    if "type" in params:
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
    outcome = _OUTCOME[template.shape]
    probes: list[_Probe] = []
    for probe in template.probes:
        move = names.move(str(probe["move"]))
        if move is None:
            missing.append(f"move {probe['move']!r}")
        probes.append(_Probe(
            name=str(probe["move"]), move=move or "", outcome=probe[outcome],
            hp=float(probe.get("hp", 1.0)), holder=bool(probe.get("holder", True)),  # type: ignore[arg-type]
        ))
    if missing:
        raise TemplateError(f"{where}: the target has no {', '.join(dict.fromkeys(missing))}")
    return _Port(shape=template.shape, params=params, ability=ability or "", type=type_,
                 flags=tuple(flags), probes=tuple(probes))


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


def _header(spec: BehaviorSpec, port: _Port) -> str:
    multiplier = _ruby_float(port.params["multiplier"])
    if port.shape == "type_boost":
        pinch = bool(port.params["pinch"])
        seam = "Battle::AbilityEffects::DamageCalcFromUser"
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
    else:
        seam = "Battle::AbilityEffects::DamageCalcFromUser"
        note = (f"Nova's Iron Fist shape: a {multiplier}x power multiplier when the move carries a "
                f"{' or '.join(port.flags)} flag. Kicking, Hammer and Piercing are custom flags the dex "
                "writes into the game's move data (appliers/essentials/vocab.py); without the flag in "
                "the data this port never fires.")
        obs = "move=<ID> ability=true category=<flag|none> result=<BOOSTED|NORMAL>"
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

    calc: the holder probes, once per (move, HP); without: the holder: false moves;
    fight: the holder's distinct moves, at most four, for one AI-vs-AI battle.
    """
    calc: list[str] = []
    for probe in port.probes:
        entry = f"[:{probe.move}, {_ruby_float(probe.hp)}]"
        if probe.holder and entry not in calc:
            calc.append(entry)
    without = list(dict.fromkeys(f":{p.move}" for p in port.probes if not p.holder))
    fight = list(dict.fromkeys(f":{p.move}" for p in port.probes if p.holder))[:_FIGHT_MOVES]
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


def _stage(name: str, probe: _Probe, pinch: bool) -> str:
    """The in-game action for a played battle (the harness prints it on `stage`)."""
    if not probe.holder:
        return f"With a Pokemon WITHOUT {name}, use {probe.name} on the foe."
    hp = ""
    if probe.hp < 1:
        hp = f" at {Fraction(probe.hp).limit_denominator(12)} max HP"
    elif pinch:
        hp = " at full HP"
    return f"With your {name} user{hp}, use {probe.name} on the foe."


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


# --- Ruby ------------------------------------------------------------------------
# The shapes' Ruby, as proven by hand in NV-5..NV-7 (chrooked_kindle.rb,
# chrooked_overcharge.rb, chrooked_chitinize.rb, chrooked_martialartist.rb). `{{KEY}}`
# is filled by _fill; everything else is literal Ruby, `#{...}` interpolation included.

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
