# chrooked:starfall
# ---------------------------------------------------------------------------
# Ruleset behavior "starfall": its special moves gain 20% per consecutive prior round in
# which it dealt damage with a move, up to 60% (1.0, 1.2, 1.4, 1.6, then 1.6).
#
# HAND-WRITTEN (mjolnir NV-27). The streak N (0 to 3) and this round's "dealt damage"
# live in the battler's chrooked_state (emptied on entry, so switching resets N; see
# chrooked_coilup.rb).
#   - OnDealingHit: a hit that dealt damage marks the round (any category).
#   - EndOfRoundEffect: a marked round raises N (capped at 3); any other round (a
#     status move, a miss, a flinch, sleep) resets it to 0.
#   - DamageCalcFromUser: a special move's power x(1 + 0.2 N).
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:starfall] OBS move=<ID> ability=true streak=<n> special=<bool>   each damage calc (EST from the AI)
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
  ChrookedLog.line("[chrooked:starfall] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromUser[:STARFALL].nil?}")
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
  Battle::AbilityEffects::OnDealingHit.add(:STARFALL,
    proc { |ability, user, target, move, battle|
      user.chrooked_state[:starfall_hit] = true
    }
  )
  Battle::AbilityEffects::EndOfRoundEffect.add(:STARFALL,
    proc { |ability, battler, battle|
      state = battler.chrooked_state
      state[:starfall] = state[:starfall_hit] ? [(state[:starfall] || 0) + 1, 3].min : 0
      state[:starfall_hit] = false
    }
  )
  Battle::AbilityEffects::DamageCalcFromUser.add(:STARFALL,
    proc { |ability, user, target, move, mults, power, type|
      streak = user.chrooked_state[:starfall] || 0
      special = move.specialMove?
      mults[:power_multiplier] *= 1 + 0.2 * streak if special && streak > 0
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:starfall] #{tag} move=#{move.id} ability=true streak=#{streak} special=#{special}")
      end
    }
  )
  # Play rounds (:hit, :status, :switch), then measure move_id: with Starfall and with
  # none, no crit (t.hit). A :hit round hands a Psybeam hit to OnDealingHit.
  chrooked_starfall_after = lambda do |t, spec, rounds, move_id|
    b, holder, foe = t.pair(spec, move_id)
    holder.ability = spec[:ability]
    psybeam = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:PSYBEAM))
    rounds.each do |round|
      holder.pbInitEffects(false) if round == :switch
      next if round == :switch
      Battle::AbilityEffects.triggerOnDealingHit(holder.ability, holder, foe, psybeam, b) if round == :hit
      Battle::AbilityEffects.triggerEndOfRoundEffect(holder.ability, holder, b)
    end
    streak = holder.chrooked_state[:starfall] || 0
    with = t.hit(b, holder, foe, move_id)
    holder.ability = nil
    none = t.hit(b, holder, foe, move_id)
    "move=#{move_id} streak=#{streak} with=#{with} none=#{none} boosted=#{with > none} " \
    "ratio=#{format('%.3f', with.to_f / none)}"
  end
  ($chrooked_selftest_cases ||= {})["starfall"] = {
    ability: :STARFALL, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["first", ->(t, spec) { chrooked_starfall_after.call(t, spec, [], :PSYBEAM) }],
      ["second", ->(t, spec) { chrooked_starfall_after.call(t, spec, [:hit], :PSYBEAM) }],
      ["fourth", ->(t, spec) { chrooked_starfall_after.call(t, spec, [:hit, :hit, :hit], :PSYBEAM) }],
      ["fifth", ->(t, spec) { chrooked_starfall_after.call(t, spec, [:hit, :hit, :hit, :hit], :PSYBEAM) }],
      ["after_recover", ->(t, spec) { chrooked_starfall_after.call(t, spec, [:hit, :hit, :status], :PSYBEAM) }],
      ["after_switch", ->(t, spec) {
        chrooked_starfall_after.call(t, spec, [:hit, :hit, :hit, :switch], :PSYBEAM)
      }],
      ["physical", ->(t, spec) { chrooked_starfall_after.call(t, spec, [:hit, :hit, :hit], :TACKLE) }]
    ],
    without: [],
    fight: [:PSYBEAM, :TACKLE]
  }
  ChrookedLog.line("[chrooked:starfall] installed on OnDealingHit, EndOfRoundEffect and DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:starfall] ERROR #{e.class}: #{e.message}")
end
