# chrooked:fixation
# ---------------------------------------------------------------------------
# Ruleset behavior "fixation" (Sage Power): special moves deal 1.5x, and after its
# first move the holder is locked into it until it switches out.
#
# HAND-WRITTEN (mjolnir NV-25). Gorilla Tactics' shape, on Sp. Atk.
#   - DamageCalcFromUser: a 1.5x attack multiplier on special moves.
#   - The lock: Nova keeps Gorilla Tactics' lock in four places, each asking
#     hasActiveAbility?(:GORILLATACTICS) (pbEndTurn sets ChoiceBand, pbCanChooseMove?
#     enforces it, item loss and Ally Switch keep it). A Fixation holder answers yes to
#     that name and to no other, so it gets the lock, its message and the AI's view of
#     it, but never Gorilla Tactics' Attack boost, which Nova keys on the ability itself.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:fixation] OBS move=<ID> ability=true special=<bool>   each damage calc (EST from the AI)
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
  ChrookedLog.line("[chrooked:fixation] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromUser[:FIXATION].nil?}")
  Battle::AbilityEffects::DamageCalcFromUser.add(:FIXATION,
    proc { |ability, user, target, move, mults, power, type|
      special = move.specialMove?
      mults[:attack_multiplier] *= 1.5 if special
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:fixation] #{tag} move=#{move.id} ability=true special=#{special}")
      end
    }
  )
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_fixation_hasActiveAbility?)
      alias_method :chrooked_fixation_hasActiveAbility?, :hasActiveAbility?
      def hasActiveAbility?(check_ability, ignore_fainted = false)
        if (check_ability.is_a?(Array) ? check_ability.include?(:GORILLATACTICS) : check_ability == :GORILLATACTICS) &&
           chrooked_fixation_hasActiveAbility?(:FIXATION, ignore_fainted)
          return true
        end
        chrooked_fixation_hasActiveAbility?(check_ability, ignore_fainted)
      end
    end
  end
  ($chrooked_selftest_cases ||= {})["fixation"] = {
    ability: :FIXATION, control: :GORILLATACTICS, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [[:FLAMETHROWER, 1.0], [:TACKLE, 1.0]],
    checks: [
      ["boost", ->(t, spec) {
        (with, _, _), (none, _, _) = t.damage(spec[:user], [spec[:ability], nil], spec[:foe], :FLAMETHROWER,
                                              neutral: true)
        "move=FLAMETHROWER with=#{with} none=#{none} boosted=#{with > none}"
      }],
      ["physical", ->(t, spec) {
        (with, _, _), (none, _, _) = t.damage(spec[:user], [spec[:ability], nil], spec[:foe], :TACKLE, neutral: true)
        "move=TACKLE with=#{with} none=#{none} boosted=#{with > none}"
      }],
      ["locked", ->(t, spec) {
        b = t.battle(t.mon(spec[:user], [:FLAMETHROWER, :PSYCHIC]), t.mon(spec[:foe], [:TACKLE]))
        b.pbCreateBattler(0, b.pbParty(0)[0], 0)
        b.pbCreateBattler(1, b.pbParty(1)[0], 0)
        holder = b.battlers[0]
        holder.ability = spec[:ability]
        flamethrower, psychic = holder.moves[0], holder.moves[1]
        holder.lastRegularMoveUsed = :FLAMETHROWER
        holder.pbEndTurn([:UseMove, 0, flamethrower, -1, 0])
        "locked_to=#{holder.effects[PBEffects::ChoiceBand] || 'none'} " \
        "flamethrower=#{holder.pbCanChooseMove?(flamethrower, false, false)} " \
        "psychic=#{holder.pbCanChooseMove?(psychic, false, false)}"
      }]
    ],
    without: [],
    fight: [:FLAMETHROWER, :PSYCHIC]
  }
  ChrookedLog.line("[chrooked:fixation] installed on DamageCalcFromUser and Battler#hasActiveAbility?")
rescue StandardError => e
  ChrookedLog.error("[chrooked:fixation] ERROR #{e.class}: #{e.message}")
end
