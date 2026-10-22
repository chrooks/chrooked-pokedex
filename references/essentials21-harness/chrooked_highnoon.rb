# chrooked:highnoon
# ---------------------------------------------------------------------------
# Ruleset behavior "highnoon", two effects (mjolnir NV-10), Full Moon's mirror:
#   1. This Pokemon's Fire- and Psychic-type moves get the Same-Type Attack Bonus,
#      regardless of its own types.
#   2. When this Pokemon uses Morning Sun, it recovers 75% of its max HP.
#
# HAND-WRITTEN: a template generates exactly one effect, and this spec has two.
# Effect 1 is the stab_grant template's handler for [Fire, Psychic]; effect 2 is
# chrooked_fullmoon.rb's heal for Morning Sun. chrooked_fullmoon.rb explains both.
# The pbOnStartUse wrapper has its own alias name, so it chains onto Full Moon's
# (which loads first, in name order) instead of replacing it.
#
# Install, load order, the marker-gated oracle, the OBS/EST split and the
# self-test registration at the end: references/essentials21-harness/README.md.
#     [chrooked:highnoon] OBS move=<ID> type=<TYPE> ability=true user_types=<T/T> own=<true|false> result=<BOOSTED|NORMAL>   a hit
#     [chrooked:highnoon] OBS move=MORNINGSUN ability=true heal=<HP> max=<HP> normal=<HP> result=BOOSTED                   a heal
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
  ChrookedLog.line("[chrooked:highnoon] load prior_handler=#{!chrooked_table[:HIGHNOON].nil?}")
  chrooked_table.add(:HIGHNOON,
    proc { |ability, user, target, move, mults, power, type|
      own     = !type.nil? && user.pbHasType?(type)
      boosted = !type.nil? && !own && [:FIRE, :PSYCHIC].include?(type)
      mults[:final_damage_multiplier] *= 1.5 if boosted
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:highnoon] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \
                         "user_types=#{user.pbTypes.join('/')} own=#{own} result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
  # class_eval, not `class ... end`: reopening a class this game lacks would quietly
  # create an empty one; class_eval raises instead, and the rescue logs it.
  Battle::Move::HealUserDependingOnWeather.class_eval do
    unless method_defined?(:chrooked_highnoon_pbOnStartUse)
      alias_method :chrooked_highnoon_pbOnStartUse, :pbOnStartUse
      def pbOnStartUse(user, targets)
        chrooked_highnoon_pbOnStartUse(user, targets)
        return if @id != :MORNINGSUN || !user.hasActiveAbility?(:HIGHNOON)
        normal = @healAmount
        @healAmount = (user.totalhp * 3 / 4.0).round
        ChrookedLog.line("[chrooked:highnoon] OBS move=#{@id} ability=true heal=#{@healAmount} " \
                         "max=#{user.totalhp} normal=#{normal} result=BOOSTED")
      end
    end
  end
  ($chrooked_selftest_cases ||= {})["highnoon"] = {
    ability: :HIGHNOON, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [[:FLAMETHROWER, 1.0, {types: [:NORMAL]}], [:DARKPULSE, 1.0, {types: [:NORMAL]}]],
    heal: [[:MORNINGSUN, 0.5]],
    without: [],
    fight: [:FLAMETHROWER, :DARKPULSE, :MORNINGSUN]
  }
  ChrookedLog.line("[chrooked:highnoon] installed on DamageCalcFromUser and HealUserDependingOnWeather#pbOnStartUse")
rescue StandardError => e
  ChrookedLog.error("[chrooked:highnoon] ERROR #{e.class}: #{e.message}")
end
