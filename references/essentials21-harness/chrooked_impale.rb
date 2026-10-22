# chrooked:impale
# ---------------------------------------------------------------------------
# Ruleset behavior "impale": Piercing moves deal 30% more damage.
#
# Essentials 21 Seam: Battle::AbilityEffects::DamageCalcFromUser, shaped like
# Nova's Iron Fist (power_multiplier *= 1.2 if move.punchingMove?): a 1.3x power
# multiplier when the move carries a piercing flag (Piercing).
# Piercing is a custom flag: the dex writes it into the game's move data
# from the Ruleset's move flags (appliers/essentials/vocab.py, mjolnir NV-7);
# Punching is Nova's own. Without the flag in the data this port never fires.
# Translated from references/rejuv-harness/chrooked_impale.rb, whose core matched
# hard-coded move lists instead.
#
# Install, load order, marker-gated oracle and the OBS/EST split: exactly as
# chrooked_kindle.rb, which explains each in full.
#     [chrooked:impale] OBS move=<ID> ability=true category=<flag|none> result=<BOOSTED|NORMAL>   a real hit
#     [chrooked:impale] EST ...   an AI estimate, never scored
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
  ChrookedLog.line("[chrooked:impale] load prior_handler=#{!chrooked_table[:IMPALE].nil?}")
  chrooked_table.add(:IMPALE,
    proc { |ability, user, target, move, mults, power, type|
      category = move.flags.find { |f| f[/^(Piercing)$/i] }
      mults[:power_multiplier] *= 1.3 if category
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:impale] #{tag} move=#{move.id} ability=true category=#{category || 'none'} " \
                         "result=#{category ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
  ChrookedLog.line("[chrooked:impale] installed on Battle::AbilityEffects::DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:impale] ERROR #{e.class}: #{e.message}")
end
