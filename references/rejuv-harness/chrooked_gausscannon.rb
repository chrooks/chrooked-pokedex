# chrooked:gausscannon
# Gauss Cannon (move) — "Super effective against Steel-types."
#   damage-calc: for each Steel type on the target, replace the chart matchup
#   with 2x (Electric vs Steel is normally 1x => corrected to 2x)
# The other type slot is untouched, so Steel/Ground keeps its Ground immunity
# (2x * 0x = 0x) — Ground stays the counterplay to the Magnet Pull trap.
# Test cases:
#   - Gauss Cannon vs a pure Steel => super effective message, 2x component
#   - vs Steel/Ground (Steelix) => no effect (Ground immunity retained)
#   - vs non-Steel => normal Electric matchup
CHROOKED_MOVE_TYPEMOD[:GAUSSCANNON] = lambda { |move, atype, attacker, opponent, typemod|
  opponent.types.each do |opptype|
    next unless opptype == :STEEL
    chart = PBTypes.oneTypeEff(atype, :STEEL)
    next if chart.immune?
    # multiply by (2 / chart) so the Steel component lands at exactly 2x
    typemod *= Typemod.new(2 * chart.denominator, chart.numerator)
  end
  typemod
}
