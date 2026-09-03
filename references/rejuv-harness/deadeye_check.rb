# Standalone check of both Deadeye clauses. `load`s chrooked_deadeye.rb so the
# shipped code is what runs; PokeBattle_Move is stubbed so the prepend lands.
CHROOKED_SURE_HIT = {}
module PBStats; DEFENSE = 2; SPDEF = 4; end
Move = Struct.new(:move, :contact, :damaging) do
  def pbIsDamaging?; damaging; end
  def contactMove?; contact; end
end
class PokeBattle_Move < Move
  # stand-in vanilla calc: returns the stages it saw so the clamp is observable
  def pbCalcDamage(attacker, opponent, *args, **kwargs)
    [opponent.stages[PBStats::DEFENSE], opponent.stages[PBStats::SPDEF]]
  end
end
Battler = Struct.new(:ability, :stages)
load File.join(__dir__, "chrooked_deadeye.rb")

dead = Battler.new(:DEADEYE, [0, 0, 0, 0, 0, 0, 0, 0])
plain = Battler.new(:TORRENT, [0, 0, 0, 0, 0, 0, 0, 0])
pump = PokeBattle_Move.new(:HYDROPUMP, false, true)
liqu = PokeBattle_Move.new(:LIQUIDATION, true, true)
foe = ->(d, s) { Battler.new(:NONE, [0, 0, d, 0, s, 0, 0, 0]) }

raise "sure-hit: non-contact" unless CHROOKED_SURE_HIT[:DEADEYE].call(pump, dead)
raise "sure-hit: contact must roll" if CHROOKED_SURE_HIT[:DEADEYE].call(liqu, dead)
raise "sure-hit: other ability" if CHROOKED_SURE_HIT[:DEADEYE].call(pump, plain)

t = foe.(2, 2)
raise "clamp +2/+2" unless pump.pbCalcDamage(dead, t) == [0, 0]
raise "restore" unless t.stages[PBStats::DEFENSE] == 2 && t.stages[PBStats::SPDEF] == 2
raise "negative stays" unless pump.pbCalcDamage(dead, foe.(-1, -1)) == [-1, -1]
raise "contact untouched" unless liqu.pbCalcDamage(dead, foe.(2, 2)) == [2, 2]
raise "other ability untouched" unless pump.pbCalcDamage(plain, foe.(2, 2)) == [2, 2]
puts "deadeye_check: 8/8 ok"
