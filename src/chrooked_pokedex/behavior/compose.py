"""Composed abilities on Essentials 21: one ability built from several behaviors (mjolnir NV-15, NV-16).

A Ruleset ability may list its parts, `behaviors: [carnivore, strongjaw]`: Apex
Predator is Carnivore's knockout heal plus Strong Jaw's biting boost. A part is
either a Ruleset behavior whose port is generated from its template, or a vanilla
ability the game already ships. Essentials 21 reaches an ability two ways, and a
composed ability's file covers both:

  * Handler registries (`Battle::AbilityEffects::DamageCalcFromUser`, ...), keyed by
    ability id. The composed ability gets its parts' handlers: a registry only one
    part has a handler in gets that handler as it is; a registry several parts
    share gets one handler that combines them the way the registry's trigger reads
    the result. Multiplier and side-effect registries run every part in turn;
    registries that pass a value along (speed, priority, the move's type, the
    critical stage) hand each part the one before's result; immunity registries
    answer yes when any part does. Two parts sharing a registry with no such rule
    log an ERROR, and only the first runs.
  * Checks by name (NV-16): the battle code asks `hasActiveAbility?(:LEVITATE)` for
    Levitate, Guts, Scrappy, Suction Cups and Gorilla Tactics instead of keeping a
    handler. A composed battler answers yes for each of its parts as well, so every
    such check (the AI's `has_active_ability?` delegates to it) sees the part.

The wiring waits for the first battle, when every port has loaded: the composed
ability's file sorts before its parts' (`chrooked_apexpredator.rb` before
`chrooked_carnivore.rb`). While a part's handler runs for the composed ability,
its port's log lines are re-tagged as the composed ability's, with `part=<id>`, so
the harness scores them for it.

The proof reuses a ported part's own probes under the composed ability, and shows
a vanilla part by comparison: the self-test measures one value (VANILLA_PARTS says
which) with the composed ability, with the part alone and with none, and the first
two must match while the last differs. A part checked by name is also asked for by
name (`identity`). A composition installs only when every part can be proven that
way. Not composed yet:

  * a vanilla part without a VANILLA_PARTS entry;
  * a Ruleset part with no template (unported, or hand-written);
  * an ability that lists itself (Finishing Kick is finishingkick plus Speed Boost),
    whose own port would share its file name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..model.behavior_spec import BehaviorSpec, BehaviorTestCase
from ..model.ruleset import Ruleset
from ..model.schema import AbilityDef, composed_behaviors, is_composed
from . import templates
from .templates import Names, TemplateError, _CHROOKED_LOG, _RULE, _STATUSES, _comment


@dataclass(frozen=True)
class _Proof:
    """What the self-test measures to show a vanilla part (its `measure`): a hit's
    damage, or whether the holder is airborne, can be forced out, can have its
    Attack lowered, is locked into its move, or what a knockout raises."""

    kind: str = "hit"
    move: Optional[str] = None                 # the move's name, for hit and locked
    target_types: tuple[str, ...] = ()         # hit: the foe's types first
    status: Optional[str] = None               # hit: the user's status first (burn)


# A vanilla ability a composition may borrow: its name in the game, whether the
# battle code checks it by name (`hasActiveAbility?`), and how the self-test shows
# it. A hit's move is picked so no other part of a composition that uses it changes
# that move too.
VANILLA_PARTS: dict[str, tuple[str, bool, tuple[_Proof, ...]]] = {
    "strongjaw": ("Strong Jaw", False, (_Proof("hit", "Crunch"),)),       # biting, not slicing
    "sharpness": ("Sharpness", False, (_Proof("hit", "Air Slash"),)),     # slicing, no contact
    "toughclaws": ("Tough Claws", False, (_Proof("hit", "Tackle"),)),     # contact, neither biting nor slicing
    "clearbody": ("Clear Body", False, (_Proof("stat_drop"),)),           # a StatLossImmunity handler
    "moxie": ("Moxie", False, (_Proof("ko"),)),                           # an OnEndOfUsingMove handler
    # Checked by name, so these work only through the composed battler's identity:
    "levitate": ("Levitate", True, (_Proof("airborne"),)),                # airborne?
    "scrappy": ("Scrappy", True, (_Proof("hit", "Tackle", target_types=("Ghost",)),)),  # the type matchup
    "suctioncups": ("Suction Cups", True, (_Proof("forced_out"),)),       # canBeForcedOutOfBattle?
    "guts": ("Guts", True, (_Proof("hit", "Tackle", status="burn"),)),    # burn's halving; its boost is a handler
    "gorillatactics": ("Gorilla Tactics", True,                           # its boost is a handler; the lock
                       (_Proof("hit", "Tackle"), _Proof("locked", "Tackle"))),  # is by name
}

# How a check's sentence says what a proof measured.
_PROOF_GIVEN = {
    "airborne": "{ability}'s holder is airborne",
    "forced_out": "a foe cannot force {ability}'s holder out",
    "stat_drop": "a foe cannot lower the Attack of {ability}'s holder",
    "locked": "{ability}'s holder is locked into {move}",
    "ko": "a knockout by {ability}'s holder raises its stats",
}


class CompositionError(ValueError):
    """A composed ability the installer must refuse; the message is the reason."""


@dataclass(frozen=True)
class _Measure:
    """A vanilla part's proof, resolved against the target."""

    proof: _Proof
    move: Optional[str]              # INTERNAL move
    target_types: tuple[str, ...]    # INTERNAL types
    status: Optional[str]            # Essentials status


