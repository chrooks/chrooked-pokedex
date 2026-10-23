# chrooked:amplifier
# ---------------------------------------------------------------------------
# Ruleset behavior "amplifier": sound moves deal 1.3x damage, and its single-target
# damaging sound moves hit all adjacent foes.
#
# HAND-WRITTEN (mjolnir NV-29).
#   - DamageCalcFromUser: a 1.3x power multiplier on a sound move (soundMove?).
#   - Battle::Move#pbTarget: for the holder, a damaging sound move that targets one foe
#     targets all near foes (:AllNearFoes) instead, so Nova picks every adjacent foe, and
#     its spread-move damage cut applies when there are several.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:amplifier] OBS move=<ID> ability=true sound=<bool>   each damage calc (EST from the AI)
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
  ChrookedLog.line("[chrooked:amplifier] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromUser[:AMPLIFIER].nil?}")
  Battle::AbilityEffects::DamageCalcFromUser.add(:AMPLIFIER,
    proc { |ability, user, target, move, mults, power, type|
      sound = move.soundMove?
      mults[:power_multiplier] *= 1.3 if sound
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:amplifier] #{tag} move=#{move.id} ability=true sound=#{sound}")
      end
    }
  )
  Battle::Move.class_eval do
    unless method_defined?(:chrooked_amplifier_pbTarget)
      alias_method :chrooked_amplifier_pbTarget, :pbTarget
      def pbTarget(user)
        target = chrooked_amplifier_pbTarget(user)
        return target if !soundMove? || !damagingMove? || !target.can_target_one_foe?
        return target if !user.respond_to?(:hasActiveAbility?) || !user.hasActiveAbility?(:AMPLIFIER)
        GameData::Target.get(:AllNearFoes)
      end
    end
  end
  ($chrooked_selftest_cases ||= {})["amplifier"] = {
    ability: :AMPLIFIER, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [[:HYPERVOICE, 1.0], [:TACKLE, 1.0]],
    without: [:HYPERVOICE],
    checks: [
      # Doubles: the holder's Bug Buzz, a single-target sound move, and a non-holder's.
      ["doubles", ->(t, spec) {
        b, holder, ally, _foe, _foe2 = t.doubles(spec, [:BUGBUZZ])
        holder.ability = spec[:ability]
        move = holder.moves[0]
        "holder_target=#{move.pbTarget(holder).id} ally_target=#{move.pbTarget(ally).id}"
      }]
    ],
    fight: [:HYPERVOICE, :TACKLE]
  }
  ChrookedLog.line("[chrooked:amplifier] installed on DamageCalcFromUser and Battle::Move#pbTarget")
rescue StandardError => e
  ChrookedLog.error("[chrooked:amplifier] ERROR #{e.class}: #{e.message}")
end
