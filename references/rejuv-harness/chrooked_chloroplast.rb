# chrooked:chloroplast
# Chloroplast — "This Pokemon's moves act as if the sun is shining."
#   damage-calc: weather resolution for this user's moves returns Harsh
#   Sunlight (Mega Sol's own seam) — Solar Beam skips charge, Weather Ball
#   turns Fire, sun damage mods apply, Synthesis heals 2/3, etc.
# Test cases:
#   - Solar Beam with no weather => fires without charging
#   - Weather Ball => Fire-type, boosted
CHROOKED_WEATHER_FOR_USER[:CHLOROPLAST] = :SUNNYDAY
