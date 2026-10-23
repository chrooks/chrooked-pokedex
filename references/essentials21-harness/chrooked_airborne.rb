# chrooked:airborne
# ---------------------------------------------------------------------------
# Ruleset behavior "airborne": Aerodynamic (Flying moves absorbed for +1 Speed, single-
# target Flying moves drawn to it in doubles) plus Levitate's Ground immunity.
#
# HAND-WRITTEN (mjolnir NV-29).
#   - MoveImmunity and the Flying draw: as chrooked_aerodynamic.rb (ChrookedDraw).
#   - Levitate: Nova asks hasAirborneAbility?, which asks hasActiveAbility?(:LEVITATE),
#     so the holder answers yes to Levitate by name, and Gravity, Smack Down, Iron Ball,
#     Ingrain, Mold Breaker and Thousand Arrows cancel it exactly as they cancel
#     Levitate. Ground moves get no Speed and no draw.
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

# Draw a single-target move of a type to the holder of an ability, as Nova's Lightning
# Rod does (NV-29; Aerodynamic and Airborne share it). Nova returns from its own
# pbChangeTargets before Lightning Rod when the move cannot be redirected, targets more
# than one foe, or Spotlight or Follow Me decided it, so those are left alone here too.
unless defined?(ChrookedDraw)
  module ChrookedDraw
    def self.draw(battler, ability, type, move, user, targets)
      battle = battler.battle
      target_data = move.pbTarget(user)
      return targets if battle.switching || move.cannotRedirect? || move.targetsPosition?
      return targets if !target_data.can_target_one_foe? || targets.length != 1
      return targets if user.hasActiveAbility?([:PROPELLERTAIL, :STALWART])
      followed = battle.allBattlers.any? do |b|
        b.opposes?(user) && (b.effects[PBEffects::Spotlight] > 0 || b.effects[PBEffects::FollowMe] > 0)
      end
      return targets if followed
      battler.pbChangeTargetByAbility(ability, type, move, user, targets, battle.pbPriority(true),
                                      !target_data.can_choose_distant_target?)
    end
  end
end

begin
  ChrookedLog.line("[chrooked:airborne] load prior_handler=#{!Battle::AbilityEffects::MoveImmunity[:AIRBORNE].nil?}")
  Battle::AbilityEffects::MoveImmunity.add(:AIRBORNE,
    proc { |ability, user, target, move, type, battle, show_message|
      next target.pbMoveImmunityStatRaisingAbility(user, move, type, :FLYING, :SPEED, 1, show_message)
    }
  )
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_airborne_pbChangeTargets)
      alias_method :chrooked_airborne_pbChangeTargets, :pbChangeTargets
      def pbChangeTargets(move, user, targets)
        targets = chrooked_airborne_pbChangeTargets(move, user, targets)
        ChrookedDraw.draw(self, :AIRBORNE, :FLYING, move, user, targets)
      end
    end
    unless method_defined?(:chrooked_airborne_hasActiveAbility?)
      alias_method :chrooked_airborne_hasActiveAbility?, :hasActiveAbility?
      def hasActiveAbility?(check_ability, ignore_fainted = false)
        asked = check_ability.is_a?(Array) ? check_ability : [check_ability]
        if asked.include?(:LEVITATE) && chrooked_airborne_hasActiveAbility?(:AIRBORNE, ignore_fainted)
          return true
        end
        chrooked_airborne_hasActiveAbility?(check_ability, ignore_fainted)
      end
    end
  end
  # The foe's move into the holder (Gravity, Smack Down or Mold Breaker first): the
  # ability's immunity, Nova's airborne Ground check, and the holder's Speed after.
  chrooked_airborne_struck = lambda do |t, spec, move_id, gravity: false, smacked: false, mold_breaker: false|
    b, foe, holder = t.pair(spec, move_id)
    holder.ability = spec[:ability]
    b.field.effects[PBEffects::Gravity] = 5 if gravity
    holder.effects[PBEffects::SmackDown] = true if smacked
    b.moldBreaker = mold_breaker
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    move.calcType = move.pbCalcType(foe)
    immune = !!move.pbImmunityByAbility(foe, holder, true)
    type_mod = move.pbCalcTypeMod(move.calcType, foe, holder)
    grounded_out = foe.pbSuccessCheckAgainstTarget_TargetImmunityByBeingAirborne?(move, foe, holder, [holder],
                                                                                  type_mod, false)
    "move=#{move_id} immune=#{immune} misses_airborne=#{grounded_out} hits=#{!immune && !grounded_out} " \
    "speed=#{holder.stages[:SPEED]}"
  end
  ($chrooked_selftest_cases ||= {})["airborne"] = {
    ability: :AIRBORNE, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["air_slash", ->(t, spec) { chrooked_airborne_struck.call(t, spec, :AIRSLASH) }],
      ["earthquake", ->(t, spec) { chrooked_airborne_struck.call(t, spec, :EARTHQUAKE) }],
      ["earthquake_cancelled", ->(t, spec) {
        hits = [{gravity: true}, {smacked: true}, {mold_breaker: true}].map do |opts|
          chrooked_airborne_struck.call(t, spec, :EARTHQUAKE, **opts)[/hits=(\w+)/, 1]
        end
        "gravity_hits=#{hits[0]} smack_down_hits=#{hits[1]} mold_breaker_hits=#{hits[2]}"
      }],
      ["tackle", ->(t, spec) { chrooked_airborne_struck.call(t, spec, :TACKLE) }],
      ["redirect", ->(t, spec) {
        b, holder, ally, foe, _foe2 = t.doubles(spec)
        holder.ability = spec[:ability]
        # Nova fills the round's speed order (pbPriority) in each attack phase; this
        # throwaway battle has had none, so order it as a round would.
        b.battlers.each_with_index { |x, i| b.pbClearChoice(i) if x }
        b.pbCalculatePriority(true)
        drawn = [:AIRSLASH, :DRILLRUN].map do |move_id|
          move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
          move.calcType = move.pbCalcType(foe)
          foe.pbChangeTargets(move, foe, [ally]).map(&:index).join("/")
        end
        "holder=#{holder.index} ally=#{ally.index} flying_to=#{drawn[0]} ground_to=#{drawn[1]}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:airborne] installed on MoveImmunity, Battler#pbChangeTargets and Levitate by name")
rescue StandardError => e
  ChrookedLog.error("[chrooked:airborne] ERROR #{e.class}: #{e.message}")
end
