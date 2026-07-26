# chrooked:quarterdrain
# Quarter Drain (move mechanic) — Reap and Siphon are 100 BP Grass drain moves
# that recover only a QUARTER of the damage dealt, not the standard half. They
# ship on the vanilla drain funccode (0x0DD, which heals 50%); this halves that
# heal. The drain funccode passes the move object to absorbHP, so the core's
# move-keyed CHROOKED_MOVE_ABSORB_MODS multiplier fires here.
# Test cases:
#   - Reap deals 100 damage => user recovers 25 (not 50)
#   - Siphon deals 40 damage => user recovers 10
#   - a normal drain move (Giga Drain) => unchanged 50% (gated to these ids)
QUARTERDRAIN_MOVES = [:REAP, :SIPHON].freeze
QUARTERDRAIN_MOVES.each do |mv|
  CHROOKED_MOVE_ABSORB_MODS[mv] = 0.5
end
