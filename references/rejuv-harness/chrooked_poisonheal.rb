# chrooked:poisonheal
# Poison Heal — "Heals when poisoned instead of taking damage. Immune to Poison-type moves."
#   damage-calc: incoming Poison move => blocked (Soundproof-style); heal clause is native Rejuv
# Test cases:
#   - Toxic Orb still poisons and heals 1/8 per turn (item, not a move)
#   - any Poison move => "It doesn't affect..." and zero damage
CHROOKED_TYPE_IMMUNITY[:POISONHEAL] = { type: :POISON, flag: :Soundproof }
