# chrooked:singingsands
# Singing Sands — NORMAL-type sound moves become Ground-type with a 1.2x rider
#   (the -ate/-ize shape, gated on the sound flag); the holder is immune to
#   Ground-type moves (Soundproof-style block, Mold Breaker respected).
#   Conversion rides the core's pbType hook (STAB then applies naturally for
#   Ground-types); non-Normal sound moves are untouched.
# Test cases:
#   - Hyper Voice => Ground-type, 1.2x (plus STAB if the user is Ground)
#   - Bug Buzz => stays Bug, no rider
#   - incoming Earthquake => "It doesn't affect..." and zero damage
CHROOKED_TYPE_IMMUNITY[:SINGINGSANDS] = { type: :GROUND, flag: :Soundproof }
CHROOKED_TYPE_MODS[:SINGINGSANDS] = lambda { |move, type|
  move.hasFlag?(:soundmove) && type == :NORMAL ? :GROUND : nil
}
CHROOKED_DAMAGE_MODS[:SINGINGSANDS] = lambda { |move, attacker, opponent|
  Chrooked.type_changed?(move, attacker) ? 1.2 : 1.0
}
