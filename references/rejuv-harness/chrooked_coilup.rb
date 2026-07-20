# chrooked:coilup
# Coil Up — "On entry, arms a one-time +1 priority for the first biting move."
#   Mirrors chrooked_stampede.rb exactly; only the arming trigger (switch-in
#   instead of KO) and the move test (bitingMove? instead of contact) differ.
#   Armed on switch-in; priority delta read via CHROOKED_PRIORITY_MODS;
#   consumed when a biting move deals damage. Re-entry re-arms it.
# Test cases:
#   - switch in, use Crunch => acts at +1 priority, flag clears
#   - switch in, use Glare (non-biting) => normal priority, flag stays armed
#   - spend the charge, switch out and back in => re-armed
CHROOKED_SWITCH_IN[:COILUP] = lambda { |battler, battle|
  battler.effects[:ChrookedCoilUp] = true
}
CHROOKED_PRIORITY_MODS[:COILUP] = lambda { |move, attacker|
  attacker.effects[:ChrookedCoilUp] && move.bitingMove? ? 1 : 0
}
# ponytail: consumed on damage dealt (mirrors Stampede) rather than at turn-order.
# Practical difference: a bite that is blocked outright keeps the charge armed.
# That is strictly kinder to the player and reuses a seam already proven in-game.
CHROOKED_ON_DEAL[:COILUP] = lambda { |move, user, target, battle|
  user.effects[:ChrookedCoilUp] = nil if user.effects[:ChrookedCoilUp] && move.bitingMove?
}
