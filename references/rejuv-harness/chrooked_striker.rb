# chrooked:striker
# Striker — "Kicking moves deal 30% more damage."
#   damage-calc: kicking move => x1.3
# Test cases:
#   - Blaze Kick / High Jump Kick => 1.3x
#   - Mach Punch => no boost (punch, not kick)
CHROOKED_DAMAGE_MODS[:STRIKER] = lambda { |move, attacker, opponent|
  Chrooked.kick_move?(move) ? 1.3 : 1.0
}
