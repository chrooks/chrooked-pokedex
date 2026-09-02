# Behavioral checks for the rejuv-harness event hooks (waves 3+), run against
# stub battle classes. ARGV[0] = harness dir. Non-zero exit lists failures.

module PBStats
  ATTACK = 1; SPATK = 3; SPDEF = 4; SPEED = 5; ACCURACY = 6
end
def _INTL(s, *a); s; end
$cache = Struct.new(:moves).new({})

class Typemod
  attr_reader :numerator, :denominator
  def initialize(n = 1, d = 1); @numerator = n; @denominator = d; end
  def self.normal; new(1, 1); end
  def self.zero; new(0, 1); end
  def *(o)
    n = numerator * o.numerator; d = denominator * o.denominator
    d = 1 if n == 0
    if n > 1 && d > 1
      m = [n, d].min
      n /= m; d /= m
    end
    Typemod.new(n, d)
  end
  def immune?; @numerator <= 0; end
  def to_a; [@numerator, @denominator]; end
end

module PBTypes
  CHART = { [:STEEL, :DRAGON] => [1, 2], [:GROUND, :FLYING] => [0, 1],
            [:ICE, :WATER] => [1, 2], [:ICE, :GROUND] => [2, 1] }
  def self.oneTypeEff(a, o); n, d = CHART.fetch([a, o], [1, 1]); Typemod.new(n, d); end
end

class StubDS
  attr_accessor :substitute, :typemod
  def initialize; @substitute = false; end
end

class PokeBattle_Battler
  attr_accessor :ability, :hp, :totalhp, :attack, :spatk, :turncount, :effects,
                :battle, :index, :moves, :lastMoveUsed, :damagestate, :log, :status
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
  def shouldBeMoldBroken?(attacker, move); false; end
  def pbChangeStats(stat, amount, inducer, mv, **kw); @log << [:stats, stat, amount]; true; end
  def pbRecoverHP(amount, anim = false, *a, **kw); @log << [:heal, amount]; end
  def pbCanPoison?(a, m, **kw); true; end
  def pbCanBurn?(a, m, **kw); true; end
  def pbPoison(a, *rest); @log << [:poison]; end
  def pbBurn(a, *rest); @log << [:burn]; end
  # Frostbite reuses the engine's frozen slot; Ice-types are immune, which is the
  # gate Frost Body relies on rather than checking types itself.
  def pbCanFreeze?(a, m, **kw); !types.include?(:ICE); end
  def pbFreeze(message: nil); @log << [:frostbite]; end
  def pbOpposing1; @battle.foes[0]; end
  def pbOpposing2; @battle.foes[1]; end
  def moldbroken; false; end
  # vanilla bodies our prepends wrap:
  def pbOnKillEffects(targets, basemove, *a); end
  def absorbHP(hpgain, opponent, agent, move = nil); @log << [:absorb, hpgain]; end
  def pbTarget(move); :SingleNonUser; end
  def types; [@types_list ||= [:NORMAL]].flatten; end
  def types_list=(t); @types_list = t; end
  def pbEffectsOnDealingDamage(move, user, target, damage, *a); end
  def pbAbilitiesOnSwitchIn(*a, **kw); end
  def pbSpeed(*a); 100; end
  def pbUseMove(choice, *a, **kw); end
  def crested; nil; end
  def pbReduceHP(amount, *a, **kw); @log << [:chip, amount]; @hp -= amount; end
  def pbFaint(*a); end
  def pbContinueStatus(showAnim = true); @log << [:continue, @status]; end
  def pbCureStatus(showMessage = true); @log << [:cure, @status]; @status = nil; end
  def hasType?(t); types.include?(t); end
  # The vanilla body our turn-skip prepend wraps. Returns :acted so a test can
  # tell "the move went through" from "the turn was cancelled".
  def pbTryUseMove(choice, basemove, flags = {})
    @log << [:tried, @battle.state.effects[:NeverMeltIce]]
    :acted
  end
