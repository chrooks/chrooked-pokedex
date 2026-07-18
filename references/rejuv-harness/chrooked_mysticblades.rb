# chrooked:mysticblades
# Mystic Blades — slicing moves +30% damage; physical slices use Sp. Atk.
#   damage-calc: slicing move => x1.3
#   damage-calc: physical slicing move => attack stat swapped for Sp. Atk
# Test cases:
#   - physical slicing move from a high-SpA mon => damage off Sp. Atk, x1.3
#   - non-slicing move => untouched
CHROOKED_DAMAGE_MODS[:MYSTICBLADES] = lambda { |move, attacker, opponent|
  move.sharpMove? ? 1.3 : 1.0
}
CHROOKED_STAT_SWAP[:MYSTICBLADES] = lambda { |move, attacker|
  move.sharpMove? && move.pbIsPhysical?(attacker, move.pbType(attacker))
}
