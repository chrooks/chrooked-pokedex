# Standalone check of the weather-attack family's branch logic:
# Solar Power (sun), Downpour (rain), Sand Force (sand), Whiteout (hail/snow).
# Stubs just enough of Rejuv's battle objects to load the real mod files and run
# their lambdas verbatim — so this can't drift from what ships.
#   ruby references/rejuv-harness/weatheratk_check.rb
CHROOKED_DAMAGE_MODS = {}
CHROOKED_HP_LOSS_VETO = {}
CHROOKED_AI_HP_REFUND = {}
CHROOKED_SWITCH_IN = {}

HERE = File.dirname(__FILE__)
%w[solarpower downpour sandforce whiteout solardynamo].each { |id| load File.join(HERE, "chrooked_#{id}.rb") }

Battle = Struct.new(:weather, :FE) do
  def pbWeather(_battler); weather; end
end

Battler = Struct.new(:attack, :spatk, :item) do
  def hasWorkingItem(sym); item == sym; end
end

Move = Struct.new(:battle, :category, :movetype) do
  def pbType(_attacker); movetype || :NORMAL; end
  def pbIsPhysical?(_a, _t); category == :physical; end
  def pbIsSpecial?(_a, _t); category == :special; end
end

PHYS_MON = Battler.new(120, 60, nil)  # Atk > SpA
SPEC_MON = Battler.new(60, 120, nil)  # SpA > Atk
TIE_MON  = Battler.new(100, 100, nil) # tie resolves physical

$failures = 0
def check(label, got, want)
  ok = (got - want).abs < 0.0001
  $failures += 1 unless ok
  puts "#{ok ? 'ok  ' : 'FAIL'} #{label} => #{got.round(4)} (want #{want.round(4)})"
end

def mult(ability, weather, mon, category, fe: nil, type: nil)
  move = Move.new(Battle.new(weather, fe), category, type)
  CHROOKED_DAMAGE_MODS[ability].call(move, mon, nil)
end

puts "-- Solar Power (sun) — vanilla already boosts SPECIAL, so we pay physical and refund special"
check("phys user, physical move",  mult(:SOLARPOWER, :SUNNYDAY, PHYS_MON, :physical), 1.5)
check("phys user, special move",   mult(:SOLARPOWER, :SUNNYDAY, PHYS_MON, :special), 1.0 / 1.5)
check("spec user, special move",   mult(:SOLARPOWER, :SUNNYDAY, SPEC_MON, :special), 1.0)
check("spec user, physical move",  mult(:SOLARPOWER, :SUNNYDAY, SPEC_MON, :physical), 1.0)
check("tie resolves physical",     mult(:SOLARPOWER, :SUNNYDAY, TIE_MON, :physical), 1.5)
check("no sun, no change",         mult(:SOLARPOWER, nil, PHYS_MON, :physical), 1.0)
check("frozen dimension",          mult(:SOLARPOWER, :SUNNYDAY, PHYS_MON, :physical, fe: :FROZENDIMENSION), 1.0)
check("utility umbrella",          mult(:SOLARPOWER, :SUNNYDAY, Battler.new(120, 60, :UTILITYUMBRELLA), :physical), 1.0)
check("drain vetoed",              CHROOKED_HP_LOSS_VETO[:SOLARPOWER].call(PHYS_MON, "Heliolisk was hurt by the sunlight!") ? 1.0 : 0.0, 1.0)
check("other damage untouched",    CHROOKED_HP_LOSS_VETO[:SOLARPOWER].call(PHYS_MON, "Heliolisk was hurt by poison!") ? 1.0 : 0.0, 0.0)

puts "\n-- Solar Power — the AI's phantom drain is refunded so it stops planning around it"
def refund(mon, weather)
  CHROOKED_AI_HP_REFUND[:SOLARPOWER].call(mon, Battle.new(weather, nil))
