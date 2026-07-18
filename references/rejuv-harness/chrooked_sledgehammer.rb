# chrooked:sledgehammer
# Sledgehammer — "Hammer and slam moves deal 30% more damage."
#   damage-calc: hammer/slam move used by this Pokemon => damage x1.3
# Test cases:
#   - Hammer Arm / Wood Hammer from a Sledgehammer mon => 1.3x damage
#   - Slam / Body Slam => 1.3x damage
#   - Mach Punch (punch, not hammer) => no boost
CHROOKED_DAMAGE_MODS[:SLEDGEHAMMER] = lambda { |move, attacker, opponent|
  Chrooked.hammer_move?(move) ? 1.3 : 1.0
}
