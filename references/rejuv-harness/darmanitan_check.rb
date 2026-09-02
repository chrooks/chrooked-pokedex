# Standalone check of chrooked_zz_darmanitan.rb. Like soulsight_check.rb it does
# NOT copy the logic — it `load`s the shipped mod so the real code runs against
# engine stand-ins. Covers the two pieces that can silently go wrong:
# the position-preserving ability swap, and the leaving-field form keep.
# Classic syntax only — the game's Ruby is not 3.x.

def _INTL(s, *a)
  return s if a.empty?
  s.gsub(/\{(\d+)\}/) { a[$1.to_i - 1].to_s }
end

module MenuHandlers
  @@added = {}
  def self.add(menu, key, opts = {})
    @@added[[menu, key]] = opts
  end
  def self.get(menu, key)
    @@added[[menu, key]]
  end
end

module Chrooked
  def self.log(msg); end
end

# Ability lists per form: 0 Unova Std, 1 Unova Zen, 2 Galar Std, 3 Galar Zen.
FORM_ABILITIES = [
  [:KINDLE, :SHEERFORCE, :HAMMERFIST],
  [:SAGEPOWER, :SOULSIGHT, :IMPENETRABLE],
  [:PERMAFROST, :THICKFAT, :GUTS],
  [:IMMOLATE, :KINDLE, :AFTERMATH]
]

class PokeBattle_Pokemon
  attr_accessor :ability, :personalID, :form, :species
  def initialize(species, form, personalID)
    @species = species
    @form = form
    @personalID = personalID
    @ability = getAbilityList[personalID % getAbilityList.length]
  end
  def getAbilityList
    @species == :DARMANITAN ? FORM_ABILITIES[@form] : [:RUNAWAY]
  end
  def changeForm(v); @form = v; end
  def setAbility(v); @ability = v.is_a?(Integer) ? getAbilityList[v] : v; end
  def isEgg?; false; end
  # The vanilla behaviour the mod has to defeat (Scripts/Pokemon.rb:891).
  def changeFormOnLeavingField
    @form = 0 if @species == :AEGISLASH && @form == 1
    @form = @form - 1 if @species == :DARMANITAN && @form.odd?
  end
end

load File.join(File.dirname(__FILE__), "chrooked_zz_darmanitan.rb")

FAILS = []
COUNT = [0]
def check(label)
  COUNT[0] += 1
  FAILS << label unless yield
end

# 1. Ability swap maps position-for-position, both directions, all three slots.
3.times do |slot|
  pkmn = PokeBattle_Pokemon.new(:DARMANITAN, 0, slot)
  check("unova slot #{slot} starts right") { pkmn.ability == FORM_ABILITIES[0][slot] }
  CHROOKED_DARMANITAN_SET_FORM.call(pkmn, 1)
  check("unova slot #{slot} -> zen") { pkmn.form == 1 && pkmn.ability == FORM_ABILITIES[1][slot] }
  CHROOKED_DARMANITAN_SET_FORM.call(pkmn, 0)
  check("unova slot #{slot} -> back") { pkmn.form == 0 && pkmn.ability == FORM_ABILITIES[0][slot] }

  gal = PokeBattle_Pokemon.new(:DARMANITAN, 2, slot)
  CHROOKED_DARMANITAN_SET_FORM.call(gal, 3)
  check("galar slot #{slot} -> zen") { gal.form == 3 && gal.ability == FORM_ABILITIES[3][slot] }
end

# 2. An ability-capsule pick keeps its SLOT rather than re-rolling off personalID.
#    personalID 0 would normally sit in slot 0; the capsule moved it to slot 2.
capsuled = PokeBattle_Pokemon.new(:DARMANITAN, 0, 0)
capsuled.setAbility(:HAMMERFIST)
CHROOKED_DARMANITAN_SET_FORM.call(capsuled, 1)
check("capsule slot survives the toggle") { capsuled.ability == :IMPENETRABLE }

# 3. The prepend defeats the leaving-field revert for Darmanitan only.
[1, 3].each do |zen|
  p1 = PokeBattle_Pokemon.new(:DARMANITAN, zen, 0)
  p1.changeFormOnLeavingField
  check("zen form #{zen} survives leaving the field") { p1.form == zen }
end
other = PokeBattle_Pokemon.new(:AEGISLASH, 1, 0)
other.changeFormOnLeavingField
check("non-Darmanitan still reverts") { other.form == 0 }

# 4. The menu entry registers, gates on species, and stays on one branch.
entry = MenuHandlers.get(:party_menu, :chrooked_zen)
check("menu entry registered") { entry && entry[:name].call == "Zen" }
check("condition rejects non-Darmanitan") do
  !entry[:condition].call(nil, [PokeBattle_Pokemon.new(:PIDGEY, 0, 0)], 0)
end
check("condition accepts Darmanitan") do
  entry[:condition].call(nil, [PokeBattle_Pokemon.new(:DARMANITAN, 0, 0)], 0)
end
[[0, 0], [1, 0], [2, 2], [3, 2]].each do |form, base|
  check("form #{form} picks base #{base}") { (form / 2) * 2 == base }
end

if FAILS.empty?
  puts "darmanitan_check: all #{COUNT[0]} assertions OK"
else
  puts "darmanitan_check FAILED:"
  FAILS.each { |f| puts "  - #{f}" }
  exit 1
end
