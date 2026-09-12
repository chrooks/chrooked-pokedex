# chrooked:timberfall
# Timberfall (move) — "Always counts as super effective against Grass-types."
#   damage-calc: for each Grass type on the target, replace the chart matchup
#   with 2x (Rock vs Grass is normally 1x => corrected to 2x)
# The user's Def/Sp.Def drop is NATIVE (funccode 0x03C, the Close Combat class)
# and is deliberately not implemented here.
# Test cases:
#   - Timberfall vs a Grass => super effective message, 2x component
#   - vs Grass/Flying => forced 2x on the Grass half, chart 2x on the Flying half
#   - vs non-Grass => normal Rock matchup
CHROOKED_MOVE_TYPEMOD[:TIMBERFALL] = lambda { |move, atype, attacker, opponent, typemod|
  opponent.types.each do |opptype|
    next unless opptype == :GRASS
    chart = PBTypes.oneTypeEff(atype, :GRASS)
    next if chart.immune?
    # multiply by (2 / chart) so the Grass component lands at exactly 2x
    typemod *= Typemod.new(2 * chart.denominator, chart.numerator)
  end
  typemod
}
