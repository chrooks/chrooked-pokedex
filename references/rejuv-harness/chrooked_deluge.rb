# chrooked:deluge
# Deluge — "This Pokemon's Water-type moves deal 50% more damage."
#   damage-calc: attacker's move type is Water => x1.5
# Test cases:
#   - Deluge mon uses a Water move => 1.5x damage
#   - non-Water move => no boost
CHROOKED_DAMAGE_MODS[:DELUGE] = lambda { |move, attacker, opponent|
  move.pbType(attacker) == :WATER ? 1.5 : 1.0
}
