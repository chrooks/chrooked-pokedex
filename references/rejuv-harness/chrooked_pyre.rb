# chrooked:pyre
# Pyre — "Ghost-type moves gain a 30% chance to burn the target."
#   status-apply: damaging Ghost move connects, target burnable, 30%
# Test cases:
#   - Ghost move hit, roll succeeds => target burned
#   - Fire-type target => unaffected (pbCanBurn? gate)
CHROOKED_ON_DEAL[:PYRE] = lambda { |move, user, target, battle|
  next unless move.pbType(user) == :GHOST && target.pbCanBurn?(user, move)
  next if battle.pbRandom(100) >= 30
  battle.pbShowAbilityBox(user)
  target.pbBurn(user)
  battle.pbHideAbilityBox(user)
}
