# chrooked:starfall
# Starfall — "Special moves gain 20% power for each consecutive turn spent
#             attacking, up to 60%. Switching or a non-attacking turn resets it."
#   damage-calc: special damaging move => x(1 + 0.2 * streak), streak capped at 3
#   turn-end:    dealt damage this round => streak += 1, else streak = 0
#   switch-in:   streak = 0
# Test cases:
#   - first attack in => x1.0; second consecutive => x1.2; fourth+ => x1.6
#   - a Recover turn resets to x1.0
#   - switching out and back resets to x1.0
#   - physical move: no boost, but the turn still counts
STARFALL_STEP = 0.2
STARFALL_CAP = 3

CHROOKED_SWITCH_IN[:STARFALL] = lambda { |battler, battle|
  battler.effects[:ChrookedStarfall] = 0
  battler.effects[:ChrookedStarfallHit] = false
}
CHROOKED_ON_DEAL[:STARFALL] = lambda { |move, user, target, battle|
  user.effects[:ChrookedStarfallHit] = true
}
CHROOKED_TURN_END[:STARFALL] = lambda { |battler, battle|
  if battler.effects[:ChrookedStarfallHit]
    battler.effects[:ChrookedStarfall] = [(battler.effects[:ChrookedStarfall] || 0) + 1, STARFALL_CAP].min
  else
    battler.effects[:ChrookedStarfall] = 0
  end
  battler.effects[:ChrookedStarfallHit] = false
}
CHROOKED_DAMAGE_MODS[:STARFALL] = lambda { |move, attacker, opponent|
  next 1.0 unless move.pbIsSpecial?(attacker, move.pbType(attacker))
  1.0 + STARFALL_STEP * [(attacker.effects[:ChrookedStarfall] || 0), STARFALL_CAP].min
}
