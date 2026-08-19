# chrooked:updraft
# Wingspan (chrooked_id updraft; renamed from "Updraft" 2026-08-19) —
#   Ground immunity + wing/wind moves deal 30% more damage.
#   Rejuv symbols are name-derived, so this registers under :WINGSPAN.
#   damage-calc: incoming Ground move => blocked
#   damage-calc: user's wing or wind move => x1.3
# Test cases:
#   - Earthquake vs Wingspan mon => no effect
#   - Wing Attack / Hurricane from Wingspan mon => 1.3x
CHROOKED_TYPE_IMMUNITY[:WINGSPAN] = { type: :GROUND, flag: :Soundproof }
CHROOKED_DAMAGE_MODS[:WINGSPAN] = lambda { |move, attacker, opponent|
  Chrooked.wing_or_wind_move?(move) ? 1.3 : 1.0
}
