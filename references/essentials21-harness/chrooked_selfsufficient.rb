# chrooked:selfsufficient
# ---------------------------------------------------------------------------
# Ruleset behavior "selfsufficient": restores 1/16 of max HP at the end of each turn
# (Leftovers as an ability).
#
# HAND-WRITTEN (mjolnir NV-21). Seam Battle::AbilityEffects::EndOfRoundHealing, as
# Hydration's. While it can heal: floor(max HP / 16), at least 1, under the splash with
# Nova's Ice Body message. Independent of the held item's own end-of-round heal.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:selfsufficient] OBS ability=true eor=true can_heal=<bool> change=<n>   each end of round
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
  ChrookedLog.line("[chrooked:selfsufficient] load prior_handler=" \
                   "#{!Battle::AbilityEffects::EndOfRoundHealing[:SELFSUFFICIENT].nil?}")
  Battle::AbilityEffects::EndOfRoundHealing.add(:SELFSUFFICIENT,
    proc { |ability, battler, battle|
      can_heal = battler.canHeal?
      healed = 0
      if can_heal
        battle.pbShowAbilitySplash(battler)
        healed = battler.pbRecoverHP([battler.totalhp / 16, 1].max)
        if Battle::Scene::USE_ABILITY_SPLASH
          battle.pbDisplay(_INTL("{1}'s HP was restored.", battler.pbThis))
        else
          battle.pbDisplay(_INTL("{1} {2} restored its HP.", battler.pbOfThis, battler.abilityName))
        end
        battle.pbHideAbilitySplash(battler)
      end
      ChrookedLog.line("[chrooked:selfsufficient] OBS ability=true eor=true can_heal=#{can_heal} change=#{healed}")
    }
  )
  ($chrooked_selftest_cases ||= {})["selfsufficient"] = {
    ability: :SELFSUFFICIENT, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    eor: [["damaged", {hp: 0.5}], ["full", {}], ["tiny", {level: 1, hp: 0.5}],
          ["leftovers", {hp: 0.5, item: :LEFTOVERS}]],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:selfsufficient] installed on EndOfRoundHealing")
rescue StandardError => e
  ChrookedLog.error("[chrooked:selfsufficient] ERROR #{e.class}: #{e.message}")
end
