# chrooked:unattainable
# Unattainable — "Ignores the foe's stat changes. Contact may infatuate the
#                 attacker, regardless of gender."
#   Unaware half:     NOT written here. ruleset/abilities/unattainable.yaml
#                     declares `behaviors: [unattainable, unaware]`, so
#                     chrooked_zz_zcompose.rb makes the holder a set that
#                     matches every vanilla `ability == :UNAWARE` check
#                     (Battle_Move.rb damage calc, accuracy, AI).
#   when-hit (contact): 30% => infatuate the attacker, with Cute Charm's gates
#                     minus the gender line. :CUTECHARM is deliberately NOT a
#                     composed part — vanilla's gender-gated roll would stack a
#                     second 30% on opposite-gender attackers.
# Test cases:
#   - same-gender or genderless attacker makes contact => ~30% infatuated
#   - attacker with Oblivious, or under an Aroma Veil => never
#   - attacker already infatuated => no second roll lands
#   - non-contact move, Protective Pads, Substitute, Z-move => never
#   - attacker fainted from recoil/Rocky Helmet before this runs => never

module ChrookedUnattainable
  CHANCE = 30

  # pbCanAttract? (Battle_Effects.rb:594) with the gender line removed; every
  # other gate is copied in order. `victim` is the contact-maker, `seducer` the
  # holder — same roles as vanilla's self / attacker.
  # ponytail: a copy, not a wrapper — re-sync if Rejuv adds a gate to pbCanAttract?.
  def self.can_attract?(victim, seducer)
    return false if victim.isFaintedAndNoShields?
    return false if victim.effects[:Attract] >= 0
    partner = victim.pbPartner
    return false if victim.ability == :AROMAVEIL && !victim.shouldBeMoldBroken?(seducer, nil)
    return false if partner && partner.ability == :AROMAVEIL && !partner.shouldBeMoldBroken?(seducer, nil)
    return false if victim.ability == :OBLIVIOUS && !victim.shouldBeMoldBroken?(seducer, nil)
    true
  end
end

# user = contact-maker, target = the Unattainable holder. The core has already
# dropped Substitute hits, a fainted holder, and a Mold-Broken holder.
CHROOKED_WHEN_HIT[:UNATTAINABLE] = lambda { |move, user, target, battle|
  next if move.zmove || !user.makesContact?(move) || user.hasWorkingItem(:PROTECTIVEPADS)
  next if battle.pbRandom(100) >= ChrookedUnattainable::CHANCE
  next unless ChrookedUnattainable.can_attract?(user, target)
  battle.pbShowAbilityBox(target)
  user.pbAttract(target)
  battle.pbHideAbilityBox(target)
}
