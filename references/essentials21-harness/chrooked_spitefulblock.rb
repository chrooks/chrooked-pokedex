# chrooked:spitefulblock
# ---------------------------------------------------------------------------
# Ruleset behavior "spitefulblock": surviving a damaging hit arms it; its next Dark-type
# move deals 1.3x damage and spends it.
#
# HAND-WRITTEN (mjolnir NV-27). The flag lives in the battler's chrooked_state
# (emptied on entry; see chrooked_coilup.rb).
#   - OnBeingHit: Nova fires it after a hit that dealt damage and missed any
#     substitute; one the holder survives arms the flag.
#   - DamageCalcFromUser: a 1.3x power multiplier on a Dark move (as used) while armed.
#   - OnEndOfUsingMove: a damaging Dark move spends it. Spending it here rather than
#     in the damage calc keeps the AI's damage estimates from spending it.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:spitefulblock] OBS move=<ID> ability=true armed=<bool> type=<TYPE>   each damage calc (EST from the AI)
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
  ChrookedLog.line("[chrooked:spitefulblock] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromUser[:SPITEFULBLOCK].nil?}")
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
  Battle::AbilityEffects::OnBeingHit.add(:SPITEFULBLOCK,
    proc { |ability, user, target, move, battle|
      target.chrooked_state[:spitefulblock] = true if !target.fainted?
    }
  )
  Battle::AbilityEffects::DamageCalcFromUser.add(:SPITEFULBLOCK,
    proc { |ability, user, target, move, mults, power, type|
      armed = !!user.chrooked_state[:spitefulblock]
      mults[:power_multiplier] *= 1.3 if armed && type == :DARK
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:spitefulblock] #{tag} move=#{move.id} ability=true armed=#{armed} type=#{type}")
      end
    }
  )
  Battle::AbilityEffects::OnEndOfUsingMove.add(:SPITEFULBLOCK,
    proc { |ability, user, targets, move, battle|
      user.chrooked_state[:spitefulblock] = false if move.damagingMove? && move.calcType == :DARK
    }
  )
  # Steps in turn: :HIT (the holder survives a foe's Tackle) or a move it uses,
  # measured (with Spiteful Block, with none) and then used.
  chrooked_spitefulblock_turns = lambda do |t, spec, steps|
    b, holder, foe = t.pair(spec, :TACKLE)
    holder.ability = spec[:ability]
    steps.map do |step|
      if step == :HIT
        tackle = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:TACKLE))
        Battle::AbilityEffects.triggerOnBeingHit(holder.ability, foe, holder, tackle, b)
        next "hit"
      end
      with = t.hit(b, holder, foe, step)
      holder.ability = nil
      none = t.hit(b, holder, foe, step)
      holder.ability = spec[:ability]
      move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(step))
      move.calcType = move.pbCalcType(holder)
      Battle::AbilityEffects.triggerOnEndOfUsingMove(holder.ability, holder, [foe], move, b)
      "#{step}:#{with > none ? 'BOOSTED' : 'NORMAL'}"
    end.join(",")
  end
  ($chrooked_selftest_cases ||= {})["spitefulblock"] = {
    ability: :SPITEFULBLOCK, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["hit_then_bite", ->(t, spec) { "steps=#{chrooked_spitefulblock_turns.call(t, spec, [:HIT, :BITE, :BITE])}" }],
      ["no_hit", ->(t, spec) { "steps=#{chrooked_spitefulblock_turns.call(t, spec, [:BITE])}" }],
      ["hit_then_tackle", ->(t, spec) {
        "steps=#{chrooked_spitefulblock_turns.call(t, spec, [:HIT, :TACKLE, :BITE])}"
      }]
    ],
    without: [],
    fight: [:BITE, :TACKLE]
  }
  ChrookedLog.line("[chrooked:spitefulblock] installed on OnBeingHit, DamageCalcFromUser and OnEndOfUsingMove")
rescue StandardError => e
  ChrookedLog.error("[chrooked:spitefulblock] ERROR #{e.class}: #{e.message}")
end
