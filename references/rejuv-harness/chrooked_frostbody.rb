# chrooked:frostbody
# Frost Body — contact frostbite both directions, 30% each. The Ice member of the
# Static / Flame Body / Poison Point family, built on the Venomous shape.
#   status-apply (out): user lands a contact move, target survives => 30% frostbite
#   status-apply (in): user hits this Pokemon with contact, it survives => 30% frostbite attacker
# Test cases:
#   - land contact move => ~30% target frostbitten
#   - get hit by contact move => ~30% attacker frostbitten
#   - Ice-type targets => unaffected (pbCanFreeze? gate)
#
# pbFreeze prints the frostbite wording through chrooked_frostbite.rb's text
# prepend, so no message is passed here.
CHROOKED_ON_DEAL[:FROSTBODY] = lambda { |move, user, target, battle|
  next unless user.makesContact?(move) && target.pbCanFreeze?(user, move)
  next if battle.pbRandom(100) >= 30
  battle.pbShowAbilityBox(user)
  target.pbFreeze
  battle.pbHideAbilityBox(user)
}
CHROOKED_WHEN_HIT[:FROSTBODY] = lambda { |move, user, target, battle|
  next unless user.makesContact?(move) && user.pbCanFreeze?(target, move)
  next if battle.pbRandom(100) >= 30
  battle.pbShowAbilityBox(target)
  user.pbFreeze
  battle.pbHideAbilityBox(target)
}
