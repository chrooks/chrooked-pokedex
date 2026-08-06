# chrooked:illusion
# Illusion — vanilla disguise (native Rejuv: effects[:Illusion] holds the fake
#   battler, breakIllusion nils it on direct damage), plus a fork rider:
#   damage-calc: while the disguise is up and unbroken => outgoing damage x1.2
# The core's AI pbRoughDamage wrapper picks the rider up automatically.
# Test cases:
#   - disguised attacker => 1.2x on its moves
#   - after being hit by a damaging move => boost gone (effects[:Illusion] is nil)
#   - last mon in party (no disguise formed) => no boost
CHROOKED_DAMAGE_MODS[:ILLUSION] = lambda { |move, attacker, opponent|
  attacker.effects[:Illusion] ? 1.2 : 1.0
}
