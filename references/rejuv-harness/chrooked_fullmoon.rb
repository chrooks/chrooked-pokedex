# chrooked:fullmoon
# Full Moon — Dark/Fairy moves get STAB regardless of own types; Moonlight
#   always restores 75% max HP.
#   damage-calc: off-type Dark or Fairy damaging move => x1.5
#   on-hit: Moonlight recovery fixed at 3/4 max HP
# Test cases:
#   - off-type Dark move => 1.5x ; on-type => unchanged
#   - Moonlight in any weather => 75% heal
CHROOKED_DAMAGE_MODS[:FULLMOON] = lambda { |move, attacker, opponent|
  Chrooked.stab_grant(move, attacker, [:DARK, :FAIRY])
}
CHROOKED_HEAL_OVERRIDE[[:FULLMOON, :MOONLIGHT]] = 0.75
