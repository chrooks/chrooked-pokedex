# chrooked:mountaineer
# Mountaineer — "Immune to Rock moves; takes no damage from them."
#   damage-calc: incoming Rock move => blocked (Soundproof-style, no stat change)
# Test cases:
#   - Stealth Rock damage unaffected (entry hazards are not moves)
#   - any Rock move => "It doesn't affect..." and zero damage
CHROOKED_TYPE_IMMUNITY[:MOUNTAINEER] = { type: :ROCK, flag: :Soundproof }
