# chrooked:tectonize
# ---------------------------------------------------------------------------
# Ruleset behavior "tectonize": Normal-type moves become Ground-type and gain +20% power.
#
# Essentials 21 Seam: Battle::AbilityEffects::ModifyMoveBaseType (the conversion) plus
# DamageCalcFromUser (the 1.2x rider), the pair Nova's own Aerilate and Dragonize use.
# Normal moves become GROUND and set move.powerBoost; the rider reads that flag, so
# moves that compute their own type (Weather Ball, Judgment, Struggle, ...) are
# never converted, because they override pbBaseType and skip this registry.
# Translated from references/rejuv-harness/chrooked_tectonize.rb (Rejuvenation's
# core multiplies final damage; Essentials 21 offers power/attack/defense/final
# multipliers, so this follows the matching vanilla handler instead).
#
# Install, load order, marker-gated oracle and the OBS/EST split: exactly as
# chrooked_kindle.rb, which explains each in full.
#     [chrooked:tectonize] OBS move=<ID> ability=true converted=<TYPE|none> boosted=<true|false>   a real hit
#     [chrooked:tectonize] EST ...   an AI estimate, never scored
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
  ChrookedLog.line("[chrooked:tectonize] load prior_handler=" \
                   "#{!Battle::AbilityEffects::ModifyMoveBaseType[:TECTONIZE].nil?}")
  Battle::AbilityEffects::ModifyMoveBaseType.add(:TECTONIZE,
    proc { |ability, user, move, type|
      next if type != :NORMAL || !GameData::Type.exists?(:GROUND)
      move.powerBoost = true
      next :GROUND
    }
  )
  Battle::AbilityEffects::DamageCalcFromUser.add(:TECTONIZE,
    proc { |ability, user, target, move, mults, power, type|
      mults[:power_multiplier] *= 1.2 if move.powerBoost
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:tectonize] #{tag} move=#{move.id} ability=true " \
                         "converted=#{move.powerBoost ? type : 'none'} boosted=#{move.powerBoost}")
      end
    }
  )
  ChrookedLog.line("[chrooked:tectonize] installed on ModifyMoveBaseType and DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:tectonize] ERROR #{e.class}: #{e.message}")
end
