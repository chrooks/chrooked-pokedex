# chrooked:hubris
# Hubris — "Knocking out a foe raises the user's Sp. Atk by one stage."
#   faint: user's move KO'd; user alive; SpA below +6 (one stage per KO)
# Test cases:
#   - KO a foe => Sp. Atk +1
#   - SpA already +6 => nothing
CHROOKED_ON_KO[:HUBRIS] = lambda { |battler, targets, basemove, battle|
  next unless battler.pbCanIncreaseStatStage?(PBStats::SPATK, battler, nil)
  battle.pbShowAbilityBox(battler)
  battler.pbChangeStats(PBStats::SPATK, targets.length, battler, nil, abilitycheck: :skip)
  battle.pbHideAbilityBox(battler)
}
