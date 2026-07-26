# chrooked:sinkhole
# Sinkhole (move mechanic) — the >110 Ground special nuke. Its data layer is a
# plain 0x000 damage funccode; this behavior IS the entire >110 self-drawback,
# because no vanilla Rejuv funccode lowers Sp. Atk and Speed together (the
# closest are Draco Meteor's SpA-only 0x03F and Hammer Arm's Speed-only 0x03E).
#   on-deal: after Sinkhole damages, the caster sinks — Sp. Atk -1 and Speed -1.
# Test cases:
#   - Sinkhole deals damage, both stats above -6 => user Sp. Atk -1 and Speed -1
#   - user Speed already at -6 => Speed holds; Sp. Atk still falls one stage
#   - a different move => unaffected (gated to :SINKHOLE only)
CHROOKED_MOVE_ON_DEAL[:SINKHOLE] = lambda { |move, user, target, battle|
  [PBStats::SPATK, PBStats::SPEED].each do |stat|
    next unless user.pbCanReduceAnyStat?([stat], user, nil)
    user.pbChangeStats(stat, -1, user, nil)
  end
}
