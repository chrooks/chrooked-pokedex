# chrooked:bonebreaker
# Bonebreaker — bone moves ignore type immunities and deal 20% more damage.
#   damage-calc: immune matchup (0x) with a bone move => neutral (1x);
#   also re-opens Levitate/air-balloon/absorb-ability blocks
#   damage-calc: bone move => x1.2
#   Rejuv has no bone flag; keyed by move symbol.
# Test cases:
#   - Bonemerang vs Flying/Levitate => connects at neutral
#   - Bone Club => 1.2x damage
BONEBREAKER_BONE_MOVES = [:BONECLUB, :BONEMERANG, :BONERUSH, :SHADOWBONE].freeze
CHROOKED_TYPEMOD_FLOOR[:BONEBREAKER] = lambda { |move, attacker|
  BONEBREAKER_BONE_MOVES.include?(move.move)
}
CHROOKED_IMMUNITY_BYPASS[:BONEBREAKER] = lambda { |move, attacker|
  BONEBREAKER_BONE_MOVES.include?(move.move)
}
CHROOKED_DAMAGE_MODS[:BONEBREAKER] = lambda { |move, attacker, opponent|
  BONEBREAKER_BONE_MOVES.include?(move.move) ? 1.2 : 1.0
}
