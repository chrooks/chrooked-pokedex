# chrooked:singingsands
# Singing Sands — sound moves become Ground-type with a 1.2x rider; the holder
#   is immune to Ground-type moves (Soundproof-style block, Mold Breaker respected).
#   Conversion rides the core's pbType hook (STAB then applies naturally for
#   Ground-types); already-Ground sound moves keep their type and still get 1.2x.
# Test cases:
#   - Hyper Voice => Ground-type, 1.2x (plus STAB if the user is Ground)
#   - incoming Earthquake => "It doesn't affect..." and zero damage
#   - Boomburst vs pure Rock => neutral Ground damage with the 1.2x
CHROOKED_TYPE_IMMUNITY[:SINGINGSANDS] = { type: :GROUND, flag: :Soundproof }
CHROOKED_TYPE_MODS[:SINGINGSANDS] = lambda { |move, type|
  move.hasFlag?(:soundmove) && type != :GROUND ? :GROUND : nil
}
CHROOKED_DAMAGE_MODS[:SINGINGSANDS] = lambda { |move, attacker, opponent|
  move.hasFlag?(:soundmove) ? 1.2 : 1.0
}
