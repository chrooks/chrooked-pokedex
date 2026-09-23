# chrooked:barrage
# Barrage — "Pulse moves never miss and hit all adjacent foes."
#   accuracy: a pulse move skips the accuracy roll entirely
#   targeting: a single-target pulse move becomes :AllOpposing
# Both halves use existing core seams — CHROOKED_SURE_HIT and
# CHROOKED_TARGET_MODS — the same pair Amplifier uses for sound moves.
# Test cases (drive in-game):
#   - Water Pulse in a double battle => hits both foes, cannot miss
#   - Hydro Pump (not a pulse) => normal accuracy, single target
#   - a pulse move into a dodge/evasion boost => still hits
CHROOKED_SURE_HIT[:BARRAGE] = lambda { |move, attacker|
  move.respond_to?(:pulseMove?) && move.pulseMove?
}
CHROOKED_TARGET_MODS[:BARRAGE] = lambda { |move, battler, target_kind|
  next nil unless move.respond_to?(:pulseMove?) && move.pulseMove?
  target_kind == :SingleNonUser ? :AllOpposing : nil
}
