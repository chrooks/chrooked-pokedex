# chrooked:selfsufficient
# Self Sufficient — "Restores a little HP at the end of each turn."
#   turn-end: on field, not fainted, below full HP => heal 1/16 max (min 1)
# Test cases:
#   - damaged mon at end of turn => heals ~1/16 max HP
#   - full HP => nothing
CHROOKED_TURN_END[:SELFSUFFICIENT] = lambda { |battler, battle|
  next unless battler.canHeal? && battler.hp < battler.totalhp
  battle.pbShowAbilityBox(battler)
  amount = [(battler.totalhp / 16.0).floor, 1].max
  battler.pbRecoverHP(amount, true, message: _INTL("{1} restored a little HP!", battler.pbThis))
  battle.pbHideAbilityBox(battler)
}
