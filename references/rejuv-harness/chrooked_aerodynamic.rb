# chrooked:aerodynamic
# Aerodynamic — "Immune to Flying moves; takes no damage from them."
#   damage-calc: incoming Flying move => blocked (ability box + no effect)
# Test cases:
#   - any Flying move => "It doesn't affect..." and zero damage
CHROOKED_TYPE_IMMUNITY[:AERODYNAMIC] = { type: :FLYING, flag: :Soundproof }
