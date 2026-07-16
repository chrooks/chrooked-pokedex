# Behavioral checks for the rejuv-harness event hooks (waves 3+), run against
# stub battle classes. ARGV[0] = harness dir. Non-zero exit lists failures.

module PBStats
  ATTACK = 1; SPATK = 3; SPDEF = 4; SPEED = 5; ACCURACY = 6
end
def _INTL(s, *a); s; end
$cache = Struct.new(:moves).new({})

class StubDS
  attr_accessor :substitute, :typemod
  def initialize; @substitute = false; end
end

class PokeBattle_Battler
  attr_accessor :ability, :hp, :totalhp, :attack, :spatk, :turncount, :effects,
                :battle, :index, :moves, :lastMoveUsed, :damagestate, :log
  def initialize(ability, battle = nil)
    @ability = ability; @hp = 50; @totalhp = 100; @attack = 100; @spatk = 200
    @turncount = 0; @effects = {}; @battle = battle; @index = 0; @moves = []
    @lastMoveUsed = -1; @damagestate = StubDS.new; @log = []
  end
  def isFainted?; false; end
  def canHeal?; true; end
  def pbThis(lower = false); "Stub"; end
  def makesContact?(move); move.flags&.include?(:contact); end
  def pbCanIncreaseStatStage?(stat, inducer, mv); true; end
  def pbCanReduceAnyStat?(stats, inducer, mv, **kw); true; end
  def pbChangeStats(stat, amount, inducer, mv, **kw); @log << [:stats, stat, amount]; true; end
  def pbRecoverHP(amount, anim = false, *a, **kw); @log << [:heal, amount]; end
  def pbCanPoison?(a, m, **kw); true; end
  def pbCanBurn?(a, m, **kw); true; end
  def pbPoison(a, *rest); @log << [:poison]; end
  def pbBurn(a, *rest); @log << [:burn]; end
  def pbOpposing1; @battle.foes[0]; end
  def pbOpposing2; @battle.foes[1]; end
  def moldbroken; false; end
  # vanilla bodies our prepends wrap:
  def pbOnKillEffects(targets, basemove, *a); end
  def pbEffectsOnDealingDamage(move, user, target, damage, *a); end
  def pbAbilitiesOnSwitchIn(*a, **kw); end
  def pbSpeed(*a); 100; end
  def pbUseMove(choice, *a, **kw); end
end

class PokeBattle_Battle
  attr_accessor :battlers, :foes, :rand_value
  def initialize; @battlers = []; @foes = []; @rand_value = 0; end
  def pbAnySideAllFainted?; false; end
  def pbRandom(x); @rand_value; end
  def pbShowAbilityBox(*a, **kw); end
  def pbHideAbilityBox(*a, **kw); end
  def pbDisplay(*a); end
  def pbEndOfRoundPhase(*a, **kw); end
  def pbCanChooseMove?(idxPokemon, idxMove, *a, **kw); true; end
end

class PokeBattle_Move
  attr_accessor :move, :flags, :type, :cat, :basedamage, :battle, :zmove
  def initialize(sym, type: :NORMAL, flags: [], cat: :physical)
    @move = sym; @type = type; @flags = flags; @cat = cat; @basedamage = 80
  end
  def pbCalcDamage(a, o, h = 0, f = {}); $observed_attack = a.attack; 100; end
  def pbType(attacker, type = @type); @type; end
  def pbIsPhysical?(a, t = nil); @cat == :physical; end
  def pbIsSpecial?(a, t = nil); @cat == :special; end
  def punchMove?; @flags.include?(:punchmove); end
  def sharpMove?; @flags.include?(:sharpmove); end
  def bitingMove?; @flags.include?(:bitingmove); end
  def windMove?; @flags.include?(:windmove); end
  def isSoundBased?; @flags.include?(:soundmove); end
  def hasFlag?(f); @flags.include?(f); end
  def contactMove?; @flags.include?(:contact); end
  def priorityCheck(attacker); 0; end
  def pbTypeImmunities(attacker, targets, hitflags, movetype: nil); end
  def pbShouldApplyTypeImmunity?(a, o); true; end
end

Dir[File.join(ARGV[0], "chrooked_*.rb")].sort.each { |f| eval(File.read(f), TOPLEVEL_BINDING) }

fails = []
def check(fails, name, got, want)
  fails << "#{name}: got #{got.inspect} want #{want.inspect}" unless got == want
