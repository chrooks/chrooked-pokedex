# chrooked:wintercoat
# Winter Coat — "The Pokémon is immune to Ice-type moves."
#   damage-calc: incoming Ice move => blocked (Soundproof-style, no heal, no stat change)
#   Ice Skater is COMPOSED as [wintercoat, slushrush]; the Speed half is vanilla
#   Slush Rush via chrooked_zz_zcompose.rb — never restate it here.
# Test cases:
#   - Blizzard => "It doesn't affect..." zero damage, no freeze roll
#   - Freeze-Dry => zero damage, immunity beats its Water override
#   - Icicle Crash => zero damage, no flinch roll
#   - Hail chip is weather, not a move: unaffected
CHROOKED_TYPE_IMMUNITY[:WINTERCOAT] = { type: :ICE, flag: :Soundproof }
