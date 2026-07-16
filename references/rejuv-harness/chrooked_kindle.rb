# chrooked:kindle
# Kindle — "This Pokemon's Fire-type moves deal 50% more damage."
#   damage-calc: attacker's move type is Fire => x1.5
# Test cases:
#   - Kindle mon uses a Fire move => 1.5x damage
#   - non-Fire move => no boost
CHROOKED_DAMAGE_MODS[:KINDLE] = lambda { |move, attacker, opponent|
  move.pbType(attacker) == :FIRE ? 1.5 : 1.0
}
