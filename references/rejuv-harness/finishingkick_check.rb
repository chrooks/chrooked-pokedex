# Standalone check of Finishing Kick. Loads chrooked_finishingkick.rb so the
# shipped lambda is what runs; the registry table and PBStats are stubbed
# BEFORE the load. The Speed Boost half is vanilla via composition and is not
# under test here.

# --- engine stand-in --------------------------------------------------------
CHROOKED_DAMAGE_MODS = {}
module PBStats; SPEED = 3; end
Move    = Struct.new(:contact) { def contactMove?; contact; end }
Battler = Struct.new(:ability, :stages)

require_relative "chrooked_finishingkick"

# --- assertions -------------------------------------------------------------
$pass = 0
$fail = 0
def check(label, actual, expected)
  if actual == expected
    $pass += 1
    puts "  ok   #{label}"
  else
    $fail += 1
    puts "  FAIL #{label} — expected #{expected.inspect}, got #{actual.inspect}"
  end
end

def runner(stage)
  stages = Array.new(8, 0); stages[PBStats::SPEED] = stage
  Battler.new(:FINISHINGKICK, stages)
end
mod = CHROOKED_DAMAGE_MODS[:FINISHINGKICK]
contact    = Move.new(true)
noncontact = Move.new(false)

puts "Spec acceptance tests:"
check("1. stage 0, Quick Attack (contact) => no boost",  mod.call(contact, runner(0), nil),     1.0)
check("2. stage +1, Wild Charge (contact) => 1.2x",      mod.call(contact, runner(1), nil),     1.2)
check("3. stage +2, Thunderbolt (non-contact) => none",  mod.call(noncontact, runner(2), nil),  1.0)
check("4. stage +6, Crunch (contact) => 1.2x at cap",    mod.call(contact, runner(6), nil),     1.2)

puts "\nScope:"
check("negative stage, contact => no boost",             mod.call(contact, runner(-2), nil),    1.0)
check("no row registered for other abilities",           CHROOKED_DAMAGE_MODS[:STRONGJAW],      nil)

puts "\n#{$pass}/#{$pass + $fail} passed"
exit($fail.zero? ? 0 : 1)
