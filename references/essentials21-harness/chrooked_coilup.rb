# chrooked:coilup
# ---------------------------------------------------------------------------
# Ruleset behavior "coilup": on entry it coils; while coiled its biting moves get +1
# priority, and the first biting move that deals damage spends the coil.
#
# HAND-WRITTEN (mjolnir NV-27). The coil lives in the battler's chrooked_state, which
# this port (or any NV-27 port, whichever loads first) adds to Battle::Battler and
# empties in pbInitEffects, so it is gone when the holder leaves and set again when it
# re-enters.
#   - OnSwitchIn: coil (silent).
#   - PriorityChange: +1 for a biting move (bitingMove?, Strong Jaw's test) while coiled.
#   - OnDealingHit: a biting move that dealt damage spends the coil.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:coilup] OBS move=<ID> ability=true coiled=<bool> priority=<n>   each priority check
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
  ChrookedLog.line("[chrooked:coilup] load prior_handler=#{!Battle::AbilityEffects::PriorityChange[:COILUP].nil?}")
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
  Battle::AbilityEffects::OnSwitchIn.add(:COILUP,
    proc { |ability, battler, battle, switch_in|
      battler.chrooked_state[:coilup] = true
    }
  )
  Battle::AbilityEffects::PriorityChange.add(:COILUP,
    proc { |ability, battler, move, pri|
      coiled = !!battler.chrooked_state[:coilup]
      raised = coiled && move.bitingMove?
      ChrookedLog.line("[chrooked:coilup] OBS move=#{move.id} ability=true coiled=#{coiled} " \
                       "priority=#{raised ? pri + 1 : pri}")
      next pri + 1 if raised
    }
  )
  Battle::AbilityEffects::OnDealingHit.add(:COILUP,
    proc { |ability, user, target, move, battle|
      user.chrooked_state[:coilup] = false if move.bitingMove?
    }
  )
  # Enter (fresh), then ask the priority of each move in turn, each used after
  # (:REENTER re-enters: pbInitEffects, then OnSwitchIn).
  chrooked_coilup_turns = lambda do |t, spec, moves|
    b, holder, foe = t.pair(spec, :TACKLE)
    holder.ability = spec[:ability]
    enter = lambda do
      holder.pbInitEffects(false)
      Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
    end
    enter.call
    moves.map do |move_id|
      enter.call if move_id == :REENTER
      next "reentered" if move_id == :REENTER
      move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
      pri = Battle::AbilityEffects.triggerPriorityChange(holder.ability, holder, move, move.pbPriority(holder))
      # A damaging move that lands hands its hit to OnDealingHit; a status move does not.
      Battle::AbilityEffects.triggerOnDealingHit(holder.ability, holder, foe, move, b) if move.damagingMove?
      "#{move_id}:#{pri}"
    end.join(",")
  end
  ($chrooked_selftest_cases ||= {})["coilup"] = {
    ability: :COILUP, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["entry_crunch", ->(t, spec) { "priorities=#{chrooked_coilup_turns.call(t, spec, [:CRUNCH, :CRUNCH])}" }],
      ["glare_first", ->(t, spec) { "priorities=#{chrooked_coilup_turns.call(t, spec, [:GLARE, :CRUNCH, :CRUNCH])}" }],
      ["reentry", ->(t, spec) {
        "priorities=#{chrooked_coilup_turns.call(t, spec, [:CRUNCH, :CRUNCH, :REENTER, :CRUNCH])}"
      }]
    ],
    without: [],
    fight: [:CRUNCH, :GLARE]
  }
  ChrookedLog.line("[chrooked:coilup] installed on OnSwitchIn, PriorityChange and OnDealingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:coilup] ERROR #{e.class}: #{e.message}")
end
