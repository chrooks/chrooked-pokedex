# chrooked:hypercutter
# Hyper Cutter (rework) — "Attack cannot be lowered; an attempt to lower it
#   raises it instead."
#
# Reskin: the :HYPERCUTTER symbol and the vanilla block stay. Vanilla Rejuv
# refuses the drop in PokeBattle_Battler#pbCanReduceStatStage?
# (Battle_Effects.rb:766, failure = :HyperCutter) and shows the ability box
# with "{1}'s Attack was not lowered!" (line 787). This wrapper rides that
# refusal: when the vanilla call returns false for an Attack drop that a FOE
# tried (statinducer != self) against an unbroken Hyper Cutter holder, raise
# Attack by 1 the way pbProcDefiant does (Battle_Effects.rb:894 — ability box,
# pbChangeStats with abilitycheck: :hide, box hidden).
#
# Fires only on the showMessage path, which is the real drop attempt
# (pbChangeStats line 1008 / pbCanReduceAnyStat? via Intimidate). The AI calls
# the same predicate silently while scoring moves and must not buff anything.
#
# ponytail: Substitute and Mist sit above Hyper Cutter in the vanilla case
# chain, so they are re-checked here to keep a Sub/Mist block from paying out.
# Flower Veil (Grass holder) is not — no Grass Hyper Cutter holder exists.
#
# Test cases (drive in-game — the harness can't prove battle behavior):
#   - Foe Intimidate on Kingler          => "Attack was not lowered!", then Attack +1.
#   - Foe Growl on Crawdaunt             => same, once per Growl.
#   - Mold Breaker foe uses Growl        => Attack drops, no buff (vanilla).
#   - Own Superpower / Close Combat drop => Attack drops, no buff (statinducer == self).
#   - Behind a Substitute, foe Growl     => Sub blocks, no buff.
#   - At +6 Attack, foe Intimidate       => block message only, no further raise.

module ChrookedHyperCutterRebound
  def pbCanReduceStatStage?(stat, statinducer, move, showMessage: false, ignoreContrary: false)
    allowed = super
    return allowed if allowed || !showMessage
    return allowed unless stat == PBStats::ATTACK && self.ability == :HYPERCUTTER
    return allowed if statinducer.nil? || statinducer == self
    return allowed if shouldBeMoldBroken?(statinducer, move)
    return allowed if @damagestate.substitute || @effects[:Substitute] > 0
    return allowed if pbOwnSide.effects[:Mist] > 0
    if pbCanIncreaseStatStage?(PBStats::ATTACK, self, nil)
      @battle.pbShowAbilityBox(self)
      pbChangeStats(PBStats::ATTACK, 1, self, nil, abilitycheck: :hide)
      @battle.pbHideAbilityBox(self)
    end
    allowed
  end
end
PokeBattle_Battler.prepend(ChrookedHyperCutterRebound)
