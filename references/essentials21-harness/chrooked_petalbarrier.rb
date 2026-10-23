# chrooked:petalbarrier
# ---------------------------------------------------------------------------
# Ruleset behavior "petalbarrier": it enters wrapped in petals; the next damaging hit
# on it deals half damage, then the petals scatter. They come back only when it
# switches out and in again.
#
# HAND-WRITTEN (mjolnir NV-31). The petals live in the battler's chrooked_state
# (emptied on entry; see chrooked_coilup.rb).
#   - OnSwitchIn: the petals (silent).
#   - DamageCalcFromTarget: x0.5 final damage while the petals hold and the hit is not
#     on a substitute.
#   - OnBeingHit: Nova fires it after a hit that dealt damage and missed any
#     substitute; that hit scatters them, "<holder>'s petals scattered!". A two-hit
#     move's second hit is therefore full.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md. Its checks measure it.
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
  ChrookedLog.line("[chrooked:petalbarrier] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromTarget[:PETALBARRIER].nil?}")
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
  Battle::AbilityEffects::OnSwitchIn.add(:PETALBARRIER,
    proc { |ability, battler, battle, switch_in|
      battler.chrooked_state[:petals] = true
    }
  )
  Battle::AbilityEffects::DamageCalcFromTarget.add(:PETALBARRIER,
    proc { |ability, user, target, move, mults, power, type|
      next if !target.chrooked_state[:petals] || target.damageState.substitute
      mults[:final_damage_multiplier] *= 0.5
    }
  )
  Battle::AbilityEffects::OnBeingHit.add(:PETALBARRIER,
    proc { |ability, user, target, move, battle|
      next if !target.chrooked_state[:petals]
      target.chrooked_state[:petals] = false
      battle.pbShowAbilitySplash(target)
      battle.pbDisplay(_INTL("{1}'s petals scattered!", target.pbThis))
      battle.pbHideAbilitySplash(target)
    }
  )
  # Steps in turn: :ENTER (pbInitEffects and OnSwitchIn), :WAIT (a round with no hit),
  # or a move the foe hits it with (its damage measured, then the hit landed).
  chrooked_petalbarrier_steps = lambda do |t, spec, steps|
    b, foe, holder = t.pair(spec, :TACKLE)
    holder.ability = spec[:ability]
    none_by_move = {}
    steps.map do |step|
      case step
      when :ENTER
        holder.pbInitEffects(false)
        Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
        "enter"
      when :WAIT
        "wait"
      else
        unless none_by_move[step]
          holder.ability = nil
          none_by_move[step] = t.hit(b, foe, holder, step)
          holder.ability = spec[:ability]
        end
        dealt = t.hit(b, foe, holder, step)
        move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(step))
        Battle::AbilityEffects.triggerOnBeingHit(holder.ability, foe, holder, move, b)
        "#{step}:#{dealt * 4 < none_by_move[step] * 3 ? 'HALF' : 'FULL'}"
      end
    end.join(",")
  end
  ($chrooked_selftest_cases ||= {})["petalbarrier"] = {
    ability: :PETALBARRIER, control: nil, user: :SNORLAX, foe: :NUMEL, neutral: true,
    calc: [],
    checks: [
      ["first_hit", ->(t, spec) { "hits=#{chrooked_petalbarrier_steps.call(t, spec, [:ENTER, :SURF])}" }],
      ["second_hit", ->(t, spec) { "hits=#{chrooked_petalbarrier_steps.call(t, spec, [:ENTER, :SURF, :SURF])}" }],
      # A two-hit move: Nova hands each hit to OnBeingHit in turn.
      ["double_kick", ->(t, spec) {
        "hits=#{chrooked_petalbarrier_steps.call(t, spec, [:ENTER, :DOUBLEKICK, :DOUBLEKICK])}"
      }],
      ["no_regrow", ->(t, spec) {
        "hits=#{chrooked_petalbarrier_steps.call(t, spec, [:ENTER, :SURF, :WAIT, :WAIT, :SURF])}"
      }],
      ["reentry", ->(t, spec) {
        "hits=#{chrooked_petalbarrier_steps.call(t, spec, [:ENTER, :SURF, :ENTER, :SURF])}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:petalbarrier] installed on OnSwitchIn, DamageCalcFromTarget and OnBeingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:petalbarrier] ERROR #{e.class}: #{e.message}")
end
