# chrooked:thermalexchange
# Thermal Exchange — "Immune to Fire moves; takes no damage from them."
#   damage-calc: incoming Fire move => blocked (ability box + no effect)
#   Burn immunity is vanilla and stays untouched.
# Test cases:
#   - any Fire move => "It doesn't affect..." and zero damage
#   - Will-O-Wisp => burn blocked (vanilla behavior, unchanged)
CHROOKED_TYPE_IMMUNITY[:THERMALEXCHANGE] = { type: :FIRE, flag: :Soundproof }
