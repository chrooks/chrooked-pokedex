# chrooked:permafrost
# Permafrost — "Super-effective hits against this Pokemon are reduced to 65% damage."
#   damage-calc (defender): incoming move is super-effective => x0.65
#   typemod is set by the vanilla calc before our wrapper reads it.
# Test cases:
#   - Fire move vs Permafrost Ice mon => 0.65x of normal SE damage
#   - neutral or resisted hit => unchanged
CHROOKED_DEFENSE_MODS[:PERMAFROST] = lambda { |move, attacker, opponent|
  opponent.damagestate.typemod.superEffective? ? 0.65 : 1.0
}
