# chrooked:landbreaker
# Landbreaker — "A mountain-crumbling blow. Destroys the terrain and leaves
#   stealth rocks around the target."
#   on-hit: end the temporary terrain / overlay (the Ice Spinner rule, Battle_MoveEffects
#   0x306 -> endTempFieldOrOverlay). Weather is NOT touched — it must coexist with
#   Sand Stream. Then set Stealth Rock on the target's side if absent.
# Test cases:
#   - hit under Grassy Terrain + Sandstorm => terrain ends, sand stays, SR on the foe
#   - hit when the foe already has SR    => damage only, no change
#   - miss                                => nothing
CHROOKED_MOVE_ON_DEAL[:LANDBREAKER] = lambda { |move, user, target, battle|
  battle.endTempFieldOrOverlay if battle.canEndTempFieldOrOverlay?
  side = target.pbOwnSide
  next if side.effects[:StealthRock]
  side.effects[:StealthRock] = true
  battle.pbDisplay(_INTL("Rubble was scattered around {1}'s team!", target.pbThis))
}
