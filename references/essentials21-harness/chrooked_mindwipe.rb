# chrooked:mindwipe
# ---------------------------------------------------------------------------
# Ruleset behavior "mindwipe": each damaging hit erases 4 PP from the target's last
# used move.
#
# HAND-WRITTEN (mjolnir NV-22). Seam Battle::AbilityEffects::OnDealingHit, so once per
# hit that dealt damage. Spite's own reduction and message
# (LowerPPOfTargetLastMoveBy4): min(4, PP left), nothing when the target has not
# moved or that move has no PP.
#     [chrooked:mindwipe] OBS ability=true move=<ID> erased=<n>   after a hit with PP to erase
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
  ChrookedLog.line("[chrooked:mindwipe] load prior_on_hit=#{!Battle::AbilityEffects::OnDealingHit[:MINDWIPE].nil?}")
  Battle::AbilityEffects::OnDealingHit.add(:MINDWIPE,
    proc { |ability, user, target, move, battle|
      last = target.pbGetMoveWithID(target.lastRegularMoveUsed)
      next if !last || last.pp == 0 || last.total_pp <= 0
      erased = [4, last.pp].min
      battle.pbShowAbilitySplash(user)
      target.pbSetPP(last, last.pp - erased)
      battle.pbDisplay(_INTL("It reduced the PP of {1} {2} by {3}!", target.pbOfThis(true), last.name, erased))
      battle.pbHideAbilitySplash(user)
      ChrookedLog.line("[chrooked:mindwipe] OBS ability=true move=#{move.id} erased=#{erased}")
    }
  )
  ($chrooked_selftest_cases ||= {})["mindwipe"] = {
    ability: :MINDWIPE, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    pp: [["recover", {last_move: :RECOVER, pp: 10}], ["unmoved", {}], ["empty", {last_move: :RECOVER, pp: 0}],
         ["three_hits", {last_move: :RECOVER, pp: 16, hits: 3}]],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:mindwipe] installed on OnDealingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:mindwipe] ERROR #{e.class}: #{e.message}")
end
