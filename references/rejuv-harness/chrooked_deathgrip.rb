# chrooked:deathgrip
# Death Grip — "Contact moves have a 30% chance to trap the target."
#   on-contact: target survives, not already trapped => wrap/bind style trap
# Test cases:
#   - contact hit, 30% roll => target bound (residual damage, cannot switch)
#   - already-trapped target => nothing
CHROOKED_ON_DEAL[:DEATHGRIP] = lambda { |move, user, target, battle|
  next unless user.makesContact?(move)
  next if target.effects[:MultiTurn] != 0 || battle.pbRandom(100) >= 30
  battle.pbShowAbilityBox(user)
  target.effects[:MultiTurn] = 5
  target.effects[:MultiTurnAttack] = :BIND
  target.effects[:MultiTurnUser] = user.index
  battle.pbDisplay(_INTL("{1} was trapped in {2}'s death grip!", target.pbThis, user.pbThis(true)))
  battle.pbHideAbilityBox(user)
}
