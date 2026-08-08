# Behavioral checks for the rejuv-harness wave-1 lambdas, run against stub
# battle classes (no game needed). Invoked by test_harness_lambda_behavior.
# Exits non-zero listing each failed expectation.
class PokeBattle_Move
  attr_accessor :move, :battle, :basedamage, :flags, :cat, :type, :zmove
  def pbCalcDamage(a, o, h = 0, f = {}); 100; end
  def pbType(attacker, type = @type); @type; end
  def isSoundBased?; @flags&.include?(:soundmove); end
  def punchMove?; @flags&.include?(:punchmove); end
  def windMove?; @flags&.include?(:windmove); end
  def hasFlag?(f); @flags&.include?(f); end
  def pbIsPhysical?(a, t = nil); @cat == :physical; end
  def pbIsSpecial?(a, t = nil); @cat == :special; end
end
class PokeBattle_Move_0DE < PokeBattle_Move; end
# Rejuv's party-menu registry — the zz_* QoL mods register handlers on it.
module MenuHandlers
  def self.add(*args, &blk); end
end
def _INTL(s, *a); s; end
class PokeBattle_Battler; end
class PokeBattle_Battle; end
Dir[File.join(ARGV[0], "chrooked_*.rb")].sort.each { |f| eval(File.read(f), TOPLEVEL_BINDING) }

Battler = Struct.new(:ability, :hp, :totalhp, :attack, :spatk, :types, :airborne, :damagestate, :status) do
  def hasType?(t); types.include?(t); end
  def isAirborne?; airborne; end
  # Rejuv's per-Pokemon Crest item. Only Suicune's matters here (it exempts the
  # holder from the status penalties), so the stub reports "no crest".
  def crested; nil; end
end
# state.effects carries the Nevermelting Hail flag the frostbite lambdas check.
BattleState = Struct.new(:effects)
Battle = Struct.new(:fe, :ov, :weather, :state) do
  def FE; fe; end
  def OV; ov; end
  def pbWeather(u); weather; end
  def state; self[:state] || BattleState.new({}); end
  def magicGuardAbilities; [:MAGICGUARD]; end
end
DS = Struct.new(:typemod)
TM = Struct.new(:se) do
  def superEffective?; se; end
end

def mv(sym, type: :NORMAL, flags: [], cat: :physical, battle: nil)
  m = PokeBattle_Move.new
  m.move = sym; m.type = type; m.flags = flags; m.basedamage = 80; m.cat = cat
  m.battle = battle || Battle.new(nil, nil, 0, BattleState.new({}))
  m
end

atk = ->(ab, **kw) {
  Battler.new(ab, kw[:hp] || 100, 100, kw[:atk] || 100, kw[:spa] || 50,
              kw[:types] || [:NORMAL], kw[:air] || false, DS.new(TM.new(false)), kw[:status])
}
defender = ->(ab, se) { Battler.new(ab, 100, 100, 0, 0, [], false, DS.new(TM.new(se))) }

