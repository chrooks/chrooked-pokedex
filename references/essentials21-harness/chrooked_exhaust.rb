# chrooked:exhaust
# ---------------------------------------------------------------------------
# Ruleset behavior "exhaust": contact moves have a 30% chance to lower the target's
# accuracy by one stage.
#
# HAND-WRITTEN (mjolnir NV-22). Seam Battle::AbilityEffects::OnDealingHit, Nova's
# Poison Touch shape and gates (contact by pbContactMove?, additional effects, Shield
# Dust), with nothing to do at -6 accuracy; the drop is pbLowerStatStageByAbility.
#     [chrooked:exhaust] OBS ability=true move=<ID> contact=true lowered=<bool>   after a contact hit
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
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
  ChrookedLog.line("[chrooked:exhaust] load prior_on_hit=#{!Battle::AbilityEffects::OnDealingHit[:EXHAUST].nil?}")
  Battle::AbilityEffects::OnDealingHit.add(:EXHAUST,
    proc { |ability, user, target, move, battle|
      next if !move.pbContactMove?(user)
      next if !target.affectedByAdditionalEffects?
      next if target.hasActiveAbility?(:SHIELDDUST) && !target.beingMoldBroken?
      next if target.statStageAtMin?(:ACCURACY)
      lowered = false
      if battle.pbRandom(100) < 30
        lowered = target.pbLowerStatStageByAbility(:ACCURACY, 1, user, true, false)
      end
      ChrookedLog.line("[chrooked:exhaust] OBS ability=true move=#{move.id} contact=true lowered=#{lowered}")
    }
  )
  ($chrooked_selftest_cases ||= {})["exhaust"] = {
    ability: :EXHAUST, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    hit_rolls: [[:TACKLE, {kind: :stat, rate: 0.3}], [:WATERGUN, {kind: :stat, rate: 0}],
                [:TACKLE, {kind: :stat, rate: 0, target_stages: {ACCURACY: -6}}]],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:exhaust] installed on OnDealingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:exhaust] ERROR #{e.class}: #{e.message}")
end
