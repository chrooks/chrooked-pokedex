# chrooked:forestry
# Forestry — "All attacks deal 30% more damage while Grassy Terrain is up."
#   damage-calc: Grassy field active AND user grounded => x1.3
#   (Rejuv models Grassy Terrain as the GRASSY field effect / overlay.)
# Test cases:
#   - Grassy field up, grounded Forestry mon attacks => 1.3x
#   - no Grassy field => no boost
#   - airborne user (Flying/Levitate) => no boost
CHROOKED_DAMAGE_MODS[:FORESTRY] = lambda { |move, attacker, opponent|
  grassy = move.battle.FE == :GRASSY || move.battle.OV == :GRASSY
  grassy && !attacker.isAirborne? ? 1.3 : 1.0
}