end

class PokeBattle_Battle
  attr_accessor :battlers, :foes, :rand_value
  def initialize; @battlers = []; @foes = []; @rand_value = 0; end
  def pbAnySideAllFainted?; false; end
  def pbRandom(x); @rand_value; end
  def pbCommonAnimation(*a); end
  def pbShowAbilityBox(*a, **kw); end
  def pbHideAbilityBox(*a, **kw); end
  attr_accessor :shown
  def pbDisplay(*a); (@shown ||= []) << a[0]; end
  # Records itself so the ordering check can prove the chrooked handlers run
  # BEFORE the vanilla body (which replaces fainted battlers inside itself).
  def pbEndOfRoundPhase(*a, **kw); ($eor_order ||= []) << :vanilla_body; end
  def pbCanChooseMove?(idxPokemon, idxMove, *a, **kw); true; end
  def pbWeather(moveuser); :RAINDANCE; end
  # state.effects carries the Nevermelting Hail flag frostbite checks; the
  # frostbite handlers no-op while it is genuinely set, so vanilla keeps that case.
  def state; @state ||= Struct.new(:effects).new({}); end
  def magicGuardAbilities; [:MAGICGUARD]; end
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
  def pbTypeModifier(atype, attacker, opponent)
    tm = Typemod.normal
    opponent.types.each { |t| tm *= PBTypes.oneTypeEff(atype, t) }
    tm
  end
  def pbAccuracyCheck(attacker, opponent); false; end
  def pbTypeImmunities(attacker, targets, hitflags, movetype: nil); end
  def pbShouldApplyTypeImmunity?(a, o); true; end
end

class PokeBattle_Move_0DE < PokeBattle_Move; end
# Rejuv's party-menu registry — the zz_* QoL mods register handlers on it.
module MenuHandlers
  def self.add(*args, &blk); end
end
def _INTL(s, *a); s; end
# Rejuv's overworld sprite class — chrooked_zz_kirincull alias-chains #update,
# so the method must exist before the shim is eval'd.
class Sprite_Character
  def update; end
end
# The party Pokemon class — chrooked_zz_darmanitan prepends onto it. The mod
# guards on its own module, not the target class, which is right for the game
# (the class always exists there) and leaves each harness to supply it.
class PokeBattle_Pokemon; end

class PokeBattle_Move_0D8 < PokeBattle_Move
  def pbEffect(attacker, alltargets, hitnum = 0); attacker.pbRecoverHP(50, true); end
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
bl.turncount = 1  # first attack phase: increment precedes setSpeedOrder
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

# frost body: the Ice member of the same family, both directions, Ice-types immune
fbody = PokeBattle_Battler.new(:FROSTBODY, battle)
fbtgt = PokeBattle_Battler.new(:NONE, battle)
contact = PokeBattle_Move.new(:TACKLE, flags: [:contact])
fbody.pbEffectsOnDealingDamage(contact, fbody, fbtgt, 30)
check(fails, "frost body out frostbite", fbtgt.log, [[:frostbite]])

# Defensive direction goes through the same hook, keyed on the TARGET's ability.
fbody2 = PokeBattle_Battler.new(:FROSTBODY, battle)
hitter2 = PokeBattle_Battler.new(:NONE, battle)
hitter2.pbEffectsOnDealingDamage(contact, hitter2, fbody2, 30)
check(fails, "frost body in frostbite", hitter2.log, [[:frostbite]])

icetgt = PokeBattle_Battler.new(:NONE, battle)
icetgt.types_list = [:ICE]
fbody.pbEffectsOnDealingDamage(contact, fbody, icetgt, 30)
check(fails, "ice type immune to frost body", icetgt.log, [])

nocontact = PokeBattle_Move.new(:WATERGUN, type: :WATER)
farr = PokeBattle_Battler.new(:NONE, battle)
fbody.pbEffectsOnDealingDamage(nocontact, fbody, farr, 30)
check(fails, "non-contact move never triggers frost body", farr.log, [])
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
# AI path passes the battler object and a move object directly
ai_move = PokeBattle_Move.new(:CALMMIND)
check(fails, "sagepower AI battler+move blocked", battle.pbCanChooseMove?(sg, ai_move), false)
ai_locked = PokeBattle_Move.new(:PSYCHIC)
check(fails, "sagepower AI locked move ok", battle.pbCanChooseMove?(sg, ai_locked), true)
nolock = PokeBattle_Battler.new(:NONE, battle)
check(fails, "no-lock battler AI path ok", battle.pbCanChooseMove?(nolock, ai_move), true)
check(fails, "sagepower special dmg", PokeBattle_Move.new(:PSYCHIC, type: :PSYCHIC, cat: :special).pbCalcDamage(sg, tgt4), 150)

# deathgrip trap
dg = PokeBattle_Battler.new(:DEATHGRIP, battle)
tgt5 = PokeBattle_Battler.new(:NONE, battle)
tgt5.effects[:MultiTurn] = 0
dg.pbEffectsOnDealingDamage(PokeBattle_Move.new(:TACKLE, flags: [:contact]), dg, tgt5, 30)
check(fails, "deathgrip trap", tgt5.effects[:MultiTurn], 5)

# wave 4: excalibur forces 2x vs Dragon (steel chart 0.5 corrected)
exc_user = PokeBattle_Battler.new(:NONE, battle)
dragon = PokeBattle_Battler.new(:NONE, battle); dragon.types_list = [:DRAGON]
tm = PokeBattle_Move.new(:EXCALIBUR, type: :STEEL).pbTypeModifier(:STEEL, exc_user, dragon)
check(fails, "excalibur vs dragon", tm.to_a, [2, 1])
nondragon = PokeBattle_Battler.new(:NONE, battle)
tm2 = PokeBattle_Move.new(:EXCALIBUR, type: :STEEL).pbTypeModifier(:STEEL, exc_user, nondragon)
check(fails, "excalibur vs nondragon", tm2.to_a, [1, 1])

# sheer cold: forces 2x vs Water (ice chart 0.5 corrected), no longer an OHKO
sc_user = PokeBattle_Battler.new(:NONE, battle)
water = PokeBattle_Battler.new(:NONE, battle); water.types_list = [:WATER]
tm_sc = PokeBattle_Move.new(:SHEERCOLD, type: :ICE).pbTypeModifier(:ICE, sc_user, water)
check(fails, "sheer cold vs water", tm_sc.to_a, [2, 1])
# Water/Ground: Water corrected to 2x, Ground already 2x => 4x overall
waterground = PokeBattle_Battler.new(:NONE, battle)
waterground.types_list = [:WATER, :GROUND]
tm_sc2 = PokeBattle_Move.new(:SHEERCOLD, type: :ICE).pbTypeModifier(:ICE, sc_user, waterground)
check(fails, "sheer cold vs water/ground", tm_sc2.to_a, [4, 1])
nonwater = PokeBattle_Battler.new(:NONE, battle)
tm_sc3 = PokeBattle_Move.new(:SHEERCOLD, type: :ICE).pbTypeModifier(:ICE, sc_user, nonwater)
check(fails, "sheer cold vs nonwater", tm_sc3.to_a, [1, 1])
# Freeze-Dry keeps its own native doubling; ours must not leak onto other moves.
tm_sc4 = PokeBattle_Move.new(:ICEBEAM, type: :ICE).pbTypeModifier(:ICE, sc_user, water)
check(fails, "other ice moves still resisted by water", tm_sc4.to_a, [1, 2])

