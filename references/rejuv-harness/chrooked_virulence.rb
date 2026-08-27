# chrooked:virulence
# Virulence — "Always criticals foes that are poisoned, paralyzed, or slowed.
#              Poison-type moves are boosted by 50%."
#   crit-calc:   same impaired-target test as Merciless
#   damage-calc: attacker's move type is Poison => x1.5 (Kindle's shape, Poison)
#   The two clauses are independent; neither gates the other.
# Test cases:
#   - Virulence mon uses Crunch on a paralyzed target => guaranteed crit, no boost
#   - Virulence mon uses Poison Fang on a healthy target => 1.5x, normal crit roll
#   - Virulence mon uses Cross Poison on a poisoned target => 1.5x AND guaranteed crit
#   - Virulence mon uses Sludge Bomb while not Poison-typed => 1.5x still applies
CHROOKED_CRIT_RATE[:VIRULENCE] = lambda { |move, attacker, opponent|
  Chrooked.impaired_target?(opponent)
}
CHROOKED_DAMAGE_MODS[:VIRULENCE] = lambda { |move, attacker, opponent|
  move.pbType(attacker) == :POISON ? 1.5 : 1.0
}
