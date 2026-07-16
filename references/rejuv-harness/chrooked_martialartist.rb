# chrooked:martialartist
# Martial Artist — "Punching moves and kicking moves deal 30% more damage."
#   damage-calc: punching OR kicking move => x1.3
# Test cases:
#   - Mach Punch => 1.3x ; Low Kick / Blaze Kick => 1.3x
#   - Tackle => no boost
CHROOKED_DAMAGE_MODS[:MARTIALARTIST] = lambda { |move, attacker, opponent|
  move.punchMove? || Chrooked.kick_move?(move) ? 1.3 : 1.0
}
