# chrooked:waterveil
# Water Veil — "Prevents burns. On entry, surrounds the Pokemon with Aqua Ring."
#   switch-in: set Aqua Ring on the holder, exactly as the move does.
# The burn half is vanilla (Battle_Effects.rb:270 :WaterVeil failure, Battler.rb:4095
# cure) — untouched here. Aqua Ring is the plain flag `effects[:AquaRing] = true`
# (move 0DA, Battle_MoveEffects.rb:5289; Phione crest, Rejuv/Battle/Battle.rb:51).
# End-of-round heal (Battle.rb:6356) reads that flag; switching out clears it
# (SwitchEff) and Baton Pass carries it (BatonEff), so re-entry re-rings.
# Test cases:
#   - Floatzel switches in                 => ability box, "surrounded itself with a veil of water!", heals 1/16 each round end
#   - Baton Pass an Aqua Ring onto Mantine => no second message (already ringed)
#   - Wailord hit by Will-O-Wisp           => still not burned (vanilla)
CHROOKED_SWITCH_IN[:WATERVEIL] = lambda { |battler, battle|
  next if battler.effects[:AquaRing]
  battler.effects[:AquaRing] = true
  battle.pbShowAbilityBox(battler)
  battle.pbAnimation(:AQUARING, battler, nil)
  battle.pbDisplay(_INTL("{1} surrounded itself with a veil of water!", battler.pbThis))
  battle.pbHideAbilityBox(battler)
}
