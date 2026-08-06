# chrooked:immunity
# Immunity — "Cannot be poisoned. Immune to Poison-type moves."
#   damage-calc: incoming Poison move => blocked (Soundproof-style); status clause is native Rejuv
# Test cases:
#   - Toxic Spikes still fails to poison (native clause; hazards are not moves)
#   - any Poison move => "It doesn't affect..." and zero damage
CHROOKED_TYPE_IMMUNITY[:IMMUNITY] = { type: :POISON, flag: :Soundproof }
