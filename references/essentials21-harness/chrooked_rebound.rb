# chrooked:rebound
# ---------------------------------------------------------------------------
# Ruleset ability "rebound": a contact move recoils a quarter of its damage back at
# the attacker, and the holder's Defense rises one stage.
#
# HAND-WRITTEN (mjolnir batch, 2026-10-26). Seam Battle::AbilityEffects::OnBeingHit,
# Nova's Iron Barbs shape (contact by pbContactMove?, affectedByContactEffect? for
# Protective Pads, takesIndirectDamage? for Magic Guard), scaled to the hit as
# Riposte is: floor(HP lost / 4), at least 1. Never through a substitute. Then
# pbRaiseStatStageByAbility(:DEFENSE, 1) on the holder, even when the recoil was
# blocked by Pads or Magic Guard (Contrary and +6 answer as they do to Stamina).
#     [chrooked:rebound] OBS ability=true move=<ID> recoil=<n> defense=<bool>
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md. Its checks measure it.
# ---------------------------------------------------------------------------

unless defined?(ChrookedLog)
  module ChrookedLog
    # Resolved once, at load, while the working directory is the game folder.
    LOG     = File.expand_path("chrooked_load.log")
    ENABLED = File.exist?(File.expand_path("chrooked-oracle.on"))

    def self.line(msg)
      write(msg) if ENABLED
    end

    def self.error(msg)
      write(msg)
    end

    def self.write(msg)
      File.open(LOG, "a") { |f| f.puts(msg) }
    rescue StandardError
      nil
    end
  end
end

begin
  ChrookedLog.line("[chrooked:rebound] load prior_on_being_hit=#{!Battle::AbilityEffects::OnBeingHit[:REBOUND].nil?}")
  Battle::AbilityEffects::OnBeingHit.add(:REBOUND,
    proc { |ability, user, target, move, battle|
      next if !user || !move.pbContactMove?(user) || !user.affectedByContactEffect?
      next if target.damageState.substitute
      recoil = 0
      battle.pbShowAbilitySplash(target)
      if user.takesIndirectDamage?
        recoil = [target.damageState.hpLost / 4, 1].max
        battle.scene.pbDamageAnimation(user)
        user.pbReduceHP(recoil, false)
        if Battle::Scene::USE_ABILITY_SPLASH
          battle.pbDisplay(_INTL("{1} is hurt!", user.pbThis))
        else
          battle.pbDisplay(_INTL("{1} is hurt by {2} {3}!", user.pbThis, target.pbOfThis(true), target.abilityName))
        end
      end
      raised = target.fainted? ? false : target.pbRaiseStatStageByAbility(:DEFENSE, 1, target, false)
      battle.pbHideAbilitySplash(target)
      ChrookedLog.line("[chrooked:rebound] OBS ability=true move=#{move.id} recoil=#{recoil} defense=#{raised}")
    }
  )
  # The foe hits the holder once for hp_lost with move_id (substitute, Pads or
  # Magic Guard as asked): the foe's HP change and the holder's Defense change.
  chrooked_rebound_hit = lambda do |t, spec, move_id: :TACKLE, hp_lost: 100, substitute: false,
                                       foe_item: nil, foe_ability: nil|
    b, foe, holder = t.pair(spec, :TACKLE)
    holder.ability = spec[:ability]
    foe.item = foe_item
    foe.ability = foe_ability
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    holder.damageState.reset
    holder.damageState.substitute = substitute
    holder.damageState.hpLost = holder.damageState.calcDamage = hp_lost
    foe_hp = foe.hp
    Battle::AbilityEffects.triggerOnBeingHit(holder.ability, foe, holder, move, b)
    "foe_change=#{foe.hp - foe_hp} defense_change=#{holder.stages[:DEFENSE]}"
  end
  ($chrooked_selftest_cases ||= {})["rebound"] = {
    ability: :REBOUND, control: nil, user: :WIGGLYTUFF, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["contact", ->(t, spec) { chrooked_rebound_hit.call(t, spec) }],
      ["no_contact", ->(t, spec) { chrooked_rebound_hit.call(t, spec, move_id: :WATERGUN) }],
      ["substitute", ->(t, spec) { chrooked_rebound_hit.call(t, spec, substitute: true) }],
      ["pads_guard", ->(t, spec) {
        pads = chrooked_rebound_hit.call(t, spec, foe_item: :PROTECTIVEPADS)
        guard = chrooked_rebound_hit.call(t, spec, foe_ability: :MAGICGUARD)
        "pads_#{pads.gsub(' ', ' pads_')} guard_#{guard.gsub(' ', ' guard_')}"
      }],
      ["graze", ->(t, spec) { chrooked_rebound_hit.call(t, spec, hp_lost: 2) }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:rebound] installed on OnBeingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:rebound] ERROR #{e.class}: #{e.message}")
end
