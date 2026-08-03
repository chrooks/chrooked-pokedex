# chrooked:duststorm
# Duststorm — "In a sandstorm, boosts moves using this Pokemon's higher attacking stat by 50%."
#   damage-calc: sand active; if Atk >= SpA boost physical moves, else special => x1.5
# The sand twin of Whiteout. Utility Umbrella does NOT block sand, so no umbrella
# clause; pbWeather returns 0 under Cloud Nine / Air Lock, which is the suppression.
# The :DESERT / :ASHENBEACH field-effect riders mirror vanilla Sand Force
# (Battle_Move.rb:1276) — in Rejuv those fields are sand for ability purposes.
# Test cases:
#   - sandstorm, physical attacker (Atk >= SpA) uses physical move => 1.5x
#   - sandstorm, same mon uses special move => no boost
#   - Desert field, no sandstorm => still boosted
#   - clear weather, neutral field => no boost
CHROOKED_DAMAGE_MODS[:DUSTSTORM] = lambda { |move, attacker, opponent|
  weather = move.battle.pbWeather(attacker)
  sandy = weather == :SANDSTORM || [:DESERT, :ASHENBEACH].include?(move.battle.FE)
  next 1.0 unless sandy
  type = move.pbType(attacker)
  physical_user = attacker.attack >= attacker.spatk
  boosted = physical_user ? move.pbIsPhysical?(attacker, type) : move.pbIsSpecial?(attacker, type)
  boosted ? 1.5 : 1.0
}
