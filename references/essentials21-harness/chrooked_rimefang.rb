# chrooked:rimefang
# ---------------------------------------------------------------------------
# Ruleset behavior "rimefang", three effects (mjolnir NV-12), Infernal Maw's Ice
# twin:
#   1. Biting moves deal 30% more damage.
#   2. Biting moves gain a 30% chance to frostbite the target.
#   3. Biting moves gain a flat 30% chance to make the target flinch.
#
# HAND-WRITTEN: a template generates exactly one effect, and this spec has three.
# Built exactly as chrooked_infernalmaw.rb (which explains every gate), with the
# status swapped: pbCanFreeze? / pbFreeze, whose :FROZEN is frostbite in this game
# because chrooked_frostbite.rb reskins it (halved special damage, a 1/16 chip, no
# lost turns). Without that port this would inflict vanilla freeze, so the two ship
# together. Ice types and an existing status block the frostbite; the flinch still
# rolls.
#
# Install, load order, the marker-gated oracle, the OBS/EST split and the
# self-test registration at the end: references/essentials21-harness/README.md.
#     [chrooked:rimefang] OBS move=<ID> ability=true category=<Biting|none> result=<BOOSTED|NORMAL>   a hit's damage
#     [chrooked:rimefang] OBS move=<ID> ability=true hit=true can_frostbite=<bool> frostbitten=<bool> flinched=<bool>   after a biting hit
# The chance cases are measured by the lab self-test and logged on this mechanic's
# behalf with source=selftest.
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
  chrooked_table = Battle::AbilityEffects::DamageCalcFromUser
  ChrookedLog.line("[chrooked:rimefang] load prior_handler=#{!chrooked_table[:RIMEFANG].nil?} " \
                   "prior_on_hit=#{!Battle::AbilityEffects::OnDealingHit[:RIMEFANG].nil?}")
  chrooked_table.add(:RIMEFANG,
    proc { |ability, user, target, move, mults, power, type|
      biting = move.bitingMove?
      mults[:power_multiplier] *= 1.3 if biting
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:rimefang] #{tag} move=#{move.id} ability=true " \
                         "category=#{biting ? 'Biting' : 'none'} result=#{biting ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
  Battle::AbilityEffects::OnDealingHit.add(:RIMEFANG,
    proc { |ability, user, target, move, battle|
      next if !move.bitingMove?
      next if !target.affectedByAdditionalEffects?
      next if target.hasActiveAbility?(:SHIELDDUST) && !target.beingMoldBroken?
      can_frostbite = target.pbCanFreeze?(user, false)
      frostbitten = false
      if can_frostbite && battle.pbRandom(100) < 30
        battle.pbShowAbilitySplash(user)
        msg = nil
        if !Battle::Scene::USE_ABILITY_SPLASH
          msg = _INTL("{1}'s {2} frostbit {3}!", user.pbThis, user.abilityName, target.pbThis(true))
        end
        target.pbFreeze(user, msg)
        battle.pbHideAbilitySplash(user)
        frostbitten = true
      end
      flinched = battle.pbRandom(100) < 30
      target.pbFlinch(user) if flinched
      ChrookedLog.line("[chrooked:rimefang] OBS move=#{move.id} ability=true hit=true " \
                       "can_frostbite=#{can_frostbite} frostbitten=#{frostbitten} flinched=#{flinched}")
    }
  )
  ($chrooked_selftest_cases ||= {})["rimefang"] = {
    ability: :RIMEFANG, control: :STRONGJAW, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [[:CRUNCH, 1.0], [:TACKLE, 1.0]],
    chance: [
      [:CRUNCH, {status: :FROZEN, status_rate: 0.3, flinch_rate: 0.3}],
      [:TACKLE, {status: :FROZEN, status_rate: 0, flinch_rate: 0}],
      [:CRUNCH, {status: :FROZEN, status_rate: 0, flinch_rate: 0.3, setup: {target_types: [:ICE]}}]
    ],
    without: [],
    fight: [:CRUNCH, :TACKLE]
  }
  ChrookedLog.line("[chrooked:rimefang] installed on DamageCalcFromUser and OnDealingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:rimefang] ERROR #{e.class}: #{e.message}")
end
