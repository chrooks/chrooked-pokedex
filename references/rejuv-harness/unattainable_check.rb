# Standalone check of Unattainable's gender-free charm. `load`s the shipped
# file so its lambda runs; battlers, move, and battle are stubs.
# docker run --rm -v $PWD/references/rejuv-harness:/h:ro ruby:3.2-slim ruby /h/unattainable_check.rb
CHROOKED_WHEN_HIT = {}
load File.join(__dir__, "chrooked_unattainable.rb")

class Mon
  attr_accessor :ability, :effects, :item, :fainted, :partner, :gender
  def initialize(ability: :NONE, gender: nil, item: nil)
    @ability, @gender, @item, @effects, @fainted = ability, gender, item, { Attract: -1 }, false
  end
  def isFaintedAndNoShields?; @fainted; end
  def pbPartner; @partner; end
  def shouldBeMoldBroken?(_a, _m); false; end
  def makesContact?(move); move.contact; end
  def hasWorkingItem(i); @item == i; end
  def pbAttract(_s); @effects[:Attract] = 1; end
end
Move = Struct.new(:contact, :zmove)
class Battle
  attr_accessor :roll
  def pbRandom(_n); @roll; end
  def pbShowAbilityBox(_b); end
  def pbHideAbilityBox(_b); end
end

hit = CHROOKED_WHEN_HIT[:UNATTAINABLE]
holder = Mon.new(ability: :UNATTAINABLE, gender: 1)
battle = Battle.new
tackle = Move.new(true, false)
charmed = lambda { |mon, move: tackle, roll: 0|
  battle.roll = roll
  mon.partner ||= Mon.new
  hit.call(move, mon, holder, battle)
  mon.effects[:Attract] >= 0
}

raise "same gender" unless charmed.(Mon.new(gender: 1))
raise "genderless" unless charmed.(Mon.new(gender: 2))
raise "roll 30 misses" if charmed.(Mon.new, roll: 30)
raise "roll 29 lands" unless charmed.(Mon.new, roll: 29)
raise "non-contact" if charmed.(Mon.new, move: Move.new(false, false))
raise "z-move" if charmed.(Mon.new, move: Move.new(true, true))
raise "pads" if charmed.(Mon.new(item: :PROTECTIVEPADS))
raise "oblivious" if charmed.(Mon.new(ability: :OBLIVIOUS))
raise "own aroma veil" if charmed.(Mon.new(ability: :AROMAVEIL))
veiled = Mon.new; veiled.partner = Mon.new(ability: :AROMAVEIL)
raise "partner aroma veil" if charmed.(veiled)
fainted = Mon.new; fainted.fainted = true
raise "fainted attacker" if charmed.(fainted)
already = Mon.new; already.effects[:Attract] = 0
battle.roll = 0; hit.call(tackle, already.tap { |m| m.partner = Mon.new }, holder, battle)
raise "already infatuated re-rolled" unless already.effects[:Attract] == 0
puts "unattainable_check: 12/12 ok"
