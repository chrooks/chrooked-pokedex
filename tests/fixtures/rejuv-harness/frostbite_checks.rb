# Frostbite on Rejuvenation 14.0.20: the engine's freeze block is unconditional
# (`if self.status == :FROZEN`), so the mod must hide the status from the
# vanilla body for the duration of pbTryUseMove and restore it after.
# Usage: ruby frostbite_checks.rb <harness-dir>
def _INTL(s, *a); a.each_with_index { |v, i| s = s.gsub("{#{i + 1}}", v.to_s) }; s; end
CHROOKED_STATUS_DAMAGE_MODS = {}
CHROOKED_STATUS_TURN_END = {}

class PokeBattle_Battle
  attr_reader :shown
  def initialize; @state = Struct.new(:effects).new({}); @shown = []; end
  def state; @state; end
  def pbDisplay(m); @shown << m; end
  def pbCommonAnimation(*a); end
  def magicGuardAbilities; [:MAGICGUARD]; end
end

class PokeBattle_Move
  attr_reader :move, :battle
  def initialize(move, battle, special: false, thaws: false)
    @move = move; @battle = battle; @special = special; @thaws = thaws
  end
  def canThawUser?; @thaws; end
  def name; @move.to_s.capitalize; end
  def pbIsSpecial?(a, t); @special; end
  def pbType(a); :NORMAL; end
end

class PokeBattle_Battler
  attr_reader :status, :log
  attr_accessor :ability, :crested
  def initialize(battle, status = nil, ability = :NONE)
    @battle = battle; @status = status; @ability = ability; @log = []; @totalhp = 160
  end
  def status=(v); @log << [:setter, v]; @status = v; end
  def totalhp; @totalhp; end
  def isFainted?; false; end
  def pbThis(*a); "Stub"; end
  def hasType?(t); false; end
  def pbCureStatus(show = true); @log << [:cure, @status]; @status = nil; end
  def pbContinueStatus(anim = true); @log << [:continue, @status]; end
  def pbReduceHP(n, *a); @log << [:chip, n]; end
  def pbFaint(*a); end
  # 14.0.20 vanilla body: no gate, a frozen mon loses the turn.
  def pbTryUseMove(choice, basemove, flags = { passedtrying: false, instructed: false })
    @log << [:vanilla_saw, @status]
    return :skipped if @status == :FROZEN
    :acted
  end
end

Dir[File.join(ARGV[0], "chrooked_frostbite.rb")].each { |f| eval(File.read(f), TOPLEVEL_BINDING, f) }

fails = []
def check(fails, name, got, want); fails << "#{name}: got #{got.inspect}, want #{want.inspect}" unless got == want; end

b = PokeBattle_Battle.new
tackle = PokeBattle_Move.new(:TACKLE, b)
flags = { passedtrying: false, instructed: false }

fb = PokeBattle_Battler.new(b, :FROZEN)
check(fails, "frostbitten mon acts", fb.pbTryUseMove(nil, tackle, flags), :acted)
check(fails, "vanilla body saw no status", fb.log.include?([:vanilla_saw, nil]), true)
check(fails, "status restored", fb.status, :FROZEN)
check(fails, "setter not used for the swap", fb.log.any? { |e| e[0] == :setter }, false)
check(fails, "no random thaw", fb.log.any? { |e| e[0] == :cure }, false)
check(fails, "no 'frozen solid' turn loss", fb.log.any? { |e| e[0] == :continue }, false)

fire = PokeBattle_Move.new(:FLAMEWHEEL, b, thaws: true)
th = PokeBattle_Battler.new(b, :FROZEN)
check(fails, "fire move still acts", th.pbTryUseMove(nil, fire, flags), :acted)
check(fails, "fire move cures", th.log.include?([:cure, :FROZEN]), true)
check(fails, "cured mon not re-frozen", th.status, nil)
check(fails, "thaw message", b.shown.any? { |m| m.include?("melted the frost") }, true)

ok = PokeBattle_Battler.new(b, nil)
check(fails, "healthy mon acts", ok.pbTryUseMove(nil, tackle, flags), :acted)
check(fails, "healthy mon untouched", ok.log, [[:vanilla_saw, nil]])

burned = PokeBattle_Battler.new(b, :BURN)
burned.pbTryUseMove(nil, tackle, flags)
check(fails, "other statuses pass straight through", burned.log, [[:vanilla_saw, :BURN]])

sp = PokeBattle_Move.new(:ICEBEAM, b, special: true)
check(fails, "special halved", CHROOKED_STATUS_DAMAGE_MODS[:FROZEN].call(sp, PokeBattle_Battler.new(b, :FROZEN), nil), 0.5)
check(fails, "physical untouched", CHROOKED_STATUS_DAMAGE_MODS[:FROZEN].call(tackle, PokeBattle_Battler.new(b, :FROZEN), nil), 1.0)
check(fails, "guts exempt", CHROOKED_STATUS_DAMAGE_MODS[:FROZEN].call(sp, PokeBattle_Battler.new(b, :FROZEN, :GUTS), nil), 1.0)
b.state.effects[:NeverMeltIce] = true
check(fails, "halves even under nevermelting hail", CHROOKED_STATUS_DAMAGE_MODS[:FROZEN].call(sp, PokeBattle_Battler.new(b, :FROZEN), nil), 0.5)
ch = PokeBattle_Battler.new(b, :FROZEN)
CHROOKED_STATUS_TURN_END[:FROZEN].call(ch, b)
check(fails, "chips 1/16 even under nevermelting hail", ch.log.include?([:chip, 10]), true)
b.state.effects[:NeverMeltIce] = false
mg = PokeBattle_Battler.new(b, :FROZEN, :MAGICGUARD)
CHROOKED_STATUS_TURN_END[:FROZEN].call(mg, b)
check(fails, "magic guard no chip", mg.log.any? { |e| e[0] == :chip }, false)

if fails.empty? then puts "OK (frostbite 14.0.20: #{19} checks)" else puts fails; exit 1 end
