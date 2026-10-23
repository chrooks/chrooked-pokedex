# chrooked:flareboost
# ---------------------------------------------------------------------------
# Ruleset behavior "flareboost": special moves deal 1.5x while burned (the game's own
# Flare Boost, kept), and its own burn deals it no damage at the end of a round.
#
# HAND-WRITTEN (mjolnir NV-24). The boost stays Nova's DamageCalcFromUser handler. The
# chip has no registry: Battle#pbEORStatusProblemDamage deals it to every battler in
# the list it is handed, so this wrapper hands it the list without a burned holder.
# The holder still takes every other indirect damage (weather, Leech Seed, ...).
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:flareboost] OBS ability=true eor=true status=BURN spared=true   each end of round it is burned
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
  ChrookedLog.line("[chrooked:flareboost] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromUser[:FLAREBOOST].nil?}")
  Battle.class_eval do
    unless method_defined?(:chrooked_flareboost_pbEORStatusProblemDamage)
      alias_method :chrooked_flareboost_pbEORStatusProblemDamage, :pbEORStatusProblemDamage
      def pbEORStatusProblemDamage(priority)
        spared = priority.select { |b| !b.fainted? && b.status == :BURN && b.hasActiveAbility?(:FLAREBOOST) }
        spared.each { ChrookedLog.line("[chrooked:flareboost] OBS ability=true eor=true status=BURN spared=true") }
        chrooked_flareboost_pbEORStatusProblemDamage(priority - spared)
      end
    end
  end
  ($chrooked_selftest_cases ||= {})["flareboost"] = {
    ability: :FLAREBOOST, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    status_hit: [["special", :SWIFT, :BURN], ["physical", :TACKLE, :BURN]],
    eor_status: [["burned", {status: :BURN}]],
    without: [],
    fight: [:SWIFT, :TACKLE]
  }
  ChrookedLog.line("[chrooked:flareboost] installed on Battle#pbEORStatusProblemDamage")
rescue StandardError => e
  ChrookedLog.error("[chrooked:flareboost] ERROR #{e.class}: #{e.message}")
end
