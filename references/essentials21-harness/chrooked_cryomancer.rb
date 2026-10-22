# chrooked:cryomancer
# ---------------------------------------------------------------------------
# Ruleset behavior "cryomancer": This Pokemon's Ice-type moves deal 50% more damage.
#
# Essentials 21 Seam: Battle::AbilityEffects::DamageCalcFromUser.
# Blaze's shape minus its HP check (Nova has no vanilla Ice booster):
# an attack-stat multiplier, so tiny hits land a little under 1.5x.
# Translated from references/rejuv-harness/chrooked_cryomancer.rb (Rejuvenation's
# core multiplies final damage; Essentials 21 offers power/attack/defense/final
# multipliers, so this follows the matching vanilla handler instead).
#
# Install, load order, marker-gated oracle and the OBS/EST split: exactly as
# chrooked_kindle.rb, which explains each in full.
#     [chrooked:cryomancer] OBS move=<ID> type=<TYPE> ability=true result=<BOOSTED|NORMAL>   a real hit
#     [chrooked:cryomancer] EST ...   an AI estimate, never scored
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
  ChrookedLog.line("[chrooked:cryomancer] load prior_handler=#{!chrooked_table[:CRYOMANCER].nil?}")
  chrooked_table.add(:CRYOMANCER,
    proc { |ability, user, target, move, mults, power, type|
      boosted = (type == :ICE)
      mults[:attack_multiplier] *= 1.5 if boosted
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:cryomancer] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \
                         "result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
  ChrookedLog.line("[chrooked:cryomancer] installed on Battle::AbilityEffects::DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:cryomancer] ERROR #{e.class}: #{e.message}")
end
