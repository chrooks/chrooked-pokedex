# chrooked:magicalfists
# Magical Fists — punching moves +30% damage; physical punches use Sp. Atk.
#   damage-calc: punching move => x1.3
#   damage-calc: physical punching move => attack stat swapped for Sp. Atk
# Test cases:
#   - physical punch from a high-SpA mon => damage computed off Sp. Atk, x1.3
#   - non-punch move => untouched
CHROOKED_DAMAGE_MODS[:MAGICALFISTS] = lambda { |move, attacker, opponent|
  move.punchMove? ? 1.3 : 1.0
}
CHROOKED_STAT_SWAP[:MAGICALFISTS] = lambda { |move, attacker|
  move.punchMove? && move.pbIsPhysical?(attacker, move.pbType(attacker))
}
