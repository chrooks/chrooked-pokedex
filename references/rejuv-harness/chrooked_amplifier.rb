# chrooked:amplifier
# Amplifier — sound moves deal 30% more damage and hit all adjacent foes.
#   damage-calc: sound move => x1.3
#   damage-calc: single-target sound move => targets all opposing battlers
# Test cases:
#   - Hyper Voice in a double battle => hits both foes, 1.3x each
#   - non-sound move => single target, no boost
CHROOKED_DAMAGE_MODS[:AMPLIFIER] = lambda { |move, attacker, opponent|
  move.isSoundBased? ? 1.3 : 1.0
}
CHROOKED_TARGET_MODS[:AMPLIFIER] = lambda { |move, battler, target_kind|
  move.isSoundBased? && target_kind == :SingleNonUser ? :AllOpposing : nil
}
