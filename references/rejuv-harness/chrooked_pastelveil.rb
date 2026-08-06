# chrooked:pastelveil
# Pastel Veil — "Protects the team from poisoning. Immune to Poison-type moves."
#   damage-calc: incoming Poison move at the HOLDER => blocked (Soundproof-style)
#   allies keep only the native status protection; the table is keyed on the defender's ability
# Test cases:
#   - ally hit by Sludge Bomb takes damage normally
#   - any Poison move at the holder => "It doesn't affect..." and zero damage
CHROOKED_TYPE_IMMUNITY[:PASTELVEIL] = { type: :POISON, flag: :Soundproof }
