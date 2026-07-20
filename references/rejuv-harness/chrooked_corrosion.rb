# chrooked:corrosion
# Corrosion — DIVERGES FROM VANILLA.
#   Vanilla clause (poison status ignores Steel/Poison immunity) is NATIVE in
#   Rejuv and is deliberately left untouched — no code here for it.
#   Added clause, damage-calc: the bearer's Poison-type moves are super
#   effective (2x) against Steel instead of having no effect (0x).
#
#   Poison-vs-Steel is 0x on the chart, and Typemod multiplication cannot scale
#   away from zero (0 * anything == 0), so the multiply-by-(2/chart) trick used
#   by chrooked_excalibur.rb / chrooked_gastricsnare.rb does not work here.
#   Instead this rebuilds the Typemod slot by slot, substituting 2x for Steel
#   and taking the real chart value for every other slot. Hence the ability-keyed
#   CHROOKED_ABILITY_TYPEMOD table rather than CHROOKED_MOVE_TYPEMOD.
#
#   Applies to the BEARER only — the global type chart is untouched, so a Poison
#   move from any other Pokemon still reads 0x vs Steel.
# Test cases:
#   - Corrosion + Gunk Shot vs Registeel (pure Steel) => 2x (vanilla 0x)
#   - Corrosion + Poison Jab vs Steelix (Steel/Ground) => Steel 2x, Ground 0.5x => 1x
#   - Corrosion + Gastric Snare vs Scizor (Bug/Steel) => Bug 2x, Steel 2x => 4x
#   - Corrosion + Razor Leaf (Grass) vs Registeel => untouched, 0.5x
#   - no Corrosion + Poison Jab vs Registeel => 0x, still immune
CHROOKED_ABILITY_TYPEMOD[:CORROSION] = lambda { |move, atype, attacker, opponent, typemod|
  next typemod unless atype == :POISON
  next typemod unless opponent.types.include?(:STEEL)
  rebuilt = Typemod.new(1, 1)
  opponent.types.each do |opptype|
    rebuilt *= opptype == :STEEL ? Typemod.new(2, 1) : PBTypes.oneTypeEff(atype, opptype)
  end
  rebuilt
}
