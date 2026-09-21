# chrooked:hydrophyte
# Hydrophyte — "Immune to Water moves. Takes half damage from Fire moves."
#   An aquatic plant: water feeds it, and its waterlogged body resists flame.
#   Adapted from Elite Redux's Seaweed with the offensive half (Grass x2 vs Fire)
#   dropped and a Water immunity added in its place.
#   damage-calc: incoming Water move => blocked (Soundproof-style, no heal, no boost)
#   damage-calc: incoming Fire move  => x0.5 (defender-side, so Mold Breaker ignores it)
# Test cases:
#   - Surf        => "It doesn't affect..." zero damage
#   - Flamethrower => half the damage it would otherwise deal
#   - Scald       => zero damage, no burn roll
#   - Tackle      => normal damage
CHROOKED_TYPE_IMMUNITY[:HYDROPHYTE] = { type: :WATER, flag: :Soundproof }
CHROOKED_DEFENSE_MODS[:HYDROPHYTE] = lambda { |move, attacker, opponent|
  move.pbType(attacker) == :FIRE ? 0.5 : 1.0
}
