# chrooked:finishingkick
# ---------------------------------------------------------------------------
# Ruleset ability "finishingkick": its own 1.2x on contact moves at +1 Speed or
# higher, plus Speed Boost (the Ruleset composes it as finishingkick + speedboost).
#
# HAND-WRITTEN WHOLE (mjolnir NV-27), as Thorned Succulent is (NV-26): an ability that
# lists itself cannot be a generated composition, so this file is the whole ability.
#   - its own part: DamageCalcFromUser, a 1.2x power multiplier on a damaging contact
#     move (pbContactMove?) while its Speed stage is +1 or more;
#   - Speed Boost: Nova's EndOfRoundEffect handler, copied (Speed +1 at the end of each
#     round after the one it entered);
#   - by name: the holder answers hasActiveAbility?(:SPEEDBOOST), as a composed battler
#     answers for its parts, so the AI sees it.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:finishingkick] OBS move=<ID> ability=true contact=<bool> speed_stage=<n>   each damage calc (EST from the AI)
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
  ChrookedLog.line("[chrooked:finishingkick] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromUser[:FINISHINGKICK].nil?}")
  Battle::AbilityEffects::DamageCalcFromUser.add(:FINISHINGKICK,
    proc { |ability, user, target, move, mults, power, type|
      contact = move.pbContactMove?(user)
      stage = user.stages[:SPEED]
      mults[:power_multiplier] *= 1.2 if contact && stage >= 1
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:finishingkick] #{tag} move=#{move.id} ability=true contact=#{contact} " \
                         "speed_stage=#{stage}")
      end
    }
  )
  Battle::AbilityEffects::EndOfRoundEffect.copy(:SPEEDBOOST, :FINISHINGKICK)
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_finishingkick_hasActiveAbility?)
      alias_method :chrooked_finishingkick_hasActiveAbility?, :hasActiveAbility?
      def hasActiveAbility?(check_ability, ignore_fainted = false)
        asked = check_ability.is_a?(Array) ? check_ability : [check_ability]
        if asked.include?(:SPEEDBOOST) && chrooked_finishingkick_hasActiveAbility?(:FINISHINGKICK, ignore_fainted)
          return true
        end
        chrooked_finishingkick_hasActiveAbility?(check_ability, ignore_fainted)
      end
    end
  end
  # move_id at the given Speed stage: with Finishing Kick and with none, no crit.
  chrooked_finishingkick_hit = lambda do |t, spec, move_id, stage|
    b, holder, foe = t.pair(spec, move_id)
    holder.stages[:SPEED] = stage
    holder.ability = spec[:ability]
    with = t.hit(b, holder, foe, move_id)
    holder.ability = nil
    none = t.hit(b, holder, foe, move_id)
    "move=#{move_id} speed_stage=#{stage} with=#{with} none=#{none} boosted=#{with > none}"
  end
  ($chrooked_selftest_cases ||= {})["finishingkick"] = {
    ability: :FINISHINGKICK, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["quick_attack_0", ->(t, spec) { chrooked_finishingkick_hit.call(t, spec, :QUICKATTACK, 0) }],
      ["wild_charge_1", ->(t, spec) { chrooked_finishingkick_hit.call(t, spec, :WILDCHARGE, 1) }],
      ["thunderbolt_2", ->(t, spec) { chrooked_finishingkick_hit.call(t, spec, :THUNDERBOLT, 2) }],
      ["crunch_6", ->(t, spec) { chrooked_finishingkick_hit.call(t, spec, :CRUNCH, 6) }],
      # Beside the test cases: Speed Boost's end of round, and the name it answers to.
      ["speed_boost", ->(t, spec) {
        b, holder, _foe = t.pair(spec, :TACKLE)
        holder.ability = spec[:ability]
        holder.turnCount = 1
        b.choices[holder.index] = [:UseMove, 0, nil, -1, 0]
        Battle::AbilityEffects.triggerEndOfRoundEffect(holder.ability, holder, b)
        "speed_stage=#{holder.stages[:SPEED]} speed_boost=#{holder.hasActiveAbility?(:SPEEDBOOST)}"
      }]
    ],
    without: [],
    fight: [:QUICKATTACK, :WILDCHARGE, :THUNDERBOLT, :CRUNCH]
  }
  ChrookedLog.line("[chrooked:finishingkick] installed: DamageCalcFromUser, Speed Boost copied")
rescue StandardError => e
  ChrookedLog.error("[chrooked:finishingkick] ERROR #{e.class}: #{e.message}")
end
