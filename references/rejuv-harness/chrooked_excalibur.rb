# chrooked:excalibur
# Excalibur (move) — "Always counts as super effective against Dragon-types."
#   damage-calc: for each Dragon type on the target, replace the chart matchup
#   with 2x (Steel vs Dragon is normally 0.5x => corrected to 2x)
# Test cases:
#   - Excalibur vs a Dragon => super effective message, 2x component
#   - vs non-Dragon => normal Steel matchup
CHROOKED_MOVE_TYPEMOD[:EXCALIBUR] = lambda { |move, atype, attacker, opponent, typemod|
  opponent.types.each do |opptype|
    next unless opptype == :DRAGON
    chart = PBTypes.oneTypeEff(atype, :DRAGON)
    next if chart.immune?
    # multiply by (2 / chart) so the Dragon component lands at exactly 2x
    typemod *= Typemod.new(2 * chart.denominator, chart.numerator)
  end
  typemod
}
