# chrooked:savant
# ---------------------------------------------------------------------------
# Ruleset behavior "savant": the first use of each move since it last entered deals
# 1.3x damage.
#
# HAND-WRITTEN (mjolnir NV-27). The moves it has used live in the battler's
# chrooked_state (emptied on entry; see chrooked_coilup.rb).
#   - DamageCalcFromUser: a 1.3x power multiplier on a move not yet used this stay
#     (every hit of a multi-hit first use).
#   - OnEndOfUsingMove: the move is remembered once it has been used.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:savant] OBS move=<ID> ability=true first_use=<bool>   each damage calc (EST from the AI)
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
  ChrookedLog.line("[chrooked:savant] load prior_handler=#{!Battle::AbilityEffects::DamageCalcFromUser[:SAVANT].nil?}")
  # Per-battler state for the armed and streak abilities (NV-27), emptied on entry.
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_state)
      def chrooked_state
        @chrooked_state ||= {}
      end

      alias_method :chrooked_state_pbInitEffects, :pbInitEffects
      def pbInitEffects(batonPass)
        @chrooked_state = {}
        chrooked_state_pbInitEffects(batonPass)
      end
    end
  end
  Battle::AbilityEffects::DamageCalcFromUser.add(:SAVANT,
    proc { |ability, user, target, move, mults, power, type|
      first = !(user.chrooked_state[:savant] || []).include?(move.id)
      mults[:power_multiplier] *= 1.3 if first
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:savant] #{tag} move=#{move.id} ability=true first_use=#{first}")
      end
    }
  )
  Battle::AbilityEffects::OnEndOfUsingMove.add(:SAVANT,
    proc { |ability, user, targets, move, battle|
      used = (user.chrooked_state[:savant] ||= [])
      used << move.id if !used.include?(move.id)
    }
  )
  # Use moves in turn (:REENTER re-enters), measuring each: with Savant, with none.
  chrooked_savant_turns = lambda do |t, spec, moves|
    b, holder, foe = t.pair(spec, :TACKLE)
    moves.map do |move_id|
      next (holder.pbInitEffects(false); "reentered") if move_id == :REENTER
      holder.ability = nil
      none = t.hit(b, holder, foe, move_id)
      holder.ability = spec[:ability]
      with = t.hit(b, holder, foe, move_id)
      move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
      Battle::AbilityEffects.triggerOnEndOfUsingMove(holder.ability, holder, [foe], move, b)
      "#{move_id}:#{with > none ? 'BOOSTED' : 'NORMAL'}"
    end.join(",")
  end
  ($chrooked_selftest_cases ||= {})["savant"] = {
    ability: :SAVANT, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [[:PSYCHIC, 1.0]],
    checks: [
      ["twice", ->(t, spec) { "uses=#{chrooked_savant_turns.call(t, spec, [:PSYCHIC, :PSYCHIC])}" }],
      ["two_moves", ->(t, spec) { "uses=#{chrooked_savant_turns.call(t, spec, [:PSYCHIC, :SHADOWBALL])}" }],
      ["reentry", ->(t, spec) { "uses=#{chrooked_savant_turns.call(t, spec, [:PSYCHIC, :REENTER, :PSYCHIC])}" }]
    ],
    without: [],
    fight: [:PSYCHIC, :SHADOWBALL]
  }
  ChrookedLog.line("[chrooked:savant] installed on DamageCalcFromUser and OnEndOfUsingMove")
rescue StandardError => e
  ChrookedLog.error("[chrooked:savant] ERROR #{e.class}: #{e.message}")
end
