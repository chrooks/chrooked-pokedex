# chrooked:bloom
# Bloom — "This Pokemon's Grass-type moves deal 50% more damage."
#   damage-calc: attacker's move type is Grass => x1.5
# Test cases:
#   - Bloom mon uses a Grass move => 1.5x damage
#   - Bloom mon uses a non-Grass move => no boost
CHROOKED_DAMAGE_MODS[:BLOOM] = lambda { |move, attacker, opponent|
  move.pbType(attacker) == :GRASS ? 1.5 : 1.0
}
