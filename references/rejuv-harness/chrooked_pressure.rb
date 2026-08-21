# chrooked:pressure
# Pressure — "Doubles the PP that foes' moves cost. On entry, erases every foe's stat boosts."
#   switch-in: Haze the foes' positive stages only (drops survive)
# The PP half is vanilla (Battler.rb applyPressure ~5915) — untouched here.
# A clear, not a stat drop: Clear Body / Mist / White Smoke do not block it, so this
# writes `stages` directly instead of going through pbChangeStats (Haze does the same
# at Battle_MoveEffects.rb ~8111). Rejuv's Dimensional-field Pressure rider
# (Battler.rb ~2292) is a separate effect and still fires on those fields.
# Test cases:
#   - foe at +2 Atk / -1 Spe => +0 Atk, still -1 Spe
#   - two boosted foes in doubles => both cleared
#   - no foe has a boost => no message, no crash
CHROOKED_SWITCH_IN[:PRESSURE] = lambda { |battler, battle|
  cleared = false
  [battler.pbOpposing1, battler.pbOpposing2].each do |foe|
    next if !foe || foe.isFainted?
    PBStats::All.each do |stat|
      next if foe.stages[stat] <= 0
      foe.stages[stat] = 0
      cleared = true
    end
  end
  next unless cleared
  battle.pbAbilityBoxAndDisplay(battler, _INTL("{1}'s pressure crushed the stat boosts around it!", battler.pbThis))
}
