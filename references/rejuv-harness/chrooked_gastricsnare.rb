# chrooked:gastricsnare
# Gastric Snare (move) — "Always counts as super effective against Bug-types."
#   damage-calc: for each Bug type on the target, replace the chart matchup
#   with 2x (Poison vs Bug is normally 1x in modern gens => corrected to 2x).
#   A Gen 1 callback — Poison WAS super effective on Bug in RBY.
#   Steel is NOT handled here; Poison-vs-Steel belongs to the Corrosion ability.
#   Same shape as chrooked_excalibur.rb (always-SE-vs-Dragon).
# Test cases:
#   - Gastric Snare vs Caterpie (pure Bug) => 2x, super effective message
#   - vs Scyther (Bug/Flying) => Bug 2x, Flying 1x => 2x
#   - vs Kangaskhan (non-Bug) => untouched, normal Poison matchup
#   - from a Corrosion holder vs Scizor (Bug/Steel) => Bug 2x here,
#     Steel 2x from chrooked_corrosion.rb => 4x
CHROOKED_MOVE_TYPEMOD[:GASTRICSNARE] = lambda { |move, atype, attacker, opponent, typemod|
  opponent.types.each do |opptype|
    next unless opptype == :BUG
    chart = PBTypes.oneTypeEff(atype, :BUG)
    # ponytail: a 0x Bug component can't be scaled by multiplication — skip it.
    # Nothing in the base chart makes Poison-vs-Bug immune, so this is a guard,
    # not a live path (mirrors excalibur's identical guard).
    next if chart.immune?
    # multiply by (2 / chart) so the Bug component lands at exactly 2x
    typemod *= Typemod.new(2 * chart.denominator, chart.numerator)
  end
  typemod
}
