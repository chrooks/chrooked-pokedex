# chrooked:rebound
# Rebound — "When hit by a contact move, the attacker takes a quarter of the
#            damage dealt as recoil and this Pokemon's Defense rises one stage."
#   when-hit (contact): attacker loses floor(damage / 4), minimum 1, with the
#                       same gates as Iron Barbs / Riposte (Protective Pads, the
#                       magicGuardAbilities list, which carries every
#                       CHROOKED_MAGIC_GUARD member); then the holder's Defense
#                       rises +1 by ability, even when the recoil was blocked.
# Test cases:
#   - take 100 from a contact move => attacker loses 25, holder Defense +1
#   - take a non-contact hit => nothing
#   - substitute eats the hit => nothing (core gates on damagestate.substitute)
#   - attacker holds Protective Pads or has Magic Guard => no recoil, Defense +1
#   - take 2 from a contact move => attacker loses 1, Defense +1
CHROOKED_WHEN_HIT_DMG[:REBOUND] = lambda { |move, user, target, damage, battle|
  next unless user.makesContact?(move)
  battle.pbShowAbilityBox(target)
  if !user.isFainted? && !user.hasWorkingItem(:PROTECTIVEPADS) &&
     !battle.magicGuardAbilities.include?(user.ability)
    recoil = (damage / 4.0).floor
    recoil = 1 if recoil < 1
    user.pbReduceHP(recoil, true, message: _INTL("{1} was hurt!", user.pbThis))
  end
  if target.pbCanIncreaseStatStage?(PBStats::DEFENSE, target, nil)
    target.pbChangeStats(PBStats::DEFENSE, 1, target, nil, abilitycheck: :hide)
  end
  battle.pbHideAbilityBox(target)
}