@dataclass(frozen=True)
class _Part:
    chrooked_id: str
    symbol: str                     # its ability's INTERNAL id in the target
    spec: Optional[BehaviorSpec]    # a Ruleset behavior part; None for a vanilla one
    name: str = ""                  # a vanilla part's name
    by_name: bool = False           # a vanilla part the battle code checks by name
    measures: tuple[_Measure, ...] = field(default_factory=tuple)


def render_essentials21(ability: AbilityDef, ruleset: Ruleset, names: Names) -> Optional[str]:
    """The composed ability's file, `chrooked_<id>.rb`, or None when it is not
    composable here yet (the target lacks the ability, or a part is one the module
    docstring lists as not composed yet). Raises CompositionError when a part that
    should compose cannot: the target lacks its ability, a proof's move or type, or
    a name its template needs."""
    resolved = _resolve(ability, ruleset, names)
    if resolved is None:
        return None
    symbol, parts = resolved
    table = ", ".join(f'[:{p.symbol}, "{p.chrooked_id}"]' for p in parts)
    case = templates.render_selftest_case(ability.chrooked_id, symbol, _case(parts, names))
    return "\n".join([
        _header(ability, parts),
        "",
        _CHROOKED_LOG,
        _COMPOSE,
        "begin",
        f'  ChrookedLog.line("[chrooked:{ability.chrooked_id}] load parts={",".join(p.symbol for p in parts)}")',
        f'  ChrookedCompose.register(:{symbol}, "{ability.chrooked_id}", [{table}])',
        case,
        f'  ChrookedLog.line("[chrooked:{ability.chrooked_id}] installed; wired before the first battle")',
        "rescue StandardError => e",
        f'  ChrookedLog.error("[chrooked:{ability.chrooked_id}] ERROR #{{e.class}}: #{{e.message}}")',
        "end",
        "",
    ])


def harness_checks(ability: AbilityDef, ruleset: Ruleset,
                   names: Names) -> tuple[list[dict[str, object]], tuple[BehaviorTestCase, ...]]:
    """The composed ability's checks and the test cases they score, part by part.

    A ported part's checks are its own, run under the composed ability; one on the
    port's OBS line also selects `part`, as the re-tagged line carries it. A vanilla
    part's checks read the self-test's comparisons with that part alone, and, for a
    part checked by name, its identity line.
    """
    resolved = _resolve(ability, ruleset, names)
    if resolved is None:
        raise CompositionError(f"{ability.chrooked_id}: not composable on this target yet "
                               "(the game lacks it, or a part is not composable; see behavior/compose.py)")
    _, parts = resolved
    checks: list[dict[str, object]] = []
    cases: list[BehaviorTestCase] = []
    for part in parts:
        if part.spec is not None:
            for check, case in zip(templates.harness_checks(part.spec, names), part.spec.test_cases):
                select = dict(check["select"])  # type: ignore[call-overload]
                if select.get("ability") == "true" and select.get("source") != "selftest":
                    select["part"] = part.chrooked_id
                checks.append({**check, "select": select})
                cases.append(BehaviorTestCase(given=f"{part.spec.name}: {case.given}", expect=case.expect))
            continue
        for measure in part.measures:
            given = _given(ability, part, measure)
            checks.append({
                "stage": f"Measured by the self-test: {given}.",
                "select": {"move": measure.move or "NONE", "ability": "true", "source": "selftest",
                           "part": part.symbol, "kind": measure.proof.kind},
                "expect": {"changed": "true", "result": "MATCHES"},
            })
            cases.append(BehaviorTestCase(given=f"{part.name}: {given}",
                                          expect=f"the same as {part.name} alone, unlike no ability"))
        if part.by_name:
            checks.append({
                "stage": f"Measured by the self-test: the battle code asks for {part.name} by name.",
                "select": {"case": "identity", "part": part.symbol, "source": "selftest"},
                "expect": {"has": "true", "array": "true", "other": "false"},
            })
            cases.append(BehaviorTestCase(given=f"{part.name}: the battle code asks {ability.name} for {part.name}",
                                          expect=f"hasActiveAbility?(:{part.symbol}) is true"))
    return checks, tuple(cases)


