# chrooked:stampede
# ---------------------------------------------------------------------------
# Ruleset behavior "stampede": knocking a foe out arms it; while armed its next contact
# move gets +1 priority, and using that contact move spends it.
#
# HAND-WRITTEN (mjolnir NV-27). The flag lives in the battler's chrooked_state
# (emptied on entry; see chrooked_coilup.rb).
#   - OnEndOfUsingMove, Moxie's shape: a contact move spends the flag first; then a
#     target its damage state marks fainted arms it, unless that ended the battle.
#   - PriorityChange: +1 for a contact move (pbContactMove?) while armed.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:stampede] OBS move=<ID> ability=true armed=<bool> priority=<n>   each priority check
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
  ChrookedLog.line("[chrooked:stampede] load prior_handler=#{!Battle::AbilityEffects::PriorityChange[:STAMPEDE].nil?}")
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
  Battle::AbilityEffects::OnEndOfUsingMove.add(:STAMPEDE,
    proc { |ability, user, targets, move, battle|
      user.chrooked_state[:stampede] = false if move.pbContactMove?(user)
      next if battle.pbAllFainted?(user.idxOpposingSide)
      user.chrooked_state[:stampede] = true if targets.any? { |b| b.damageState.fainted }
    }
  )
  Battle::AbilityEffects::PriorityChange.add(:STAMPEDE,
    proc { |ability, battler, move, pri|
      armed = !!battler.chrooked_state[:stampede]
      raised = armed && move.pbContactMove?(battler)
      ChrookedLog.line("[chrooked:stampede] OBS move=#{move.id} ability=true armed=#{armed} " \
                       "priority=#{raised ? pri + 1 : pri}")
      next pri + 1 if raised
    }
  )
  # Each move in turn: its priority, then it is used (:KO = a Tackle that knocks the
  # foe out, its damage state marked fainted and the foe kept, so the battle goes on).
  chrooked_stampede_turns = lambda do |t, spec, moves|
    b, holder, foe = t.pair(spec, :TACKLE)
    holder.ability = spec[:ability]
    moves.map do |entry|
      move_id = entry == :KO ? :TACKLE : entry
      move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
      pri = Battle::AbilityEffects.triggerPriorityChange(holder.ability, holder, move, move.pbPriority(holder))
      foe.damageState.reset
      foe.damageState.fainted = (entry == :KO)
      Battle::AbilityEffects.triggerOnEndOfUsingMove(holder.ability, holder, [foe], move, b)
      foe.damageState.reset
      "#{entry}:#{pri}"
    end.join(",")
  end
  ($chrooked_selftest_cases ||= {})["stampede"] = {
    ability: :STAMPEDE, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["ko_then_contact", ->(t, spec) { "priorities=#{chrooked_stampede_turns.call(t, spec, [:KO, :TACKLE, :TACKLE])}" }],
      ["ko_then_water_gun", ->(t, spec) {
        "priorities=#{chrooked_stampede_turns.call(t, spec, [:KO, :WATERGUN, :TACKLE])}"
      }],
      ["no_ko", ->(t, spec) { "priorities=#{chrooked_stampede_turns.call(t, spec, [:TACKLE, :TACKLE])}" }]
    ],
    without: [],
    fight: [:TACKLE, :WATERGUN]
  }
  ChrookedLog.line("[chrooked:stampede] installed on OnEndOfUsingMove and PriorityChange")
rescue StandardError => e
  ChrookedLog.error("[chrooked:stampede] ERROR #{e.class}: #{e.message}")
end
