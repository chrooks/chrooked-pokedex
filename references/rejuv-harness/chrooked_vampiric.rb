# chrooked:vampiric
# Vampiric — "Contact moves heal the user for a quarter of the damage dealt."
#   on-deal (damage-aware): contact move => drain 25% of damage via absorbHP
# Test cases:
#   - contact move deals 100 => user recovers 25
#   - non-contact move => no drain
#   - Liquid Ooze target, 100 damage => user loses 25 instead
CHROOKED_ON_DEAL_DMG[:VAMPIRIC] = lambda { |move, user, target, damage, battle|
  next unless user.makesContact?(move)
  # ponytail: skip the no-op (full HP, no ooze to punish) so the ability box isn't spam
  next if user.hp == user.totalhp && target.ability != :LIQUIDOOZE
  battle.pbShowAbilityBox(user)
  user.absorbHP((damage / 4.0).round, target, :HPDrainingMove, move)
  battle.pbHideAbilityBox(user)
}