def _given(ability: AbilityDef, part: _Part, measure: _Measure) -> str:
    proof = measure.proof
    if proof.kind == "hit":
        scene = ""
        if proof.target_types:
            scene += f" on {templates._a('/'.join(proof.target_types))}-type foe"
        if proof.status:
            scene += f" while it has a {proof.status}"
        return f"{ability.name} uses {proof.move}{scene}"
    return _PROOF_GIVEN[proof.kind].format(ability=ability.name, move=proof.move)


def _resolve(ability: AbilityDef, ruleset: Ruleset, names: Names) -> Optional[tuple[str, list[_Part]]]:
    where = f"ruleset/abilities/{ability.chrooked_id}.yaml"
    if not is_composed(ability):
        raise CompositionError(f"{where}: not a composed ability")
    symbol = names.ability(ability.name)
    if symbol is None:
        return None
    parts: list[_Part] = []
    for part in composed_behaviors(ability):
        # Not composable YET (see the module docstring), like a behavior with no port:
        # the ability stays DATA ONLY, with no report line.
        nested = ruleset.abilities.get(part)
        if part == ability.chrooked_id or (nested is not None and is_composed(nested)):
            return None
        spec = ruleset.behaviors.get(part)
        if spec is not None:
            if spec.template is None:
                return None
            part_symbol = names.ability(spec.name)
            if part_symbol is None:
                raise CompositionError(f"{where}: the target has no ability {spec.name!r} for part {part!r}")
            parts.append(_Part(chrooked_id=part, symbol=part_symbol, spec=spec))
            continue
        vanilla = VANILLA_PARTS.get(part)
        if vanilla is None:
            return None
        name, by_name, proofs = vanilla
        part_symbol = names.ability(name)
        if part_symbol is None:
            raise CompositionError(f"{where}: the target has no ability {name!r} for part {part!r}")
        parts.append(_Part(chrooked_id=part, symbol=part_symbol, spec=None, name=name, by_name=by_name,
                           measures=tuple(_measure(proof, names, f"{where}: part {part!r}") for proof in proofs)))
    return symbol, parts


def _measure(proof: _Proof, names: Names, where: str) -> _Measure:
    move = None
    if proof.move is not None:
        move = names.move(proof.move)
        if move is None:
            raise CompositionError(f"{where}: the target has no move {proof.move!r} to prove it")
    types = []
    for type_name in proof.target_types:
        internal = names.type(type_name)
        if internal is None:
            raise CompositionError(f"{where}: the target has no type {type_name!r} to prove it")
        types.append(internal)
    status = _STATUSES[proof.status][0] if proof.status else None
    return _Measure(proof=proof, move=move, target_types=tuple(types), status=status)


def _compare_entry(part: _Part, measure: _Measure) -> str:
    """The self-test's compare entry: [move, part] for a plain hit, so the first
    compositions' files did not change; [move, part, kind, setup] otherwise."""
    move = f":{measure.move}" if measure.move else "nil"
    setup = []
    if measure.target_types:
        setup.append(f"target_types: [{', '.join(':' + t for t in measure.target_types)}]")
    if measure.status:
        setup.append(f"status: :{measure.status}")
    if measure.proof.kind == "hit" and not setup:
        return f"[{move}, :{part.symbol}]"
    extra = f", {{{', '.join(setup)}}}" if setup else ""
    return f"[{move}, :{part.symbol}, :{measure.proof.kind}{extra}]"