end
check("sun, refunds the 1/8 the AI docked", refund(PHYS_MON, :SUNNYDAY), 0.125)
check("no sun, nothing to refund",          refund(PHYS_MON, nil), 0.0)
check("umbrella — AI never docked, so 0",   refund(Battler.new(120, 60, :UTILITYUMBRELLA), :SUNNYDAY), 0.0)

puts "\n-- Downpour (rain) and Whiteout (hail/snow) — full boost, both branches ours"
[[:DOWNPOUR, :RAINDANCE], [:WHITEOUT, :HAIL], [:WHITEOUT, :SNOW]].each do |ability, weather|
  check("#{ability}/#{weather} phys user, physical", mult(ability, weather, PHYS_MON, :physical), 1.5)
  check("#{ability}/#{weather} phys user, special",  mult(ability, weather, PHYS_MON, :special), 1.0)
  check("#{ability}/#{weather} spec user, special",  mult(ability, weather, SPEC_MON, :special), 1.5)
  check("#{ability}/#{weather} wrong weather",       mult(ability, :SUNNYDAY, PHYS_MON, :physical), 1.0)
end
check("Downpour negated by Utility Umbrella", mult(:DOWNPOUR, :RAINDANCE, Battler.new(120, 60, :UTILITYUMBRELLA), :physical), 1.0)

puts "\n-- Sand Force (sand) — vanilla's 1.3 Rock/Ground/Steel rider is refunded, ours pays 1.5"
check("phys user, physical Ice move",  mult(:SANDFORCE, :SANDSTORM, PHYS_MON, :physical, type: :ICE), 1.5)
check("phys user, physical Ground",    mult(:SANDFORCE, :SANDSTORM, PHYS_MON, :physical, type: :GROUND), 1.5 / 1.3)
check("phys user, special Ice",        mult(:SANDFORCE, :SANDSTORM, PHYS_MON, :special, type: :ICE), 1.0)
check("phys user, special Rock",       mult(:SANDFORCE, :SANDSTORM, PHYS_MON, :special, type: :ROCK), 1.0 / 1.3)
check("spec user, special Steel",      mult(:SANDFORCE, :SANDSTORM, SPEC_MON, :special, type: :STEEL), 1.5 / 1.3)
check("tie resolves physical",         mult(:SANDFORCE, :SANDSTORM, TIE_MON, :physical, type: :ICE), 1.5)
check("Desert field, no sandstorm",    mult(:SANDFORCE, nil, PHYS_MON, :physical, type: :ICE, fe: :DESERT), 1.5)
check("no sand, nothing touched",      mult(:SANDFORCE, nil, PHYS_MON, :physical, type: :GROUND), 1.0)
check("ignores Utility Umbrella",      mult(:SANDFORCE, :SANDSTORM, Battler.new(120, 60, :UTILITYUMBRELLA), :physical, type: :ICE), 1.5)

puts "\n-- Solar Dynamo: COMPOSED, so it must own no damage rule of its own --"
# It used to hand-copy Solar Power's lambda here and drifted: Sp.Atk-only after
# Solar Power moved to the higher attacking stat, wrong in-game on four species.
# The Ruleset now declares `behaviors: [solarpower, drought]`, so the holder
# becomes a ChrookedAbilitySet and Solar Power's OWN lambda applies. A lambda
# reappearing under :SOLARDYNAMO means someone re-copied the rule.
def check_nil(label, got)
  ok = got.nil?
  $failures += 1 unless ok
  puts "#{ok ? 'ok  ' : 'FAIL'} #{label}: got #{got.inspect}, want nil"
end
check_nil("no damage mod of its own",  CHROOKED_DAMAGE_MODS[:SOLARDYNAMO])
check_nil("no HP-loss veto of its own", CHROOKED_HP_LOSS_VETO[:SOLARDYNAMO])
check_nil("no AI refund of its own",    CHROOKED_AI_HP_REFUND[:SOLARDYNAMO])

puts "\n#{$failures.zero? ? 'all checks passed' : "#{$failures} FAILURES"}"
exit($failures.zero? ? 0 : 1)
