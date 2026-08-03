# chrooked:downpour
# Downpour — "In rain, boosts moves using this Pokemon's higher attacking stat by 50%."
#   damage-calc: rain active; if Atk >= SpA boost physical moves, else special => x1.5
# The rain twin of Whiteout. Utility Umbrella negates it, same as every other rain
# ability; pbWeather returns 0 under Cloud Nine / Air Lock, and Primordial Sea's
# heavy rain still reads as :RAINDANCE (Battler.rb:2784), so it counts.
# ponytail: weather-only, no Rejuv field-effect riders — matches Whiteout.
# Test cases:
#   - rain, physical attacker (Atk >= SpA) uses physical move => 1.5x
#   - rain, same mon uses special move => no boost
#   - rain, Utility Umbrella held => no boost
#   - no rain => no boost
CHROOKED_DAMAGE_MODS[:DOWNPOUR] = lambda { |move, attacker, opponent|
  weather = move.battle.pbWeather(attacker)
  next 1.0 unless weather == :RAINDANCE
  next 1.0 if attacker.hasWorkingItem(:UTILITYUMBRELLA)
  type = move.pbType(attacker)
  physical_user = attacker.attack >= attacker.spatk
  boosted = physical_user ? move.pbIsPhysical?(attacker, type) : move.pbIsSpecial?(attacker, type)
  boosted ? 1.5 : 1.0
}
