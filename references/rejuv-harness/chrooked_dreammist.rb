# chrooked:dreammist
# Dream Mist (move mechanic) — a 65 BP special Psychic hit that ALSO applies the
#   Nightmare effect. The move data layer can't express "inflict Nightmare" as an
#   additional effect, so this adds it. The damage itself is plain move data.
#   on-hit: Dream Mist connects => apply Nightmare if the target is asleep, or if
#           the user has Daydreamer (which waives target-asleep requirements)
#   The 1/4 max HP end-of-round tick, and the clearing of the effect when neither
#   sleep nor a Daydreamer bearer sustains it, are both NATIVE (Battle.rb:6516).
# Test cases:
#   - asleep target, any user => Nightmare applied, ticks 1/4 per round
#   - awake target, Daydreamer user => Nightmare applied anyway
#   - awake target, non-Daydreamer user => damage only, silent, no residual
#   - target already under Nightmare => damage only, not reapplied
#   - target faints from the hit => no application
#   - damage absorbed by a Substitute => damage only, no residual
CHROOKED_MOVE_ON_DEAL[:DREAMMIST] = lambda { |move, user, target, battle|
  next if target.isFainted? || target.effects[:Nightmare]
  next if target.damagestate.substitute
  # The gate Daydreamer waives. Mirrors the vanilla Nightmare requirement.
  next unless target.isSleeping? || user.ability == :DAYDREAMER

  target.effects[:Nightmare] = true
  battle.pbDisplay(_INTL("{1} began having a nightmare!", target.pbThis))
}
