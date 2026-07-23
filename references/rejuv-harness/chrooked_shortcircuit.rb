# chrooked:shortcircuit
# Short Circuit (move) — Electric Venoshock: damage doubles when the target is
#   paralyzed (mirrors Venoshock's x2-on-Poison, mapped to the Electric type and
#   paralysis). The move data (70 BP Electric special) is a plain Definitions
#   Override; this file is the conditional x2 the funccode can't express.
#   damage-calc: target.status == :PARALYSIS => x2
# ponytail: applied as x2 on final damage (the core's only damage seam), not
#   literally on base power — differs from a true base-power double only by the
#   formula's flat +2 and one rounding step, immaterial in play. Promote to a
#   base-power hook only if a later move needs exact base-power semantics.
# Test cases:
#   - Short Circuit vs a paralyzed foe => x2 damage
#   - vs a burned / poisoned / statusless foe => x1, no bonus
#   - vs a Ground-type (Electric immune) => still no damage; multiplier irrelevant
CHROOKED_MOVE_DAMAGE_MODS[:SHORTCIRCUIT] = lambda { |move, attacker, opponent|
  opponent && opponent.status == :PARALYSIS ? 2.0 : 1.0
}
