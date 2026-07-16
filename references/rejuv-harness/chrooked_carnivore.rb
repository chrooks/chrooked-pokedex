# chrooked:carnivore
# Carnivore — "Knocking out a foe heals the user 1/4 of its max HP."
#   faint: user's move KO'd a foe; user alive, below full HP, can heal
# Test cases:
#   - KO a foe while damaged => heal 1/4 max HP
#   - KO at full HP => nothing ; under Heal Block => nothing
CHROOKED_ON_KO[:CARNIVORE] = lambda { |battler, targets, basemove, battle|
  next unless battler.canHeal? && battler.hp < battler.totalhp
  battle.pbShowAbilityBox(battler)
  battler.pbRecoverHP((battler.totalhp / 4.0).floor, true,
                      message: _INTL("{1} feasted on its prey!", battler.pbThis))
  battle.pbHideAbilityBox(battler)
}
