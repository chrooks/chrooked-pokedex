MoveDescriptions::
; entries correspond to move ids (see constants/move_constants.asm)
	table_width 2
	dw AcrobaticsDescription
	dw KarateChopDescription
	dw DoubleSlapDescription
	dw AerialAceDescription
	dw DragonClawDescription
	dw PayDayDescription
	dw FirePunchDescription
	dw IcePunchDescription
	dw ThunderpunchDescription
	dw ScratchDescription
	dw XScissorDescription
	dw NightSlashDescription
	dw AirSlashDescription
	dw SwordsDanceDescription
	dw CutDescription
	dw GustDescription
	dw WingAttackDescription
	dw SuckerPunchDescription
	dw FlyDescription
	dw DazzlingleamDescription
	dw VoltSwitchDescription
	dw VineWhipDescription
	dw StompDescription
	dw DoubleKickDescription
	dw FlareBlitzDescription
	dw StoneEdgeDescription
	dw FocusBlastDescription
	done

LowKickDescription:
	text "Deals more damage"
	next "to heavier foes."
	done

KarateChopDescription:
RazorLeafDescription:
CrabhammerDescription:
SlashDescription:
AeroblastDescription:
CrossChopDescription:
NightSlashDescription:
ShadowClawDescription:
StoneEdgeDescription:
if !DEF(FAITHFUL)
XScissorDescription:
endc
	text "Has a high criti-"
	next "cal hit ratio."
	done

SwiftDescription:
FeintAttackDescription:
DisarmVoiceDescription:
