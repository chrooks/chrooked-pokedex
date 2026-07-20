# chrooked:daydreamer
# Daydreamer — the mirror of Comatose. Moves that normally require a SLEEPING
#   TARGET work on any target. The target's real status is never changed.
#   Rejuv already has an ability doing this bypass (World of Nightmares), so
#   both hooks below just widen the checks that already exist.
#
#   Nightmare  — can-affect gate (Battle_MoveEffects.rb:6575) and the end-of-round
#                1/4 residual (Battle.rb:6516) BOTH resolve their bypass through
#                pbCheckSideAbility(:WORLDOFNIGHTMARES, ...). One wrapper on that
#                lookup covers both sites.
#   Dream Eater — Battle_MoveEffects.rb:5390 gates on `attacker.ability ==`
#                instead of the side lookup, so it needs its own prepend.
#
# Test cases:
#   - Dream Eater from a Daydreamer user hits an AWAKE foe and drains normally
#   - Nightmare from a Daydreamer user applies to an AWAKE foe and ticks 1/4 per turn
#   - Daydreamer switches out, foe is awake -> Nightmare clears next end-of-round
#   - Snore / Sleep Talk (user-asleep gates) are unaffected
#   - an ally WITHOUT Daydreamer still fails Dream Eater on an awake foe

module Chrooked
  module DaydreamerNightmare
    # Nightmare's two sleep gates both ask for :WORLDOFNIGHTMARES holders on the
    # side. Answer that question as if Daydreamer bearers were also holders.
    # Only that one query is widened, so Daydreamer does NOT pick up World of
    # Nightmares' other behavior (MeanLook trapping, the Starlight field message)
    # — those read `.ability ==` directly and never come through here.
    def pbCheckSideAbility(abilities, battler, **kwargs)
      list = Array(abilities)
      list += [:DAYDREAMER] if list.include?(:WORLDOFNIGHTMARES)
      super(list, battler, **kwargs)
    end
  end

  module DaydreamerDreamEater
    def pbCanAffectTarget(attacker, opponent, showMessage = false)
      return true if attacker.ability == :DAYDREAMER

      super
    end
  end
end

PokeBattle_Battle.prepend(Chrooked::DaydreamerNightmare)
PokeBattle_Move_0DE.prepend(Chrooked::DaydreamerDreamEater)
