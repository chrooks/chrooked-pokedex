; excerpt — trainer party referencing an ability slot by name
	db ABIL_BULBASAUR_CHLOROPHYLL | NAT_ADAMANT
	tr_mon 30, FARFETCH_D_GALARIAN @ LEEK, MALE
if DEF(FAITHFUL)
		tr_extra STEADFAST
else
		tr_extra STEADFAST, ATK_UP_SATK_DOWN
endc