# bonebreaker: immune ground-vs-flying floored to neutral for bone moves
bb = PokeBattle_Battler.new(:BONEBREAKER, battle)
flyer = PokeBattle_Battler.new(:NONE, battle); flyer.types_list = [:FLYING]
tm3 = PokeBattle_Move.new(:BONEMERANG, type: :GROUND).pbTypeModifier(:GROUND, bb, flyer)
check(fails, "bonebreaker floors immunity", tm3.to_a, [1, 1])
tm4 = PokeBattle_Move.new(:EARTHQUAKE, type: :GROUND).pbTypeModifier(:GROUND, bb, flyer)
check(fails, "bonebreaker nonbone stays immune", tm4.immune?, true)
check(fails, "bonebreaker bone dmg", PokeBattle_Move.new(:BONECLUB).pbCalcDamage(bb, nondragon), 120)
hitflags_bb = [:Levitate]
PokeBattle_Move.new(:BONEMERANG, type: :GROUND).pbTypeImmunities(bb, [flyer], hitflags_bb)
check(fails, "bonebreaker reopens levitate", hitflags_bb, [:Success])

# deeprooted: absorb heal x1.3
dr = PokeBattle_Battler.new(:DEEPROOTED, battle)
dr.absorbHP(40, nondragon, :HPDrainingMove)
check(fails, "deeprooted absorb boost", dr.log, [[:absorb, 52]])

# chloroplast: own moves see sun; others see real weather
ch = PokeBattle_Battler.new(:CHLOROPLAST, battle)
check(fails, "chloroplast sun", battle.pbWeather(ch), :SUNNYDAY)
check(fails, "other user real weather", battle.pbWeather(nondragon), :RAINDANCE)

# fullmoon: moonlight heal override 75%
fm = PokeBattle_Battler.new(:FULLMOON, battle)
ml = PokeBattle_Move_0D8.new(:MOONLIGHT)
ml.pbEffect(fm, [])
check(fails, "fullmoon moonlight 75", fm.log, [[:heal, 75]])
other = PokeBattle_Battler.new(:NONE, battle)
ml.pbEffect(other, [])
check(fails, "moonlight vanilla for others", other.log, [[:heal, 50]])

# amplifier: sound move spreads, 1.3x
amp = PokeBattle_Battler.new(:AMPLIFIER, battle)
check(fails, "amplifier spread", amp.pbTarget(PokeBattle_Move.new(:HYPERVOICE, flags: [:soundmove])), :AllOpposing)
check(fails, "amplifier nonsound target", amp.pbTarget(PokeBattle_Move.new(:TACKLE)), :SingleNonUser)
check(fails, "amplifier sound dmg", PokeBattle_Move.new(:HYPERVOICE, flags: [:soundmove]).pbCalcDamage(amp, nondragon), 130)

# innerfocus: focus blast never misses
inf = PokeBattle_Battler.new(:INNERFOCUS, battle)
check(fails, "innerfocus focus blast", PokeBattle_Move.new(:FOCUSBLAST).pbAccuracyCheck(inf, nondragon), true)
check(fails, "innerfocus other move", PokeBattle_Move.new(:TACKLE).pbAccuracyCheck(inf, nondragon), false)

# AI visibility: block immunities zero the typemod; absorb-heals do not
ft = PokeBattle_Battler.new(:FLYTRAP, battle)
tm_ft = PokeBattle_Move.new(:XSCISSOR, type: :BUG).pbTypeModifier(:BUG, hitter, ft)
check(fails, "flytrap typemod zero", tm_ft.immune?, true)
tm_ft2 = PokeBattle_Move.new(:TACKLE).pbTypeModifier(:NORMAL, hitter, ft)
check(fails, "flytrap other types normal", tm_ft2.immune?, false)
sb2 = PokeBattle_Battler.new(:STONEBARK, battle)
tm_sb = PokeBattle_Move.new(:VINEWHIP, type: :GRASS).pbTypeModifier(:GRASS, hitter, sb2)
check(fails, "stonebark heal keeps typemod", tm_sb.immune?, false)

