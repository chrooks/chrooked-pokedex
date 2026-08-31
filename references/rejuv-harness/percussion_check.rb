# Standalone check of Percussion. Loads chrooked_percussion.rb so the shipped
# code is what runs; PokeBattle_Move is stubbed BEFORE the load so the mod's
# `defined?`-guarded prepend actually installs and can be driven.

# --- engine stand-in --------------------------------------------------------
# Mirrors Rejuv's Battle_Move.rb: pbIsPhysical?/pbIsSpecial? answer from
# @category, and the stat-selection questions derive from them.
class PokeBattle_Move
  attr_accessor :category, :sound
  def initialize(category, sound); @category = category; @sound = sound; end
  def isSoundBased?;  @sound; end
  def pbIsStatus?;    @category == :status; end
  def pbIsDamaging?;  !pbIsStatus?; end
  def pbIsPhysical?(_attacker, _type = nil); @category == :physical; end
  def pbIsSpecial?(_attacker, _type = nil);  @category == :special;  end
  # The two seams pbCalcDamage actually reads for stat selection.
  def pbHitsPhysicalStat?(attacker); pbIsPhysical?(attacker); end
  def pbHitsSpecialStat?(attacker);  pbIsSpecial?(attacker);  end
end

Battler = Struct.new(:ability)

require_relative "chrooked_percussion"

# --- assertions -------------------------------------------------------------
$pass = 0
$fail = 0
def check(label, actual, expected)
  if actual == expected
    $pass += 1
    puts "  ok   #{label}"
  else
    $fail += 1
    puts "  FAIL #{label} — expected #{expected.inspect}, got #{actual.inspect}"
  end
end

percussion = Battler.new(:PERCUSSION)
galvanize  = Battler.new(:GALVANIZE)

boomburst  = PokeBattle_Move.new(:special,  true)   # Normal sound 140
overdrive  = PokeBattle_Move.new(:special,  true)   # Electric sound 100
thunderblt = PokeBattle_Move.new(:special,  false)  # not sound
wildcharge = PokeBattle_Move.new(:physical, false)
growl      = PokeBattle_Move.new(:status,   true)   # sound, but status

puts "Percussion active — damaging sound moves flip to physical:"
check("Boomburst pbIsPhysical?",        boomburst.pbIsPhysical?(percussion),      true)
check("Boomburst pbIsSpecial?",         boomburst.pbIsSpecial?(percussion),       false)
check("Boomburst uses Attack stat",     boomburst.pbHitsPhysicalStat?(percussion), true)
check("Boomburst not Sp.Atk stat",      boomburst.pbHitsSpecialStat?(percussion),  false)
check("Overdrive pbIsPhysical?",        overdrive.pbIsPhysical?(percussion),      true)

puts "\nScope — nothing else moves:"
check("non-sound special untouched",    thunderblt.pbIsPhysical?(percussion),     false)
check("non-sound special still special", thunderblt.pbIsSpecial?(percussion),     true)
check("physical move untouched",        wildcharge.pbIsPhysical?(percussion),     true)
check("STATUS sound move stays status", growl.pbIsStatus?,                        true)
check("STATUS sound not made physical", growl.pbIsPhysical?(percussion),          false)

puts "\nWithout the ability — RED without the mechanic:"
check("Boomburst stays special",        boomburst.pbIsSpecial?(galvanize),        true)
check("Boomburst not physical",         boomburst.pbIsPhysical?(galvanize),       false)
check("Boomburst uses Sp.Atk stat",     boomburst.pbHitsSpecialStat?(galvanize),  true)

puts "\nDefensive guards:"
check("nil attacker does not crash",    boomburst.pbIsPhysical?(nil),             false)
check("nil attacker still special",     boomburst.pbIsSpecial?(nil),              true)
check("@category left untouched",       boomburst.category,                       :special)

puts "\n#{$pass}/#{$pass + $fail} passed"
exit($fail.zero? ? 0 : 1)
