# chrooked:deadeye
# ---------------------------------------------------------------------------
# Ruleset behavior "deadeye": its non-contact damaging moves never miss and ignore the
# target's raised Defense and Sp. Def (lowered stages still count); a semi-invulnerable
# target (Fly, Dig, Dive) still dodges.
#
# HAND-WRITTEN (mjolnir NV-30).
#   - AccuracyCalcFromUser: base accuracy 0 for a damaging move that makes no contact
#     (pbContactMove?), a certain hit, as No Guard's handler sets it. Nova decides a
#     semi-invulnerable miss before it checks accuracy (pbSuccessCheckAgainstTarget_
#     CanHitSemiInvulnerableTarget?), and only No Guard by name skips that, so Dive
#     still dodges.
#   - Battle::Move#pbGetDefenseStats: for such a move, the target's defensive stage is
#     taken as at most 0, the Unaware clause for raised stages only.
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
  ChrookedLog.line("[chrooked:deadeye] load prior_handler=#{!Battle::AbilityEffects::AccuracyCalcFromUser[:DEADEYE].nil?}")
  Battle::AbilityEffects::AccuracyCalcFromUser.add(:DEADEYE,
    proc { |ability, mods, user, target, move, type|
      mods[:base_accuracy] = 0 if move.damagingMove? && !move.pbContactMove?(user)
    }
  )
  Battle::Move.class_eval do
    unless method_defined?(:chrooked_deadeye_pbGetDefenseStats)
      alias_method :chrooked_deadeye_pbGetDefenseStats, :pbGetDefenseStats
      def pbGetDefenseStats(user, target)
        stat, stage = chrooked_deadeye_pbGetDefenseStats(user, target)
        if damagingMove? && user.hasActiveAbility?(:DEADEYE) && !pbContactMove?(user)
          stage = [stage, Battle::Battler::STAT_STAGE_MAXIMUM].min   # STAT_STAGE_MAXIMUM is stage 0 here
        end
        return stat, stage
      end
    end
  end
  # The holder's move into a target (its stages, ability, weather and Dive set first):
  # a no-crit hit with Deadeye against the same hit at stage 0, and 30 hit checks.
  chrooked_deadeye_shot = lambda do |t, spec, move_id, stages: {}, target_ability: nil, weather: nil,
                                      accuracy: 0, diving: false|
    b, holder, target = t.pair(spec, move_id)
    holder.ability = spec[:ability]
    holder.stages[:ACCURACY] = accuracy
    target.ability = target_ability
    b.field.weather = weather if weather
    stages.each { |stat, n| target.stages[stat] = n }
    with = t.hit(b, holder, target, move_id)
    saved = target.stages.dup
    [:DEFENSE, :SPECIAL_DEFENSE].each { |s| target.stages[s] = 0 }
    at_zero = t.hit(b, holder, target, move_id)
    saved.each { |s, n| target.stages[s] = n }
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    move.calcType = move.pbCalcType(holder)
    target.effects[PBEffects::TwoTurnAttack] = :DIVE if diving
    srand(t::SEED)
    # Nova's two gates for a hit, in its order: the semi-invulnerable one, then per hit.
    hits = 30.times.count do
      holder.pbSuccessCheckAgainstTarget_CanHitSemiInvulnerableTarget?(move, holder, target) &&
        holder.pbSuccessCheckPerHit(move, holder, target)
    end
    "move=#{move_id} with=#{with} at_stage_zero=#{at_zero} same_as_zero=#{with == at_zero} hits=#{hits} " \
    "never_misses=#{hits == 30}"
  end
  ($chrooked_selftest_cases ||= {})["deadeye"] = {
    ability: :DEADEYE, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["hydro_pump_evasive", ->(t, spec) {
        chrooked_deadeye_shot.call(t, spec, :HYDROPUMP, stages: {EVASION: 6}, target_ability: :SANDVEIL,
                                   weather: :Sandstorm)
      }],
      ["snipe_shot_raised", ->(t, spec) { chrooked_deadeye_shot.call(t, spec, :SNIPESHOT, stages: {SPECIAL_DEFENSE: 2}) }],
      ["snipe_shot_lowered", ->(t, spec) {
        chrooked_deadeye_shot.call(t, spec, :SNIPESHOT, stages: {SPECIAL_DEFENSE: -1})
      }],
      ["liquidation_contact", ->(t, spec) {
        chrooked_deadeye_shot.call(t, spec, :LIQUIDATION, stages: {DEFENSE: 2}, accuracy: -2)
      }],
      ["hydro_pump_dive", ->(t, spec) { chrooked_deadeye_shot.call(t, spec, :HYDROPUMP, diving: true) }]
    ],
    without: [],
    fight: [:HYDROPUMP, :SNIPESHOT]
  }
  ChrookedLog.line("[chrooked:deadeye] installed on AccuracyCalcFromUser and Battle::Move#pbGetDefenseStats")
rescue StandardError => e
  ChrookedLog.error("[chrooked:deadeye] ERROR #{e.class}: #{e.message}")
end
