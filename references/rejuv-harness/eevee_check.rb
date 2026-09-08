# Standalone check of chrooked_zz_eevee.rb. `load`s the shipped mod against
# engine stand-ins. Run: ruby references/rejuv-harness/eevee_check.rb
# Classic syntax only — the game's Ruby is not 3.x.

def _INTL(s, *a)
  return s if a.empty?
  s.gsub(/\{(\d+)\}/) { a[$1.to_i - 1].to_s }
end

module MenuHandlers
  @@added = {}
  def self.add(menu, key, opts = {}); @@added[[menu, key]] = opts; end
  def self.get(menu, key); @@added[[menu, key]]; end
end

module Chrooked
  def self.log(msg); end
end

ABILITIES = {
  :VAPOREON => [:WATERABSORB, :HYDRATION, :DELUGE],
  :JOLTEON  => [:VOLTABSORB, :QUICKFEET, :BLITZ],
  :FLAREON  => [:FLASHFIRE, :GUTS, :IMMOLATE]
}
def getMonName(species, form = 0); species.to_s.capitalize; end

class Pokedex
  attr_reader :seen, :owned
  def initialize; @seen = []; @owned = []; end
  def setSeen(p); @seen << p.species; end
  def setOwned(p); @owned << p.species; end
end
Trainer = Struct.new(:pokedex)
$Trainer = Trainer.new(Pokedex.new)

class PokeBattle_Pokemon
  attr_accessor :ability, :personalID, :form, :species, :name, :calced, :mega
  def initialize(species, personalID, name = nil, form = 0)
    @species = species; @form = form; @personalID = personalID
    @name = name || getMonName(species)
    @ability = getAbilityList[personalID % getAbilityList.length]
  end
  def getAbilityList; ABILITIES[@species] || [:RUNAWAY]; end
  def setAbility(v); @ability = v; end
  def isEgg?; false; end
  def calcStats; @calced = true; end
  def updateMegaData; @mega = true; end
end

load File.join(File.dirname(__FILE__), "chrooked_zz_eevee.rb")

FAILS = []
COUNT = [0]
def check(label); COUNT[0] += 1; FAILS << label unless yield; end

# 1. Species swap carries the ability slot across, all three slots.
3.times do |slot|
  p = PokeBattle_Pokemon.new(:VAPOREON, slot)
  CHROOKED_EEVEE_SET_SPECIES.call(p, :JOLTEON)
  check("slot #{slot} -> jolteon") { p.species == :JOLTEON && p.ability == ABILITIES[:JOLTEON][slot] }
  check("slot #{slot} recalced") { p.calced && p.mega && p.form == 0 }
end

# 2. Capsule slot survives (personalID 0 would sit in slot 0; capsule moved it to 2).
c = PokeBattle_Pokemon.new(:VAPOREON, 0)
c.setAbility(:DELUGE)
CHROOKED_EEVEE_SET_SPECIES.call(c, :FLAREON)
check("capsule slot survives") { c.ability == :IMMOLATE }

# 3. Nickname rule mirrors evolution.
d = PokeBattle_Pokemon.new(:VAPOREON, 0)
CHROOKED_EEVEE_SET_SPECIES.call(d, :JOLTEON)
check("species-name nickname follows") { d.name == "Jolteon" }
e = PokeBattle_Pokemon.new(:VAPOREON, 0, "Bubbles")
CHROOKED_EEVEE_SET_SPECIES.call(e, :JOLTEON)
check("real nickname kept") { e.name == "Bubbles" }
check("dex registered") { $Trainer.pokedex.owned.include?(:JOLTEON) }

# 4. Menu gating.
entry = MenuHandlers.get(:party_menu, :chrooked_eevee)
check("menu entry registered") { entry && entry[:name].call == "Eevee" }
check("rejects Pidgey") { !entry[:condition].call(nil, [PokeBattle_Pokemon.new(:PIDGEY, 0)], 0) }
check("rejects Eevee") { !entry[:condition].call(nil, [PokeBattle_Pokemon.new(:EEVEE, 0)], 0) }
check("rejects Rift Flareon") { !entry[:condition].call(nil, [PokeBattle_Pokemon.new(:FLAREON, 0, nil, 1)], 0) }
check("accepts Umbreon") { entry[:condition].call(nil, [PokeBattle_Pokemon.new(:UMBREON, 0)], 0) }

if FAILS.empty?
  puts "eevee_check: all #{COUNT[0]} assertions OK"
else
  puts "eevee_check FAILED:"; FAILS.each { |f| puts "  - #{f}" }; exit 1
end
