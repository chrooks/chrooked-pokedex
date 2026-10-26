# chrooked:allure
# Allure — "Infatuation caused by this Pokemon ignores gender. When an
#           infatuated foe attacks it, that foe's higher attacking stat falls."
#   status-apply: any infatuation the holder is the attractor of (Attract, or
#                 any other source that routes through pbCanAttract?) skips the
#                 gender / genderless test. Every other gate stays: already
#                 infatuated, Aroma Veil (self or partner), Oblivious.
#   when-hit:     a damaging hit from a foe whose infatuation points at the
#                 holder => that foe's higher attacking stat (Attack vs Sp. Atk,
#                 raw stat x stage, ties go to Attack) is lowered one stage.
#   NOT a contact-roll infatuation: that is Cute Charm / Unattainable.
# Test cases:
#   - holder uses Attract on a genderless or same-gender foe => it falls in love
#   - holder uses Attract on an Oblivious or Aroma Veil foe => still blocked
#   - foe in love with the holder hits it with a special move while its Sp. Atk
#     is higher => Sp. Atk -1 (Clear Body, Mist, Substitute still refuse it)
#   - raw Attack == raw Sp. Atk => Attack falls
#   - foe NOT in love with the holder, or a status move => nothing
#
# The gender bypass is a prepend on PokeBattle_Battler#pbCanAttract?
# (Battle_Effects.rb:594), never alias_method: zz_zcompose / zz_redux alias other
# methods on this class and a class-body alias would capture a prepended wrapper
# (see chrooked_soulsight.rb). `self` is the victim, `attacker` the seducer.
# ponytail: a copy of the vanilla body minus the gender line, as unattainable does
# for Cute Charm — re-sync if Rejuv adds a gate to pbCanAttract?.
module ChrookedAllureAttract
  def pbCanAttract?(attacker, move, showMessage: false)
    return super unless attacker && Chrooked.ability_in?([:ALLURE], attacker.ability)
    return false if isFaintedAndNoShields?
    if @effects[:Attract] >= 0
      @battle.pbDisplay(_INTL("But it failed!")) if showMessage
      return false
    end
    moldbroken = shouldBeMoldBroken?(attacker, move)
    partnerMoldbroken = pbPartner.shouldBeMoldBroken?(attacker, move)
    aromaVeil = []
    aromaVeil.push(self) if self.ability == :AROMAVEIL && !moldbroken
    aromaVeil.push(pbPartner) if pbPartner.ability == :AROMAVEIL && !partnerMoldbroken
    if aromaVeil.any?
      @battle.pbAbilityBoxAndDisplay(aromaVeil.first, _INTL("{1} is protected by an aromatic veil!", pbThis)) if showMessage
      return false
    end
    if self.ability == :OBLIVIOUS && !moldbroken
      @battle.pbAbilityBoxAndDisplay(self, _INTL("It doesn't affect\n{1}...", pbThis(true))) if showMessage
      return false
    end
    true
  end
end
PokeBattle_Battler.prepend(ChrookedAllureAttract) if defined?(PokeBattle_Battler)

module ChrookedAllure
  # The foe's higher attacking stat after stages; ties go to Attack. Same
  # arithmetic as Chrooked.with_equalized_attack in the core.
  def self.higher_attacking_stat(battler)
    atk = battler.attack * PBStats::StageMul[battler.stages[PBStats::ATTACK] + 6]
    spa = battler.spatk * PBStats::StageMul[battler.stages[PBStats::SPATK] + 6]
    spa > atk ? PBStats::SPATK : PBStats::ATTACK
  end
end

# user = the attacker, target = the Allure holder. The core only fires this after
# a damaging hit that missed any Substitute, on a holder that survived and is not
# Mold-Broken.
CHROOKED_WHEN_HIT[:ALLURE] = lambda { |move, user, target, battle|
  next if user.isFainted?
  next unless user.effects[:Attract] == target.index
  stat = ChrookedAllure.higher_attacking_stat(user)
  next unless user.pbCanReduceStatStage?(stat, target, nil)
  battle.pbShowAbilityBox(target)
  user.pbChangeStats(stat, -1, target, nil, abilitycheck: :hide)
  battle.pbHideAbilityBox(target)
}
