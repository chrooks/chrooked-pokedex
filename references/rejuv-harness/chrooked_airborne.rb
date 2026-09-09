# chrooked:airborne
# Airborne — "Draws Flying moves. Raises Speed. Not hit by Ground attacks."
#   Aerodynamic plus Levitate in one slot. Aerodynamic is kept as the
#   Flying-only version; the two coexist deliberately.
#
#   The core's CHROOKED_TYPE_IMMUNITY entry accepts an array of {type:, flag:}
#   hashes, so each blocked type carries its own flag. Ground uses :Levitate on
#   purpose: every vanilla Levitate counter — Gravity, Smack Down, Thousand
#   Arrows, Iron Ball, Ingrain, Mold Breaker, Bonebreaker's immunity bypass —
#   then cancels it with no extra code here.
#
# Test cases (drive in-game — the harness can't prove battle behavior):
#   - Air Slash   => "It doesn't affect..." and zero damage.
#   - Earthquake  => "It doesn't affect..." and zero damage.
#   - Earthquake under Gravity, or from a Mold Breaker user => normal damage.
CHROOKED_TYPE_IMMUNITY[:AIRBORNE] = [
  { type: :FLYING, flag: :Soundproof },
  { type: :GROUND, flag: :Levitate },
]
