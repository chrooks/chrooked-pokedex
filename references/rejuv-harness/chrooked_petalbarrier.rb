# chrooked:petalbarrier
# Petal Barrier — "Fresh petals halve the first hit after entry. They regrow
#   only on switching out."
#   switch-in:   arm effects[:ChrookedPetals] (pbInitEffects wipes it on
#                switch-out, so re-entry is the only regrow — by decision, a
#                per-unhit-turn regrow is farmable with Protect / Substitute).
#   damage-calc: armed and no Substitute => x0.5 on the incoming hit.
#   when-hit:    disarm + announce. Fires per hit, so a multi-hit move halves
#                only its first strike.
# Test cases:
#   - enter, take Surf => half damage, "petals scattered"; next hit => full
#   - Double Kick => first hit halved, second full
#   - Protect / idle turns => no regrow; switch out and in => armed again
#   - hit into a Substitute => no reduction, petals stay
CHROOKED_SWITCH_IN[:PETALBARRIER] = lambda { |battler, battle|
  battler.effects[:ChrookedPetals] = true
}
CHROOKED_DEFENSE_MODS[:PETALBARRIER] = lambda { |move, attacker, opponent|
  armed = opponent.effects[:ChrookedPetals] && opponent.effects[:Substitute].to_i <= 0
  armed ? 0.5 : 1.0
}
CHROOKED_WHEN_HIT[:PETALBARRIER] = lambda { |move, user, target, battle|
  next unless target.effects[:ChrookedPetals]
  target.effects[:ChrookedPetals] = nil
  battle.pbAbilityBoxAndDisplay(target, _INTL("{1}'s petals scattered!", target.pbThis))
  Chrooked.log("PETALBARRIER #{target.pbThis} scattered on #{move.name}")
}
