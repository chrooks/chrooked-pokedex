# chrooked:petalbarrier
# Petal Barrier — incoming special moves deal 25% less; may shed status each
#   turn (Shed Skin mechanic: 30% cure at end of round).
#   damage-calc (defender): special-category damaging move => x0.75
#   turn-end: non-volatile status, 30% => cured
# Test cases:
#   - special hit => 0.75x damage taken; physical hit => unchanged
#   - poisoned at end of turn => ~30% chance cured
CHROOKED_DEFENSE_MODS[:PETALBARRIER] = lambda { |move, attacker, opponent|
  move.pbIsSpecial?(attacker, move.pbType(attacker)) ? 0.75 : 1.0
}
CHROOKED_TURN_END[:PETALBARRIER] = lambda { |battler, battle|
  next if battler.status.nil? || battle.pbRandom(10) >= 3
  battle.pbShowAbilityBox(battler)
  battler.pbCureStatus
  battle.pbHideAbilityBox(battler)
}
