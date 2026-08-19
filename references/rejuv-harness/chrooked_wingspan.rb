# chrooked:wingspan
# Updraft (chrooked_id wingspan; renamed from "Wingspan" 2026-08-19) —
#   "Wing moves and wind moves deal 30% more damage."
#   Rejuv symbols are name-derived, so this registers under :UPDRAFT.
#   damage-calc: wing-set move OR native :windmove flag => x1.3
# Test cases:
#   - Wing Attack / Brave Bird => 1.3x ; Hurricane (wind) => 1.3x
#   - Tackle => no boost
CHROOKED_DAMAGE_MODS[:UPDRAFT] = lambda { |move, attacker, opponent|
  Chrooked.wing_or_wind_move?(move) ? 1.3 : 1.0
}