def _case(parts: list[_Part], names: Names) -> templates.SelftestCase:
    """The parts' self-test cases merged into one, plus each vanilla part's proofs."""
    control: Optional[str] = None
    calc: list[str] = []
    phases: dict[str, list[str]] = {}
    without: list[str] = []
    fight: list[str] = []
    for part in parts:
        if part.spec is not None:
            try:
                case = templates.selftest_case(part.spec, names)
            except TemplateError as exc:
                raise CompositionError(f"part {part.chrooked_id!r}: {exc}") from exc
            control = control or case.control
            calc += case.calc
            for key, entries in case.phases:
                phases.setdefault(key, []).extend(entries)
            without += case.without
            fight += case.fight
            continue
        for measure in part.measures:
            phases.setdefault("compare", []).append(_compare_entry(part, measure))
            if measure.move:
                fight.append(f":{measure.move}")
        if part.by_name:
            phases.setdefault("identity", []).append(f":{part.symbol}")
    return templates.SelftestCase(
        control=control,
        calc=tuple(dict.fromkeys(calc)),
        phases=tuple((key, tuple(dict.fromkeys(entries))) for key, entries in phases.items()),
        without=tuple(dict.fromkeys(without)),
        fight=tuple(dict.fromkeys(fight))[:templates.FIGHT_MOVES],
    )


def _header(ability: AbilityDef, parts: list[_Part]) -> str:
    listed = ", ".join(
        f"{p.symbol} (the Ruleset's {p.chrooked_id}, its port chrooked_{p.chrooked_id}.rb)" if p.spec is not None
        else f"{p.symbol} (the game's own {p.name}{', checked by name' if p.by_name else ''})"
        for p in parts)
    description = " ".join(ability.description.split()) or ability.name
    lines = [
        f"# chrooked:{ability.chrooked_id}",
        _RULE,
        f"# GENERATED by chrooked-pokedex from ruleset/abilities/{ability.chrooked_id}.yaml",
        f"# (behaviors: [{', '.join(p.chrooked_id for p in parts)}]). Do not edit this file: change",
        "# the ability or its parts and run apply.",
        "#",
        *_comment(f'Ruleset ability "{ability.chrooked_id}": {description}'),
        "#",
        *_comment(f"COMPOSED (mjolnir NV-15). Before the first battle, when every port has loaded, "
                  f"{ability.name} gets its parts' handlers in each Battle::AbilityEffects registry: "
                  f"{listed}. One part's handler is used as it is; parts sharing a registry are combined "
                  "the way its trigger reads the result (ChrookedCompose below), and its holder answers "
                  "hasActiveAbility? for each part too (NV-16). A part's port lines are re-tagged as "
                  f"{ability.chrooked_id}'s, with part=<id>."),
        "#",
        *_comment("Install, load order, the marker-gated oracle and the self-test registration are "
                  "explained once, in references/essentials21-harness/README.md."),
        f"#     [chrooked:{ability.chrooked_id}] wired <Registry>=<part>...   once, before the first battle",
        f"#     [chrooked:{ability.chrooked_id}] OBS ... part=<id>   a part's port line, re-tagged",
        _RULE,
    ]
    return "\n".join(lines)


