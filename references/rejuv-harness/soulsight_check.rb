# Standalone check of all four Soulsight clauses. Unlike the older *_check.rb
# scripts this does NOT copy the lambdas — it `load`s chrooked_soulsight.rb so
# the shipped code is what runs. The mod's PokeBattle_Battler block is guarded
# by `defined?`, so the flinch clause is exercised against a stub battler here.

# --- engine stand-ins -------------------------------------------------------
class Typemod
  attr_reader :numerator, :denominator
  def initialize(n = 1, d = 1); @numerator = n; @denominator = d; end
  def self.normal; new(1, 1); end
  def *(o)
    n = numerator * o.numerator; d = denominator * o.denominator
    d = 1 if n == 0
    if n > 1 && d > 1
      m = [n, d].min; n /= m; d /= m
    end
    Typemod.new(n, d)
  end
  def immune?; @numerator <= 0; end
  def multiplier; (@numerator == -1 ? 0 : @numerator) * 1.0 / @denominator; end
end

module PBTypes
  ROWS = {
    NORMAL:   { GHOST: [0,1], NORMAL: [1,1], STEEL: [1,2] },
    FIGHTING: { GHOST: [0,1], NORMAL: [2,1], STEEL: [2,1], PSYCHIC: [1,2] },
    PSYCHIC:  { DARK: [0,1], FIGHTING: [2,1], PSYCHIC: [1,2], NORMAL: [1,1] },
  }
  def self.oneTypeEff(atype, dtype)
    n, d = ROWS.fetch(atype).fetch(dtype)
    Typemod.new(n, d)
  end
end

# A move the lambdas can interrogate. `special` is the resolved category, the
# same thing Rejuv's pbIsSpecial? returns after field effects.
Move = Struct.new(:move, :type, :special, :damaging) do
  def pbType(_attacker); type; end
  def pbIsSpecial?(_attacker, _type = nil); special; end
  def pbIsDamaging?; damaging; end
end

# Stub battler so the mod's flinch alias installs and can be driven.
class PokeBattle_Battler
  attr_accessor :effects, :ability
  def initialize(ability); @ability = ability; @effects = { Flinch: false }; end
  def pbTryUseMove(*_args); @effects[:Flinch] ? :flinched : :acted; end
end

CHROOKED_SURE_HIT = {}
CHROOKED_TYPEMOD_FLOOR = {}
CHROOKED_DAMAGE_MODS = {}

load File.join(File.dirname(__FILE__), "chrooked_soulsight.rb")

SURE  = CHROOKED_SURE_HIT[:SOULSIGHT]
FLOOR = CHROOKED_TYPEMOD_FLOOR[:SOULSIGHT]
DMG   = CHROOKED_DAMAGE_MODS[:SOULSIGHT]

# Mirrors core pbTypeModifier's floor step: vanilla chart, then floor an
# immune result to neutral when the ability lambda says so.
def resolve(move, defender_types, soulsight:)
  tm = Typemod.new(1, 1)
  defender_types.each { |t| tm *= PBTypes.oneTypeEff(move.type, t) }
  tm = Typemod.normal if soulsight && tm.immune? && FLOOR.call(move, nil)
  tm.multiplier
end

RESULTS = []
def check(label, got, want)
  ok = got.is_a?(Float) ? (got - want).abs < 1e-9 : got == want
  puts "#{ok ? 'ok  ' : 'FAIL'} #{label}: got #{got.inspect}, want #{want.inspect}"
  RESULTS << ok
end

AURA_SPHERE  = Move.new(:AURASPHERE,  :FIGHTING, true,  true)
FOCUS_BLAST  = Move.new(:FOCUSBLAST,  :FIGHTING, true,  true)
KI_BLAST     = Move.new(:KIBLAST,     :FIGHTING, true,  true)
CHI_WAVE     = Move.new(:CHIWAVE,     :FIGHTING, true,  true)
VACUUM_WAVE  = Move.new(:VACUUMWAVE,  :FIGHTING, true,  true)
AURA_SPARK   = Move.new(:AURASPARK,   :FIGHTING, true,  true)
CLOSE_COMBAT = Move.new(:CLOSECOMBAT, :FIGHTING, false, true)
DRAIN_PUNCH  = Move.new(:DRAINPUNCH,  :FIGHTING, false, true)
COACHING     = Move.new(:COACHING,    :FIGHTING, false, false)
EXTRASENSORY = Move.new(:EXTRASENSORY,:PSYCHIC,  true,  true)
ASTRAL_HAND  = Move.new(:ASTRALHAND,  :PSYCHIC,  false, true)
EXTREME_SPD  = Move.new(:EXTREMESPEED,:NORMAL,   false, true)

puts "-- clause 4: Fighting specials never miss --"
[AURA_SPHERE, FOCUS_BLAST, KI_BLAST, CHI_WAVE, VACUUM_WAVE, AURA_SPARK].each do |m|
  check("#{m.move} skips the accuracy roll", SURE.call(m, nil), true)
end
check("Close Combat (Fighting PHYSICAL) rolls normally", SURE.call(CLOSE_COMBAT, nil), false)
check("Extrasensory (Psychic special) rolls normally",   SURE.call(EXTRASENSORY, nil), false)
check("Coaching (Fighting STATUS) is not a sure hit",    SURE.call(COACHING, nil), false)

puts "-- clause 2: Scrappy, and nothing wider --"
check("Close Combat vs Ghost",           resolve(CLOSE_COMBAT, [:GHOST], soulsight: true),  1.0)
check("Extreme Speed vs Ghost",          resolve(EXTREME_SPD,  [:GHOST], soulsight: true),  1.0)
check("Close Combat vs Ghost, no ability", resolve(CLOSE_COMBAT, [:GHOST], soulsight: false), 0.0)
check("Extrasensory vs Dark STAYS immune", resolve(EXTRASENSORY, [:DARK], soulsight: true),  0.0)
check("Astral Hand vs Dark STAYS immune",  resolve(ASTRAL_HAND,  [:DARK], soulsight: true),  0.0)
check("Aura Sphere vs Steel unchanged",    resolve(AURA_SPHERE,  [:STEEL], soulsight: true), 2.0)
check("Aura Sphere vs Ghost/Steel",        resolve(AURA_SPHERE,  [:GHOST, :STEEL], soulsight: true), 1.0)

puts "-- clause 3: Psychic +30%, nothing else --"
check("Extrasensory boosted", DMG.call(EXTRASENSORY, nil, nil), 1.3)
check("Astral Hand boosted",  DMG.call(ASTRAL_HAND,  nil, nil), 1.3)
check("Aura Sphere unboosted", DMG.call(AURA_SPHERE, nil, nil), 1.0)
check("Extreme Speed unboosted", DMG.call(EXTREME_SPD, nil, nil), 1.0)

puts "-- clause 1: flinch immunity --"
holder = PokeBattle_Battler.new(:SOULSIGHT)
holder.effects[:Flinch] = true
check("Soulsight holder still acts", holder.pbTryUseMove, :acted)
check("flinch flag cleared",         holder.effects[:Flinch], false)
other = PokeBattle_Battler.new(:MEGALAUNCHER)
other.effects[:Flinch] = true
check("non-holder still flinches",   other.pbTryUseMove, :flinched)
unflinched = PokeBattle_Battler.new(:SOULSIGHT)
check("holder with no flinch acts",  unflinched.pbTryUseMove, :acted)

puts
failed = RESULTS.count(false)
puts "#{RESULTS.size - failed}/#{RESULTS.size} passed"
exit(failed.zero? ? 0 : 1)
