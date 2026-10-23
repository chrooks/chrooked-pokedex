# chrooked:sunbask
# ---------------------------------------------------------------------------
# Ruleset behavior "sunbask": in sun it heals 1/8 of its max HP at the end of each
# round, and its drains recover double (all of the damage dealt, not half).
#
# HAND-WRITTEN (mjolnir NV-31). "In sun" is the holder's effective weather, so Air Lock,
# Cloud Nine and a Utility Umbrella clear both.
#   - EndOfRoundWeather, Rain Dish's shape for sun: while it can heal, floor(max/8)
#     under the splash, with Rain Dish's message.
#   - Battle::Battler#pbRecoverHPFromDrain: a drain the holder recovers in sun is
#     doubled before Nova's own step (Big Root on top; Liquid Ooze still reverses).
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
  ChrookedLog.line("[chrooked:sunbask] load prior_handler=#{!Battle::AbilityEffects::EndOfRoundWeather[:SUNBASK].nil?}")
  Battle::AbilityEffects::EndOfRoundWeather.add(:SUNBASK,
    proc { |ability, weather, battler, battle|
      next unless [:Sun, :HarshSun].include?(weather)
      next if !battler.canHeal?
      battle.pbShowAbilitySplash(battler)
      battler.pbRecoverHP(battler.totalhp / 8)
      if Battle::Scene::USE_ABILITY_SPLASH
        battle.pbDisplay(_INTL("{1}'s HP was restored.", battler.pbThis))
      else
        battle.pbDisplay(_INTL("{1}'s {2} restored its HP.", battler.pbThis, battler.abilityName))
      end
      battle.pbHideAbilitySplash(battler)
    }
  )
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_sunbask_pbRecoverHPFromDrain)
      alias_method :chrooked_sunbask_pbRecoverHPFromDrain, :pbRecoverHPFromDrain
      def pbRecoverHPFromDrain(amt, target, msg = nil)
        if hasActiveAbility?(:SUNBASK) && [:Sun, :HarshSun].include?(effectiveWeather) &&
           !target.hasActiveAbility?(:LIQUIDOOZE, true)
          amt *= 2
        end
        chrooked_sunbask_pbRecoverHPFromDrain(amt, target, msg)
      end
    end
  end
  # The holder at 1 HP in the weather (an Air Lock foe or an Umbrella first): a Giga
  # Drain that dealt 80 (it drains 40), then the end of a round from 1 HP.
  chrooked_sunbask_scene = lambda do |t, spec, weather, foe_ability: nil, item: nil|
    b, holder, foe = t.pair(spec, :GIGADRAIN)
    holder.ability = spec[:ability]
    holder.item = item
    foe.ability = foe_ability
    b.field.weather = weather if weather
    b.field.weatherDuration = 5 if weather
    holder.hp = 1
    drain = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:GIGADRAIN))
    foe.damageState.reset
    foe.damageState.hpLost = 80
    drain.pbEffectAgainstTarget(holder, foe)
    drained = holder.hp - 1
    holder.hp = 1
    b.send(:pbEOREndWeather, [holder])
    "weather=#{weather || 'none'} drained=#{drained} round_end_heal=#{holder.hp - 1} " \
    "eighth_healed=#{holder.hp - 1 == holder.totalhp / 8}"
  end
  ($chrooked_selftest_cases ||= {})["sunbask"] = {
    ability: :SUNBASK, control: nil, user: :SNORLAX, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["sun", ->(t, spec) { chrooked_sunbask_scene.call(t, spec, :Sun) }],
      ["clear", ->(t, spec) { chrooked_sunbask_scene.call(t, spec, nil) }],
      ["air_lock_umbrella", ->(t, spec) {
        lock = chrooked_sunbask_scene.call(t, spec, :Sun, foe_ability: :AIRLOCK)
        brella = chrooked_sunbask_scene.call(t, spec, :Sun, item: :UTILITYUMBRELLA)
        "air_lock_drained=#{lock[/drained=(\d+)/, 1]} air_lock_heal=#{lock[/round_end_heal=(\d+)/, 1]} " \
        "umbrella_drained=#{brella[/drained=(\d+)/, 1]} umbrella_heal=#{brella[/round_end_heal=(\d+)/, 1]}"
      }]
    ],
    without: [],
    fight: [:GIGADRAIN]
  }
  ChrookedLog.line("[chrooked:sunbask] installed on EndOfRoundWeather and Battler#pbRecoverHPFromDrain")
rescue StandardError => e
  ChrookedLog.error("[chrooked:sunbask] ERROR #{e.class}: #{e.message}")
end
