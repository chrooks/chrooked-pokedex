# chrooked:sheercold
# Sheer Cold (move) — "Always counts as super effective against Water-types."
#   damage-calc: for each Water type on the target, replace the chart matchup
#   with 2x (Ice vs Water is normally 0.5x => corrected to 2x)
# No longer an OHKO: the data layer moves :function from 0x070 to 0x00C, which
# drops the level gate, the Ice-type immunity, the Sturdy block, and the
# 20-accuracy penalty along with it.
#
# Rejuv hardcodes this same doubling for Freeze-Dry at Battle_Move.rb ~542, but
# that check is keyed on the move symbol, so a second move cannot reuse it.
# Test cases:
#   - Sheer Cold vs a Water type => super effective, 2x component
#   - vs Water/Ground => 4x overall (Water corrected to 2x, Ground already 2x)
#   - vs non-Water => normal Ice matchup
CHROOKED_MOVE_TYPEMOD[:SHEERCOLD] = lambda { |move, atype, attacker, opponent, typemod|
  opponent.types.each do |opptype|
    next unless opptype == :WATER
    chart = PBTypes.oneTypeEff(atype, :WATER)
    next if chart.immune?
    # multiply by (2 / chart) so the Water component lands at exactly 2x
    typemod *= Typemod.new(2 * chart.denominator, chart.numerator)
  end
  typemod
}
