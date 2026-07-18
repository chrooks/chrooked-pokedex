# chrooked:starfall
# Starfall — "Special moves have a 30% chance to lower the target's Sp. Def."
#   stat-change: user lands a special move, target survives, 30%
# Test cases:
#   - special hit, roll succeeds => target SpD -1
#   - physical hit => nothing
CHROOKED_ON_DEAL[:STARFALL] = lambda { |move, user, target, battle|
  next unless move.pbIsSpecial?(user, move.pbType(user))
  next if battle.pbRandom(100) >= 30
  next unless target.pbCanReduceAnyStat?([PBStats::SPDEF], user, nil)
  battle.pbShowAbilityBox(user)
  target.pbChangeStats(PBStats::SPDEF, -1, user, nil)
  battle.pbHideAbilityBox(user)
}
