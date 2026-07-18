# chrooked:liquified
# Liquified — a liquid body: contact hits sink in harmlessly, Water destabilises it.
#   damage-calc (defender): incoming contact move => x0.5
#   damage-calc (defender): incoming Water move   => x2 ON TOP of the type chart
#   The x2 is an extra multiplier, not a chart edit, so it is independent of the
#   bearer's real typing (neutral becomes x2, an existing x2 becomes x4). Both
#   clauses stack multiplicatively when a move is contact AND Water.
# Test cases:
#   - Close Combat (contact, Fighting) => 0.5x
#   - Scald (non-contact, Water)       => 2x
#   - Liquidation (contact + Water)    => 0.5 * 2 = 1x, exactly cancelling
#   - Earthquake (non-contact)         => unchanged
CHROOKED_DEFENSE_MODS[:LIQUIFIED] = lambda { |move, attacker, opponent|
  mult = 1.0
  mult *= 0.5 if move.contactMove?
  mult *= 2.0 if move.pbType(attacker) == :WATER
  mult
}
