# chrooked:virtualized
# Virtualized — a digital body: strikes pass through it, Dark intrudes on it.
#   damage-calc (defender): incoming contact move => x1/3
#   damage-calc (defender): incoming Dark move    => x2 ON TOP of the type chart
#   The x2 is an extra multiplier, not a chart edit, so it is independent of the
#   bearer's real typing (neutral becomes x2, an existing x2 becomes x4). Both
#   clauses stack multiplicatively when a move is contact AND Dark.
# Test cases:
#   - Close Combat (contact, Fighting)        => 1/3x
#   - Dark Pulse (non-contact, Dark, vs 2x)   => 4x
#   - Crunch (contact + Dark, vs 2x)          => 4 * 1/3 ~= 1.33x
#   - Earthquake (non-contact physical)       => unchanged
CHROOKED_DEFENSE_MODS[:VIRTUALIZED] = lambda { |move, attacker, opponent|
  mult = 1.0
  mult *= (1.0 / 3.0) if move.contactMove?
  mult *= 2.0 if move.pbType(attacker) == :DARK
  mult
}
