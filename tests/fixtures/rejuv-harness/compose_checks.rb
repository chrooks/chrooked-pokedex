# Drives the GENERATED chrooked_zz_zcompose.rb — not a fixture copy — so this
# cannot pass while the applier emits something else.
#   ruby compose_checks.rb <harness_dir> <generated_compose.rb>
HARNESS = ARGV[0]
GENERATED = ARGV[1]

$failures = 0
def check(label, got, want)
  ok = (got == want)
  $failures += 1 unless ok
  puts "#{ok ? 'ok  ' : 'FAIL'} #{label}: got #{got.inspect}, want #{want.inspect}"
end

# Stub battler so the compose hook installs and can be driven.
class PokeBattle_Battler
  attr_accessor :ability, :backupability
  def initialize(ability); @ability = ability; end
  def pbInitPokemon(_pkmn, _idx); end
end

module Chrooked; end

load File.join(HARNESS, "chrooked_zz_redux.rb")   # defines ChrookedAbilitySet
load GENERATED                                     # the applier's output

def build(sym)
  b = PokeBattle_Battler.new(sym)
  b.pbInitPokemon(nil, 0)
  b
end

puts "-- the table came from the Ruleset --"
check("solardynamo is composed", CHROOKED_COMPOSITION.key?(:SOLARDYNAMO), true)
check("its parts", CHROOKED_COMPOSITION[:SOLARDYNAMO], [:SOLARPOWER, :DROUGHT])
check("a plain ability is absent", CHROOKED_COMPOSITION.key?(:SOULSIGHT), false)

puts "\n-- a composed ability matches AS its parts, both operand orders --"
b = build(:SOLARDYNAMO)
check("set built",                    b.ability.is_a?(ChrookedAbilitySet), true)
check("== part (set on left)",        b.ability == :SOLARPOWER, true)
check("== part (symbol on left)",     :SOLARPOWER == b.ability, true)
check("== other part",                b.ability == :DROUGHT, true)
check("!= an unrelated ability",      b.ability == :SOULSIGHT, false)
check("include? via Array",           [:SOLARPOWER, :STATIC].include?(b.ability), true)
hit = case b.ability when :DROUGHT then :yes else :no end
check("case/when matches a part",     hit, :yes)

puts "\n-- but it is CALLED by its own name --"
check("display symbol",  b.ability.display_sym, :SOLARDYNAMO)
check("to_s",            b.ability.to_s, "SOLARDYNAMO")
check("hash lookup",     ({ :SOLARDYNAMO => "Solar Dynamo" }[b.ability]), "Solar Dynamo")

puts "\n-- suppression restores the full set --"
check("backupability is the set", b.backupability.equal?(b.ability), true)

puts "\n-- a plain ability is untouched --"
p2 = build(:SOULSIGHT)
check("stays a Symbol", p2.ability.class, Symbol)

puts "\n-- Redux on: one FLAT set, never nested --"
redux = PokeBattle_Battler.new(ChrookedAbilitySet.new([:SOLARDYNAMO, :STATIC]))
redux.instance_variable_set(:@ability, Chrooked.composed_ability(redux.ability))
flat = redux.ability
check("still a set",           flat.is_a?(ChrookedAbilitySet), true)
check("expanded + flattened",  flat.list, [:SOLARPOWER, :DROUGHT, :STATIC])
check("no nested member",      flat.list.any? { |m| m.is_a?(ChrookedAbilitySet) }, false)
check("matches an inner part", flat == :DROUGHT, true)
check("matches the sibling",   flat == :STATIC, true)

puts "\n#{$failures.zero? ? 'all checks passed' : "#{$failures} FAILURES"}"
exit($failures.zero? ? 0 : 1)
