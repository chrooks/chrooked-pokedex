# chrooked:solarpower
# Solar Power — rebuilt into Whiteout's shape, for sun.
#   damage-calc: in sun, the 1.5x follows the user's HIGHER attacking stat
#                (Atk >= SpA => physical moves, otherwise special moves)
#   turn-end:    the vanilla 1/8-max-HP sun drain is vetoed outright
#
# Vanilla already appends its own x1.5 to atkmult for SPECIAL moves in sun
# (Battle_Move.rb:1492 — the damage path; Battler.rb:7344 is the AI/stat-screen
# twin), so this handler only has to cover the difference:
#   - special user (SpA > Atk)   -> vanilla's boost is already the right one => 1.0
#   - physical user (Atk >= SpA) -> pay 1.5 on physical, refund vanilla on special
#
# The drain lives inside pbEndOfRoundPhase (Battle.rb:5446) with no hook of its
# own, so the veto keys on the holder + the sunlight message. Dry Skin's identical
# message is safe (different ability), and the Desert-field burn already excludes
# :SOLARPOWER at Battle.rb:5464. Castform Crest shares the block but not the
# ability symbol, so it keeps its vanilla drain.
#
# Gating mirrors vanilla exactly: pbWeather returns 0 under Cloud Nine / Air Lock,
# Utility Umbrella and the FROZENDIMENSION field negate it, and Rejuv's harsh sun
# (Desolate Land / Orichalcum Pulse) still reads as :SUNNYDAY.
#
# ponytail: the refund divides final damage by 1.5 where vanilla multiplied the
#   stat by 1.5, so a physical holder clicking a special move can land +-1 damage
#   off true parity. Exact parity would mean overriding all of pbCalcDamage.
# ponytail: Rejuv's AI still models Solar Power as spatk-only (Battle_AI.rb:13896)
#   and still docks 0.125 HP/turn for the drain (Battle_AI.rb:9218), so it
#   under-rates a physical holder. Cosmetic — it never changes what resolves.
#
# Test cases:
#   - sun, Atk >= SpA, physical move => 1.5x
#   - sun, Atk >= SpA, special move  => ~1.0x (vanilla's boost refunded)
#   - sun, SpA > Atk, special move   => 1.5x (vanilla's, untouched)
#   - sun, SpA > Atk, physical move  => no boost
#   - sun, end of turn               => no HP lost, no ability box
#   - Utility Umbrella / FROZENDIMENSION / Air Lock => no boost
#   - Dry Skin holder in sun         => still takes its 1/8 drain
CHROOKED_DAMAGE_MODS[:SOLARPOWER] = lambda { |move, attacker, opponent|
  weather = move.battle.pbWeather(attacker)
  next 1.0 unless weather == :SUNNYDAY
  next 1.0 if attacker.hasWorkingItem(:UTILITYUMBRELLA) || move.battle.FE == :FROZENDIMENSION
  next 1.0 if attacker.spatk > attacker.attack # vanilla's spatk boost is already correct

  type = move.pbType(attacker)
  next 1.5 if move.pbIsPhysical?(attacker, type)
  next 1.0 / 1.5 if move.pbIsSpecial?(attacker, type)
  1.0
}

CHROOKED_HP_LOSS_VETO[:SOLARPOWER] = lambda { |battler, message|
  message.to_s.include?("sunlight")
}
