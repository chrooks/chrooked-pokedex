# chrooked:wingspan
# Wingspan — "Wing moves and wind moves deal 30% more damage."
#   damage-calc: wing-set move OR native :windmove flag => x1.3
# Test cases:
#   - Wing Attack / Brave Bird => 1.3x ; Hurricane (wind) => 1.3x
#   - Tackle => no boost
CHROOKED_DAMAGE_MODS[:WINGSPAN] = lambda { |move, attacker, opponent|
  Chrooked.wing_or_wind_move?(move) ? 1.3 : 1.0
}
