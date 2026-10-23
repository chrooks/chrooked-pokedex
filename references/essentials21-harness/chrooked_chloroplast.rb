# chrooked:chloroplast
# ---------------------------------------------------------------------------
# Ruleset behavior "chloroplast": its moves act as if the sun were shining, whatever
# the weather: Solar Beam fires at once, Weather Ball is a Fire move at double power,
# Fire moves are sun-boosted even in rain, Synthesis and its kin heal 2/3, Growth
# raises two stages.
#
# HAND-WRITTEN (mjolnir NV-31). Nova already has this ability: Mega Sol, which
# its move code and its AI ask for by name (hasActiveAbility?(:MEGASOL)) at every one of
# those places, the damage calc's weather step included. The holder answers yes to Mega
# Sol, and to nothing else, so it gets all of them, the AI's view too.
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
  ChrookedLog.line("[chrooked:chloroplast] load mega_sol=#{GameData::Ability.exists?(:MEGASOL)}")
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_chloroplast_hasActiveAbility?)
      alias_method :chrooked_chloroplast_hasActiveAbility?, :hasActiveAbility?
      def hasActiveAbility?(check_ability, ignore_fainted = false)
        asked = check_ability.is_a?(Array) ? check_ability : [check_ability]
        if asked.include?(:MEGASOL) && chrooked_chloroplast_hasActiveAbility?(:CHLOROPLAST, ignore_fainted)
          return true
        end
        chrooked_chloroplast_hasActiveAbility?(check_ability, ignore_fainted)
      end
    end
  end
  # The holder (or a Pokemon with no ability) in the weather: what each sun clause does.
  chrooked_chloroplast_scene = lambda do |t, spec, move_id, weather, ability = spec[:ability]|
    b, holder, foe = t.pair(spec, move_id)
    holder.ability = ability
    b.field.weather = weather if weather
    [b, holder, foe, holder.moves[0]]
  end
  ($chrooked_selftest_cases ||= {})["chloroplast"] = {
    ability: :CHLOROPLAST, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["solar_beam", ->(t, spec) {
        _b, holder, _foe, move = chrooked_chloroplast_scene.call(t, spec, :SOLARBEAM, nil)
        "charges=#{move.pbIsChargingTurn?(holder)}"
      }],
      ["weather_ball", ->(t, spec) {
        b, holder, foe, move = chrooked_chloroplast_scene.call(t, spec, :WEATHERBALL, nil)
        "type=#{move.pbBaseType(holder)} power=#{move.pbBasePower(move.power, holder, foe)}"
      }],
      ["fire_blast", ->(t, spec) {
        b, holder, foe, _move = chrooked_chloroplast_scene.call(t, spec, :FIREBLAST, nil)
        with = t.hit(b, holder, foe, :FIREBLAST)
        holder.ability = nil
        none = t.hit(b, holder, foe, :FIREBLAST)
        "with=#{with} none=#{none} sun_boosted=#{with > none}"
      }],
      ["fire_in_rain", ->(t, spec) {
        b, holder, foe, _move = chrooked_chloroplast_scene.call(t, spec, :FIREBLAST, :Rain)
        with = t.hit(b, holder, foe, :FIREBLAST)
        holder.ability = nil
        rain = t.hit(b, holder, foe, :FIREBLAST)
        b.field.weather = :None
        clear = t.hit(b, holder, foe, :FIREBLAST)
        "with=#{with} rain_none=#{rain} clear_none=#{clear} sun_boosted=#{with > clear}"
      }],
      ["synthesis", ->(t, spec) {
        _b, holder, _foe, move = chrooked_chloroplast_scene.call(t, spec, :SYNTHESIS, nil)
        move.pbOnStartUse(holder, [holder])
        "heal=#{move.pbHealAmount(holder)} max=#{holder.totalhp} " \
        "two_thirds_healed=#{move.pbHealAmount(holder) == (holder.totalhp * 2 / 3.0).round}"
      }],
      ["growth", ->(t, spec) {
        _b, holder, _foe, move = chrooked_chloroplast_scene.call(t, spec, :GROWTH, nil)
        move.pbOnStartUse(holder, [holder])
        move.pbEffectGeneral(holder)
        "attack=#{holder.stages[:ATTACK]} spatk=#{holder.stages[:SPECIAL_ATTACK]}"
      }]
    ],
    without: [],
    fight: [:SOLARBEAM, :WEATHERBALL]
  }
  ChrookedLog.line("[chrooked:chloroplast] installed: answers to Mega Sol by name")
rescue StandardError => e
  ChrookedLog.error("[chrooked:chloroplast] ERROR #{e.class}: #{e.message}")
end
