# chrooked:exhaust
# Exhaust — "Contact moves have a 30% chance to lower the target's accuracy."
#   stat-change: user lands contact, target survives, acc above -6, 30%
# Test cases:
#   - contact hit, roll succeeds => target accuracy -1
#   - non-contact move => nothing
CHROOKED_ON_DEAL[:EXHAUST] = lambda { |move, user, target, battle|
  next unless user.makesContact?(move)
  next if battle.pbRandom(100) >= 30
  next unless target.pbCanReduceAnyStat?([PBStats::ACCURACY], user, nil)
  battle.pbShowAbilityBox(user)
  target.pbChangeStats(PBStats::ACCURACY, -1, user, nil)
  battle.pbHideAbilityBox(user)
}
