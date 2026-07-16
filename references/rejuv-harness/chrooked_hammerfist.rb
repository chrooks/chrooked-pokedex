# chrooked:hammerfist
# Hammerfist — "Punch, hammer, and slam moves deal 30% more damage."
#   damage-calc: punching move OR hammer/slam move => x1.3
# Test cases:
#   - Mach Punch => 1.3x ; Hammer Arm => 1.3x ; Body Slam => 1.3x
#   - Tackle => no boost
CHROOKED_DAMAGE_MODS[:HAMMERFIST] = lambda { |move, attacker, opponent|
  move.punchMove? || Chrooked.hammer_move?(move) ? 1.3 : 1.0
}
