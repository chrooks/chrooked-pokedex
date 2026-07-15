MACRO move
	db \1 ; animation
	db \2 ; effect
	db \3 ; power (0 for status moves, 1 for nonstandard base power)
	db \4 ; type
	db \5 ; accuracy (-1 for moves that ignore accuracy checks)
	db \6 ; pp
	db \7 ; effect chance
	db \8 ; category
	assert (\2 != EFFECT_MULTI_HIT || \3 < 52), "AI routines assume multihit BP x 5 <= 255"
ENDM

Moves::
; entries correspond to move ids (see constants/move_constants.asm)
	table_width MOVE_LENGTH
	move ACROBATICS,      EFFECT_CONDITIONAL_BOOST,  55, FLYING,    100, 15,   0, PHYSICAL
	move KARATE_CHOP,     EFFECT_NORMAL_HIT,         50, FIGHTING,  100, 25,   0, PHYSICAL
	move DOUBLE_SLAP,     EFFECT_MULTI_HIT,          15, NORMAL,     85, 10,   0, PHYSICAL
	move AERIAL_ACE,      EFFECT_ALWAYS_HIT,         60, FLYING,     -1, 20,   0, PHYSICAL
	move DRAGON_CLAW,     EFFECT_NORMAL_HIT,         80, DRAGON,    100, 15,   0, PHYSICAL
	move PAY_DAY,         EFFECT_PAY_DAY,            40, NORMAL,    100, 20,   0, PHYSICAL
	move FIRE_PUNCH,      EFFECT_BURN_HIT,           75, FIRE,      100, 15,  10, PHYSICAL
	move ICE_PUNCH,       EFFECT_FREEZE_HIT,         75, ICE,       100, 15,  10, PHYSICAL
	move THUNDERPUNCH,    EFFECT_PARALYZE_HIT,       75, ELECTRIC,  100, 15,  10, PHYSICAL
	move SCRATCH,         EFFECT_NORMAL_HIT,         40, NORMAL,    100, 35,   0, PHYSICAL
	move X_SCISSOR,       EFFECT_NORMAL_HIT,         80, BUG,       100, 15,   0, PHYSICAL
	move NIGHT_SLASH,     EFFECT_NORMAL_HIT,         70, DARK,      100, 15,   0, PHYSICAL
	move AIR_SLASH,       EFFECT_FLINCH_HIT,         75, FLYING,     95, 15,  30, SPECIAL
	move SWORDS_DANCE,    EFFECT_ATTACK_UP_2,         0, NORMAL,     -1, 20,   0, STATUS
if DEF(FAITHFUL)
	move CUT,             EFFECT_NORMAL_HIT,         50, NORMAL,     95, 30,   0, PHYSICAL
else
	move CUT,             EFFECT_NORMAL_HIT,         60, STEEL,     100, 30,   0, PHYSICAL
endc
	move GUST,            EFFECT_GUST,               40, FLYING,    100, 35,   0, SPECIAL
	move WING_ATTACK,     EFFECT_NORMAL_HIT,         60, FLYING,    100, 35,   0, PHYSICAL
	move SUCKER_PUNCH,    EFFECT_SUCKER_PUNCH,       70, DARK,      100,  5,   0, PHYSICAL
if DEF(FAITHFUL)
	move FLY,             EFFECT_FLY,                90, FLYING,     95, 15,   0, PHYSICAL
else
	move FLY,             EFFECT_FLY,                90, FLYING,    100, 15,   0, PHYSICAL
endc
	move DAZZLINGLEAM,    EFFECT_NORMAL_HIT,         80, FAIRY,     100, 10,   0, SPECIAL
	move VOLT_SWITCH,     EFFECT_SWITCH_HIT,         70, ELECTRIC,  100, 20,   0, SPECIAL
