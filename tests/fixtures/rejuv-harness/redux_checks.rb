# Semantic checks for chrooked_zz_redux.rb against stub battle classes.
# Usage: ruby redux_checks.rb <harness-dir>

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

eval(File.read(File.join(ARGV[0], "chrooked_zz_redux.rb")), TOPLEVEL_BINDING)

Pkmn = Struct.new(:ability) do
  def getAbilityList
    [:INTIMIDATE, :MOXIE, :SANDRUSH]
  end
end

# --- option default and Off behavior ------------------------------------------
$Settings = PokemonOptions.new
assert $Settings.chrooked_redux == 1, "default is Off (1)"

b = PokeBattle_Battler.new
b.pbInitPokemon(Pkmn.new(:INTIMIDATE), 0)
assert b.ability.is_a?(Symbol), "Off leaves a plain Symbol"
assert b.ability == :INTIMIDATE, "Off keeps the mon's own ability"

# --- On: the set matches every owned ability ----------------------------------
$Settings.chrooked_redux = 0
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
assert opts[idx + 1].name == "Redux Mode", "option is named Redux Mode"
assert opts.last == "Back", "Back still closes the list"

# --- registry dispatch across the whole set (the Web Weaver bug) -------------
# Chrooked.entries/entry live in chrooked_00_core.rb; load it under stubs so the
# real helpers are exercised, not a copy.
module PBStats; SPEED = 5; end
class PokeBattle_Move; end
class PokeBattle_Battle; end
eval(File.read(File.join(ARGV[0], "chrooked_00_core.rb")), TOPLEVEL_BINDING)

Ariados = Struct.new(:ability) do
  def getAbilityList; [:WEBWEAVER, :VIRULENCE, :VAMPIRIC]; end
end

ariados = PokeBattle_Battler.new
ariados.pbInitPokemon(Ariados.new(:VIRULENCE), 0)
set = ariados.ability
assert set.primary == :VIRULENCE, "primary is the mon's own rolled ability"

CHROOKED_SWITCH_IN[:WEBWEAVER] = ->(*) { :web }
CHROOKED_CRIT_RATE[:VIRULENCE]  = ->(*) { true }
CHROOKED_ON_DEAL_DMG[:VAMPIRIC] = ->(*) { :drain }

# A raw Hash lookup still collapses to the primary — that is the trap.
assert CHROOKED_SWITCH_IN[set].nil?, "raw hash lookup misses a non-primary ability"

# entries/entry see every ability the mon owns, whatever the primary is.
assert Chrooked.entries(CHROOKED_SWITCH_IN, set).length == 1, "switch-in found via the set"
assert Chrooked.entry(CHROOKED_SWITCH_IN, set).call == :web, "Web Weaver fires off-primary"
assert Chrooked.entry(CHROOKED_CRIT_RATE, set).call, "primary ability still fires"
assert Chrooked.entry(CHROOKED_ON_DEAL_DMG, set).call == :drain, "hidden ability fires"

# Stacking: two owned abilities in one table both come back, in ability order.
CHROOKED_DAMAGE_MODS[:VIRULENCE] = ->(*) { 1.5 }
CHROOKED_DAMAGE_MODS[:VAMPIRIC]  = ->(*) { 2.0 }
mods = Chrooked.entries(CHROOKED_DAMAGE_MODS, set)
assert mods.length == 2, "both owned damage mods resolve"
assert mods.inject(1.0) { |m, f| m * f.call } == 3.0, "owned damage mods stack"

# Plain Symbol path unchanged (Redux Mode off, or a one-ability mon).
assert Chrooked.entry(CHROOKED_SWITCH_IN, :WEBWEAVER).call == :web, "symbol path works"
assert Chrooked.entries(CHROOKED_SWITCH_IN, :VIRULENCE).empty?, "symbol path misses cleanly"
assert Chrooked.entries(CHROOKED_SWITCH_IN, nil).empty?, "nil ability is safe"

puts "OK"
