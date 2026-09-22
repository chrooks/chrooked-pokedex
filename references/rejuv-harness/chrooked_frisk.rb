# chrooked:frisk
# Frisk — vanilla Frisk (it sees the foes' held items) plus a Chrooked rider:
#   on entry, every adjacent foe is under Embargo for 2 rounds, so its held
#   item does nothing while the timer runs.
#   The vanilla peek is untouched; this file only adds the Embargo on top.
#
# Reuses the vanilla effects[:Embargo] counter the move Embargo sets
# (Battle_MoveEffects.rb, PokeBattle_Move_0F8, which sets 5). Decay, the
# item-suppression checks, and Battle_Inspect all read the same counter, so
# nothing else here is needed.
#
# Test cases (drive in-game — the harness can't prove battle behavior):
#   - Switch in vs a Leftovers holder => "can't use items", no Leftovers heal for 2 rounds.
#   - A foe already under Embargo     => the longer timer is kept, no message.
#   - Round 3 after entry             => the foe's item works again.
CHROOKED_SWITCH_IN[:FRISK] = lambda { |battler, battle|
  [battler.pbOpposing1, battler.pbOpposing2].each do |foe|
    next if !foe || foe.isFainted?
    next if foe.effects[:Embargo] >= 2
    battle.pbShowAbilityBox(battler)
    foe.effects[:Embargo] = 2
    battle.pbDisplay(_INTL("{1} can't use items anymore!", foe.pbThis))
    battle.pbHideAbilityBox(battler)
  end
}
