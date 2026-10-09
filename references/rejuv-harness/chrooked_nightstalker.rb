# chrooked:nightstalker
# Night Stalker — "In darkness, its stronger attacking stat hits 1.3x harder
#              and its critical-hit ratio rises one stage."
#   Darkness = exactly the Dusk Ball gate (Balls.rb ~166): night, or one of
#   the dark fields. Nothing happens in light. Two seams:
#   1. damage: CHROOKED_DAMAGE_MODS x1.3 when the move's category matches the
#      holder's higher raw attacking stat (Attack vs Sp. Atk, before stages).
#   2. crit: +1 stage in darkness. No core table carries an additive stage, so
#      this file prepends its own wrapper on PokeBattle_Move (loads after the
#      core, so super = core wrapper = vanilla). A -1 (crit impossible) or a
#      forced 3 passes through untouched, so Shell Armor still denies it.
#   History: until 2026-10-09 this forced a crit in darkness and gave +1 in
#   light — "too OP" with night plus every cave counting as dark.
# Test cases:
#   - night, Crobat Cross Poison                => 1.3x, 1-in-8 crit roll
#   - night, Crobat Air Cutter (special)        => no 1.3x, crit stage still +1
#   - day,   Noctowl Air Slash, no item         => normal damage, base crit
#   - night, any holder into Shell Armor        => 1.3x, no crit
module ChrookedNightStalker
  DARK_FIELDS = [:DARKCRYSTALCAVERN, :SHORTCIRCUIT, :UNDERWATER, :CAVE, :CRYSTALCAVERN,
                 :DRAGONSDEN, :STARLIGHT, :NEWWORLD, :INVERSE].freeze
  BOOST = 1.3

  def self.dark?(battle)
    PBDayNight.isNight?(pbGetTimeNow) || DARK_FIELDS.include?(battle.FE)
  end

  # Dark-side +1 crit stage. Runs ahead of the core's wrapper.
  module CritStage
    def pbCritRate?(attacker, opponent, *rest)
      rate = super
      return rate if rate < 0 || rate >= 3
      return rate + 1 if attacker.ability == :NIGHTSTALKER && ChrookedNightStalker.dark?(@battle)
      rate
    end
  end
end

CHROOKED_DAMAGE_MODS[:NIGHTSTALKER] = lambda { |move, attacker, opponent|
  next 1.0 unless ChrookedNightStalker.dark?(move.instance_variable_get(:@battle))
  physical_user = attacker.attack >= attacker.spatk
  matches = physical_user ? move.pbIsPhysical?(attacker, move.pbType(attacker)) :
                            move.pbIsSpecial?(attacker, move.pbType(attacker))
  matches ? ChrookedNightStalker::BOOST : 1.0
}
PokeBattle_Move.prepend(ChrookedNightStalker::CritStage)
