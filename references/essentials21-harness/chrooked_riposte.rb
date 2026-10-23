# chrooked:riposte
# ---------------------------------------------------------------------------
# Ruleset behavior "riposte": a contact move recoils a quarter of its damage back at
# the attacker.
#
# HAND-WRITTEN (mjolnir NV-22). Seam Battle::AbilityEffects::OnBeingHit, Nova's Rough
# Skin shape (contact by pbContactMove?, affectedByContactEffect? for Protective Pads,
# takesIndirectDamage? for Magic Guard), scaled to the hit: floor(HP lost / 4), at
# least 1. Never through a substitute. Fires even if the holder fainted to the hit,
# as Nova calls OnBeingHit for a fainted holder.
#     [chrooked:riposte] OBS ability=true move=<ID> recoil=<n>   after a contact hit on the holder
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
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
  ChrookedLog.line("[chrooked:riposte] load prior_on_being_hit=#{!Battle::AbilityEffects::OnBeingHit[:RIPOSTE].nil?}")
  Battle::AbilityEffects::OnBeingHit.add(:RIPOSTE,
    proc { |ability, user, target, move, battle|
      next if !move.pbContactMove?(user) || !user.affectedByContactEffect?
      next if target.damageState.substitute || !user.takesIndirectDamage?
      recoil = [target.damageState.hpLost / 4, 1].max
      battle.pbShowAbilitySplash(target)
      battle.scene.pbDamageAnimation(user)
      user.pbReduceHP(recoil, false)
      if Battle::Scene::USE_ABILITY_SPLASH
        battle.pbDisplay(_INTL("{1} is hurt!", user.pbThis))
      else
        battle.pbDisplay(_INTL("{1} is hurt by {2} {3}!", user.pbThis, target.pbOfThis(true), target.abilityName))
      end
      battle.pbHideAbilitySplash(target)
      ChrookedLog.line("[chrooked:riposte] OBS ability=true move=#{move.id} recoil=#{recoil}")
    }
  )
  ($chrooked_selftest_cases ||= {})["riposte"] = {
    ability: :RIPOSTE, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    recoil: [["contact", {move: :TACKLE, hp_lost: 100}], ["no_contact", {move: :WATERGUN, hp_lost: 100}],
             ["substitute", {move: :TACKLE, hp_lost: 100, substitute: true}],
             ["pads", {move: :TACKLE, hp_lost: 100, foe_item: :PROTECTIVEPADS}],
             ["guard", {move: :TACKLE, hp_lost: 100, foe_ability: :MAGICGUARD}],
             ["graze", {move: :TACKLE, hp_lost: 2}]],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:riposte] installed on OnBeingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:riposte] ERROR #{e.class}: #{e.message}")
end
