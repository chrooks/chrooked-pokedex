# chrooked:sandguard
# Sand Guard — in a sandstorm, halves damage from special moves; immune to
# sandstorm chip. The Sp. Def lane of the sand family (Rush = Speed,
# Force = power, Veil = evasion). Ice Scales gated behind sand.
#   damage-calc (defender): sand active AND incoming move is special => x0.5
#   turn-end: no sandstorm residual (CHROOKED_WEATHER_IMMUNE via takesWeatherDamage?)
#
# Sand check mirrors chrooked_sandforce.rb: pbWeather returns 0 under Cloud
# Nine / Air Lock (the suppression), and the :DESERT / :ASHENBEACH fields count
# as sand the way vanilla's own sand riders treat them. Desert's Mark still
# negates the immunity — vanilla checks it before any ability (Battle_Effects.rb:1359)
# and our wrapper only runs when the vanilla list would have said "takes damage".
#
# The AI needs nothing: the core's pbRoughDamage wrapper runs damage_mult, so
# trainers see the halving.
#
# Test cases:
#   - sand, foe uses Surf (special)        => half damage
#   - sand, foe uses Earthquake (physical) => unchanged
#   - no weather, foe uses Thunderbolt     => unchanged
#   - sand end of turn                     => 0 chip
CHROOKED_DEFENSE_MODS[:SANDGUARD] = lambda { |move, attacker, opponent|
  battle = move.battle
  sandy = battle.pbWeather(attacker) == :SANDSTORM ||
          [:DESERT, :ASHENBEACH].include?(battle.FE)
  next 1.0 unless sandy
  move.pbIsSpecial?(attacker, move.pbType(attacker)) ? 0.5 : 1.0
}
CHROOKED_WEATHER_IMMUNE[:SANDGUARD] = [:SANDSTORM]
