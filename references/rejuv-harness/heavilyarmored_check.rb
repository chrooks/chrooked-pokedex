# Runnable check for Heavily Armored (Soundproof + Bulletproof + Battle Armor).
# The ability is a pure composition — chrooked_zz_zcompose.rb turns the holder
# into ChrookedAbilitySet[:SOUNDPROOF, :BULLETPROOF, :BATTLEARMOR] displayed as
# :HEAVILYARMORED — so this loads the real set class (chrooked_zz_redux.rb) and
# the real core, then replays the vanilla check shapes against it.
#   docker run --rm -v "$PWD/references/rejuv-harness:/h:ro" ruby:3.2-slim ruby /h/heavilyarmored_check.rb

class Typemod
  attr_reader :n
  def initialize(n) = @n = n
  def self.zero = new(0)
  def self.normal = new(4)
  def immune? = @n <= 0
end

class PokeBattle_Move; end
class PokeBattle_Battle; end
class PokeBattle_Battler; end

Move = Struct.new(:sound, :bullet, :target) do
  def checkSoundMove?(_attacker) = sound
  def bulletMove? = bullet
end
Mon = Struct.new(:ability, :moldbroken) do
  def pbTarget(move) = move.target
end

# Copies the shape of Battle_AI.rb:9426-9444: one `case` whose
# `when :BULLETPROOF` (9439) sits BEFORE `when :SOUNDPROOF` (9441).
class PokeBattle_AI
  MEDIUMSKILL = 30
  def initialize(mold = false) = @mold = mold
  def moldBreakerCheck(_a, _o, _m) = @mold

  def pbTypeModNoMessages(type, attacker, opponent, move, skill)
    return Typemod.normal if [:User, :UserSide].include?(attacker.pbTarget(move))
    if !moldBreakerCheck(attacker, opponent, move) && skill >= MEDIUMSKILL
      case opponent.ability
        when :BULLETPROOF then return Typemod.zero if move.bulletMove?
        when :SOUNDPROOF then return Typemod.zero if move.checkSoundMove?(attacker)
      end
    end
    Typemod.normal
  end
end

require_relative "chrooked_zz_redux"
require_relative "chrooked_00_core"

def check(label) = (yield ? puts("ok   #{label}") : abort("FAIL #{label}"))

ha = ChrookedAbilitySet.new([:SOUNDPROOF, :BULLETPROOF, :BATTLEARMOR])
ha.chrooked_display = :HEAVILYARMORED
def_ = Mon.new(ha, false)

# Battle code shapes, copied from the check sites.
check("Soundproof hitflag (Battle_Move.rb:684)") { def_.ability == :SOUNDPROOF }
check("Bulletproof hitflag (Battler.rb:5392)") { def_.ability == :BULLETPROOF }
check("crit block include? (Battle_Move.rb:976)") { [:BATTLEARMOR, :SHELLARMOR].include?(def_.ability) }
check("sleep/Uproar != (Battle.rb:6096)") { !(def_.ability != :SOUNDPROOF) }
check("field case/when (Battle_Effects.rb:873)") {
  case def_.ability
  when :BATTLEARMOR, :SHELLARMOR then true
  else false
  end
}
check("name/description resolve to Heavily Armored") { ha.to_sym == :HEAVILYARMORED }
check("not Shell Armor-only riders") { !(def_.ability == :SHELLARMOR) }

attacker = Mon.new(:DRAGONITE, false)
sound = Move.new(true, false, :SingleNonUser)
ball = Move.new(false, true, :SingleNonUser)
plain = Move.new(false, false, :SingleNonUser)
ai = PokeBattle_AI.new

check("AI: ball move is immune") { ai.pbTypeModNoMessages(:STEEL, attacker, def_, ball, 100).immune? }
check("AI: sound move is immune (case shadow fixed)") { ai.pbTypeModNoMessages(:NORMAL, attacker, def_, sound, 100).immune? }
check("AI: plain move still lands") { !ai.pbTypeModNoMessages(:NORMAL, attacker, def_, plain, 100).immune? }
check("AI: Mold Breaker ignores it") { !PokeBattle_AI.new(true).pbTypeModNoMessages(:NORMAL, attacker, def_, sound, 100).immune? }
check("AI: low skill does not know") { !ai.pbTypeModNoMessages(:NORMAL, attacker, def_, sound, 10).immune? }
check("AI: plain Soundproof symbol untouched") { ai.pbTypeModNoMessages(:NORMAL, attacker, Mon.new(:SOUNDPROOF, false), sound, 100).immune? }
