# chrooked:blitz
# ---------------------------------------------------------------------------
# Ruleset behavior "blitz": on its first turn out, Speed 1.5x and physical moves 1.3x.
#
# HAND-WRITTEN (mjolnir NV-25). "First turn" is Fake Out's: Nova zeroes
# battler.turnCount on entry and adds one at the start of each attack phase, before it
# orders the round, so the turn the holder first acts on is turnCount 1 (0 while the AI
# plans that round).
#   - SpeedCalc: Speed x1.5 while turnCount <= 1, as Quick Feet multiplies it.
#   - DamageCalcFromUser: a 1.3x attack multiplier on physical moves then.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:blitz] OBS move=<ID> ability=true first=<bool> physical=<bool>   each damage calc (EST from the AI)
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
  ChrookedLog.line("[chrooked:blitz] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromUser[:BLITZ].nil?}")
  Battle::AbilityEffects::SpeedCalc.add(:BLITZ,
    proc { |ability, battler, mult|
      next mult * 1.5 if battler.turnCount <= 1
    }
  )
  Battle::AbilityEffects::DamageCalcFromUser.add(:BLITZ,
    proc { |ability, user, target, move, mults, power, type|
      first = user.turnCount <= 1
      physical = move.physicalMove?
      mults[:attack_multiplier] *= 1.3 if first && physical
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:blitz] #{tag} move=#{move.id} ability=true first=#{first} physical=#{physical}")
      end
    }
  )
  # The holder at turnCount `turn`: its Speed and one hit's damage, with Blitz and with none.
  chrooked_blitz_measure = lambda do |t, spec, move_id, turn|
    b, user, target = t.pair(spec, move_id)
    user.turnCount = turn
    user.ability = spec[:ability]
    speed, with = user.pbSpeed, t.hit(b, user, target, move_id)
    user.ability = nil
    speed_none, none = user.pbSpeed, t.hit(b, user, target, move_id)
    "move=#{move_id} turn=#{turn} speed=#{speed} speed_none=#{speed_none} faster=#{speed > speed_none} " \
    "with=#{with} none=#{none} boosted=#{with > none}"
  end
  ($chrooked_selftest_cases ||= {})["blitz"] = {
    ability: :BLITZ, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["first_speed", ->(t, spec) { chrooked_blitz_measure.call(t, spec, :TACKLE, 1) }],
      ["first_physical", ->(t, spec) { chrooked_blitz_measure.call(t, spec, :TACKLE, 1) }],
      ["second_turn", ->(t, spec) { chrooked_blitz_measure.call(t, spec, :TACKLE, 2) }],
      ["first_special", ->(t, spec) { chrooked_blitz_measure.call(t, spec, :SWIFT, 1) }]
    ],
    without: [],
    fight: [:TACKLE, :SWIFT]
  }
  ChrookedLog.line("[chrooked:blitz] installed on SpeedCalc and DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:blitz] ERROR #{e.class}: #{e.message}")
end
