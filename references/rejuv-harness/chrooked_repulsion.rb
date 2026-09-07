# chrooked:repulsion
# Repulsion — "On entry, the user gains Magnet Rise for 5 turns, becoming immune
#   to Ground-type moves. Ended early by Smack Down, Gravity, or Thousand Arrows."
#   switch-in: set effects[:MagnetRise] exactly as the move does
#   (Battle_MoveEffects ~6825): 5 turns, 8 on Electric Terrain / Factory /
#   Short Circuit; on Deep Earth the move gives +2 Speed instead, so we do too.
#   Does not stack with an active Magnet Rise. Ingrain / Smack Down block it
#   like they block the move. Vanilla handles the countdown and the removals.
# Test cases:
#   - switch in, foe Earthquakes the same turn => immune
#   - Smack Down on turn 3 => grounded at once
#   - switch in with Magnet Rise already active (Baton Pass) => no change
#   - Deep Earth field => +2 Speed, no float
CHROOKED_SWITCH_IN[:REPULSION] = lambda { |battler, battle|
  fe = battle.respond_to?(:FE) ? battle.FE : nil
  if fe == :DEEPEARTH
    battle.pbDisplay(_INTL("{1} uses electromagnetism to move faster!", battler.pbThis))
    battler.pbChangeStats(PBStats::SPEED, 2, battler, nil, abilitycheck: :skip)
    next
  end
  next if battler.effects[:MagnetRise] > 0 || battler.effects[:Ingrain] || battler.effects[:SmackDown]
  ov = battle.respond_to?(:OV) ? battle.OV : nil
  battler.effects[:MagnetRise] = ([:ELECTERRAIN, :FACTORY, :SHORTCIRCUIT].include?(fe) || ov == :ELECTERRAIN) ? 8 : 5
  battle.pbDisplay(_INTL("{1} levitated with electromagnetism!", battler.pbThis))
}
