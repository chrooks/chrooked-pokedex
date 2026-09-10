# Runnable check for the Magic-Guard-alike seam. No game needed:
#   docker run --rm -v "$PWD/references/rejuv-harness:/h:ro" ruby:3.2-slim ruby /h/impenetrable_check.rb
CHROOKED_HP_LOSS_VETO = {}
CHROOKED_WEATHER_IMMUNE = {}
CHROOKED_MAGIC_GUARD = []

# Vanilla shape, copied from Battle.rb:893.
class FakeBattle
  def magicGuardAbilities = [:MAGICGUARD]
end
module ChrookedBattleHooks
  def magicGuardAbilities
    guards = super
    CHROOKED_MAGIC_GUARD.empty? ? guards : guards + CHROOKED_MAGIC_GUARD
  end
end
FakeBattle.prepend(ChrookedBattleHooks)

require_relative "chrooked_impenetrable"
battle = FakeBattle.new

# Vanilla getRecoil, Battle_Move.rb:2268-2274.
def recoil(battle, ability, damage) =
  battle.magicGuardAbilities.include?(ability) ? 0 : (damage * 0.5).round

def check(label) = (yield ? puts("ok   #{label}") : abort("FAIL #{label}"))

check("Impenetrable joins the guard list") { battle.magicGuardAbilities.include?(:IMPENETRABLE) }
check("vanilla Magic Guard still listed")  { battle.magicGuardAbilities.include?(:MAGICGUARD) }
check("Head Smash recoil is 0")            { recoil(battle, :IMPENETRABLE, 200) == 0 }
check("a normal ability still recoils")    { recoil(battle, :STURDY, 200) == 100 }
check("weather immunity still registered") { CHROOKED_WEATHER_IMMUNE[:IMPENETRABLE].include?(:SANDSTORM) }

veto = CHROOKED_HP_LOSS_VETO[:IMPENETRABLE]
check("veto still blocks a burn tick")     { veto.call(nil, "Bastiodon was hurt by its burn!") }
check("veto ignores message-less ticks")   { !veto.call(nil, "") }
puts "all checks passed"
