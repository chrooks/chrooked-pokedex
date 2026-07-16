# chrooked:highnoon
# High Noon — Fire/Psychic moves get STAB regardless of own types; Morning Sun
#   always restores 75% max HP.
#   damage-calc: off-type Fire or Psychic damaging move => x1.5
#   on-hit: Morning Sun recovery fixed at 3/4 max HP
# Test cases:
#   - off-type Fire move => 1.5x ; on-type => unchanged
#   - Morning Sun in any weather => 75% heal
CHROOKED_DAMAGE_MODS[:HIGHNOON] = lambda { |move, attacker, opponent|
  Chrooked.stab_grant(move, attacker, [:FIRE, :PSYCHIC])
}
CHROOKED_HEAL_OVERRIDE[[:HIGHNOON, :MORNINGSUN]] = 0.75
