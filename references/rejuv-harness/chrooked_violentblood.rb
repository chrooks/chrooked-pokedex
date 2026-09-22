# chrooked:violentblood
# Violent Blood — "Dark-type moves get STAB even when the user is not Dark."
#   damage-calc: off-type Dark damaging move => x1.5 (on-type is untouched —
#   Chrooked.stab_grant already pays nothing when vanilla STAB applies)
# Same seam and shape as Full Moon's Dark/Fairy grant, narrowed to Dark alone.
# Test cases (drive in-game):
#   - a non-Dark user's Crunch => 1.5x
#   - a Dark-type user's Crunch => unchanged (no double STAB)
#   - Waterfall => unchanged
CHROOKED_DAMAGE_MODS[:VIOLENTBLOOD] = lambda { |move, attacker, opponent|
  Chrooked.stab_grant(move, attacker, [:DARK])
}
