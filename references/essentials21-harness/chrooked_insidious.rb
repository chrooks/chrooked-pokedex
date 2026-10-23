# chrooked:insidious
# ---------------------------------------------------------------------------
# Ruleset behavior "insidious": using a status move raises the user's Speed by one
# stage.
#
# HAND-WRITTEN (mjolnir NV-22). Seam Battle::AbilityEffects::OnEndOfUsingMove, Moxie's
# registry: after a status move, Speed +1 by pbRaiseStatStageByAbility, while it can
# rise.
#     [chrooked:insidious] OBS ability=true move=<ID> status_move=<bool> raised=<bool>   after each move
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
  ChrookedLog.line("[chrooked:insidious] load prior_handler=#{!Battle::AbilityEffects::OnEndOfUsingMove[:INSIDIOUS].nil?}")
  Battle::AbilityEffects::OnEndOfUsingMove.add(:INSIDIOUS,
    proc { |ability, user, targets, move, battle|
      raised = false
      if move.statusMove? && user.pbCanRaiseStatStage?(:SPEED, user)
        raised = user.pbRaiseStatStageByAbility(:SPEED, 1, user)
      end
      ChrookedLog.line("[chrooked:insidious] OBS ability=true move=#{move.id} status_move=#{move.statusMove?} raised=#{raised}")
    }
  )
  ($chrooked_selftest_cases ||= {})["insidious"] = {
    ability: :INSIDIOUS, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    used: [[:SWORDSDANCE, {}], [:TACKLE, {}], [:SWORDSDANCE, {stages: {SPEED: 6}}]],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:insidious] installed on OnEndOfUsingMove")
rescue StandardError => e
  ChrookedLog.error("[chrooked:insidious] ERROR #{e.class}: #{e.message}")
end
