# chrooked:sandguard
# ---------------------------------------------------------------------------
# Ruleset behavior "sandguard": in a sandstorm, special moves deal it half damage, and
# it takes no sandstorm damage.
#
# HAND-WRITTEN (mjolnir NV-25).
#   - DamageCalcFromTarget: final damage x0.5 for a special move while the holder's
#     effective weather is a sandstorm (so Air Lock and Cloud Nine clear it).
#   - Battle::Battler#takesSandstormDamage? answers false for the holder, beside
#     Nova's own Sand Veil, Sand Rush and Overcoat there.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:sandguard] OBS move=<ID> ability=true sand=<bool> special=<bool>   each damage calc on it (EST from the AI)
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
  ChrookedLog.line("[chrooked:sandguard] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromTarget[:SANDGUARD].nil?}")
  Battle::AbilityEffects::DamageCalcFromTarget.add(:SANDGUARD,
    proc { |ability, user, target, move, mults, power, type|
      sand = target.effectiveWeather == :Sandstorm
      special = move.specialMove?
      mults[:final_damage_multiplier] *= 0.5 if sand && special
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:sandguard] #{tag} move=#{move.id} ability=true sand=#{sand} special=#{special}")
      end
    }
  )
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_sandguard_takesSandstormDamage?)
      alias_method :chrooked_sandguard_takesSandstormDamage?, :takesSandstormDamage?
      def takesSandstormDamage?
        return false if hasActiveAbility?(:SANDGUARD)
        chrooked_sandguard_takesSandstormDamage?
      end
    end
  end
  # The foe's move into the holder, with Sand Guard and with none, in the weather.
  chrooked_sandguard_taken = lambda do |t, spec, move_id, weather|
    setup = weather ? {weather: weather} : {}
    with = t.damage(spec[:foe], [nil], spec[:user], move_id, neutral: true, setup: setup,
                    target_ability: spec[:ability])[0][0]
    none = t.damage(spec[:foe], [nil], spec[:user], move_id, neutral: true, setup: setup)[0][0]
    "weather=#{weather || 'none'} with=#{with} none=#{none} halved=#{with * 4 < none * 3}"
  end
  ($chrooked_selftest_cases ||= {})["sandguard"] = {
    ability: :SANDGUARD, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["special_sand", ->(t, spec) { chrooked_sandguard_taken.call(t, spec, :SURF, :Sandstorm) }],
      ["physical_sand", ->(t, spec) { chrooked_sandguard_taken.call(t, spec, :EARTHQUAKE, :Sandstorm) }],
      ["special_clear", ->(t, spec) { chrooked_sandguard_taken.call(t, spec, :THUNDERBOLT, nil) }],
      # Effect 2, which no test case states: the end of a round in a sandstorm, from half HP.
      ["chip", ->(t, spec) {
        with, none = [spec[:ability], nil].map { |a| t.keep_measure(spec, :eor_weather, {weather: :Sandstorm}, a) }
        "weather=Sandstorm chip_with=#{with} chip_none=#{none}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:sandguard] installed on DamageCalcFromTarget and Battler#takesSandstormDamage?")
rescue StandardError => e
  ChrookedLog.error("[chrooked:sandguard] ERROR #{e.class}: #{e.message}")
end
