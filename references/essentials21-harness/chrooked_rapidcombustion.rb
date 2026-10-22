# chrooked:rapidcombustion
# ---------------------------------------------------------------------------
# Ruleset behavior "rapidcombustion": Fire-type moves gain +1 priority while this
# Pokemon is at full HP.
#
# HAND-WRITTEN (mjolnir NV-14) to prove a priority change before it becomes the
# priority_boost template. Seam Battle::AbilityEffects::PriorityChange, which
# pbCalculatePriority asks for the holder's chosen move each round while its
# ability is active (and the AI asks when it weighs moves). Nova's Gale Wings for
# Fire: the move's own type (move.type, as Gale Wings reads it) and HP at its
# maximum (battler.hp == battler.totalhp).
#
# Install, load order, the marker-gated oracle, the OBS/EST split and the self-test
# registration at the end: references/essentials21-harness/README.md.
#     [chrooked:rapidcombustion] OBS move=<ID> type=<TYPE> ability=true hp_full=<bool> priority=<n> result=<BOOSTED|NORMAL>   each round's priority
#     [chrooked:rapidcombustion] EST ...   an AI estimate, never scored
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
  ChrookedLog.line("[chrooked:rapidcombustion] load prior_handler=" \
                   "#{!Battle::AbilityEffects::PriorityChange[:RAPIDCOMBUSTION].nil?}")
  Battle::AbilityEffects::PriorityChange.add(:RAPIDCOMBUSTION,
    proc { |ability, battler, move, pri|
      hp_full = battler.hp == battler.totalhp
      boosted = hp_full && move.type == :FIRE
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s =~ /AI[ _]?Move/ } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:rapidcombustion] #{tag} move=#{move.id} type=#{move.type} ability=true " \
                         "hp_full=#{hp_full} priority=#{boosted ? pri + 1 : pri} " \
                         "result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
      next pri + 1 if boosted
    }
  )
  ($chrooked_selftest_cases ||= {})["rapidcombustion"] = {
    ability: :RAPIDCOMBUSTION, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    priority: [[:FLAMETHROWER, 1.0], [:FLAMETHROWER, 0.5], [:SURF, 1.0]],
    without: [],
    fight: [:FLAMETHROWER, :SURF]
  }
  ChrookedLog.line("[chrooked:rapidcombustion] installed on PriorityChange")
rescue StandardError => e
  ChrookedLog.error("[chrooked:rapidcombustion] ERROR #{e.class}: #{e.message}")
end
