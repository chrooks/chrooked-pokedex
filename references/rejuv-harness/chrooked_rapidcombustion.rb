# chrooked:rapidcombustion
# Rapid Combustion — "Fire-type moves gain +1 priority while at full HP."
#   turn-order: Gale Wings clone for Fire
# Test cases:
#   - full HP + Fire move => +1 priority
#   - damaged, or non-Fire move => normal priority
CHROOKED_PRIORITY_MODS[:RAPIDCOMBUSTION] = lambda { |move, attacker|
  attacker.hp == attacker.totalhp && move.pbType(attacker) == :FIRE ? 1 : 0
}