end

battle = PokeBattle_Battle.new

# priority: rapid combustion full HP fire
rc = PokeBattle_Battler.new(:RAPIDCOMBUSTION, battle); rc.hp = rc.totalhp
check(fails, "rapidcombustion full-hp fire", PokeBattle_Move.new(:EMBER, type: :FIRE).priorityCheck(rc), 1)
rc.hp = 50
check(fails, "rapidcombustion damaged", PokeBattle_Move.new(:EMBER, type: :FIRE).priorityCheck(rc), 0)

# priority: stampede armed contact
st = PokeBattle_Battler.new(:STAMPEDE, battle)
st.effects[:ChrookedStampede] = true
check(fails, "stampede armed contact", PokeBattle_Move.new(:TACKLE, flags: [:contact]).priorityCheck(st), 1)
check(fails, "stampede armed noncontact", PokeBattle_Move.new(:SWIFT).priorityCheck(st), 0)

# speed: blitz first turn
bl = PokeBattle_Battler.new(:BLITZ, battle)
check(fails, "blitz first turn", bl.pbSpeed, 150)
bl.turncount = 2
check(fails, "blitz later turn", bl.pbSpeed, 100)

# KO: demolition raises attack, carnivore heals
dm = PokeBattle_Battler.new(:DEMOLITION, battle)
dm.pbOnKillEffects([:x], nil)
check(fails, "demolition ko", dm.log, [[:stats, PBStats::ATTACK, 1]])
cv = PokeBattle_Battler.new(:CARNIVORE, battle)
cv.pbOnKillEffects([:x], nil)
check(fails, "carnivore ko heal", cv.log, [[:heal, 25]])

# on-deal: venomous out (rand 0 => success), pyre burn, exhaust acc drop
vn = PokeBattle_Battler.new(:VENOMOUS, battle)
tgt = PokeBattle_Battler.new(:NONE, battle)
vn.pbEffectsOnDealingDamage(PokeBattle_Move.new(:TACKLE, flags: [:contact]), vn, tgt, 30)
check(fails, "venomous out poison", tgt.log, [[:poison]])
py = PokeBattle_Battler.new(:PYRE, battle)
tgt2 = PokeBattle_Battler.new(:NONE, battle)
py.pbEffectsOnDealingDamage(PokeBattle_Move.new(:SHADOWBALL, type: :GHOST), py, tgt2, 30)
check(fails, "pyre burn", tgt2.log, [[:burn]])
ex = PokeBattle_Battler.new(:EXHAUST, battle)
tgt3 = PokeBattle_Battler.new(:NONE, battle)
ex.pbEffectsOnDealingDamage(PokeBattle_Move.new(:TACKLE, flags: [:contact]), ex, tgt3, 30)
check(fails, "exhaust acc drop", tgt3.log, [[:stats, PBStats::ACCURACY, -1]])

# spiteful block: arm on hit, boost dark, consume
sp = PokeBattle_Battler.new(:SPITEFULBLOCK, battle)
hitter = PokeBattle_Battler.new(:NONE, battle)
sp.pbEffectsOnDealingDamage(PokeBattle_Move.new(:TACKLE), hitter, sp, 30)
check(fails, "spiteful armed", sp.effects[:ChrookedSpiteful], true)
check(fails, "spiteful dark boost", PokeBattle_Move.new(:CRUNCH, type: :DARK).pbCalcDamage(sp, hitter), 130)
sp.pbEffectsOnDealingDamage(PokeBattle_Move.new(:CRUNCH, type: :DARK), sp, hitter, 30)
check(fails, "spiteful consumed", sp.effects[:ChrookedSpiteful], nil)

# infernal maw: flinch (rand 0 passes both rolls)
im = PokeBattle_Battler.new(:INFERNALMAW, battle)
tgt4 = PokeBattle_Battler.new(:NONE, battle)
im.pbEffectsOnDealingDamage(PokeBattle_Move.new(:BITE, flags: [:bitingmove]), im, tgt4, 30)
check(fails, "infernalmaw burn", tgt4.log.include?([:burn]), true)
check(fails, "infernalmaw flinch", tgt4.effects[:Flinch], true)
check(fails, "infernalmaw biting dmg", PokeBattle_Move.new(:BITE, flags: [:bitingmove]).pbCalcDamage(im, tgt4), 130)

