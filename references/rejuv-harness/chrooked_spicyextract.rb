# chrooked:spicyextract
# Spicy Extract — widened from the Attack/Defense pair to all four battle stats:
#   target gets +2 Attack AND +2 Sp. Atk, -2 Defense AND -2 Sp. Def.
#
# Vanilla is function 0x50D (Battle_MoveEffects.rb:9321), which calls
# pbChangeStats(PBStats::Physical, [2, -2]) — PBStats::Physical is
# [ATTACK, DEFENSE]. pbChangeStats (Battle_Effects.rb:985) already takes parallel
# stat/amount arrays and Array()s them, so re-sending four of each is the whole
# change; Contrary, Mirror Armor, Clear Body and the stat-message path all keep
# working because nothing else is touched.
#
# pbCanAffectTarget is widened to match: the move may still be used while any one
# of the four stages can move. Leaving the vanilla check would have made it fail
# against a target already at -6 Defense even though the other three can change.
#
# Scovillain is the only holder in the Ruleset, so this is a signature rework.
#
# Test cases (drive in-game — the harness can't run a battle):
#   - neutral target => +2 Atk, +2 SpA, -2 Def, -2 SpD.
#   - target at -6 Def / -6 SpD => still works; both attacking stats rise.
#   - Contrary holder => all four changes invert.
module ChrookedSpicyExtract
  STATS = [PBStats::ATTACK, PBStats::SPATK, PBStats::DEFENSE, PBStats::SPDEF]
  AMOUNTS = [2, 2, -2, -2]

  def pbCanAffectTarget(attacker, opponent, showMessage = false)
    ups = [PBStats::ATTACK, PBStats::SPATK].any? do |stat|
      opponent.pbCanIncreaseStatStage?(stat, attacker, self, showMessage: false)
    end
    downs = [PBStats::DEFENSE, PBStats::SPDEF].any? do |stat|
      opponent.pbCanReduceStatStage?(stat, attacker, self, showMessage: false)
    end
    return true if ups || downs
    # Nothing can move — fall through to vanilla so it owns the failure message.
    super
  end

  def pbEffectTarget(attacker, opponent, hitnum = 0, alltargets = nil)
    opponent.pbChangeStats(STATS, AMOUNTS, attacker, self)
  end
end
PokeBattle_Move_50D.prepend(ChrookedSpicyExtract)
