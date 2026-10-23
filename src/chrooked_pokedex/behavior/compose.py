"""Composed abilities on Essentials 21: one ability built from several behaviors (mjolnir NV-15).

A Ruleset ability may list its parts, `behaviors: [carnivore, strongjaw]`: Apex
Predator is Carnivore's knockout heal plus Strong Jaw's biting boost. A part is
either a Ruleset behavior whose port is generated from its template, or a vanilla
ability the game already ships. Essentials 21 keys every battle effect by ability
id in its handler registries (`Battle::AbilityEffects::DamageCalcFromUser`, ...),
so the composed ability's file gives it its parts' handlers:

  * a registry only one part has a handler in gets that handler as it is;
  * a registry several parts share gets one handler that combines them the way the
    registry's trigger reads the result: multiplier and side-effect registries run
    every part in turn; registries that pass a value along (speed, priority, the
    move's type, the critical stage) hand each part the one before's result;
    immunity registries answer yes when any part does. Two parts sharing a registry
    with no such rule log an ERROR, and only the first runs.

The wiring waits for the first battle, when every port has loaded: the composed
ability's file sorts before its parts' (`chrooked_apexpredator.rb` before
`chrooked_carnivore.rb`). While a part's handler runs for the composed ability,
its port's log lines are re-tagged as the composed ability's, with `part=<id>`, so
the harness scores them for it.

The proof reuses a ported part's own probes under the composed ability, and shows
a vanilla part by comparison: the composed ability hits a move exactly as hard as
the part alone (VANILLA_PARTS names the move). A composition installs only when
every part can be proven that way. Not composed yet:

  * a vanilla part without a VANILLA_PARTS entry, including every part the battle
    code checks by name (`hasActiveAbility?(:LEVITATE)`: Levitate, Guts, Scrappy,
    Suction Cups), which would need the battler to answer to its parts' names too;
  * a Ruleset part with no template (unported, or hand-written);
  * an ability that lists itself (Finishing Kick is finishingkick plus Speed Boost),
    whose own port would share its file name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..model.behavior_spec import BehaviorSpec, BehaviorTestCase
from ..model.ruleset import Ruleset
from ..model.schema import AbilityDef, composed_behaviors, is_composed
from . import templates
from .templates import Names, TemplateError, _CHROOKED_LOG, _RULE, _comment

# A vanilla ability a composition may borrow: its name in the game, and the moves
# whose damage it alone changes, for the self-test's `compare` phase. Each move is
# picked so no other part of a composition that uses it changes it too.
VANILLA_PARTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "strongjaw": ("Strong Jaw", ("Crunch",)),      # biting, not slicing
    "sharpness": ("Sharpness", ("Air Slash",)),    # slicing, no contact
    "toughclaws": ("Tough Claws", ("Tackle",)),    # contact, neither biting nor slicing
}


class CompositionError(ValueError):
    """A composed ability the installer must refuse; the message is the reason."""


@dataclass(frozen=True)
class _Part:
    chrooked_id: str
    symbol: str                     # its ability's INTERNAL id in the target
    spec: Optional[BehaviorSpec]    # a Ruleset behavior part; None for a vanilla one
    name: str = ""                  # a vanilla part's name
    moves: tuple[tuple[str, str], ...] = ()  # a vanilla part's (name, INTERNAL) compare moves


def render_essentials21(ability: AbilityDef, ruleset: Ruleset, names: Names) -> Optional[str]:
    """The composed ability's file, `chrooked_<id>.rb`, or None when it is not
    composable here yet (the target lacks the ability, or a part is one the module
    docstring lists as not composed yet). Raises CompositionError when a part that
    should compose cannot: the target lacks its ability, its proof move, or a name
    its template needs."""
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
    part's check reads the self-test's comparison with that part alone.
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
        for move_name, move in part.moves:
            checks.append({
                "stage": f"With your {ability.name} user, use {move_name} on the foe.",
                "select": {"move": move, "ability": "true", "source": "selftest", "part": part.symbol},
                "expect": {"boosted": "true", "result": "MATCHES"},
            })
            cases.append(BehaviorTestCase(
                given=f"{part.name}: {ability.name} uses {move_name}",
                expect=f"the same damage as {part.name} alone, more than with no ability"))
    return checks, tuple(cases)


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
        name, move_names = vanilla
        part_symbol = names.ability(name)
        if part_symbol is None:
            raise CompositionError(f"{where}: the target has no ability {name!r} for part {part!r}")
        moves = []
        for move_name in move_names:
            move = names.move(move_name)
            if move is None:
                raise CompositionError(f"{where}: the target has no move {move_name!r} to prove part {part!r}")
            moves.append((move_name, move))
        parts.append(_Part(chrooked_id=part, symbol=part_symbol, spec=None, name=name, moves=tuple(moves)))
    return symbol, parts


def _case(parts: list[_Part], names: Names) -> templates.SelftestCase:
    """The parts' self-test cases merged into one, plus a comparison per vanilla move."""
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
        for _, move in part.moves:
            phases.setdefault("compare", []).append(f"[:{move}, :{part.symbol}]")
            fight.append(f":{move}")
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
        else f"{p.symbol} (the game's own {p.name})"
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
                  "the way its trigger reads the result (ChrookedCompose below). A part's port lines "
                  f"are re-tagged as {ability.chrooked_id}'s, with part=<id>."),
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
    @stack = []
    @wired = false

    def self.register(ability, tag, parts)
      @compositions[ability] = [tag, parts]
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
end
"""
