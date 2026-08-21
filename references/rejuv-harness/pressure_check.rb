# Standalone check of the Pressure entry-clear lambda. Stubs the handful of Rejuv
# objects it touches, then runs chrooked_pressure.rb verbatim.
class PBStats
  ATTACK = 1; DEFENSE = 2; SPATK = 3; SPDEF = 4; SPEED = 5; ACCURACY = 6; EVASION = 7
  All = [ATTACK, DEFENSE, SPATK, SPDEF, SPEED, ACCURACY, EVASION]
end

def _INTL(str, *args)
  args.each_with_index { |a, i| str = str.gsub("{#{i + 1}}", a.to_s) }
  str
end

Foe = Struct.new(:stages, :fainted) do
  def isFainted?; fainted; end
  def pbThis; "the foe"; end
end

class Battler
  attr_accessor :foes
  def initialize(foes); @foes = foes; end
  def pbOpposing1; @foes[0]; end
  def pbOpposing2; @foes[1]; end
  def pbThis; "Dusknoir"; end
end

class Battle
  attr_reader :messages
  def initialize; @messages = []; end
  def pbAbilityBoxAndDisplay(_battler, msg); @messages << msg; end
end

CHROOKED_SWITCH_IN = {}
load File.join(__dir__, "chrooked_pressure.rb")
handler = CHROOKED_SWITCH_IN[:PRESSURE]

def stages(hash = {})
  Array.new(8, 0).tap { |s| hash.each { |k, v| s[k] = v } }
end

# 1. boosts cleared, drops survive
foe = Foe.new(stages(PBStats::ATTACK => 2, PBStats::SPEED => -1), false)
battle = Battle.new
handler.call(Battler.new([foe, nil]), battle)
raise "atk not cleared" unless foe.stages[PBStats::ATTACK] == 0
raise "drop was erased" unless foe.stages[PBStats::SPEED] == -1
raise "no message" if battle.messages.empty?

# 2. doubles: both foes cleared, fainted slot skipped
a = Foe.new(stages(PBStats::EVASION => 3), false)
b = Foe.new(stages(PBStats::DEFENSE => 1), false)
handler.call(Battler.new([a, b]), Battle.new)
raise "foe A not cleared" unless a.stages[PBStats::EVASION] == 0
raise "foe B not cleared" unless b.stages[PBStats::DEFENSE] == 0

dead = Foe.new(stages(PBStats::ATTACK => 6), true)
handler.call(Battler.new([dead, nil]), Battle.new)
raise "fainted foe touched" unless dead.stages[PBStats::ATTACK] == 6

# 3. nothing to clear => silent
quiet = Battle.new
handler.call(Battler.new([Foe.new(stages, false), nil]), quiet)
raise "message on a no-op" unless quiet.messages.empty?

puts "pressure entry-clear: OK"
