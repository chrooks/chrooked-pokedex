# chrooked:sagepower
# Sage Power — special moves deal 1.5x; user locks into its first move
#   (Gorilla Tactics for Special). Lock armed after the first move via
#   AFTER_MOVE; enforced at move selection by the core pbCanChooseMove? hook.
# Test cases:
#   - special move => 1.5x damage
#   - after first move => only that move selectable until switch-out
CHROOKED_DAMAGE_MODS[:SAGEPOWER] = lambda { |move, attacker, opponent|
  move.pbIsSpecial?(attacker, move.pbType(attacker)) ? 1.5 : 1.0
}
CHROOKED_AFTER_MOVE[:SAGEPOWER] = lambda { |battler, move_symbol, battle|
  battler.effects[:ChrookedMoveLock] ||= move_symbol
}
