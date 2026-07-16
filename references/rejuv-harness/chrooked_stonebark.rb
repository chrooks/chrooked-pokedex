# chrooked:stonebark
# Stonebark — absorbs Grass moves (heals 1/4 max HP); takes 25% more from Water.
#   damage-calc: incoming Grass move => absorbed, heal 1/4 (HpAbsorb flag)
#   damage-calc: incoming Water move => x1.25
# Test cases:
#   - Grass move => no damage, heals 1/4
#   - Water move => 1.25x damage taken
CHROOKED_TYPE_IMMUNITY[:STONEBARK] = { type: :GRASS, flag: :HpAbsorbAbility }
CHROOKED_DEFENSE_MODS[:STONEBARK] = lambda { |move, attacker, opponent|
  move.pbType(attacker) == :WATER ? 1.25 : 1.0
}
