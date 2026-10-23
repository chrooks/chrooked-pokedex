# chrooked:sporulation
# ---------------------------------------------------------------------------
# Ruleset behavior "sporulation": on entry it readies a burst; while ready, Spore gets
# +1 priority, and using Spore spends it until the holder re-enters.
#
# HAND-WRITTEN (mjolnir NV-27). The flag lives in the battler's chrooked_state
# (emptied on entry; see chrooked_coilup.rb).
#   - OnSwitchIn: ready (silent).
#   - PriorityChange: +1 for Spore while ready.
#   - OnEndOfUsingMove: using Spore spends it, whatever Spore did.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:sporulation] OBS move=<ID> ability=true ready=<bool> priority=<n>   each priority check
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
  ChrookedLog.line("[chrooked:sporulation] load prior_handler=" \
                   "#{!Battle::AbilityEffects::PriorityChange[:SPORULATION].nil?}")
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
  Battle::AbilityEffects::OnSwitchIn.add(:SPORULATION,
    proc { |ability, battler, battle, switch_in|
      battler.chrooked_state[:sporulation] = true
    }
  )
  Battle::AbilityEffects::PriorityChange.add(:SPORULATION,
    proc { |ability, battler, move, pri|
      ready = !!battler.chrooked_state[:sporulation]
      raised = ready && move.id == :SPORE
      ChrookedLog.line("[chrooked:sporulation] OBS move=#{move.id} ability=true ready=#{ready} " \
                       "priority=#{raised ? pri + 1 : pri}")
      next pri + 1 if raised
    }
  )
  Battle::AbilityEffects::OnEndOfUsingMove.add(:SPORULATION,
    proc { |ability, user, targets, move, battle|
      user.chrooked_state[:sporulation] = false if move.id == :SPORE
    }
  )
  # Enter, then each move's priority, each used after (:REENTER re-enters).
  chrooked_sporulation_turns = lambda do |t, spec, moves|
    b, holder, foe = t.pair(spec, :TACKLE)
    holder.ability = spec[:ability]
    enter = lambda do
      holder.pbInitEffects(false)
      Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
    end
    enter.call
    moves.map do |move_id|
      next (enter.call; "reentered") if move_id == :REENTER
      move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
      pri = Battle::AbilityEffects.triggerPriorityChange(holder.ability, holder, move, move.pbPriority(holder))
      Battle::AbilityEffects.triggerOnEndOfUsingMove(holder.ability, holder, [foe], move, b)
      "#{move_id}:#{pri}"
    end.join(",")
  end
  ($chrooked_selftest_cases ||= {})["sporulation"] = {
    ability: :SPORULATION, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["first_spore", ->(t, spec) { "priorities=#{chrooked_sporulation_turns.call(t, spec, [:SPORE])}" }],
      ["second_spore", ->(t, spec) { "priorities=#{chrooked_sporulation_turns.call(t, spec, [:SPORE, :SPORE])}" }],
      ["sleep_powder", ->(t, spec) {
        "priorities=#{chrooked_sporulation_turns.call(t, spec, [:SLEEPPOWDER, :SPORE])}"
      }],
      ["reentry", ->(t, spec) {
        "priorities=#{chrooked_sporulation_turns.call(t, spec, [:SPORE, :REENTER, :SPORE])}"
      }]
    ],
    without: [],
    fight: [:SPORE, :TACKLE]
  }
  ChrookedLog.line("[chrooked:sporulation] installed on OnSwitchIn, PriorityChange and OnEndOfUsingMove")
rescue StandardError => e
  ChrookedLog.error("[chrooked:sporulation] ERROR #{e.class}: #{e.message}")
end
