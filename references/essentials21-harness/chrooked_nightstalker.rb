# chrooked:nightstalker
# ---------------------------------------------------------------------------
# Ruleset behavior "nightstalker": at night, moves of the holder's stronger attacking
# stat hit 1.3x, and every move's critical-hit stage is one higher.
#
# HAND-WRITTEN (mjolnir NV-25). Night is Nova's own PBDayNight.isNight? (20:00 to
# 05:00 on the clock the overworld tints by); Nova has no fields, so no dark field.
#   - DamageCalcFromUser: a 1.3x attack multiplier when the move's category matches the
#     higher raw stat (Attack >= Sp. Atk is physical, as Nova's Solar Power shape ties).
#   - CriticalCalcFromUser: stage + 1, so Scope Lens, Super Luck and Focus Energy add on
#     top; the target's Battle Armor or Shell Armor and Lucky Chant still deny it, as
#     pbIsCritical? asks the target after the user.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:nightstalker] OBS move=<ID> ability=true night=<bool> matches=<bool>   each damage calc (EST from the AI)
#     [chrooked:nightstalker] OBS move=<ID> ability=true night=<bool> crit_stage=<n>   each critical-hit check
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

module ChrookedNightStalker
  # The self-test fixes the clock for a measurement (at); play reads Nova's.
  def self.night?
    @forced.nil? ? PBDayNight.isNight? : @forced
  end

  def self.at(night)
    @forced = night
    yield
  ensure
    @forced = nil
  end

  def self.matches?(user, move)
    user.attack >= user.spatk ? move.physicalMove? : move.specialMove?
  end
end

begin
  ChrookedLog.line("[chrooked:nightstalker] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromUser[:NIGHTSTALKER].nil?}")
  Battle::AbilityEffects::DamageCalcFromUser.add(:NIGHTSTALKER,
    proc { |ability, user, target, move, mults, power, type|
      night = ChrookedNightStalker.night?
      matches = ChrookedNightStalker.matches?(user, move)
      mults[:attack_multiplier] *= 1.3 if night && matches
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:nightstalker] #{tag} move=#{move.id} ability=true night=#{night} matches=#{matches}")
      end
    }
  )
  Battle::AbilityEffects::CriticalCalcFromUser.add(:NIGHTSTALKER,
    proc { |ability, user, target, move, c|
      night = ChrookedNightStalker.night?
      ChrookedLog.line("[chrooked:nightstalker] OBS move=#{move.id} ability=true night=#{night} " \
                       "crit_stage=#{night ? c + 1 : c}")
      next c + 1 if night
    }
  )
  # One move by the holder at night or by day, its higher stat set (the self-test's
  # stats: setup): damage with the ability and with none (no crit, t.hit), its
  # critical-hit stage, and how many of 30 checks crit against target_ability.
  chrooked_nightstalker_measure = lambda do |t, spec, move_id, night, stats, target_ability = nil|
    ChrookedNightStalker.at(night) do
      b, user, target = t.pair(spec, move_id)
      t.arrange(b, user, target, {stats: stats})
      none = t.hit(b, user, target, move_id)
      user.ability = spec[:ability]
      with = t.hit(b, user, target, move_id)
      target.ability = target_ability
      move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
      stage = Battle::AbilityEffects.triggerCriticalCalcFromUser(user.ability, user, target, move, 0)
      srand(t::SEED)
      crits = 30.times.count { move.pbIsCritical?(user, target) }
      "night=#{night} stats=#{stats} with=#{with} none=#{none} boosted=#{with > none} " \
      "crit_stage=#{stage} crits=#{crits}"
    end
  end
  ($chrooked_selftest_cases ||= {})["nightstalker"] = {
    ability: :NIGHTSTALKER, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["night_physical", ->(t, spec) { chrooked_nightstalker_measure.call(t, spec, :CROSSPOISON, true, :physical) }],
      ["night_special", ->(t, spec) { chrooked_nightstalker_measure.call(t, spec, :AIRCUTTER, true, :physical) }],
      ["day", ->(t, spec) { chrooked_nightstalker_measure.call(t, spec, :AIRSLASH, false, :special) }],
      ["shell_armor", ->(t, spec) {
        chrooked_nightstalker_measure.call(t, spec, :CROSSPOISON, true, :physical, :SHELLARMOR)
      }]
    ],
    without: [],
    fight: [:CROSSPOISON, :AIRCUTTER]
  }
  ChrookedLog.line("[chrooked:nightstalker] installed on DamageCalcFromUser and CriticalCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:nightstalker] ERROR #{e.class}: #{e.message}")
end
