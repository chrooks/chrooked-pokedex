# chrooked:equinox
# Equinox — "Boosts Atk or SpAtk to match the higher value."
#   Ported from Elite Redux (include/constants/abilities.h: "The user Attack and
#   Special Attack are equal to the higher of the two, Applies after Stat
#   Modifiers"; src/battle_util.c highestAttackStat).
#
#   The comparison is made AFTER stat stages, and the winning stat carries its
#   own stage across — so a Swords Dance also powers special moves. The move's
#   category is untouched, so a special move fired off a higher Attack still
#   targets the foe's Sp. Def, and contact/flags are unchanged.
#
#   Ties go to Attack (the source compares with `>`, defaulting to STAT_ATK).
#
# Test cases (drive in-game — the harness can't run a battle):
#   - 170 Atk / 65 SpA, use a special move => damage off 170, still vs Sp. Def.
#   - Same mon after Nasty Plot x2 => SpA 65 at +2 is still under 170, so
#     Attack keeps winning; damage does not change.
#   - Swords Dance then a special move => the +2 Attack stage carries over.
CHROOKED_ATTACK_EQUALIZE << :EQUINOX
