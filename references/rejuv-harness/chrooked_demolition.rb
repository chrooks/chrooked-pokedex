# chrooked:demolition
# Demolition — "Knocking out a target raises this Pokemon's Attack by one stage."
#   faint: user's move KO'd; battlers remain both sides (core guard); below +6
# Test cases:
#   - KO a foe => Attack +1 (one per KO'd target)
#   - Attack already +6 => nothing
CHROOKED_ON_KO[:DEMOLITION] = lambda { |battler, targets, basemove, battle|
  next unless battler.pbCanIncreaseStatStage?(PBStats::ATTACK, battler, nil)
  battle.pbShowAbilityBox(battler)
  battler.pbChangeStats(PBStats::ATTACK, targets.length, battler, nil, abilitycheck: :skip)
  battle.pbHideAbilityBox(battler)
}
