# chrooked:truant
# Truant — "Loafs every other turn, but may still use status moves while loafing."
#   Elite Redux rule. Vanilla blocks EVERY move on the loaf turn
#   (Battler.rb:5747, inside pbTryUseMove). Now only damaging moves are blocked.
#   The active/loaf toggle at end of round (Battle.rb:7462) is untouched, so the
#   rhythm is exactly vanilla.
#
# Vanilla's loaf check is INLINE inside pbTryUseMove, not a method of its own.
# This wrapper prepends pbTryUseMove and, only for a status move on a loaf turn,
# clears effects[:Truant] for the duration of that one call so vanilla's check
# falls through; an ensure puts the flag back, so nothing outside the call sees
# it (same wrap-and-restore as chrooked_frostbite.rb). Nothing else in
# pbTryUseMove reads the flag.
#
# What stays vanilla, by construction:
#   - Recharge (Hyper Beam / Giga Impact): the "must recharge" return comes
#     BEFORE the loaf check, so recharge still eats the loaf turn.
#   - Locked / two-turn moves continue as their damaging move, so they loaf.
#   - Called moves (Metronome, Sleep Talk, Nature Power, Assist, Dancer) re-enter
#     pbTryUseMove through pbUseMoveSimple AFTER this call restored the flag, so
#     a damaging called move still loafs; a status one goes through.
#   - "Status" is the engine's own pbIsStatus?, so Gravity / Topsy-Turvy on Deep
#     Earth (damaging there) loaf, like any other damaging move.
#
# AI: getModifiedMoveScore is prepended so a Truant holder scores every damaging
# move 0 on its own loaf turn (it cannot land). Any status move scoring above 0
# then wins; with none, the AI falls back to its "only bad options" path.
#
# Test cases (drive in-game — the harness can't run a battle):
#   - Slaking loaf turn, picks Bulk Up  => Bulk Up works; next turn is active.
#   - Slaking loaf turn, picks Double-Edge => "Slaking is loafing around!"
#   - Slaking uses Giga Impact, next turn => "must recharge", no move.
#   - Trainer Slaking with Slack Off on its loaf turn => AI picks Slack Off.
module ChrookedTruantStatusOnLoaf
  def pbTryUseMove(*args, **kwargs)
    basemove = args[1]
    loafing_status = @effects && @effects[:Truant] && self.ability == :TRUANT &&
                     basemove.respond_to?(:pbIsStatus?) && basemove.pbIsStatus?
    return super unless loafing_status

    @effects[:Truant] = false
    begin
      super
    ensure
      @effects[:Truant] = true
    end
  end
end
PokeBattle_Battler.prepend(ChrookedTruantStatusOnLoaf) if defined?(PokeBattle_Battler)

if defined?(PokeBattle_AI)
  module ChrookedTruantAI
    def getModifiedMoveScore(finalscores, scoreindex, opponent)
      score = super
      begin
        loafing = @attacker && @attacker.effects[:Truant] && @attacker.ability == :TRUANT
        # min keeps a vanilla -1 ("actively harmful") below the other zeros.
        loafing && @move && @move.pbIsDamaging? ? [score, 0].min : score
      rescue StandardError
        score # a mispredicted score is survivable; a crashed AI turn is not
      end
    end
  end
  PokeBattle_AI.prepend(ChrookedTruantAI)
end
