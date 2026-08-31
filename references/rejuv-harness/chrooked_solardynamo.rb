# chrooked:solardynamo
# Solar Dynamo — Drought's sun on entry + Solar Power's boost with no drain.
#   switch-in: summon harsh sunlight (:SUNNYDAY), exactly like vanilla Drought
#     (Battler.rb — same duration/Heat Rock/field rules, canSetWeather? gating so
#     Heavy Rain / Delta Stream / etc. still block it).
#   damage-calc: in sun, this user's SPECIAL moves => x1.5
#     (1.5x damage == the 1.5x Sp.Atk vanilla Solar Power applies)
#   turn-end: NOTHING — :SOLARDYNAMO is its own symbol, so vanilla's
#     :SOLARPOWER end-of-turn drain (Battle.rb) never keys on it. No drain to add.
# Boost gating mirrors vanilla Solar Power exactly (Battler.rb:7432):
#   - pbWeather returns 0 under Cloud Nine / Air Lock, so == :SUNNYDAY is the
#     built-in suppression clause.
#   - Rejuv harsh sun (Desolate Land / Orichalcum Pulse) keeps weather :SUNNYDAY,
#     so Desert-summoned and extreme sun both count.
#   - Utility Umbrella and the FROZENDIMENSION field effect negate it, same as
#     vanilla Solar Power.
# Test cases:
#   - switch in with clear skies => harsh sunlight is set (5 turns, 8 w/ Heat Rock)
#   - switch in while Heavy Rain / Delta Stream active => sun blocked, no crash
#   - :SUNNYDAY, special move => 1.5x; end of turn => no HP lost
#   - :SUNNYDAY, physical move => no boost
#   - Air Lock / Cloud Nine active => pbWeather == 0 => no boost
CHROOKED_SWITCH_IN[:SOLARDYNAMO] = lambda { |battler, battle|
  next if battle.weather == :SUNNYDAY
  battle.pbShowAbilityBox(battler)
  if battle.canSetWeather?(:SUNNYDAY, showMessage: true)
    duration = battler.hasWorkingItem(:HEATROCK) ||
               [:DESERT, :MOUNTAIN, :SNOWYMOUNTAIN, :SKY].include?(battle.FE) ? 8 : 5
    duration = 3 + battle.pbRandom(6) if battle.FE == :DIMENSIONAL
    rainbowduration = duration
    duration = -1 if $game_switches[:Gen_5_Weather] == true && !battle.isOnline?
    battle.pbSetWeather(:SUNNYDAY, duration, nil, rainbowduration)
  end
  battle.pbHideAbilityBox(battler)
}

# Mirrors chrooked_solarpower.rb's RULE — boost whichever attacking stat is
# higher — but NOT its lambda. Solar Power corrects a boost vanilla already
# pays for :SOLARPOWER (Battle_Move.rb / Battle_AI.rb key on that symbol);
# vanilla knows nothing about :SOLARDYNAMO, so this pays the full 1.5 itself.
# Same rule, different baseline. Change Solar Power's rule and change this too
# until the composition model lands.
# Tie (Attack == Sp. Atk) resolves physical, matching Solar Power and Whiteout.
CHROOKED_DAMAGE_MODS[:SOLARDYNAMO] = lambda { |move, attacker, opponent|
  weather = move.battle.pbWeather(attacker)
  next 1.0 unless weather == :SUNNYDAY
  next 1.0 if attacker.hasWorkingItem(:UTILITYUMBRELLA) || move.battle.FE == :FROZENDIMENSION
  type = move.pbType(attacker)
  if attacker.attack >= attacker.spatk
    next 1.5 if move.pbIsPhysical?(attacker, type)
  else
    next 1.5 if move.pbIsSpecial?(attacker, type)
  end
  1.0
}