# season's edge: type follows the user's seasonal form; others untouched
StubSpecies = Struct.new(:species)
se = PokeBattle_Battler.new(:NONE, battle)
def se.pokemon; StubSpecies.new(:SAWSBUCK); end
def se.form; 3; end
se_move = PokeBattle_Move.new(:SEASONSEDGE, type: :NORMAL)
check(fails, "seasons edge winter -> ice", se_move.pbType(se), :ICE)
def se.form; 0; end
check(fails, "seasons edge spring -> fairy", se_move.pbType(se), :FAIRY)
notdeer = PokeBattle_Battler.new(:NONE, battle)
def notdeer.pokemon; StubSpecies.new(:KANGASKHAN); end
def notdeer.form; 0; end
check(fails, "seasons edge non-seasonal user stays normal", se_move.pbType(notdeer), :NORMAL)
check(fails, "other move unaffected", PokeBattle_Move.new(:TACKLE, type: :NORMAL).pbType(se), :NORMAL)

# --- frostbite: chip, turn-skip removal, Fire-move thaw --------------------
fb = PokeBattle_Battler.new(:NONE, battle)
fb.status = :FROZEN
CHROOKED_STATUS_TURN_END[:FROZEN].call(fb, battle)
check(fails, "frostbite chips 1/16", fb.log.include?([:chip, 6]), true)
check(fails, "frostbite announces itself", battle.shown.to_a.any? { |m| m.include?("frostbite") }, true)

mg = PokeBattle_Battler.new(:MAGICGUARD, battle)
mg.status = :FROZEN
CHROOKED_STATUS_TURN_END[:FROZEN].call(mg, battle)
check(fails, "magic guard takes no chip", mg.log.any? { |e| e[0] == :chip }, false)

# While Nevermelting Hail is really on, vanilla already chipped - ours must not.
battle.state.effects[:NeverMeltIce] = true
nm = PokeBattle_Battler.new(:NONE, battle)
nm.status = :FROZEN
CHROOKED_STATUS_TURN_END[:FROZEN].call(nm, battle)
check(fails, "no double chip under nevermelting hail", nm.log.any? { |e| e[0] == :chip }, false)
battle.state.effects[:NeverMeltIce] = false

# The turn-skip block is guarded by !NeverMeltIce, so the vanilla body must see
# the flag ON - and the flag must be restored the moment the call returns.
act = PokeBattle_Battler.new(:NONE, battle)
act.status = :FROZEN
plain = PokeBattle_Move.new(:TACKLE)
check(fails, "frostbitten mon still acts", act.pbTryUseMove(nil, plain), :acted)
check(fails, "turn-skip block sees the flag on", act.log.include?([:tried, true]), true)
check(fails, "flag restored after the call", battle.state.effects[:NeverMeltIce], false)

thaw = PokeBattle_Battler.new(:NONE, battle)
thaw.status = :FROZEN
fire = PokeBattle_Move.new(:FLAMEWHEEL, type: :FIRE)
def fire.canThawUser?; true; end
def fire.name; "Flame Wheel"; end
thaw.pbTryUseMove(nil, fire)
check(fails, "fire move thaws the frostbite", thaw.log.include?([:cure, :FROZEN]), true)

# --- end-of-round handlers run BEFORE the vanilla body ---------------------
# Vanilla pbEndOfRoundPhase replaces fainted battlers inside itself (Battle.rb
# ~7423/7448). A chip dealt after super KO's a mon the engine has already
# finished replacing for this round, stranding an empty slot until next turn.
$eor_order = []
ko = PokeBattle_Battler.new(:NONE, battle)
ko.status = :FROZEN
ko.define_singleton_method(:pbContinueStatus) { |*a| $eor_order << :chip }
battle.battlers = [ko]
battle.pbEndOfRoundPhase
check(fails, "status chip precedes vanilla faint-replacement", $eor_order, [:chip, :vanilla_body])

fails.each { |f| puts "FAIL #{f}" }
raise "#{fails.size} failures" unless fails.empty?
puts "all event-hook checks pass"
