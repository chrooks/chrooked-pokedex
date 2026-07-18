# chrooked:spectralize
# Spectralize — "Normal-type moves become Ghost-type and gain +20% power."
#   damage-calc: raw Normal move (not Z-move; excludes Weather Ball, Natural
#   Gift, Judgment, Techno Blast, Multi-Attack, Revelation Dance, Terrain
#   Pulse, Struggle) => type becomes GHOST, damage x1.2
# Test cases:
#   - Normal move (e.g. Body Slam) => hits as Ghost with 1.2x power
#   - non-Normal move => untouched
#   - Weather Ball / Struggle => untouched
Chrooked.register_ize(:SPECTRALIZE, :GHOST)
