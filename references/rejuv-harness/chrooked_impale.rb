# chrooked:impale
# Impale — "Piercing moves deal 30% more damage."
#   damage-calc: piercing (horn/drill) move => x1.3
#   Rejuv has no piercing flag; keyed on Chrooked::PIERCING_MOVES.
# Test cases:
#   - Megahorn / Drill Run / Smart Strike => 1.3x
#   - Tackle => no boost
CHROOKED_DAMAGE_MODS[:IMPALE] = lambda { |move, attacker, opponent|
  Chrooked.piercing_move?(move) ? 1.3 : 1.0
}
