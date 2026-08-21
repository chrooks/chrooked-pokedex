# Semantic checks for chrooked_zz_multiability.rb against stub battle classes.
# Usage: ruby multiability_checks.rb <harness-dir>

def assert(cond, msg)
  raise "FAIL: #{msg}" unless cond
end

# --- stubs (shapes mirror Rejuv's Scripts) ------------------------------------
class PokemonOptions; end

class PokeBattle_Battler
  attr_accessor :ability

  def pbInitPokemon(pkmn, pkmnIndex)
    @ability = pkmn.ability
    @backupability = pkmn.ability
  end
end

class PokemonOptionScene
  def initOptions
    ["Gameplay", "Battle", "Back"]
  end
end

class EnumOption
  attr_reader :name
  def initialize(name, values, getProc, setProc, description = "")
    @name = name
  end
end

def _INTL(s, *args)
  s
end

eval(File.read(File.join(ARGV[0], "chrooked_zz_multiability.rb")), TOPLEVEL_BINDING)

Pkmn = Struct.new(:ability) do
  def getAbilityList
    [:INTIMIDATE, :MOXIE, :SANDRUSH]
  end
end

# --- option default and Off behavior ------------------------------------------
$Settings = PokemonOptions.new
assert $Settings.chrooked_all_abilities == 1, "default is Off (1)"

b = PokeBattle_Battler.new
b.pbInitPokemon(Pkmn.new(:INTIMIDATE), 0)
assert b.ability.is_a?(Symbol), "Off leaves a plain Symbol"
assert b.ability == :INTIMIDATE, "Off keeps the mon's own ability"

# --- On: the set matches every owned ability ----------------------------------
$Settings.chrooked_all_abilities = 0
b = PokeBattle_Battler.new
b.pbInitPokemon(Pkmn.new(:INTIMIDATE), 0)
a = b.ability
assert a.is_a?(ChrookedAbilitySet), "On wraps the ability in a set"
assert b.instance_variable_get(:@backupability).equal?(a), "backupability holds the set"

assert a == :INTIMIDATE, "receiver == primary"
assert a == :MOXIE, "receiver == secondary"
assert a == :SANDRUSH, "receiver == hidden"
assert !(a == :LEVITATE), "receiver == unowned is false"
assert :MOXIE == a, "reversed Symbol == set"
assert !(:LEVITATE == a), "reversed unowned is false"
assert [:MOXIE, :GUTS].include?(a), "Array#include? matches owned"
assert ![:GUTS, :STURDY].include?(a), "Array#include? rejects unowned"
matched = case a
          when :SANDRUSH then true
          else false
          end
assert matched, "case/when matches owned"
assert({ INTIMIDATE: "x" }[a] == "x", "hash lookup resolves to primary")
assert a.to_s == "INTIMIDATE", "method_missing delegates to primary"
assert (a != :LEVITATE) && !(a != :MOXIE), "!= follows =="

# --- plain Symbol comparisons unharmed by the == patch ------------------------
assert :A == :A, "sym == same sym"
assert !(:A == :B), "sym == other sym"
assert !(:A == nil), "sym == nil"
assert !(:A == "A"), "sym == string"

# --- single-ability mon stays plain -------------------------------------------
solo = Struct.new(:ability) do
  def getAbilityList
    [:LEVITATE]
  end
end
b = PokeBattle_Battler.new
b.pbInitPokemon(solo.new(:LEVITATE), 0)
assert b.ability.is_a?(Symbol), "single-ability mon keeps a plain Symbol"

# --- options splice: first entry of the Battle section ------------------------
opts = PokemonOptionScene.new.initOptions
idx = opts.index("Battle")
assert opts[idx + 1].is_a?(EnumOption), "option lands after the Battle header"
assert opts[idx + 1].name == "All Abilities", "option is named All Abilities"
assert opts.last == "Back", "Back still closes the list"

puts "OK"
