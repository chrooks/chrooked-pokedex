# Standalone check of the Starfall streak. `load`s chrooked_starfall.rb so the
# shipped lambdas are what runs; the registries and battler are stubs.
CHROOKED_SWITCH_IN = {}; CHROOKED_ON_DEAL = {}; CHROOKED_TURN_END = {}; CHROOKED_DAMAGE_MODS = {}
load File.join(__dir__, "chrooked_starfall.rb")
Move = Struct.new(:special) do
  def pbType(_a); :PSYCHIC; end
  def pbIsSpecial?(_a, _t = nil); special; end
end
B = Struct.new(:effects)
b = B.new({}); sp = Move.new(true); ph = Move.new(false)
mult = -> { CHROOKED_DAMAGE_MODS[:STARFALL].call(sp, b, nil).round(2) }
attack = ->(m) { CHROOKED_ON_DEAL[:STARFALL].call(m, b, nil, nil); CHROOKED_TURN_END[:STARFALL].call(b, nil) }
idle = -> { CHROOKED_TURN_END[:STARFALL].call(b, nil) }

CHROOKED_SWITCH_IN[:STARFALL].call(b, nil)
raise "t1" unless mult.() == 1.0
attack.(sp); raise "t2" unless mult.() == 1.2
attack.(sp); raise "t3" unless mult.() == 1.4
attack.(sp); raise "t4" unless mult.() == 1.6
attack.(sp); raise "cap" unless mult.() == 1.6
raise "physical no boost" unless CHROOKED_DAMAGE_MODS[:STARFALL].call(ph, b, nil) == 1.0
attack.(ph); raise "physical counts" unless mult.() == 1.6
idle.(); raise "reset on idle" unless mult.() == 1.0
attack.(sp); attack.(sp); CHROOKED_SWITCH_IN[:STARFALL].call(b, nil)
raise "reset on switch" unless mult.() == 1.0
puts "starfall_check: 10/10 ok"
