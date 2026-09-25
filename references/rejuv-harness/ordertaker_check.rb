# Standalone check of Order Taker. `load`s chrooked_ordertaker.rb so the
# shipped code runs, against stubs that copy only the vanilla behavior the mod
# depends on (pbPartySingleOwner, pbCanIncreaseAnyStat?, pbChangeStats' +6 cap).
# Run: ruby references/rejuv-harness/ordertaker_check.rb

CHROOKED_SWITCH_IN = {}
module PBStats
  ATTACK = 1; DEFENSE = 2; SPATK = 3; SPDEF = 4; SPEED = 5
  Omni = [ATTACK, DEFENSE, SPATK, SPDEF, SPEED]
end
def _INTL(fmt, *args) = args.each_with_index.reduce(fmt) { |s, (a, i)| s.sub("{#{i + 1}}", a.to_s) }

Mon = Struct.new(:species, :hp, :egg, :name) do
  def isEgg? = egg
end
def mon(species, hp: 100, egg: false) = Mon.new(species, hp, egg, species.to_s.capitalize)

class Battle
  attr_reader :log
  def initialize(parties) = (@parties = parties; @log = [])
  def pbPartySingleOwner(index) = @parties[index]
  def pbShowAbilityBox(_b) = @log << :box
  def pbHideAbilityBox(_b) = nil
  def pbDisplay(msg) = @log << msg
end

class PokeBattle_Battler
  attr_accessor :index, :pokemonIndex, :stages, :ability
  def initialize(index, party_index, ability = :ORDERTAKER, stage = 0)
    @index, @pokemonIndex, @ability = index, party_index, ability
    @stages = Array.new(8, stage)
  end
  def pbThis = "Dondozo"
  def pbCanIncreaseAnyStat?(stats, *_) = stats.any? { |s| @stages[s] < 6 }
  def pbChangeStats(stats, amount, *_rest, **_kw) = stats.each { |s| @stages[s] = [@stages[s] + amount, 6].min }
end

class PokeBattle_AI
  def initialize(battle) = @battle = battle
  def pbStatChangingSwitch(mon, onlyabilities: false) = nil
end

load File.join(File.dirname(__FILE__), "chrooked_ordertaker.rb")

$fails = 0
def check(label, got, want)
  ok = got == want
  $fails += 1 unless ok
  puts "#{ok ? 'PASS' : 'FAIL'}  #{label}: got #{got.inspect}, want #{want.inspect}"
end

def enter(parties, battler)
  battle = Battle.new(parties)
  CHROOKED_SWITCH_IN[:ORDERTAKER].call(battler, battle)
  [battler.stages[1..5], battle.log]
end

dozo = mon(:DONDOZO)
up = [1, 1, 1, 1, 1]
flat = [0, 0, 0, 0, 0]

stages, log = enter({ 0 => [dozo, mon(:TATSUGIRI)] }, PokeBattle_Battler.new(0, 0))
check("Tatsugiri in the back => all five +1", stages, up)
check("ability box and message shown", log, [:box, "Dondozo is taking orders from Tatsugiri!"])

stages, log = enter({ 0 => [dozo, mon(:TATSUGIRI, hp: 0)] }, PokeBattle_Battler.new(0, 0))
check("fainted Tatsugiri => nothing", [stages, log], [flat, []])

stages, _ = enter({ 0 => [dozo, mon(:TATSUGIRI, egg: true)] }, PokeBattle_Battler.new(0, 0))
check("Tatsugiri egg => nothing", stages, flat)

stages, _ = enter({ 0 => [dozo, mon(:PIKACHU)] }, PokeBattle_Battler.new(0, 0))
check("no Tatsugiri => nothing", stages, flat)

# Multi battle: battler 0's owner has no Tatsugiri; ally owner (index 2) does.
stages, _ = enter({ 0 => [dozo, mon(:PIKACHU)], 2 => [mon(:TATSUGIRI)] }, PokeBattle_Battler.new(0, 0))
check("only the ally trainer has Tatsugiri => nothing", stages, flat)

stages, _ = enter({ 0 => [mon(:TATSUGIRI)] }, PokeBattle_Battler.new(0, 0))
check("holder itself is the only Tatsugiri => nothing", stages, flat)

stages, log = enter({ 0 => [dozo, mon(:TATSUGIRI)] }, PokeBattle_Battler.new(0, 0, :ORDERTAKER, 6))
check("already +6 everywhere => no box", [stages, log], [[6, 6, 6, 6, 6], []])

stages, _ = enter({ 0 => [nil, mon(:TATSUGIRI), dozo] }, PokeBattle_Battler.new(0, 2, :ORDERTAKER, 5))
check("nil slots skipped, cap at +6", stages, [6, 6, 6, 6, 6])

ai = PokeBattle_AI.new(Battle.new({ 1 => [mon(:TATSUGIRI), dozo] }))
cand = PokeBattle_Battler.new(1, 1)
ai.pbStatChangingSwitch(cand)
check("AI: candidate scored with +1s", cand.stages[1..5], up)
cand = PokeBattle_Battler.new(1, 1)
ai.pbStatChangingSwitch(cand, onlyabilities: true)
check("AI: post-Mega re-run adds nothing", cand.stages[1..5], flat)
cand = PokeBattle_Battler.new(1, 1, :INTREPIDSWORD)
ai.pbStatChangingSwitch(cand)
check("AI: other abilities untouched", cand.stages[1..5], flat)

exit($fails.zero? ? 0 : 1)
