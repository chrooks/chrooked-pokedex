# chrooked:sandforce
# Sand Force — rebuilt into Whiteout's shape, for sand. Replaces the vanilla
# "Rock/Ground/Steel moves x1.3" rider with "the move category matching your
# higher attacking stat x1.5", on every type.
#   damage-calc: sand active; if Atk >= SpA boost physical moves, else special => x1.5
#
# Vanilla appends its 1.3 as a BASE POWER rider (Battle_Move.rb:1276) under exactly
# the condition mirrored below, so this handler refunds that 1.3 on Rock/Ground/
# Steel moves and pays its own 1.5 on the right category. The two compose: a
# physical holder's Earthquake in sand nets 1.5/1.3, its Ice Punch nets a clean 1.5.
#
# The sandstorm-damage immunity Sand Force grants (Battle_Effects.rb:1363) is
# untouched — it keys on the ability symbol and is not part of this rework.
# The AI needs no special handling: the core's pbRoughDamage wrapper runs this
# same lambda over the AI's damage model, which cancels its mirrored 1.3 too
# (Battle_AI.rb:13677). Its sand-setting score at Battle_AI.rb:7191 stays correct.
#
# Utility Umbrella does not block sand, so there is no umbrella clause; pbWeather
# returns 0 under Cloud Nine / Air Lock, which is the suppression. The
# :DESERT / :ASHENBEACH field riders are vanilla's own — kept verbatim.
#
# ponytail: the refund divides final damage by 1.3 where vanilla multiplied base
#   power by 1.3 through chainMods/pokeRound, so a Rock/Ground/Steel hit can land
#   +-1 damage off true parity. Exact parity would mean overriding pbCalcDamage.
#
# Test cases:
#   - sand, Atk >= SpA, physical Ice move  => 1.5x
#   - sand, Atk >= SpA, physical Ground move => 1.5/1.3 (vanilla's rider refunded)
#   - sand, Atk >= SpA, special move       => no boost, and Rock/Ground/Steel refunded
#   - sand, SpA > Atk, special move        => 1.5x
#   - Desert field, no sandstorm           => still active
#   - clear weather, neutral field         => no change at all
CHROOKED_DAMAGE_MODS[:SANDFORCE] = lambda { |move, attacker, opponent|
  battle = move.battle
  sandy = battle.pbWeather(attacker) == :SANDSTORM ||
          [:DESERT, :ASHENBEACH].include?(battle.FE)
  next 1.0 unless sandy

  type = move.pbType(attacker)
  mult = 1.0
  # Refund vanilla's Rock/Ground/Steel base-power rider — this ability no longer
  # cares about the move's type, only which attacking stat it uses.
  mult /= 1.3 if [:ROCK, :GROUND, :STEEL].include?(type)
  physical_user = attacker.attack >= attacker.spatk
  boosted = physical_user ? move.pbIsPhysical?(attacker, type) : move.pbIsSpecial?(attacker, type)
  mult *= 1.5 if boosted
  mult
}
