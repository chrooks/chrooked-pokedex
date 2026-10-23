# chrooked:bonebreaker
# ---------------------------------------------------------------------------
# Ruleset behavior "bonebreaker": its bone moves deal 1.2x damage and ignore type
# immunities: a 0x matchup becomes 1x, Ground connects with an airborne or Levitate
# target, and an ability that would absorb the move does not.
#
# HAND-WRITTEN (mjolnir NV-30). A bone move carries the Ruleset's bone flag, written
# to Nova as the custom flag Bone (vocab.py).
#   - DamageCalcFromUser: a 1.2x power multiplier on a bone move.
#   - Battle::Move#pbCalcTypeModSingle: a type slot that would make the holder's bone
#     move ineffective counts as neutral, as Scrappy turns Ghost's.
#   - Battle::Battler#pbSuccessCheckAgainstTarget_TargetImmunityByBeingAirborne?: no
#     airborne miss for the holder's bone move.
#   - Battle::Move#pbImmunityByAbility: no ability immunity to the holder's bone move
#     (Earth Eater, Levitate's kin among the absorbers).
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:bonebreaker] OBS move=<ID> ability=true bone=<bool>   each damage calc (EST from the AI)
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

module ChrookedBoneBreaker
  def self.breaks?(user, move)
    user.respond_to?(:hasActiveAbility?) && user.hasActiveAbility?(:BONEBREAKER) &&
      move.flags.any? { |f| f[/^Bone$/i] }
  end
end

begin
  ChrookedLog.line("[chrooked:bonebreaker] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromUser[:BONEBREAKER].nil?}")
  Battle::AbilityEffects::DamageCalcFromUser.add(:BONEBREAKER,
    proc { |ability, user, target, move, mults, power, type|
      bone = move.flags.any? { |f| f[/^Bone$/i] }
      mults[:power_multiplier] *= 1.2 if bone
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:bonebreaker] #{tag} move=#{move.id} ability=true bone=#{bone}")
      end
    }
  )
  Battle::Move.class_eval do
    unless method_defined?(:chrooked_bonebreaker_pbCalcTypeModSingle)
      alias_method :chrooked_bonebreaker_pbCalcTypeModSingle, :pbCalcTypeModSingle
      def pbCalcTypeModSingle(moveType, defType, user, target)
        ret = chrooked_bonebreaker_pbCalcTypeModSingle(moveType, defType, user, target)
        return ret if ret != Effectiveness::INEFFECTIVE_MULTIPLIER || !ChrookedBoneBreaker.breaks?(user, self)
        Effectiveness::NORMAL_EFFECTIVE_MULTIPLIER
      end
    end
    unless method_defined?(:chrooked_bonebreaker_pbImmunityByAbility)
      alias_method :chrooked_bonebreaker_pbImmunityByAbility, :pbImmunityByAbility
      def pbImmunityByAbility(user, target, show_message)
        return false if ChrookedBoneBreaker.breaks?(user, self)
        chrooked_bonebreaker_pbImmunityByAbility(user, target, show_message)
      end
    end
  end
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_bonebreaker_airborne_immunity?)
      alias_method :chrooked_bonebreaker_airborne_immunity?, :pbSuccessCheckAgainstTarget_TargetImmunityByBeingAirborne?
      def pbSuccessCheckAgainstTarget_TargetImmunityByBeingAirborne?(move, user, target, targets, typeMod, show_message)
        return false if ChrookedBoneBreaker.breaks?(user, move)
        chrooked_bonebreaker_airborne_immunity?(move, user, target, targets, typeMod, show_message)
      end
    end
  end
  # The holder's move into a target typed or holding an ability: the type multiplier,
  # the ability immunity, the airborne miss, and whether it connects.
  chrooked_bonebreaker_into = lambda do |t, spec, move_id, target_types: nil, target_ability: nil|
    b, holder, target = t.pair(spec, move_id)
    holder.ability = spec[:ability]
    target.ability = target_ability
    if target_types
      target.types = target_types
      target.effects[PBEffects::ExtraType] = nil
    end
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    move.calcType = move.pbCalcType(holder)
    type_mod = move.pbCalcTypeMod(move.calcType, holder, target)
    absorbed = !!move.pbImmunityByAbility(holder, target, false)
    airborne = holder.pbSuccessCheckAgainstTarget_TargetImmunityByBeingAirborne?(move, holder, target, [target],
                                                                                  type_mod, false)
    connects = !Effectiveness.ineffective?(type_mod) && !absorbed && !airborne
    "move=#{move_id} type_mod=#{type_mod} absorbed=#{absorbed} airborne_miss=#{airborne} connects=#{connects}"
  end
  ($chrooked_selftest_cases ||= {})["bonebreaker"] = {
    ability: :BONEBREAKER, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [[:BONERUSH, 1.0], [:TACKLE, 1.0]],
    checks: [
      ["flying", ->(t, spec) { chrooked_bonebreaker_into.call(t, spec, :BONERUSH, target_types: [:FLYING]) }],
      ["levitate_absorb", ->(t, spec) {
        lev = chrooked_bonebreaker_into.call(t, spec, :BONERUSH, target_ability: :LEVITATE)[/connects=(\w+)/, 1]
        eater = chrooked_bonebreaker_into.call(t, spec, :BONERUSH, target_ability: :EARTHEATER)[/connects=(\w+)/, 1]
        "levitate_connects=#{lev} earth_eater_connects=#{eater}"
      }],
      ["tackle_ghost", ->(t, spec) { chrooked_bonebreaker_into.call(t, spec, :TACKLE, target_types: [:GHOST]) }]
    ],
    without: [],
    fight: [:BONERUSH, :TACKLE]
  }
  ChrookedLog.line("[chrooked:bonebreaker] installed on DamageCalcFromUser and three Battle methods")
rescue StandardError => e
  ChrookedLog.error("[chrooked:bonebreaker] ERROR #{e.class}: #{e.message}")
end
