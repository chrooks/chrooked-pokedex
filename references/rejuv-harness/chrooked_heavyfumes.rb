# chrooked:heavyfumes
# Heavy Fumes — "Foes lose 1/16 max HP at the end of each turn. Poison and
#   Grass types are unaffected." Bad Dreams keyed on type instead of sleep.
#   turn-end: each opposing battler on the field takes floor(maxHP/16), min 1.
#   Magic-Guard-alikes are skipped through the same list vanilla gates on, so
#   Impenetrable and friends are covered for free.
# ponytail: the AI is not taught the chip; it plays as if the foe took nothing.
#   Teach it via hpGainPerTurn on the FOE's side if trainers misjudge KOs.
# Test cases (drive in-game):
#   - Normal foe, end of turn => loses 1/16 with "is choked by the heavy fumes"
#   - Poison or Grass foe    => nothing
#   - Magic Guard foe        => nothing
CHROOKED_TURN_END[:HEAVYFUMES] = lambda { |battler, battle|
  guards = battle.magicGuardAbilities
  shown = false
  [battler.pbOpposing1, battler.pbOpposing2].each do |foe|
    next if !foe || foe.isFainted? || foe.hp <= 0
    next if foe.hasType?(:POISON) || foe.hasType?(:GRASS)
    next if guards.include?(foe.ability)
    unless shown
      battle.pbShowAbilityBox(battler)
      shown = true
    end
    foe.pbReduceHP([(foe.totalhp / 16.0).floor, 1].max, true,
                   message: _INTL("{1} is choked by the heavy fumes!", foe.pbThis))
  end
  battle.pbHideAbilityBox(battler) if shown
}
