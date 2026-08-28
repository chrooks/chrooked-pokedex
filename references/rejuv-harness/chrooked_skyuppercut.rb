# chrooked:skyuppercut
# Sky Uppercut (move) — "Super effective against Flying-types."
#   damage-calc: for each Flying type on the target, replace the chart matchup
#   with 2x (Fighting vs Flying is normally 0.5x => corrected to 2x)
# The other type slot is untouched, so Ghost/Flying keeps its Ghost immunity
# (0x * anything = 0x). The canon airborne-hit perk (funccode 0x11B +
# AIRHITMOVES) is engine data and is not touched here.
# Test cases:
#   - Sky Uppercut vs a pure Flying => super effective message, 2x component
#   - vs Normal/Flying (Pidgeot) => 4x (2x Normal * 2x corrected Flying)
#   - vs Ghost/Flying (Drifblim) => no effect (Ghost immunity retained)
#   - vs non-Flying => normal Fighting matchup
CHROOKED_MOVE_TYPEMOD[:SKYUPPERCUT] = lambda { |move, atype, attacker, opponent, typemod|
  opponent.types.each do |opptype|
    next unless opptype == :FLYING
    chart = PBTypes.oneTypeEff(atype, :FLYING)
    next if chart.immune?
    # multiply by (2 / chart) so the Flying component lands at exactly 2x
    typemod *= Typemod.new(2 * chart.denominator, chart.numerator)
  end
  typemod
}
