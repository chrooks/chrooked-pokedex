# chrooked:riposte
# Riposte — a contact move recoils a quarter of the damage dealt back at the
# attacker. The scaling twin of Rough Skin / Iron Barbs (flat 1/8 max HP): a
# heavy hit recoils hard, chip damage barely registers.
#   when-hit: attacker made contact => attacker loses damage/4 (minimum 1)
# Test cases:
#   - take 100 from a contact move => attacker loses 25
#   - take a non-contact hit => no recoil
#   - substitute eats the hit => no recoil (core gates on damagestate.substitute)
#   - attacker holds Protective Pads or has Magic Guard => no recoil
#
# Gates mirror the vanilla Iron Barbs block in Battler.rb (~3624) so the same
# things that turn Iron Barbs off turn Riposte off.
CHROOKED_WHEN_HIT_DMG[:RIPOSTE] = lambda { |move, user, target, damage, battle|
  next unless user.makesContact?(move)
  next if user.isFainted? || user.hasWorkingItem(:PROTECTIVEPADS)
  next if battle.magicGuardAbilities.include?(user.ability)
  recoil = (damage / 4.0).floor
  recoil = 1 if recoil < 1
  battle.pbShowAbilityBox(target)
  user.pbReduceHP(recoil, true, message: _INTL("{1} was hurt!", user.pbThis))
  battle.pbHideAbilityBox(target)
}
