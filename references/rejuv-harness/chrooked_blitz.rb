# chrooked:blitz
# Blitz — "On the turn it is sent out, the user's Speed is multiplied by 1.5."
#   turn-order: flat multiplier on computed Speed while turncount == 0
# Test cases:
#   - first turn on the field => 1.5x effective Speed
#   - any later turn => normal Speed
CHROOKED_SPEED_MODS[:BLITZ] = lambda { |battler|
  battler.turncount == 0 ? 1.5 : 1.0
}
