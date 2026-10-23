# chrooked:truant
# ---------------------------------------------------------------------------
# Ruleset behavior "truant": the act-then-loaf rhythm is the game's own, but on a loaf
# turn a status move goes ahead; only a damaging move loafs. A move called by another
# (Metronome) is judged by the move it calls.
#
# HAND-WRITTEN (mjolnir NV-30). Nova flips effects[PBEffects::Truant] in pbTryUseMove
# each time the holder tries to move (true: it acts; false: it loafs, "<holder> is
# loafing around!"), and a recharge turn takes the loaf. Wrapping pbTryUseMove:
#   - on a loaf turn (the flag true before the flip, no recharge pending) with a status
#     move, the flag is set as on an active turn so Nova lets it through, then left
#     false, as Nova leaves it after a loaf, so the next turn acts;
#   - a called move (Nova skips its own checks for those) that is damaging, on a turn
#     the holder loafed into a status move, loafs with Nova's message.
#   - Battle::AI#pbPredictMoveFailure: on a loaf turn the AI expects the holder's
#     damaging moves to fail, so it picks a status move, but only when it has one, so
#     a holder with none does not keep switching out (Nova's note on why its AI ignores
#     Truant).
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:truant] OBS move=<ID> ability=true loaf_turn=<bool> status_move=<bool>   each move it tries
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
  ChrookedLog.line("[chrooked:truant] load prior_wrapper=#{Battle::Battler.method_defined?(:chrooked_truant_pbTryUseMove)}")
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_truant_pbTryUseMove)
      alias_method :chrooked_truant_pbTryUseMove, :pbTryUseMove
      def pbTryUseMove(choice, move, specialUsage, skipStatusFailureChecks)
        return chrooked_truant_pbTryUseMove(choice, move, specialUsage, skipStatusFailureChecks) if !hasActiveAbility?(:TRUANT)
        if skipStatusFailureChecks
          # A called move on a turn it loafed into a status move: a damaging one loafs.
          if move.damagingMove? && @chrooked_truant_loafed == @battle.turnCount
            @battle.pbShowAbilitySplash(self)
            @battle.pbDisplay(_INTL("{1} is loafing around!", pbThis))
            @lastMoveFailed = true
            @battle.pbHideAbilitySplash(self)
            return false
          end
          return chrooked_truant_pbTryUseMove(choice, move, specialUsage, skipStatusFailureChecks)
        end
        loaf_turn = @effects[PBEffects::Truant] && @effects[PBEffects::HyperBeam] == 0
        ChrookedLog.line("[chrooked:truant] OBS move=#{move.id} ability=true loaf_turn=#{!!loaf_turn} " \
                         "status_move=#{move.statusMove?}")
        return chrooked_truant_pbTryUseMove(choice, move, specialUsage, skipStatusFailureChecks) if !loaf_turn || !move.statusMove?
        @effects[PBEffects::Truant] = false   # as on an active turn: Nova flips it to true and lets it act
        @chrooked_truant_loafed = @battle.turnCount
        ret = chrooked_truant_pbTryUseMove(choice, move, specialUsage, skipStatusFailureChecks)
        @effects[PBEffects::Truant] = false   # as Nova leaves it after a loaf: the next turn acts
        ret
      end
    end
  end
  Battle::AI.class_eval do
    unless method_defined?(:chrooked_truant_pbPredictMoveFailure)
      alias_method :chrooked_truant_pbPredictMoveFailure, :pbPredictMoveFailure
      def pbPredictMoveFailure
        b = @user.battler
        if b.hasActiveAbility?(:TRUANT) && b.effects[PBEffects::Truant] && b.effects[PBEffects::HyperBeam] == 0 &&
           @move.move.damagingMove? && b.moves.any? { |m| m&.statusMove? && m.pp > 0 }
          return true
        end
        chrooked_truant_pbPredictMoveFailure
      end
    end
  end
  # The holder on a loaf turn (or an active one) tries move_id; whether it acted, and the
  # flag after (false: the next turn acts).
  chrooked_truant_try = lambda do |t, spec, move_id, loaf_turn: true, recharge: false|
    b, holder, foe = t.pair(spec, move_id)
    holder.ability = spec[:ability]
    holder.effects[PBEffects::Truant] = loaf_turn
    holder.effects[PBEffects::HyperBeam] = 1 if recharge
    move = holder.moves[0]
    acted = holder.pbTryUseMove([:UseMove, 0, move, foe.index, 0], move, false, false)
    "move=#{move_id} acted=#{acted} next_turn_acts=#{!holder.effects[PBEffects::Truant]}"
  end
  ($chrooked_selftest_cases ||= {})["truant"] = {
    ability: :TRUANT, control: nil, user: :SNORLAX, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["bulk_up", ->(t, spec) { chrooked_truant_try.call(t, spec, :BULKUP) }],
      ["double_edge", ->(t, spec) { chrooked_truant_try.call(t, spec, :DOUBLEEDGE) }],
      # After Giga Impact on an active turn: the flag says loaf, and a recharge is pending.
      ["recharge", ->(t, spec) { chrooked_truant_try.call(t, spec, :BULKUP, recharge: true) }],
      # Metronome on a loaf turn goes ahead; the damaging move it calls then loafs.
      ["metronome", ->(t, spec) {
        b, holder, foe = t.pair(spec, :METRONOME)
        holder.ability = spec[:ability]
        holder.effects[PBEffects::Truant] = true
        metronome = holder.moves[0]
        went = holder.pbTryUseMove([:UseMove, 0, metronome, foe.index, 0], metronome, false, false)
        called = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:TACKLE))
        called_acts = holder.pbTryUseMove([:UseMove, -1, called, foe.index, 0], called, true, true)
        "metronome_acted=#{went} called_damaging_acted=#{called_acts}"
      }],
      ["ai_slack_off", ->(t, spec) {
        b = t.battle(t.mon(spec[:user], [:DOUBLEEDGE, :SLACKOFF]), t.mon(spec[:foe], [:TACKLE]))
        b.pbCreateBattler(0, b.pbParty(0)[0], 0)
        b.pbCreateBattler(1, b.pbParty(1)[0], 0)
        holder = b.battlers[0]
        holder.ability = spec[:ability]
        holder.hp = holder.totalhp / 2   # Slack Off has something to heal
        holder.effects[PBEffects::Truant] = true
        ai = b.instance_variable_get(:@battleAI)
        ai.create_ai_objects
        ai.set_up(holder.index)
        fails = holder.moves.map do |m|
          ai.set_up_move_check(m)
          "#{m.id}:#{ai.pbPredictMoveFailure}"
        end
        "predicted_fail=#{fails.join(',')}"
      }],
      ["not_truant", ->(t, spec) {
        b, user, foe = t.pair(spec, :DOUBLEEDGE)
        user.ability = nil
        move = user.moves[0]
        "acted=#{user.pbTryUseMove([:UseMove, 0, move, foe.index, 0], move, false, false)}"
      }]
    ],
    without: [],
    fight: [:BULKUP, :DOUBLEEDGE]
  }
  ChrookedLog.line("[chrooked:truant] installed on Battler#pbTryUseMove and Battle::AI#pbPredictMoveFailure")
rescue StandardError => e
  ChrookedLog.error("[chrooked:truant] ERROR #{e.class}: #{e.message}")
end
