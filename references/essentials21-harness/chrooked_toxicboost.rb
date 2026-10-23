# chrooked:toxicboost
# ---------------------------------------------------------------------------
# Ruleset behavior "toxicboost": physical moves deal 1.5x while poisoned (the game's own
# Toxic Boost, kept), and its own poison, regular or bad, deals it no damage at the end
# of a round.
#
# HAND-WRITTEN (mjolnir NV-24). The boost stays Nova's DamageCalcFromUser handler. The
# chip has no registry: Battle#pbEORStatusProblemDamage deals it to every battler in
# the list it is handed, so this wrapper hands it the list without a poisoned holder.
# Bad poison's count still climbs each round, as Nova's loop climbs it for Poison Heal,
# so a holder that loses the ability resumes at the right step.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:toxicboost] OBS ability=true eor=true status=POISON toxic=<bool> spared=true   each end of round it is poisoned
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
  ChrookedLog.line("[chrooked:toxicboost] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromUser[:TOXICBOOST].nil?}")
  Battle.class_eval do
    unless method_defined?(:chrooked_toxicboost_pbEORStatusProblemDamage)
      alias_method :chrooked_toxicboost_pbEORStatusProblemDamage, :pbEORStatusProblemDamage
      def pbEORStatusProblemDamage(priority)
        spared = priority.select { |b| !b.fainted? && b.status == :POISON && b.hasActiveAbility?(:TOXICBOOST) }
        spared.each do |b|
          toxic = b.statusCount > 0
          b.effects[PBEffects::Toxic] = [b.effects[PBEffects::Toxic] + 1, 16].min if toxic
          ChrookedLog.line("[chrooked:toxicboost] OBS ability=true eor=true status=POISON toxic=#{toxic} spared=true")
        end
        chrooked_toxicboost_pbEORStatusProblemDamage(priority - spared)
      end
    end
  end
  ($chrooked_selftest_cases ||= {})["toxicboost"] = {
    ability: :TOXICBOOST, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    status_hit: [["physical", :TACKLE, :POISON], ["special", :SWIFT, :POISON]],
    eor_status: [["toxic", {status: :POISON, toxic: true}]],
    without: [],
    fight: [:TACKLE, :SWIFT]
  }
  ChrookedLog.line("[chrooked:toxicboost] installed on Battle#pbEORStatusProblemDamage")
rescue StandardError => e
  ChrookedLog.error("[chrooked:toxicboost] ERROR #{e.class}: #{e.message}")
end
