# chrooked:glittertap
# Glitter Tap (move mechanic) — a damaging Fairy move that may infatuate. The move
# data layer can't express infatuation as an additional effect, so this adds it.
#   on-hit: Glitter Tap connects => 10% chance to infatuate the target
# Test cases:
#   - hit on an opposite-gender target, roll succeeds => target falls in love
#   - roll fails => damage only, no message
#   - same-gender/genderless/Oblivious/Aroma Veil target => damage only, silent
#   - other moves => unaffected
CHROOKED_MOVE_ON_DEAL[:GLITTERTAP] = lambda { |move, user, target, battle|
  next if target.isFainted? || battle.pbRandom(100) >= 10
  # showMessage stays false: a secondary effect that misses its gate should be
  # silent, not print "But it failed!" over the damage message.
  next unless target.pbCanAttract?(user, move)
  target.pbAttract(user)
}
