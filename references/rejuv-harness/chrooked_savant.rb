# chrooked:savant
# Savant — "The first use of each move is boosted."
#   damage-calc: move not yet used since this switch-in => x1.3
#   after-move: record the move as used (AFTER_MOVE fires once per pbUseMove,
#     after damage, so every hit of a multi-hit first use is boosted)
#   switch-in: the used set resets (pbInitEffects rebuilds @effects on entry;
#     CHROOKED_SWITCH_IN makes the reset explicit)
# Test cases:
#   - Psychic, first use   => 1.3x ; Psychic again => 1.0x
#   - Psychic then Shadow Ball => Shadow Ball also 1.3x (per move, not per battle turn)
#   - switch out and back in, Psychic => 1.3x again
#   - Rock Blast first use => every hit 1.3x
CHROOKED_SWITCH_IN[:SAVANT] = lambda { |battler, battle|
  battler.effects[:ChrookedSavantUsed] = []
}
CHROOKED_DAMAGE_MODS[:SAVANT] = lambda { |move, attacker, opponent|
  used = attacker.effects[:ChrookedSavantUsed] || []
  used.include?(move.move) ? 1.0 : 1.3
}
CHROOKED_AFTER_MOVE[:SAVANT] = lambda { |battler, move_symbol, battle|
  battler.effects[:ChrookedSavantUsed] = (battler.effects[:ChrookedSavantUsed] || []) + [move_symbol]
}
