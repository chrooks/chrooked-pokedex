# chrooked:bloom
# ---------------------------------------------------------------------------
# Ruleset behavior "bloom": This Pokemon's Grass-type moves deal 50% more damage.
#
# Essentials 21 Seam: Battle::AbilityEffects::DamageCalcFromUser.
# Nova's Overgrow handler minus its HP check: an attack-stat multiplier,
# so tiny hits land a little under 1.5x (the formula's flat +2 is never scaled).
# Translated from references/rejuv-harness/chrooked_bloom.rb (Rejuvenation's
# core multiplies final damage; Essentials 21 offers power/attack/defense/final
# multipliers, so this follows the matching vanilla handler instead).
#
# Install, load order, marker-gated oracle and the OBS/EST split: exactly as
# chrooked_kindle.rb, which explains each in full.
#     [chrooked:bloom] OBS move=<ID> type=<TYPE> ability=true result=<BOOSTED|NORMAL>   a real hit
#     [chrooked:bloom] EST ...   an AI estimate, never scored
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
  ChrookedLog.line("[chrooked:bloom] load prior_handler=#{!chrooked_table[:BLOOM].nil?}")
  chrooked_table.add(:BLOOM,
    proc { |ability, user, target, move, mults, power, type|
      boosted = (type == :GRASS)
      mults[:attack_multiplier] *= 1.5 if boosted
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:bloom] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \
                         "result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
  ChrookedLog.line("[chrooked:bloom] installed on Battle::AbilityEffects::DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:bloom] ERROR #{e.class}: #{e.message}")
end
