# chrooked:sacredtoll
# Sacred Toll — "Sound moves become Psychic-type and gain a 20% damage boost."
#   damage-calc: any sound-flagged move => type becomes PSYCHIC, damage x1.2
# Test cases:
#   - Hyper Voice => hits as Psychic with 1.2x power
#   - non-sound move => untouched
CHROOKED_TYPE_MODS[:SACREDTOLL] = lambda { |move, type|
  move.isSoundBased? ? :PSYCHIC : nil
}
CHROOKED_DAMAGE_MODS[:SACREDTOLL] = lambda { |move, attacker, opponent|
  Chrooked.type_changed?(move, attacker) ? 1.2 : 1.0
}
