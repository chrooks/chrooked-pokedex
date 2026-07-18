# chrooked:updraft
# Updraft — Ground immunity + wing/wind moves deal 30% more damage.
#   damage-calc: incoming Ground move => blocked
#   damage-calc: user's wing or wind move => x1.3
# Test cases:
#   - Earthquake vs Updraft mon => no effect
#   - Wing Attack / Hurricane from Updraft mon => 1.3x
CHROOKED_TYPE_IMMUNITY[:UPDRAFT] = { type: :GROUND, flag: :Soundproof }
CHROOKED_DAMAGE_MODS[:UPDRAFT] = lambda { |move, attacker, opponent|
  Chrooked.wing_or_wind_move?(move) ? 1.3 : 1.0
}
