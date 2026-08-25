# chrooked:dualaegis
# Dual Aegis — "On entry, sets up Reflect and Light Screen on the user's side
# for 5 turns each (8 with Light Clay), leaving an already-active screen untouched."
#
# Pure registry entry — the core's CHROOKED_SWITCH_IN table fires from
# pbAbilitiesOnSwitchIn after vanilla switch-in abilities resolve. Durations
# mirror the vanilla Reflect / Light Screen moves (Battle_MoveEffects.rb):
# 5 turns, 8 with a working Light Clay, 8 on the Mirror / Dance Floor fields.
#
# Test cases (drive in-game — the harness can't prove battle behavior):
#   - Switch in with no screens        => Reflect AND Light Screen up, 5 turns each.
#   - Reflect already active           => only Light Screen applied; Reflect's counter untouched.
#   - Holding Light Clay, no screens   => both screens at 8 turns.

CHROOKED_SWITCH_IN[:DUALAEGIS] = lambda { |battler, battle|
  own = battler.pbOwnSide
  turns = battler.hasWorkingItem(:LIGHTCLAY) ? 8 : 5
  turns = 8 if battle.respond_to?(:FE) && [:MIRROR, :DANCEFLOOR].include?(battle.FE)
  raised = false
  if own.effects[:Reflect] <= 0
    own.effects[:Reflect] = turns
    raised = true
  end
  if own.effects[:LightScreen] <= 0
    own.effects[:LightScreen] = turns
    raised = true
  end
  if raised
    battle.pbShowAbilityBox(battler)
    if !battle.pbIsOpposing?(battler.index)
      battle.pbDisplay(_INTL("{1}'s Dual Aegis raised screens over your team!", battler.pbThis))
    else
      battle.pbDisplay(_INTL("{1}'s Dual Aegis raised screens over the opposing team!", battler.pbThis))
    end
    battle.pbHideAbilityBox(battler)
  end
}
