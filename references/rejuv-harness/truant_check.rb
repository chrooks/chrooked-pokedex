# Standalone check of the Truant rework. `load`s chrooked_truant.rb so the
# shipped code runs, against stub battler/AI classes that copy only the vanilla
# lines the mod depends on (Battler.rb:5704 recharge, :5747 loaf check).
# Run: ruby references/rejuv-harness/truant_check.rb

Move = Struct.new(:status) do
  def pbIsStatus?; status; end
  def pbIsDamaging?; !status; end
end
STATUS = Move.new(true)
DAMAGE = Move.new(false)

class PokeBattle_Battler
  attr_accessor :effects, :ability
  def initialize(ability, loafing, recharge = 0)
    @ability = ability
    @effects = { Truant: loafing, HyperBeam: recharge }
  end

  def pbTryUseMove(choice, basemove, flags = {})
    return :recharge if @effects[:HyperBeam] > 0
    return :loafed if self.ability == :TRUANT && @effects[:Truant]
    :acted
  end
end

class PokeBattle_AI
  attr_accessor :attacker, :move
  def getModifiedMoveScore(finalscores, scoreindex, _opponent); finalscores[scoreindex]; end
end

load File.join(File.dirname(__FILE__), "chrooked_truant.rb")

$fails = 0
def check(label, got, want)
  ok = got == want
  $fails += 1 unless ok
  puts "#{ok ? 'PASS' : 'FAIL'}  #{label}: got #{got.inspect}, want #{want.inspect}"
end

loaf = PokeBattle_Battler.new(:TRUANT, true)
check("loaf turn, status move acts", loaf.pbTryUseMove([], STATUS), :acted)
check("loaf flag restored after the call", loaf.effects[:Truant], true)
check("loaf turn, damaging move loafs", loaf.pbTryUseMove([], DAMAGE), :loafed)
check("active turn, damaging move acts", PokeBattle_Battler.new(:TRUANT, false).pbTryUseMove([], DAMAGE), :acted)
check("recharge still eats the loaf turn", PokeBattle_Battler.new(:TRUANT, true, 1).pbTryUseMove([], STATUS), :recharge)
check("non-Truant battler untouched", PokeBattle_Battler.new(:INNERFOCUS, true).pbTryUseMove([], DAMAGE), :acted)

ai = PokeBattle_AI.new
ai.attacker = loaf
ai.move = DAMAGE
check("AI: damaging move on own loaf turn scores 0", ai.getModifiedMoveScore([80], 0, nil), 0)
check("AI: harmful -1 stays -1", ai.getModifiedMoveScore([-1], 0, nil), -1)
ai.move = STATUS
check("AI: status move on loaf turn keeps its score", ai.getModifiedMoveScore([40], 0, nil), 40)
ai.attacker = PokeBattle_Battler.new(:TRUANT, false)
ai.move = DAMAGE
check("AI: damaging move on active turn keeps its score", ai.getModifiedMoveScore([80], 0, nil), 80)

exit($fails.zero? ? 0 : 1)
