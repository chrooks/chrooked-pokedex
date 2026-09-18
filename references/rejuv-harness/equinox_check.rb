# Runnable check for Equinox's stat equalization. No game needed:
#   docker run --rm -v "$PWD/references/rejuv-harness:/h:ro" ruby:3.2-slim ruby /h/equinox_check.rb
module PBStats
  ATTACK = 1
  SPATK = 3
  StageMul = [2.0/8, 2.0/7, 2.0/6, 2.0/5, 2.0/4, 2.0/3, 2.0/2,
              3.0/2, 4.0/2, 5.0/2, 6.0/2, 7.0/2, 8.0/2]
end
CHROOKED_ATTACK_EQUALIZE = []

module Chrooked
  def self.ability_in?(list, ability)
    return false if ability.nil?
    return list.include?(ability) unless ability.respond_to?(:list)
    ability.list.any? { |a| list.include?(a) }
  end

  def self.with_equalized_attack(battler)
    atk_stage = battler.stages[PBStats::ATTACK]
    spa_stage = battler.stages[PBStats::SPATK]
    atk_eff = battler.attack * PBStats::StageMul[atk_stage + 6]
    spa_eff = battler.spatk  * PBStats::StageMul[spa_stage + 6]
    old_atk = battler.attack
    old_spa = battler.spatk
    if spa_eff > atk_eff
      battler.attack = old_spa
      battler.stages[PBStats::ATTACK] = spa_stage
    else
      battler.spatk = old_atk
      battler.stages[PBStats::SPATK] = atk_stage
    end
    begin
      yield
    ensure
      battler.attack = old_atk
      battler.spatk = old_spa
      battler.stages[PBStats::ATTACK] = atk_stage
      battler.stages[PBStats::SPATK] = spa_stage
    end
  end
end

require_relative "chrooked_equinox"

class Mon
  attr_accessor :attack, :spatk, :stages, :ability
  def initialize(atk, spa, ability: :EQUINOX, atk_stage: 0, spa_stage: 0)
    @attack, @spatk, @ability = atk, spa, ability
    @stages = Array.new(6, 0)
    @stages[PBStats::ATTACK] = atk_stage
    @stages[PBStats::SPATK] = spa_stage
  end
  # What Rejuv's damage calc reads for a special move.
  def special_power = (spatk * PBStats::StageMul[stages[PBStats::SPATK] + 6]).floor
  def physical_power = (attack * PBStats::StageMul[stages[PBStats::ATTACK] + 6]).floor
end

def check(label) = (yield ? puts("ok   #{label}") : abort("FAIL #{label}"))
def used(mon)
  return [mon.physical_power, mon.special_power] unless
    Chrooked.ability_in?(CHROOKED_ATTACK_EQUALIZE, mon.ability)
  Chrooked.with_equalized_attack(mon) { [mon.physical_power, mon.special_power] }
end

check("registered") { CHROOKED_ATTACK_EQUALIZE == [:EQUINOX] }

# Mega Absol's spread: 170 Atk / 65 SpA.
absol = Mon.new(170, 65)
phys, spec = used(absol)
check("special moves fire off the higher Attack") { spec == 170 }
check("physical is unchanged")                    { phys == 170 }
check("stats are restored after the hit")         { absol.spatk == 65 && absol.attack == 170 }

# Swords Dance: the winning stat carries its own stage across.
sd = Mon.new(170, 65, atk_stage: 2)
check("Swords Dance powers special moves too") { used(sd)[1] == (170 * 2.0).floor }
check("stages restored")                        { sd.stages[PBStats::SPATK] == 0 }

# Nasty Plot x2 on 65 SpA = 130, still under 170 — Attack keeps winning.
np = Mon.new(170, 65, spa_stage: 2)
check("a losing boost does not win")           { used(np)[1] == 170 }

# The reverse case: a special attacker lifts its Attack.
mage = Mon.new(60, 150)
check("special mon lifts its Attack")          { used(mage)[0] == 150 }

# Ties go to Attack, matching the source's `>` comparison.
tie = Mon.new(100, 100, atk_stage: 1)
check("ties resolve to Attack")                { used(tie) == [150, 150] }

# A mon without the ability is untouched.
plain = Mon.new(170, 65, ability: :PRESSURE)
check("no ability, no change")                 { used(plain) == [170, 65] }

# Rejuv multi-ability sets (zz_redux) expose .list.
AbilitySet = Struct.new(:list)
multi = Mon.new(170, 65, ability: AbilitySet.new([:PRESSURE, :EQUINOX]))
check("works inside a multi-ability set")      { used(multi)[1] == 170 }
puts "all checks passed"
