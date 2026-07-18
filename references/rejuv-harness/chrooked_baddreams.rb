# chrooked:baddreams
# Bad Dreams — the end-of-turn sleep damage is NATIVE in Rejuv (Battle.rb).
#   This file adds only the chrooked extension: a Bad Dreams user's Hypnosis
#   lands 1.2x more accurately.
#   accuracy-check: Hypnosis from a Bad Dreams user gets x1.2 final accuracy
# Test cases:
#   - Hypnosis (60 acc) from a Bad Dreams user rolls at 72
#   - other moves keep normal accuracy
CHROOKED_ACCURACY_MODS[:BADDREAMS] = lambda { |move, attacker, opponent|
  move.move == :HYPNOSIS ? 1.2 : 1.0
}
