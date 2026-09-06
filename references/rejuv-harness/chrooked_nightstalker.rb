# chrooked:nightstalker
# Night Stalker — "In darkness, all moves land as critical hits. In light,
#              critical-hit ratio is raised by one stage."
#   Neutral spec: darkness = the night clock. Rejuv extension: darkness is
#   exactly the Dusk Ball gate (Balls.rb ~166) — night, or one of the dark
#   fields. Two seams:
#   1. crit-rate (dark):  CHROOKED_CRIT_RATE forces the crit. The core consults
#      it only after vanilla says crits are possible, so Battle Armor / Shell
#      Armor / Lucky Chant still deny it.
#   2. crit-rate (light): +1 stage. No core table carries an additive stage, so
#      this file prepends its own wrapper on PokeBattle_Move (loads after the
#      core, so super = core wrapper = vanilla).
# Test cases:
#   - night, Air Slash into Blissey             => always a crit
#   - day, Air Slash, no item                   => +1 stage (Scope Lens-equivalent)
#   - night, Tackle into Shell Armor            => no crit (vanilla immunity wins)
#   - day, Starlight field                      => counts as dark => always a crit
module ChrookedNightStalker
  DARK_FIELDS = [:DARKCRYSTALCAVERN, :SHORTCIRCUIT, :UNDERWATER, :CAVE, :CRYSTALCAVERN,
                 :DRAGONSDEN, :STARLIGHT, :NEWWORLD, :INVERSE].freeze

  def self.dark?(battle)
    PBDayNight.isNight?(pbGetTimeNow) || DARK_FIELDS.include?(battle.FE)
  end

  # Light-side +1 crit stage. Runs ahead of the core's wrapper; a -1 (crit
  # impossible) or an already-forced 3 passes through untouched.
  module CritStage
    def pbCritRate?(attacker, opponent, *rest)
      rate = super
      return rate if rate < 0 || rate >= 3
      return rate + 1 if attacker.ability == :NIGHTSTALKER && !ChrookedNightStalker.dark?(@battle)
      rate
    end
  end
end

CHROOKED_CRIT_RATE[:NIGHTSTALKER] = lambda { |move, attacker, opponent|
  ChrookedNightStalker.dark?(move.instance_variable_get(:@battle))
}
PokeBattle_Move.prepend(ChrookedNightStalker::CritStage)
