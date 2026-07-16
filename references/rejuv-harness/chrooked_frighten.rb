# chrooked:frighten
# Frighten — "On entry, lowers the Sp. Atk of all adjacent foes by one stage."
#   switch-in: Intimidate clone for Special Attack
# Test cases:
#   - switch in vs two foes => both lose 1 SpA stage
#   - foe at -6 SpA / behind protection => unaffected, no crash
CHROOKED_SWITCH_IN[:FRIGHTEN] = lambda { |battler, battle|
  [battler.pbOpposing1, battler.pbOpposing2].each do |foe|
    next if !foe || foe.isFainted?
    next unless foe.pbCanReduceAnyStat?([PBStats::SPATK], battler, :Frighten)
    battle.pbShowAbilityBox(battler)
    foe.pbChangeStats(PBStats::SPATK, -1, battler, :Frighten)
    battle.pbHideAbilityBox(battler)
  end
}
