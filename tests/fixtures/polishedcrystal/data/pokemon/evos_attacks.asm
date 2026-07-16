DEF EVOS_ATTACKS_STATE EQU -1
DEF EVOS_ATTACKS_LAST_LEVEL EQU -1
DEF EVOS_ATTACKS_CURRENT_MON EQUS ""
DEF EVOS_ATTACKS_FIRST EQU 1

MACRO evo_data
	if EVOS_ATTACKS_STATE == 0
		if !EVOS_ATTACKS_FIRST
			db -1 ; end of previous mon's moves
		endc
		REDEF EVOS_ATTACKS_FIRST EQU 0
		{EVOS_ATTACKS_CURRENT_MON}EvosAttacks:
	endc
	assert EVOS_ATTACKS_STATE != 2, "{EVOS_ATTACKS_CURRENT_MON} has evo_data after its learnset!"
	REDEF EVOS_ATTACKS_STATE EQU 1
	db \1 ; evolution type
	if \1 == EVOLVE_PARTY
		dp \2, PLAIN_FORM ; parameter
	else
		db \2 ; parameter
	endc
	if \1 == EVOLVE_STAT || \1 == EVOLVE_HOLDING
		db \3 ; ATK_*_DEF | time of day
		shift
	endc
	if _NARG > 3
		dp \3, \4
	else
		dp \3, PLAIN_FORM
	endc
ENDM

MACRO evos_attacks
	REDEF EVOS_ATTACKS_CURRENT_MON EQUS "\1"
	assert EVOS_ATTACKS_STATE != 0, "Empty learnset preceding {EVOS_ATTACKS_CURRENT_MON}!"
	REDEF EVOS_ATTACKS_STATE EQU 0
	REDEF EVOS_ATTACKS_LAST_LEVEL EQU -1
ENDM

; For split banks, adds a terminator and resets tracking
MACRO end_evos_attacks
	assert EVOS_ATTACKS_STATE != 0, "Empty learnset for {EVOS_ATTACKS_CURRENT_MON}!"
	db -1
	REDEF EVOS_ATTACKS_STATE EQU -1
	REDEF EVOS_ATTACKS_FIRST EQU 1
ENDM

MACRO learnset
	REDEF EVOS_ATTACKS_FIRST EQU 0
	if \1 < EVOS_ATTACKS_LAST_LEVEL
		warn "{EVOS_ATTACKS_CURRENT_MON} learns \2 at a lower level than previous move!"
	endc
	if EVOS_ATTACKS_LAST_LEVEL == -1 && \1 != 1
		warn "{EVOS_ATTACKS_CURRENT_MON} learns its first move at level \1 instead of level 1!"
	endc
	if \1 < 1 || \1 > 100
		warn "{EVOS_ATTACKS_CURRENT_MON} learns a move at level \1, which should be impossible!"
	endc
	REDEF EVOS_ATTACKS_LAST_LEVEL EQU \1
	if EVOS_ATTACKS_STATE != 2
		if EVOS_ATTACKS_STATE == 0
			{EVOS_ATTACKS_CURRENT_MON}EvosAttacks:
		endc
		db -1 ; end of evolutions and, if there were no evos, previous mon's moves
	endc
	REDEF EVOS_ATTACKS_STATE EQU 2
	db \1 ; level
	db \2 ; move
ENDM


SECTION "Evolutions and Attacks", ROMX

INCLUDE "data/pokemon/evolution_moves.asm"

INCLUDE "data/pokemon/evos_attacks_pointers.asm"

