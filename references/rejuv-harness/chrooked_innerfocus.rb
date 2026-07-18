# chrooked:innerfocus
# Inner Focus — flinch immunity is NATIVE in Rejuv (Battler.rb checks
#   ability != :INNERFOCUS before applying Flinch). This file adds only the
#   chrooked extension: the user's Focus Blast never misses.
#   accuracy-check: Focus Blast from an Inner Focus user skips the roll
# Test cases:
#   - Focus Blast (70% acc) never misses
#   - other moves keep normal accuracy
CHROOKED_SURE_HIT[:INNERFOCUS] = lambda { |move, attacker|
  move.move == :FOCUSBLAST
}
