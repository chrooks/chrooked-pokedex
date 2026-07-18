# chrooked:blitz
# Blitz — "On the turn it is sent out, the user's Speed is multiplied by 1.5."
#   turn-order: flat multiplier on computed Speed during the first attack
#   phase on the field (turncount increments to 1 BEFORE setSpeedOrder,
#   Battle.rb:4950, so first-round ordering sees 1, not 0)
# Test cases:
#   - first turn on the field => 1.5x effective Speed
#   - any later turn => normal Speed
CHROOKED_SPEED_MODS[:BLITZ] = lambda { |battler|
  battler.turncount <= 1 ? 1.5 : 1.0
}
