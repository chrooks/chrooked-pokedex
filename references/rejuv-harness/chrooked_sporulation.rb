# chrooked:sporulation
# Sporulation — "On entry it readies a burst of spores. Its next Spore goes first."
#   Mirrors chrooked_coilup.rb: armed on switch-in, +1 priority read via
#   CHROOKED_PRIORITY_MODS, consumed after the move. Spore deals no damage, so
#   the burst is spent in CHROOKED_AFTER_MOVE rather than Coil Up's on-deal seam.
#   pbInitEffects wipes the flag on switch-out; re-entry re-arms it.
# Test cases (drive in-game — the harness can't prove battle behavior):
#   - switch in, Spore vs a faster foe => Spore goes first; next turn normal
#   - Sleep Powder while armed         => normal priority, flag stays armed
#   - switch out and in                => armed again
CHROOKED_SWITCH_IN[:SPORULATION] = lambda { |battler, battle|
  battler.effects[:ChrookedSporulation] = true
}
CHROOKED_PRIORITY_MODS[:SPORULATION] = lambda { |move, attacker|
  attacker.effects[:ChrookedSporulation] && move.move == :SPORE ? 1 : 0
}
CHROOKED_AFTER_MOVE[:SPORULATION] = lambda { |battler, move_symbol, battle|
  next unless move_symbol == :SPORE && battler.effects[:ChrookedSporulation]
  battler.effects[:ChrookedSporulation] = nil
  Chrooked.log("SPORULATION #{battler.pbThis} spent its burst")
}
