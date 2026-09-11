# chrooked:sunbask
# Sunbask — "In sun, restores 1/8 max HP each turn and drain moves recover all
#   damage dealt." Rain Dish for sun plus a x2 drain (50% -> 100%).
#   turn-end:    in sun, heal 1/8 max HP (ability box, like Rain Dish)
#   damage-calc: in sun, absorb heals are doubled (stacks with Big Root)
#   Gating mirrors Solar Power: pbWeather(battler) handles Air Lock, and
#   Utility Umbrella / FROZENDIMENSION are checked by hand.
# Test cases (drive in-game):
#   - sun, end of turn, damaged holder => heals 1/8 with the ability box
#   - sun, Giga Drain for 80           => recovers 80
#   - no weather, Giga Drain for 80    => recovers 40, no end-of-turn heal
#   - Utility Umbrella in sun          => nothing
module Chrooked
  def self.sunbask_sun?(battler, battle)
    return false unless battle.pbWeather(battler) == :SUNNYDAY
    return false if battler.hasWorkingItem(:UTILITYUMBRELLA) || battle.FE == :FROZENDIMENSION
    true
  end
end

CHROOKED_TURN_END[:SUNBASK] = lambda { |battler, battle|
  next unless Chrooked.sunbask_sun?(battler, battle) && battler.canHeal?
  battle.pbShowAbilityBox(battler)
  battler.pbRecoverHP((battler.totalhp / 8.0).floor, true,
                      message: _INTL("{1} basked in the sunlight!", battler.pbThis))
  battle.pbHideAbilityBox(battler)
}

CHROOKED_ABSORB_MODS[:SUNBASK] = lambda { |battler, hpgain, agent|
  Chrooked.sunbask_sun?(battler, battler.battle) ? hpgain * 2 : hpgain
}

# The AI's hpGainPerTurn knows Rain Dish by symbol only; credit the sun heal.
CHROOKED_AI_HP_REFUND[:SUNBASK] = lambda { |battler, battle|
  Chrooked.sunbask_sun?(battler, battle) ? 0.125 : 0.0
}
