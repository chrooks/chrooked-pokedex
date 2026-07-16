# chrooked:tectonize
# Tectonize — "Normal-type moves become Ground-type and gain +20% power."
#   damage-calc: raw Normal move (not Z-move; excludes Weather Ball, Natural
#   Gift, Judgment, Techno Blast, Multi-Attack, Revelation Dance, Terrain
#   Pulse, Struggle) => type becomes GROUND, damage x1.2
# Test cases:
#   - Normal move (e.g. Body Slam) => hits as Ground with 1.2x power
#   - non-Normal move => untouched
#   - Weather Ball / Struggle => untouched
Chrooked.register_ize(:TECTONIZE, :GROUND)
