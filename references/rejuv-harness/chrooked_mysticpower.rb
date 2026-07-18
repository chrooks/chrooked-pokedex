# chrooked:mysticpower
# Mystic Power — "Every move gets STAB regardless of the Pokemon's own types."
#   damage-calc: real damaging move (not Struggle) whose type the user does NOT
#   already carry => x1.5 (vanilla already paid STAB when it does carry it)
# Test cases:
#   - off-type damaging move => 1.5x
#   - on-type move => unchanged (no double STAB)
#   - Struggle / status move => unchanged
CHROOKED_DAMAGE_MODS[:MYSTICPOWER] = lambda { |move, attacker, opponent|
  Chrooked.stab_grant(move, attacker)
}
