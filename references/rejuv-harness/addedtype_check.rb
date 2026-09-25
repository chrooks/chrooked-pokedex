# Standalone check of the CHROOKED_ADDED_TYPE registry (chrooked_00_core.rb)
# and its first user, Phantom (chrooked_phantom.rb). Loads the real core and
# plugin against stubs that copy only the vanilla shapes they touch:
# Battler#types (Battler.rb:226), canChangeType? (:232), pbInitEffects clearing
# OtherEff (:655), Trick-or-Treat / Forest's Curse (Battle_MoveEffects.rb
# :7416/:7424, :7386/:7392), and the AI's getTypesOnEntry (Battle_AI.rb:349).
#   docker run --rm -v "$PWD/references/rejuv-harness:/h:ro" ruby:3.2-slim ruby /h/addedtype_check.rb

def _INTL(fmt, *args) = args.each_with_index.reduce(fmt) { |s, (a, i)| s.sub("{#{i + 1}}", a.to_s) }
def getTypeName(type) = type.to_s.capitalize

class PokeBattle_Move; end

class PokeBattle_Battle
  attr_reader :log
  def initialize = @log = []
  def pbAbilityBoxAndDisplay(_battler, msg) = @log << [:box, msg]
end

class PokeBattle_Battler
  attr_accessor :ability, :type1, :type2, :effects, :hp, :tera
  def initialize(battle, ability, type1, type2 = nil, hp: 100, tera: false)
    @battle, @ability, @type1, @type2, @hp, @tera = battle, ability, type1, type2, hp, tera
    pbInitEffects
  end
  def pbInitEffects = @effects = { TemporaryType: nil }
  def types = [@type1, @type2, @effects[:TemporaryType]].compact.uniq
  def hasType?(type) = types.include?(type)
  def canChangeType? = ![:MULTITYPE, :RKSSYSTEM].include?(ability) && !@tera
  def isFainted? = @hp <= 0
  def pbThis(_lower = false) = "the Rotom"
  def pbAbilitiesOnSwitchIn(*) = nil
end

# vanilla move effects, reduced to their validity gate + the one write
def trick_or_treat(t) = (t.canChangeType? && !t.hasType?(:GHOST)) ? (t.effects[:TemporaryType] = :GHOST; true) : false
def forests_curse(t) = (t.canChangeType? && !t.hasType?(:GRASS)) ? (t.effects[:TemporaryType] = :GRASS; true) : false

class PokeBattle_AI
  attr_reader :vanilla_ran
  def getTypesOnEntry(_trainer, _pkmn, _delay = false) = @vanilla_ran = true
end

require_relative "chrooked_zz_redux"
require_relative "chrooked_00_core"
require_relative "chrooked_phantom"

$fails = 0
def check(label, got, want)
  ok = got == want
  $fails += 1 unless ok
  puts "#{ok ? 'PASS' : 'FAIL'}  #{label}: got #{got.inspect}, want #{want.inspect}"
end

def enter(ability, t1, t2 = nil, **kw)
  battle = PokeBattle_Battle.new
  mon = PokeBattle_Battler.new(battle, ability, t1, t2, **kw)
  mon.pbAbilitiesOnSwitchIn
  [mon, battle.log]
end

heat, log = enter(:PHANTOM, :ELECTRIC, :FIRE)
check("Rotom-Heat enters => Ghost added as third type", heat.types, [:ELECTRIC, :FIRE, :GHOST])
check("ability box + Trick-or-Treat's message", log, [[:box, "Ghost type was added to the Rotom!"]])

heat.pbAbilitiesOnSwitchIn
check("re-activation while already Ghost => no second box", heat.types.count(:GHOST), 1)

check("later Trick-or-Treat fails (already Ghost)", trick_or_treat(heat), false)
forests_curse(heat)
check("later Forest's Curse replaces Ghost with Grass", heat.types, [:ELECTRIC, :FIRE, :GRASS])

heat.pbInitEffects
check("switch-out (pbInitEffects) clears it", heat.types, [:ELECTRIC, :FIRE])

rotom, log = enter(:PHANTOM, :ELECTRIC, :GHOST)
check("already Ghost-type => nothing, no box", [rotom.types, log], [[:ELECTRIC, :GHOST], []])

tera, log = enter(:PHANTOM, :ELECTRIC, :FIRE, tera: true)
check("cannot change type (Terastallized) => nothing", [tera.types, log], [[:ELECTRIC, :FIRE], []])

fainted, _ = enter(:PHANTOM, :ELECTRIC, :FIRE, hp: 0)
check("fainted on entry => nothing", fainted.types, [:ELECTRIC, :FIRE])

other, log = enter(:LEVITATE, :ELECTRIC, :FIRE)
check("unregistered ability => nothing", [other.types, log], [[:ELECTRIC, :FIRE], []])

redux, _ = enter(ChrookedAbilitySet.new([:LEVITATE, :PHANTOM]), :ELECTRIC, :WATER)
check("Redux multi-ability set holding Phantom => Ghost added", redux.types, [:ELECTRIC, :WATER, :GHOST])

CHROOKED_ADDED_TYPE[:TESTPLATING] = :STEEL # the next type-adder is one line
plated, _ = enter(:TESTPLATING, :BUG)
check("pattern: a new one-line registry entry works", plated.types, [:BUG, :STEEL])

ai = PokeBattle_AI.new
cand = PokeBattle_Battler.new(PokeBattle_Battle.new, :PHANTOM, :ELECTRIC, :ICE)
ai.getTypesOnEntry(nil, cand)
check("AI: switch candidate scored as part Ghost", cand.types, [:ELECTRIC, :ICE, :GHOST])
check("AI: vanilla getTypesOnEntry still runs", ai.vanilla_ran, true)
cand = PokeBattle_Battler.new(PokeBattle_Battle.new, :VOLTABSORB, :ELECTRIC, :FLYING)
ai.getTypesOnEntry(nil, cand)
check("AI: other abilities untouched", cand.types, [:ELECTRIC, :FLYING])

exit($fails.zero? ? 0 : 1)