EvosAttacks::

	evos_attacks Bulbasaur
	evo_data EVOLVE_LEVEL, 16, IVYSAUR
	learnset 1, TACKLE
	learnset 3, GROWL
	learnset 7, LEECH_SEED
	learnset 9, VINE_WHIP
	learnset 13, POISONPOWDER
	learnset 13, SLEEP_POWDER
	learnset 15, MUD_SLAP ; Take Down → GSC TM move
	learnset 19, RAZOR_LEAF
	learnset 21, TAKE_DOWN ; Sweet Scent → Take Down
	learnset 25, GROWTH
	learnset 27, DOUBLE_EDGE
	learnset 31, ANCIENTPOWER ; Worry Seed → event move
	learnset 33, HEALINGLIGHT ; Synthesis → similar move
	learnset 37, SEED_BOMB
	learnset 43, SLUDGE_BOMB ; TM move

	evos_attacks Caterpie
	evo_data EVOLVE_LEVEL, 7, METAPOD
	learnset 1, TACKLE
	learnset 1, STRING_SHOT
	learnset 9, BUG_BITE

	evos_attacks Metapod
	evo_data EVOLVE_LEVEL, 10, BUTTERFREE
	learnset 1, TACKLE ; Caterpie move
	learnset 1, STRING_SHOT ; Caterpie move
	learnset 1, DEFENSE_CURL ; Harden → similar move

	evos_attacks FarfetchDGalarian
	evo_data EVOLVE_CRIT, TR_ANYTIME, SIRFETCH_D, PLAIN_FORM
	learnset 1, PECK
	learnset 1, MUD_SLAP ; Sand Attack → similar move
	learnset 5, LEER
	learnset 10, QUICK_ATTACK ; Fury Cutter → egg move
if DEF(FAITHFUL)
	learnset 15, ROCK_SMASH
else
	learnset 15, REVERSAL ; Rock Smash → TM move
endc
	learnset 20, FEINT_ATTACK ; Brutal Swing → similar move
	learnset 25, PROTECT ; Detect → similar move
	learnset 30, KNOCK_OFF
	learnset 35, STEEL_WING ; Defog → TM move
if DEF(FAITHFUL)
	learnset 40, NIGHT_SLASH ; Brick Break → egg move
else
	learnset 40, ROCK_SMASH ; Brick Break
endc
	learnset 45, SWORDS_DANCE
	learnset 50, BODY_SLAM ; Slam → TR move
	learnset 55, POISON_JAB ; Leaf Blade → TR move
	learnset 60, CLOSE_COMBAT ; Final Gambit → TR move
	learnset 65, BRAVE_BIRD

	evos_attacks FarfetchDPlain
	learnset 1, POISON_JAB
	learnset 1, BATON_PASS ; Brave Bird → event move
	learnset 1, PECK
	learnset 1, MUD_SLAP ; Sand Attack → similar move
	learnset 1, LEER
	learnset 7, FURY_STRIKES ; Fury Attack → similar move
	learnset 9, AERIAL_ACE
	learnset 13, KNOCK_OFF
	learnset 15, RAZOR_LEAF ; LGPE move
	learnset 19, SLASH
	learnset 21, KARATE_CHOP ; Air Cutter → new move
	learnset 25, SWORDS_DANCE
	learnset 31, AGILITY
	learnset 33, NIGHT_SLASH
	learnset 37, ACROBATICS
	learnset 43, HI_JUMP_KICK ; Feint → new move
	learnset 45, FALSE_SWIPE
	learnset 49, AIR_SLASH
	learnset 55, BRAVE_BIRD

	evos_attacks Flaaffy
if DEF(FAITHFUL)
	evo_data EVOLVE_LEVEL, 30, AMPHAROS
else
	evo_data EVOLVE_LEVEL, 36, AMPHAROS
endc
	learnset 1, TACKLE
	learnset 1, GROWL
	learnset 4, THUNDER_WAVE
	learnset 8, THUNDERSHOCK
	learnset 11, MUD_SLAP ; Cotton Spore → GSC TM move
	learnset 16, SPARK ; Charge → new move
	learnset 20, HEAL_BELL ; Take Down → HGSS tutor move
	learnset 25, TAKE_DOWN ; Electro Ball → Take Down
	learnset 29, CONFUSE_RAY
	learnset 34, POWER_GEM
	learnset 38, THUNDERBOLT ; Discharge → TM move
	learnset 43, SAFEGUARD ; Cotton Guard → egg move
	learnset 47, DAZZLINGLEAM ; Signal Beam → new move
	learnset 52, LIGHT_SCREEN
	learnset 56, THUNDER


	; Also terminates previous mon's learnset
	EggEvosAttacks:
	db -1 ; no more evolutions
	db -1 ; no more level-up moves
