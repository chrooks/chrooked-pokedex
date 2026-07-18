# chrooked:whiteout
# Whiteout — "In hail, boosts moves using this Pokemon's higher attacking stat by 50%."
#   damage-calc: hail active; if Atk >= SpA boost physical moves, else special => x1.5
# Test cases:
#   - hail, physical attacker (Atk >= SpA) uses physical move => 1.5x
#   - hail, same mon uses special move => no boost
#   - no hail => no boost
CHROOKED_DAMAGE_MODS[:WHITEOUT] = lambda { |move, attacker, opponent|
  weather = move.battle.pbWeather(attacker)
  next 1.0 unless weather == :HAIL || weather == :SNOW
  type = move.pbType(attacker)
  physical_user = attacker.attack >= attacker.spatk
  boosted = physical_user ? move.pbIsPhysical?(attacker, type) : move.pbIsSpecial?(attacker, type)
  boosted ? 1.5 : 1.0
}
