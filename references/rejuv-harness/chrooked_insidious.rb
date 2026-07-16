# chrooked:insidious
# Insidious — "Using a status move raises the user's Speed by one stage."
#   stat-change: after this Pokemon uses a status-category move, Speed below +6
# Test cases:
#   - use a status move (e.g. Toxic) => Speed +1
#   - damaging move => nothing
CHROOKED_AFTER_MOVE[:INSIDIOUS] = lambda { |battler, move_symbol, battle|
  data = $cache.moves[move_symbol]
  next unless data && data.category == :status
  next unless battler.pbCanIncreaseStatStage?(PBStats::SPEED, battler, nil)
  battle.pbShowAbilityBox(battler)
  battler.pbChangeStats(PBStats::SPEED, 1, battler, nil, abilitycheck: :skip)
  battle.pbHideAbilityBox(battler)
}
