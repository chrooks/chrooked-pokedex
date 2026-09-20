# chrooked:angerpoint
# Anger Point — "Maxes its highest attacking stat when hit by a critical hit."
#   Vanilla always maxes Attack (Battler.rb:4024). Camerupt runs 105 Sp. Atk
#   against 80 Attack, so vanilla handed it +6 in the stat it never uses.
#
# Vanilla's block is INLINE inside pbEffectsOnDealingDamage, not a method of its
# own, so there is nothing to override directly. This wrapper prepends that
# method, records the Attack stage before vanilla runs, and — only when vanilla
# just maxed Attack on a special-leaning holder — restores the old stage and
# maxes Sp. Atk instead. One stat is maxed, never both.
#
# Loading after chrooked_00_core.rb puts this module outside the core's own
# prepend of the same method, which is what lets it read the pre-super state.
#
# The comparison uses raw stats, not stage-adjusted ones, so a given species
# always picks the same stat.
#
# Test cases (drive in-game — the harness can't run a battle):
#   - Camerupt (80 Atk / 105 SpA) eats a crit => Sp. Atk maxed, Attack untouched.
#   - Primeape (105 Atk / 60 SpA) eats a crit => Attack maxed, exactly as vanilla.
#   - Special holder already at +6 Sp. Atk => nothing happens; Attack is NOT a fallback.
module ChrookedAngerPoint
  def pbEffectsOnDealingDamage(move, user, target, damage, *args, **kwargs)
    special = target && !target.isFainted? &&
              Chrooked.ability_in?([:ANGERPOINT], target.ability) &&
              target.damagestate.critical &&
              target.spatk > target.attack
    before = special ? target.stages[PBStats::ATTACK] : nil
    ret = super
    return ret unless special
    # Vanilla only moves the stage when it fired; leave everything alone if not.
    return ret unless target.stages[PBStats::ATTACK] > before

    target.stages[PBStats::ATTACK] = before
    if target.pbCanIncreaseStatStage?(PBStats::SPATK, target, nil)
      @battle.pbShowAbilityBox(target)
      target.pbChangeStats(PBStats::SPATK, 12, target, nil,
                           abilitycheck: :skip, statmessage: :none)
      @battle.pbDisplay(_INTL("{1} maxed its {2}!", target.pbThis,
                              getStatName(PBStats::SPATK)))
      @battle.pbHideAbilityBox(target)
    end
    ret
  end
end
PokeBattle_Battler.prepend(ChrookedAngerPoint)