# immunities: flag set post-super
aero = PokeBattle_Battler.new(:AERODYNAMIC, battle)
hitflags = [:Success]
PokeBattle_Move.new(:GUST, type: :FLYING).pbTypeImmunities(hitter, [aero], hitflags)
check(fails, "aerodynamic blocks flying", hitflags, [:Soundproof])
sb = PokeBattle_Battler.new(:STONEBARK, battle)
hitflags2 = [:Success]
PokeBattle_Move.new(:VINEWHIP, type: :GRASS).pbTypeImmunities(hitter, [sb], hitflags2)
check(fails, "stonebark absorbs grass", hitflags2, [:HpAbsorbAbility])
hitflags3 = [:Success]
PokeBattle_Move.new(:TACKLE, type: :NORMAL).pbTypeImmunities(hitter, [sb], hitflags3)
check(fails, "stonebark normal passes", hitflags3, [:Success])

# stat swap: magical fists physical punch uses SpA during the vanilla calc
mfist = PokeBattle_Battler.new(:MAGICALFISTS, battle)
PokeBattle_Move.new(:MACHPUNCH, flags: [:punchmove]).pbCalcDamage(mfist, tgt4)
check(fails, "magicalfists spa swap", $observed_attack, 200)
check(fails, "magicalfists attack restored", mfist.attack, 100)
PokeBattle_Move.new(:TACKLE).pbCalcDamage(mfist, tgt4)
check(fails, "magicalfists no swap non-punch", $observed_attack, 100)

# turn end: self sufficient heal 1/16
ss = PokeBattle_Battler.new(:SELFSUFFICIENT, battle)
battle.battlers = [ss]
battle.pbEndOfRoundPhase
check(fails, "selfsufficient heal", ss.log, [[:heal, 6]])

# switch-in: frighten drops both foes' SpA
fr = PokeBattle_Battler.new(:FRIGHTEN, battle)
foe1 = PokeBattle_Battler.new(:NONE, battle); foe2 = PokeBattle_Battler.new(:NONE, battle)
battle.foes = [foe1, foe2]
fr.pbAbilitiesOnSwitchIn
check(fails, "frighten foe1", foe1.log, [[:stats, PBStats::SPATK, -1]])
check(fails, "frighten foe2", foe2.log, [[:stats, PBStats::SPATK, -1]])

# after-move: insidious speed boost on status move
$cache.moves[:TOXIC] = Struct.new(:category).new(:status)
$cache.moves[:TACKLE] = Struct.new(:category).new(:physical)
ins = PokeBattle_Battler.new(:INSIDIOUS, battle)
ins.lastMoveUsed = :TOXIC
ins.pbUseMove(nil)
check(fails, "insidious status move", ins.log, [[:stats, PBStats::SPEED, 1]])
ins.log.clear; ins.lastMoveUsed = :TACKLE
ins.pbUseMove(nil)
check(fails, "insidious damaging move", ins.log, [])

# sage power: lock arms after first move, choose-move enforced
sg = PokeBattle_Battler.new(:SAGEPOWER, battle)
sg.lastMoveUsed = :PSYCHIC
sg.pbUseMove(nil)
check(fails, "sagepower lock armed", sg.effects[:ChrookedMoveLock], :PSYCHIC)
MoveSlot = Struct.new(:move)
sg.moves = [MoveSlot.new(:PSYCHIC), MoveSlot.new(:CALMMIND)]
battle.battlers = [sg]
check(fails, "sagepower locked move ok", battle.pbCanChooseMove?(0, 0), true)
check(fails, "sagepower other move blocked", battle.pbCanChooseMove?(0, 1), false)
check(fails, "sagepower special dmg", PokeBattle_Move.new(:PSYCHIC, type: :PSYCHIC, cat: :special).pbCalcDamage(sg, tgt4), 150)

# deathgrip trap
dg = PokeBattle_Battler.new(:DEATHGRIP, battle)
tgt5 = PokeBattle_Battler.new(:NONE, battle)
tgt5.effects[:MultiTurn] = 0
dg.pbEffectsOnDealingDamage(PokeBattle_Move.new(:TACKLE, flags: [:contact]), dg, tgt5, 30)
check(fails, "deathgrip trap", tgt5.effects[:MultiTurn], 5)

fails.each { |f| puts "FAIL #{f}" }
raise "#{fails.size} failures" unless fails.empty?
puts "all event-hook checks pass"