# Shared by every composed ability's file; the first one loaded defines it. Its
# rules come from the registries' triggers in Nova's 008_Battle_AbilityEffects.rb.
_COMPOSE = """\
unless defined?(ChrookedCompose)
  module ChrookedCompose
    # How a registry combines parts that share it, as its trigger reads the result:
    # EACH runs every part (the result is unused, or a multipliers hash each part
    # changes); THREAD passes the trigger's last argument through each part in turn
    # (nil means unchanged); ANY answers with the first part that says yes.
    EACH   = [:DamageCalcFromUser, :DamageCalcFromTarget, :OnBeingHit, :OnDealingHit,
              :OnEndOfUsingMove, :OnSwitchIn]
    THREAD = [:SpeedCalc, :PriorityChange, :ModifyMoveBaseType, :CriticalCalcFromUser,
              :CriticalCalcFromTarget]
    ANY    = [:MoveImmunity, :StatLossImmunity]
    @compositions = {}
    @parts = {}
    @stack = []
    @wired = false

    def self.register(ability, tag, parts)
      @compositions[ability] = [tag, parts]
      @parts[ability] = parts.map(&:first)
    end

    # The part symbols a composed ability answers to by name; nil for any other.
    def self.parts_of(ability)
      @parts[ability]
    end

    # Once, before the first battle: every port and the game's own handlers exist.
    def self.wire
      return if @wired
      @wired = true
      @compositions.each do |ability, (tag, parts)|
        wired = []
        Battle::AbilityEffects.constants.sort.each do |name|
          registry = Battle::AbilityEffects.const_get(name)
          next if !registry.is_a?(HandlerHashSymbol)
          handlers = parts.map { |sym, part| [part, registry[sym]] }.select { |_, handler| handler }
          next if handlers.empty?
          registry.add(ability, combine(name, tag, handlers))
          wired << "#{name}=#{handlers.map(&:first).join('+')}"
        end
        ChrookedLog.line("[chrooked:#{tag}] wired #{wired.join(' ')}")
      end
    rescue StandardError => e
      ChrookedLog.error("[chrooked:compose] ERROR wire #{e.class}: #{e.message}")
    end

    def self.combine(name, tag, handlers)
      calls = handlers.map { |part, handler| proc { |*args| as(tag, part) { handler.call(*args) } } }
      return calls[0] if calls.length == 1
      if EACH.include?(name)
        proc { |*args| calls.reduce(nil) { |ret, call| r = call.call(*args); r.nil? ? ret : r } }
      elsif THREAD.include?(name)
        proc { |*args| calls.reduce(args[-1]) { |value, call| r = call.call(*args[0...-1], value); r.nil? ? value : r } }
      elsif ANY.include?(name)
        proc { |*args| calls.reduce(false) { |yes, call| yes || call.call(*args) } }
      else
        ChrookedLog.error("[chrooked:#{tag}] ERROR parts #{handlers.map(&:first).join(', ')} share #{name}, " \\
                          "which has no rule to combine them; only #{handlers[0][0]} runs")
        calls[0]
      end
    end

    # A part's handler, run for the composed ability: its port's log lines become
    # the composed ability's, and an AI estimate stays EST (the extra frames here
    # hide the AI's caller from the port's own check).
    def self.as(tag, part)
      ai = ChrookedLog::ENABLED && caller_locations(1, 12).any? { |l| l.path.to_s =~ /AI[ _]?Move/ }
      @stack.push([tag, part, ai])
      begin
        yield
      ensure
        @stack.pop
      end
    end

    def self.retag(msg)
      tag, part, ai = @stack.last
      prefix = "[chrooked:#{part}] "
      return msg if tag.nil? || !msg.start_with?(prefix)
      line = "[chrooked:#{tag}] #{msg.delete_prefix(prefix)} part=#{part}"
      ai ? line.sub("] OBS ", "] EST ") : line
    end
  end

  module ChrookedLog
    class << self
      alias_method :chrooked_compose_line, :line
      def line(msg)
        chrooked_compose_line(ChrookedCompose.retag(msg))
      end
    end
  end

  class Battle
    alias_method :chrooked_compose_initialize, :initialize
    def initialize(*args, &block)
      ChrookedCompose.wire
      chrooked_compose_initialize(*args, &block)
    end
  end

  class Battle::Battler
    # A composed battler also answers to its parts' names, so the battle code's
    # checks by name (airborne? asks for :LEVITATE, burn's halving for :GUTS) see
    # them. Not for an ability it lacks; not while its ability is suppressed.
    alias_method :chrooked_compose_has_active_ability?, :hasActiveAbility?
    def hasActiveAbility?(check_ability, ignore_fainted = false)
      return true if chrooked_compose_has_active_ability?(check_ability, ignore_fainted)
      parts = ChrookedCompose.parts_of(@ability_id)
      return false if parts.nil? || !abilityActive?(ignore_fainted, check_ability)
      (check_ability.is_a?(Array) ? check_ability : [check_ability]).any? { |a| parts.include?(a) }
    end
    alias hasWorkingAbility hasActiveAbility?
  end
end
"""
