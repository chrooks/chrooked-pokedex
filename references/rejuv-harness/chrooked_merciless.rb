# chrooked:merciless
# Merciless — "Always criticals foes that are poisoned, paralyzed, or slowed."
#   crit-calc: target poisoned / paralyzed / at negative Speed stage => guaranteed crit
#   Vanilla Rejuv already forces the crit on poison; this widens it to paralysis
#   and to a Speed drop. No bleed clause — Rejuv has no bleed status.
# Test cases:
#   - Merciless mon attacks a badly poisoned target => guaranteed crit (unchanged)
#   - Merciless mon attacks a paralyzed target => guaranteed crit
#   - Merciless mon attacks a -1 Speed target with no status => guaranteed crit
#   - Merciless mon attacks a burned target at +1 Speed => normal crit roll
#   - Merciless mon attacks a poisoned Shell Armor target => no crit
CHROOKED_CRIT_RATE[:MERCILESS] = lambda { |move, attacker, opponent|
  Chrooked.impaired_target?(opponent)
}
