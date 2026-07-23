# chrooked:electroweb
# Electroweb (move mechanic) — base function 0x044 carries the 100% Speed drop
# natively; this adds the chrooked buff's 50% paralysis rider on hit.
#   on-hit: Electroweb connects => 50% chance to paralyze the target
# Test cases:
#   - Electroweb hits a paralyzable foe (roll succeeds) => target paralyzed
#   - hits an Electric-type / already-statused foe => pbCanParalyze? blocks it, no crash
#   - roll fails => Speed still drops (native), no paralysis
CHROOKED_MOVE_ON_DEAL[:ELECTROWEB] = lambda { |move, user, target, battle|
  next if target.isFainted? || battle.pbRandom(100) >= 50
  next unless target.pbCanParalyze?(user, move)
  target.pbParalyze(user)
}
