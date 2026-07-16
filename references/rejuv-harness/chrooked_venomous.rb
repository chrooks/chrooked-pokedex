# chrooked:venomous
# Venomous — contact poison both directions, 30% each.
#   status-apply (out): user lands a contact move, target survives => 30% poison
#   status-apply (in): user hits this Pokemon with contact, it survives => 30% poison attacker
# Test cases:
#   - land contact move => ~30% target poisoned
#   - get hit by contact move => ~30% attacker poisoned
#   - Poison/Steel targets => unaffected (pbCanPoison? gate)
CHROOKED_ON_DEAL[:VENOMOUS] = lambda { |move, user, target, battle|
  next unless user.makesContact?(move) && target.pbCanPoison?(user, move)
  next if battle.pbRandom(100) >= 30
  battle.pbShowAbilityBox(user)
  target.pbPoison(user)
  battle.pbHideAbilityBox(user)
}
CHROOKED_WHEN_HIT[:VENOMOUS] = lambda { |move, user, target, battle|
  next unless user.makesContact?(move) && user.pbCanPoison?(target, move)
  next if battle.pbRandom(100) >= 30
  battle.pbShowAbilityBox(target)
  user.pbPoison(target)
  battle.pbHideAbilityBox(target)
}
