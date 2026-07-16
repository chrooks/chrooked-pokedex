# chrooked:overcharge
# Overcharge — "While at low HP, Electric-type moves deal 50% more damage."
#   damage-calc: move type Electric AND user HP <= 1/3 max => x1.5
# Test cases:
#   - Overcharge mon at 1/3 HP or less uses Thunderbolt => 1.5x
#   - full-HP Thunderbolt => no boost ; low-HP Tackle => no boost
CHROOKED_DAMAGE_MODS[:OVERCHARGE] = lambda { |move, attacker, opponent|
  move.pbType(attacker) == :ELECTRIC && attacker.hp * 3 <= attacker.totalhp ? 1.5 : 1.0
}
