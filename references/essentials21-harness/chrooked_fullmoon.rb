# chrooked:fullmoon
# ---------------------------------------------------------------------------
# Ruleset behavior "fullmoon", two effects (mjolnir NV-10):
#   1. This Pokemon's Dark- and Fairy-type moves get the Same-Type Attack Bonus,
#      regardless of its own types.
#   2. When this Pokemon uses Moonlight, it recovers 75% of its max HP.
#
# HAND-WRITTEN: a template generates exactly one effect, and this spec has two.
# Effect 1 is also the model for the stab_grant template.
#
# Effect 1, Seam Battle::AbilityEffects::DamageCalcFromUser. Nova's own STAB
# (Battle::Move#pbCalcDamageMultipliersSTAB) multiplies final damage by 1.5 when
# `type && user.pbHasType?(type)`. The grant applies the same factor in the same
# slot only when the user LACKS the type, so a Dark-type Full Moon user gets the
# ordinary STAB and nothing more (no double STAB), and Struggle (type nil) gets
# none, as in Nova's STAB.
#
# Effect 2, Seam Battle::Move::HealUserDependingOnWeather#pbOnStartUse, where
# Moonlight, Morning Sun and Synthesis set @healAmount from the weather (and where
# Nova's own Mega Sol overrides it). The wrapper lets that run, then sets
# Moonlight's amount to 3/4 of max HP for a Full Moon user, whatever the weather.
# A user at full HP still fails as usual (the move's own check, untouched).
#
# Install, load order, the marker-gated oracle, the OBS/EST split and the
# self-test registration at the end: references/essentials21-harness/README.md.
#     [chrooked:fullmoon] OBS move=<ID> type=<TYPE> ability=true user_types=<T/T> own=<true|false> result=<BOOSTED|NORMAL>   a hit
#     [chrooked:fullmoon] OBS move=MOONLIGHT ability=true heal=<HP> max=<HP> normal=<HP> result=BOOSTED                    a heal
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
  chrooked_table = Battle::AbilityEffects::DamageCalcFromUser
  ChrookedLog.line("[chrooked:fullmoon] load prior_handler=#{!chrooked_table[:FULLMOON].nil?}")
  chrooked_table.add(:FULLMOON,
    proc { |ability, user, target, move, mults, power, type|
      own     = !type.nil? && user.pbHasType?(type)
      boosted = !type.nil? && !own && [:DARK, :FAIRY].include?(type)
      mults[:final_damage_multiplier] *= 1.5 if boosted
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:fullmoon] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \
                         "user_types=#{user.pbTypes.join('/')} own=#{own} result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
  # class_eval, not `class ... end`: reopening a class this game lacks would quietly
  # create an empty one; class_eval raises instead, and the rescue logs it.
  Battle::Move::HealUserDependingOnWeather.class_eval do
    unless method_defined?(:chrooked_fullmoon_pbOnStartUse)
      alias_method :chrooked_fullmoon_pbOnStartUse, :pbOnStartUse
      def pbOnStartUse(user, targets)
        chrooked_fullmoon_pbOnStartUse(user, targets)
        return if @id != :MOONLIGHT || !user.hasActiveAbility?(:FULLMOON)
        normal = @healAmount
        @healAmount = (user.totalhp * 3 / 4.0).round
        ChrookedLog.line("[chrooked:fullmoon] OBS move=#{@id} ability=true heal=#{@healAmount} " \
                         "max=#{user.totalhp} normal=#{normal} result=BOOSTED")
      end
    end
  end
  ($chrooked_selftest_cases ||= {})["fullmoon"] = {
    ability: :FULLMOON, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [[:DARKPULSE, 1.0, {types: [:NORMAL]}], [:FLAMETHROWER, 1.0, {types: [:NORMAL]}]],
    heal: [[:MOONLIGHT, 0.5]],
    without: [],
    fight: [:DARKPULSE, :FLAMETHROWER, :MOONLIGHT]
  }
  ChrookedLog.line("[chrooked:fullmoon] installed on DamageCalcFromUser and HealUserDependingOnWeather#pbOnStartUse")
rescue StandardError => e
  ChrookedLog.error("[chrooked:fullmoon] ERROR #{e.class}: #{e.message}")
end
