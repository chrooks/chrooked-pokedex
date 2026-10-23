# chrooked:aerodynamic
# ---------------------------------------------------------------------------
# Ruleset behavior "aerodynamic": Flying moves do not affect it and raise its Speed one
# stage instead, and in double battles it draws single-target Flying moves to itself.
#
# HAND-WRITTEN (mjolnir NV-29). Motor Drive and Lightning Rod, for Flying.
#   - MoveImmunity: Nova's pbMoveImmunityStatRaisingAbility for :FLYING and :SPEED, as
#     Motor Drive's handler calls it for Electric (Mold Breaker skips it).
#   - Battle::Battler#pbChangeTargets: after Nova's own redirection, unless a move or
#     a Follow Me already decided the target, Nova's pbChangeTargetByAbility draws a
#     single-target Flying move to the holder, with Lightning Rod's message.
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
  ChrookedLog.line("[chrooked:aerodynamic] load prior_handler=" \
                   "#{!Battle::AbilityEffects::MoveImmunity[:AERODYNAMIC].nil?}")
  Battle::AbilityEffects::MoveImmunity.add(:AERODYNAMIC,
    proc { |ability, user, target, move, type, battle, show_message|
      next target.pbMoveImmunityStatRaisingAbility(user, move, type, :FLYING, :SPEED, 1, show_message)
    }
  )
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_aerodynamic_pbChangeTargets)
      alias_method :chrooked_aerodynamic_pbChangeTargets, :pbChangeTargets
      def pbChangeTargets(move, user, targets)
        targets = chrooked_aerodynamic_pbChangeTargets(move, user, targets)
        ChrookedDraw.draw(self, :AERODYNAMIC, :FLYING, move, user, targets)
      end
    end
  end
  # The foe's move into the holder: immune (through pbImmunityByAbility, messages shown)
  # and the holder's Speed stage after.
  chrooked_aerodynamic_struck = lambda do |t, spec, move_id|
    b, foe, holder = t.pair(spec, move_id)
    holder.ability = spec[:ability]
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    move.calcType = move.pbCalcType(foe)
    immune = !!move.pbImmunityByAbility(foe, holder, true)
    "move=#{move_id} immune=#{immune} speed=#{holder.stages[:SPEED]}"
  end
  ($chrooked_selftest_cases ||= {})["aerodynamic"] = {
    ability: :AERODYNAMIC, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["air_slash", ->(t, spec) { chrooked_aerodynamic_struck.call(t, spec, :AIRSLASH) }],
      ["tackle", ->(t, spec) { chrooked_aerodynamic_struck.call(t, spec, :TACKLE) }],
      # Doubles: a foe aims Air Slash at the holder's ally.
      ["redirect", ->(t, spec) {
        b, holder, ally, foe, _foe2 = t.doubles(spec)
        holder.ability = spec[:ability]
        # Nova fills the round's speed order (pbPriority) in each attack phase; this
        # throwaway battle has had none, so order it as a round would.
        b.battlers.each_with_index { |x, i| b.pbClearChoice(i) if x }
        b.pbCalculatePriority(true)
        move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:AIRSLASH))
        move.calcType = move.pbCalcType(foe)
        targets = foe.pbChangeTargets(move, foe, [ally])
        "aimed_at=#{ally.index} drawn_to=#{targets.map(&:index).join('/')} holder=#{holder.index}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:aerodynamic] installed on MoveImmunity and Battler#pbChangeTargets")
rescue StandardError => e
  ChrookedLog.error("[chrooked:aerodynamic] ERROR #{e.class}: #{e.message}")
end
