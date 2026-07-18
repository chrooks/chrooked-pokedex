# chrooked:cryomancer
# Cryomancer — "This Pokemon's Ice-type moves deal 50% more damage."
#   damage-calc: attacker's move type is Ice => x1.5
# Test cases:
#   - Cryomancer mon uses an Ice move => 1.5x damage
#   - non-Ice move => no boost
CHROOKED_DAMAGE_MODS[:CRYOMANCER] = lambda { |move, attacker, opponent|
  move.pbType(attacker) == :ICE ? 1.5 : 1.0
}
