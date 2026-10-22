# chrooked:overcharge
# ---------------------------------------------------------------------------
# Ruleset behavior "overcharge": While at low HP, this Pokemon's Electric-type moves deal 50% more damage.
#
# Essentials 21 Seam: Battle::AbilityEffects::DamageCalcFromUser.
# Nova's Blaze handler with Electric for Fire: an attack-stat multiplier
# at or below 1/3 max HP, the spec's integer-division threshold (hp <= totalhp / 3).
# Translated from references/rejuv-harness/chrooked_overcharge.rb (Rejuvenation's
# core multiplies final damage; Essentials 21 offers power/attack/defense/final
# multipliers, so this follows the matching vanilla handler instead).
#
# Install, load order, marker-gated oracle and the OBS/EST split: exactly as
# chrooked_kindle.rb, which explains each in full.
#     [chrooked:overcharge] OBS move=<ID> type=<TYPE> ability=true hp_low=<true|false> result=<BOOSTED|NORMAL>   a real hit
#     [chrooked:overcharge] EST ...   an AI estimate, never scored
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
  ChrookedLog.line("[chrooked:overcharge] load prior_handler=#{!chrooked_table[:OVERCHARGE].nil?}")
  chrooked_table.add(:OVERCHARGE,
    proc { |ability, user, target, move, mults, power, type|
      hp_low  = user.hp <= user.totalhp / 3
      boosted = hp_low && type == :ELECTRIC
      mults[:attack_multiplier] *= 1.5 if boosted
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:overcharge] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \
                         "hp_low=#{hp_low} result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
  ChrookedLog.line("[chrooked:overcharge] installed on Battle::AbilityEffects::DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:overcharge] ERROR #{e.class}: #{e.message}")
end
