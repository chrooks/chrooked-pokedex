# chrooked:flytrap
# Flytrap — "Immune to Bug moves; takes no damage from them."
#   damage-calc: incoming Bug move => blocked (ability box + no effect)
# Test cases:
#   - any Bug move => "It doesn't affect..." and zero damage
CHROOKED_TYPE_IMMUNITY[:FLYTRAP] = { type: :BUG, flag: :Soundproof }
