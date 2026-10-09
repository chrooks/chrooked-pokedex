# chrooked:nocturnal
# Nocturnal — "A creature of the night. Dark-type moves do not affect it."
#   damage-calc: incoming Dark move => blocked (Soundproof-style, no heal, no stat change)
#   Witching Hour is COMPOSED as [nocturnal, levitate]; the Ground half is vanilla
#   Levitate via chrooked_zz_zcompose.rb — never restate it here.
# Test cases (drive in-game — the harness can't prove battle behavior):
#   - Knock Off / Dark Pulse => "It doesn't affect..." zero damage, item kept
#   - Shadow Ball            => normal damage
CHROOKED_TYPE_IMMUNITY[:NOCTURNAL] = { type: :DARK, flag: :Soundproof }
