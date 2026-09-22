# chrooked:scaldingpulse
# Scalding Pulse — "Pulse moves gain a 30% chance to burn."
#   status-apply: a damaging pulse move that deals damage => 30% burn
# Modeled on Infernal Maw's biting-move burn rider; the pbCanBurn? gate keeps
# Fire types, already-statused targets and Substitute hits safe.
# Test cases (drive in-game):
#   - Dragon Pulse => may burn (30%)
#   - Flame Burst (pulse) => may burn on top of its own effect
#   - Waterfall (not a pulse) => never burns
#   - a Fire-type target => never burns
CHROOKED_ON_DEAL[:SCALDINGPULSE] = lambda { |move, user, target, battle|
  next unless move.respond_to?(:pulseMove?) && move.pulseMove?
  next unless target.pbCanBurn?(user, move) && battle.pbRandom(100) < 30
  battle.pbShowAbilityBox(user)
  target.pbBurn(user)
  battle.pbHideAbilityBox(user)
}
