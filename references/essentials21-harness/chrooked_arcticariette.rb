# chrooked:arcticariette
# ---------------------------------------------------------------------------
# Ruleset behavior "arcticariette": Normal-type sound moves become Ice-type and gain
# a 1.3x power rider.
#
# HAND-WRITTEN (mjolnir NV-13) to prove a flag-gated type change before the
# type_conversion template learns it: Nova's Aerilate pair (ModifyMoveBaseType sets
# move.powerBoost and the new type; a DamageCalcFromUser rider reads powerBoost)
# with one more gate, the move's Sound flag, as Nova's Liquid Voice checks sound.
# Only Normal-type sound moves convert; Bug Buzz and Body Slam stay as they are.
#
# Install, load order, the marker-gated oracle, the OBS/EST split and the self-test
# registration at the end: references/essentials21-harness/README.md.
#     [chrooked:arcticariette] OBS move=<ID> ability=true converted=<TYPE|none> boosted=<true|false>   a real hit
#     [chrooked:arcticariette] EST ...   an AI estimate, never scored
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
  ChrookedLog.line("[chrooked:arcticariette] load prior_handler=" \
                   "#{!Battle::AbilityEffects::ModifyMoveBaseType[:ARCTICARIETTE].nil?}")
  Battle::AbilityEffects::ModifyMoveBaseType.add(:ARCTICARIETTE,
    proc { |ability, user, move, type|
      next if type != :NORMAL || !GameData::Type.exists?(:ICE)
      next if !move.flags.any? { |f| f[/^(Sound)$/i] }
      move.powerBoost = true
      next :ICE
    }
  )
  Battle::AbilityEffects::DamageCalcFromUser.add(:ARCTICARIETTE,
    proc { |ability, user, target, move, mults, power, type|
      mults[:power_multiplier] *= 1.3 if move.powerBoost
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:arcticariette] #{tag} move=#{move.id} ability=true " \
                         "converted=#{move.powerBoost ? type : 'none'} boosted=#{move.powerBoost}")
      end
    }
  )
  ($chrooked_selftest_cases ||= {})["arcticariette"] = {
    ability: :ARCTICARIETTE, control: :AERILATE, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [[:HYPERVOICE, 1.0], [:BUGBUZZ, 1.0], [:BODYSLAM, 1.0]],
    without: [],
    fight: [:HYPERVOICE, :BUGBUZZ, :BODYSLAM]
  }
  ChrookedLog.line("[chrooked:arcticariette] installed on ModifyMoveBaseType and DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:arcticariette] ERROR #{e.class}: #{e.message}")
end