checks = {
  # Frostbite: special damage halved, physical untouched, Guts exempt. The
  # attacker's status drives it, not its ability — so :NONE is the ability here.
  "frostbite special" => [mv(:X, cat: :special).pbCalcDamage(atk.(:NONE, status: :FROZEN), atk.(:NONE)), 50],
  "frostbite physical" => [mv(:X, cat: :physical).pbCalcDamage(atk.(:NONE, status: :FROZEN), atk.(:NONE)), 100],
  "frostbite guts special" => [mv(:X, cat: :special).pbCalcDamage(atk.(:GUTS, status: :FROZEN), atk.(:NONE)), 100],
  "frostbite unstatused" => [mv(:X, cat: :special).pbCalcDamage(atk.(:NONE, status: nil), atk.(:NONE)), 100],
  "bloom grass" => [mv(:X, type: :GRASS).pbCalcDamage(atk.(:BLOOM), atk.(:NONE)), 150],
  "bloom other" => [mv(:X, type: :FIRE).pbCalcDamage(atk.(:BLOOM), atk.(:NONE)), 100],
  "cryomancer ice" => [mv(:X, type: :ICE).pbCalcDamage(atk.(:CRYOMANCER), atk.(:NONE)), 150],
  "deluge water" => [mv(:X, type: :WATER).pbCalcDamage(atk.(:DELUGE), atk.(:NONE)), 150],
  "kindle fire" => [mv(:X, type: :FIRE).pbCalcDamage(atk.(:KINDLE), atk.(:NONE)), 150],
  "overcharge low" => [mv(:X, type: :ELECTRIC).pbCalcDamage(atk.(:OVERCHARGE, hp: 33), atk.(:NONE)), 150],
  "overcharge full" => [mv(:X, type: :ELECTRIC).pbCalcDamage(atk.(:OVERCHARGE, hp: 100), atk.(:NONE)), 100],
  "mysticpower offtype" => [mv(:X, type: :FIRE).pbCalcDamage(atk.(:MYSTICPOWER), atk.(:NONE)), 150],
  "mysticpower ontype" => [mv(:X, type: :NORMAL).pbCalcDamage(atk.(:MYSTICPOWER), atk.(:NONE)), 100],
  "mysticpower struggle" => [mv(:STRUGGLE, type: :FIRE).pbCalcDamage(atk.(:MYSTICPOWER), atk.(:NONE)), 100],
  "hammerfist punch" => [mv(:MACHPUNCH, flags: [:punchmove]).pbCalcDamage(atk.(:HAMMERFIST), atk.(:NONE)), 130],
  "hammerfist slam" => [mv(:BODYSLAM).pbCalcDamage(atk.(:HAMMERFIST), atk.(:NONE)), 130],
  "martialartist kick" => [mv(:X, flags: [:kickmove]).pbCalcDamage(atk.(:MARTIALARTIST), atk.(:NONE)), 130],
  "striker kick" => [mv(:BLAZEKICK, flags: [:kickmove]).pbCalcDamage(atk.(:STRIKER), atk.(:NONE)), 130],
  "striker punch" => [mv(:MACHPUNCH, flags: [:punchmove]).pbCalcDamage(atk.(:STRIKER), atk.(:NONE)), 100],
  "impale horn" => [mv(:MEGAHORN).pbCalcDamage(atk.(:IMPALE), atk.(:NONE)), 130],
  "wingspan wind" => [mv(:HURRICANE, flags: [:windmove]).pbCalcDamage(atk.(:WINGSPAN), atk.(:NONE)), 130],
  "wingspan wing" => [mv(:BRAVEBIRD).pbCalcDamage(atk.(:WINGSPAN), atk.(:NONE)), 130],
  "forestry grassy" => [mv(:X, battle: Battle.new(:GRASSY, nil, 0)).pbCalcDamage(atk.(:FORESTRY), atk.(:NONE)), 130],
  "forestry airborne" => [mv(:X, battle: Battle.new(:GRASSY, nil, 0)).pbCalcDamage(atk.(:FORESTRY, air: true), atk.(:NONE)), 100],
  "whiteout hail phys" => [mv(:X, battle: Battle.new(nil, nil, :HAIL)).pbCalcDamage(atk.(:WHITEOUT), atk.(:NONE)), 150],
  "whiteout hail offstat" => [mv(:X, cat: :special, battle: Battle.new(nil, nil, :HAIL)).pbCalcDamage(atk.(:WHITEOUT), atk.(:NONE)), 100],
  "whiteout no hail" => [mv(:X).pbCalcDamage(atk.(:WHITEOUT), atk.(:NONE)), 100],
  "permafrost SE" => [mv(:X).pbCalcDamage(atk.(:NONE), defender.(:PERMAFROST, true)), 65],
  "permafrost neutral" => [mv(:X).pbCalcDamage(atk.(:NONE), defender.(:PERMAFROST, false)), 100],
  "sledgehammer hammer" => [mv(:HAMMERARM).pbCalcDamage(atk.(:SLEDGEHAMMER), atk.(:NONE)), 130],
  "venomize normal type" => [mv(:BODYSLAM, type: :NORMAL).pbType(atk.(:VENOMIZE)), :POISON],
  "venomize normal dmg" => [mv(:BODYSLAM, type: :NORMAL).pbCalcDamage(atk.(:VENOMIZE), atk.(:NONE)), 120],
  "venomize offtype" => [mv(:X, type: :FIRE).pbType(atk.(:VENOMIZE)), :FIRE],
  "venomize offtype dmg" => [mv(:X, type: :FIRE).pbCalcDamage(atk.(:VENOMIZE), atk.(:NONE)), 100],
  "venomize weatherball" => [mv(:WEATHERBALL, type: :NORMAL).pbType(atk.(:VENOMIZE)), :NORMAL],
  "wyvernize normal type" => [mv(:BODYSLAM, type: :NORMAL).pbType(atk.(:WYVERNIZE)), :DRAGON],
  "sacredtoll sound type" => [mv(:HYPERVOICE, type: :NORMAL, flags: [:soundmove]).pbType(atk.(:SACREDTOLL)), :PSYCHIC],
  "sacredtoll sound dmg" => [mv(:HYPERVOICE, type: :NORMAL, flags: [:soundmove]).pbCalcDamage(atk.(:SACREDTOLL), atk.(:NONE)), 120],
  "sacredtoll nonsound" => [mv(:TACKLE, type: :NORMAL).pbType(atk.(:SACREDTOLL)), :NORMAL],
  "bloom sees ize type" => [mv(:BODYSLAM, type: :NORMAL).pbCalcDamage(atk.(:FOLIATE), atk.(:NONE)), 120],
  "sledgehammer punch" => [mv(:MACHPUNCH, flags: [:punchmove]).pbCalcDamage(atk.(:SLEDGEHAMMER), atk.(:NONE)), 100],
}
fails = checks.reject { |k, (got, want)| got == want }
fails.each { |k, (got, want)| puts "FAIL #{k}: got #{got} want #{want}" }
raise "#{fails.size} failures" unless fails.empty?
puts "all #{checks.size} lambda checks pass"
