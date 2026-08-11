# chrooked:arcticariette
# Arctic Ariette — NORMAL-type sound moves become Ice-type with a 1.3x rider
#   (the -ate/-ize shape gated on the sound flag, same as Singing Sands).
#   Conversion rides the core's pbType hook, so STAB applies naturally for
#   Ice-types; non-Normal sound moves are untouched. No defensive half.
# Test cases:
#   - Hyper Voice => Ice-type, 1.3x (plus STAB if the user is Ice)
#   - Bug Buzz => stays Bug, no rider
#   - Body Slam => stays Normal (no sound flag)
CHROOKED_TYPE_MODS[:ARCTICARIETTE] = lambda { |move, type|
  move.hasFlag?(:soundmove) && type == :NORMAL ? :ICE : nil
}
CHROOKED_DAMAGE_MODS[:ARCTICARIETTE] = lambda { |move, attacker, opponent|
  Chrooked.type_changed?(move, attacker) ? 1.3 : 1.0
}
