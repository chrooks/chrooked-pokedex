# chrooked:deeprooted
# Deep Rooted — "Increases HP recovered from draining effects by 30%."
#   damage-calc: drain/absorb heals (Giga Drain, Leech Seed, etc.) => x1.3
# Test cases:
#   - Giga Drain heal => 1.3x the normal drain amount
#   - direct heals (Recover) => unchanged (not an absorb)
CHROOKED_ABSORB_MODS[:DEEPROOTED] = lambda { |battler, hpgain, agent|
  [(hpgain * 1.3).floor, 1].max
}
