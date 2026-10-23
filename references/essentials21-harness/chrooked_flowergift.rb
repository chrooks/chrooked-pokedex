# chrooked:flowergift
# ---------------------------------------------------------------------------
# Ruleset behavior "flowergift": Cherrim's form follows the sun (the game's own), its
# Fire and Grass moves get a same-type bonus (1.5x, not on top of its own), and Morning
# Sun heals 3/4 of its max HP whatever the weather.
#
# HAND-WRITTEN (mjolnir NV-31). Full Moon's shape (chrooked_fullmoon.rb), for Fire and
# Grass and Morning Sun:
#   - DamageCalcFromUser: Nova's own Flower Gift handler runs first (its sun boost for
#     a Cherrim; the spec does not mention it, and Nova's ally and defensive Flower
#     Gift handlers are left as they are too), then 1.5x final damage on a Fire or
#     Grass move the holder is not that type for, as Nova's STAB step applies it.
#   - HealUserDependingOnWeather#pbOnStartUse: Morning Sun heals 3/4, in any weather.
#   Its forms change through Nova's own Cherrim code, untouched.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:flowergift] OBS move=<ID> type=<TYPE> ability=true own=<bool> result=<BOOSTED|NORMAL>   each damage calc (EST from the AI)
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
  chrooked_flowergift_own = Battle::AbilityEffects::DamageCalcFromUser[:FLOWERGIFT]
  ChrookedLog.line("[chrooked:flowergift] load prior_handler=#{!chrooked_flowergift_own.nil?}")
  Battle::AbilityEffects::DamageCalcFromUser.add(:FLOWERGIFT,
    proc { |ability, user, target, move, mults, power, type|
      chrooked_flowergift_own&.call(ability, user, target, move, mults, power, type)
      own     = !type.nil? && user.pbHasType?(type)
      boosted = !type.nil? && !own && [:FIRE, :GRASS].include?(type)
      mults[:final_damage_multiplier] *= 1.5 if boosted
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:flowergift] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \
                         "own=#{own} result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
  Battle::Move::HealUserDependingOnWeather.class_eval do
    unless method_defined?(:chrooked_flowergift_pbOnStartUse)
      alias_method :chrooked_flowergift_pbOnStartUse, :pbOnStartUse
      def pbOnStartUse(user, targets)
        chrooked_flowergift_pbOnStartUse(user, targets)
        return if @id != :MORNINGSUN || !user.hasActiveAbility?(:FLOWERGIFT)
        @healAmount = (user.totalhp * 3 / 4.0).round
      end
    end
  end
  # Cherrim (form, types as given) uses move_id in the weather: with Flower Gift, and
  # with Flower Gift's handler only (Nova's own, no grant), no crit.
  chrooked_flowergift_hit = lambda do |t, spec, move_id, form, types, weather|
    b, holder, foe = t.pair(spec, move_id)
    holder.pokemon.form = form
    holder.ability = spec[:ability]
    holder.types = types
    holder.effects[PBEffects::ExtraType] = nil
    foe.pbChangeTypes(:QMARKS)
    b.field.weather = weather
    with = t.hit(b, holder, foe, move_id)
    holder.ability = nil
    none = t.hit(b, holder, foe, move_id)
    "move=#{move_id} types=#{types.join('/')} with=#{with} none=#{none} boosted=#{with > none} " \
    "ratio=#{format('%.3f', with.to_f / none)}"
  end
  ($chrooked_selftest_cases ||= {})["flowergift"] = {
    ability: :FLOWERGIFT, control: nil, user: :CHERRIM, foe: :SNORLAX, neutral: false,
    calc: [],
    checks: [
      ["petal_dance_rain", ->(t, spec) { chrooked_flowergift_hit.call(t, spec, :PETALDANCE, 0, [:GRASS], :Rain) }],
      ["solar_beam_sun", ->(t, spec) {
        chrooked_flowergift_hit.call(t, spec, :SOLARBEAM, 1, [:FIRE, :FAIRY], :Sun)
      }],
      ["morning_sun_sand", ->(t, spec) {
        b, holder, _foe = t.pair(spec, :MORNINGSUN)
        holder.ability = spec[:ability]
        b.field.weather = :Sandstorm
        move = holder.moves[0]
        move.pbOnStartUse(holder, [holder])
        "heal=#{move.pbHealAmount(holder)} max=#{holder.totalhp} " \
        "three_quarters_healed=#{move.pbHealAmount(holder) == (holder.totalhp * 3 / 4.0).round}"
      }]
    ],
    without: [],
    fight: [:PETALDANCE, :MORNINGSUN]
  }
  ChrookedLog.line("[chrooked:flowergift] installed on DamageCalcFromUser and HealUserDependingOnWeather")
rescue StandardError => e
  ChrookedLog.error("[chrooked:flowergift] ERROR #{e.class}: #{e.message}")
end
