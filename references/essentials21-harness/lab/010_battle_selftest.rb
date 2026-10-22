# chrooked dex lab: headless battle self-test for ported mechanics.
# LAB-ONLY - lives in the lab copy's Data/Scripts/998_ChrookedDexLab/ and is
# never deployed to a played copy, except briefly, by hand, for a one-boot proof
# (mjolnir runbook 31), and removed straight after.
#
# Runs only when chrooked-selftest.on exists in the game folder; its words name
# the mechanics to test, in order (e.g. "kindle bloom"). Boots without the marker
# are unaffected.
# It triggers once per process, at the first of these hooks it reaches:
#   1. GameData.load_all  - inside Game.initialize, the moment game data exists;
#   2. Game.set_up_system - before the title screen and any language prompt;
#   3. Scene_Intro#main   - the title screen;
#   4. Graphics.update    - first frame after game data exists (armed boots only).
# Kirin 0.3.5 reached Nova's title without calling 2 or 3 as wrapped here
# (mjolnir NV-5, 2026-10-22), so the hooks are layered and each logs when it fires,
# with where Game.set_up_system and Scene_Intro#main are defined at that moment.
# It writes chrooked_load.log, and the runner stops the game once it logs DONE.
#
# Safety, because a played copy's real save sits next to it:
#   - it builds only the throwaway globals the battle code reads ($player, $bag,
#     $stats, $game_switches, $game_variables) and restores the previous values
#     afterwards, so nothing it made survives into the session;
#   - while it runs, SaveData::DIRECTORY points at chrooked-selftest-saves/, so
#     even an emergency save (Essentials' Hangup path) cannot touch the real save;
#   - everything runs inside a rescue-all that logs, so the boot always continues.
#
# Paths are resolved when the file loads, while the working directory is the game
# folder, so a runtime that changes directory later cannot hide the log.
#
# Two phases, both through Essentials' own battle code:
#   CALC  - damage-calc mechanics: Battle::Move#pbCalcDamage on the SAME
#           battlers and RNG seed with the ability, with none, and with a
#           control ability, so the effect is measured rather than assumed.
#   FIGHT - one AI-vs-AI battle in Battle::DebugSceneNoVisuals (the scene the
#           Battle Frontier simulator uses), so the handler fires in real flow.
# The port's own OBS lines are marker-gated too (chrooked-oracle.on); the runner
# sets that marker and the harness scores those lines against the spec.
module ChrookedSelfTest
  MARKER       = File.expand_path("chrooked-selftest.on")
  ARMED        = File.exist?(MARKER)
  LOG          = File.expand_path("chrooked_load.log")
  SAVE_SCRATCH = File.expand_path("chrooked-selftest-saves") + "/"
  LEVEL        = 50
  SEED         = 12_345

  # One case per ported mechanic, registered by the port itself when it loads:
  #   ($chrooked_selftest_cases ||= {})["kindle"] = { ability: :KINDLE, ... }
  # A port generated from its spec's template: block writes that line from the
  # spec's probes (chrooked_pokedex.behavior.templates); a hand-written port adds
  # its own. This file loads before 998_ChrookedMods/, but reads the cases only
  # when it triggers (GameData.load_all at the earliest), after every port loaded.
  #   ability  - the ability under test        control - a comparison ability, or nil
  #   user/foe - species for both phases       calc    - moves measured in CALC; an
  #   fight    - the ability holder's moves      entry may be [move, hp_fraction] to
  #              in FIGHT (foe knows Tackle)     set the user's HP first (e.g. 0.25),
  #                                              or [move, hp_fraction, setup] to set
  #              the field or the user first (see arrange): {weather: :Rain,
  #              terrain: :Grassy, item: :UTILITYUMBRELLA, airborne: true,
  #              stats: :physical|:special, types: [:WATER]}. :STRUGGLE is
  #              built as Essentials builds it (Battle::Move::Struggle)
  #   heal     - [move, hp_fraction] entries for a healing move whose amount the
  #              mechanic changes (Moonlight under Full Moon): the user's HP is set,
  #              the move starts, and pbHealAmount is read with the ability and
  #              without (HEAL line); the port logs its own OBS line
  #   neutral  - CALC sets both battlers' types to ??? (QMARKS): no same-type bonus,
  #              no type matchups, so the ratio is the ability's effect alone
  #   without  - moves for a spec case about a Pokemon WITHOUT the ability. A port
  #              only runs for its holder, so it can never log that case; the
  #              self-test measures it instead (holder, a NON_HOLDER, and no ability
  #              on the same battlers) and logs the result as the mechanic's OBS
  #              line, tagged source=selftest
  NON_HOLDER = :STENCH   # exists in Nova, no damage handler, no Ruleset behavior

  def self.log(msg)
    File.open(LOG, "a") { |f| f.puts("[chrooked:selftest] #{msg}") }
  rescue StandardError
    nil
  end

  # An observation the self-test measured on the mechanic's behalf (see `without`).
  def self.obs(mechanic, fields)
    File.open(LOG, "a") { |f| f.puts("[chrooked:#{mechanic}] OBS #{fields}") }
  rescue StandardError
    nil
  end

  def self.guard(phase)
    yield
  rescue Exception => e   # report everything (Hangup included); the boot must survive
    log("ERROR #{phase} #{e.class}: #{e.message} @ #{(e.backtrace || [])[0, 3].join(' | ')}")
  end

  # Where the two hooked methods are defined right now (file:line). A runtime
  # that redefines them after the game's scripts load shows up here.
  def self.owners
    sus = (Game.method(:set_up_system).source_location rescue nil)
    tm  = (Scene_Intro.instance_method(:main).source_location rescue nil)
    "set_up_system@#{sus ? sus.join(':') : '?'} title_main@#{tm ? tm.join(':') : '?'}"
  end

  # Graphics.update fallback: fire once, on the first frame after game data exists.
  def self.poll
    return if $chrooked_selftest_ran || @polled
    return unless defined?(GameData::Ability::DATA) && !GameData::Ability::DATA.empty?
    @polled = true
    trigger("graphics")
  end

  def self.trigger(where)
    armed = File.exist?(MARKER)
    log("hook #{where} armed=#{armed} ran=#{!!$chrooked_selftest_ran} cwd=#{Dir.pwd} #{owners}")
    return if !armed || $chrooked_selftest_ran
    $chrooked_selftest_ran = true
    mechanics = File.read(MARKER).split.map(&:downcase)
    guard("run") { with_test_state { run_all(mechanics) } }
  end

  def self.swap_save_dir(dir)
    SaveData.send(:remove_const, :DIRECTORY)
    SaveData.const_set(:DIRECTORY, dir)
  end

  def self.with_test_state
    old = [$player, $bag, $stats, $game_switches, $game_variables]
    old_dir = SaveData::DIRECTORY
    Dir.mkdir(SAVE_SCRATCH) unless File.directory?(SAVE_SCRATCH)
    swap_save_dir(SAVE_SCRATCH)
    $player         = Player.new("Lab", GameData::TrainerType.keys.first)
    $bag            = PokemonBag.new
    $stats          = GameStats.new
    $game_switches  = Game_Switches.new
    $game_variables = Game_Variables.new
    yield
  ensure
    $player, $bag, $stats, $game_switches, $game_variables = old
    swap_save_dir(old_dir) if old_dir
  end

  # Fixed IVs, EVs and nature, so stats are the same on every boot.
  def self.mon(species, moves)
    pkmn = Pokemon.new(species, LEVEL)
    GameData::Stat.each_main do |s|
      pkmn.iv[s.id] = 31
      pkmn.ev[s.id] = 0
    end
    pkmn.nature = :HARDY
    pkmn.forget_all_moves
    moves.each { |m| pkmn.learn_move(m) }
    pkmn.calc_stats
    pkmn
  end

  def self.battle(p1, p2)
    tt = GameData::TrainerType.keys.first
    t1 = NPCTrainer.new("LabA", tt)
    t1.party = [p1]
    t2 = NPCTrainer.new("LabB", tt)
    t2.party = [p2]
    b = Battle.new(Battle::DebugSceneNoVisuals.new, [p1], [p2], t1, t2)
    b.debug          = true
    b.controlPlayer  = true
    b.internalBattle = false
    b
  end

  # One hit's damage by Essentials' own formula, for each ability in turn, on
  # the SAME battlers. The target has no ability and the RNG is reseeded before
  # each hit, so the only difference between results is the user's ability.
  def self.damage(user_species, abilities, foe_species, move_id, hp_fraction: 1.0, neutral: false, setup: {})
    # Struggle is no PBS move: Essentials builds it in code, so the user knows
    # Tackle and the move object is made the way a battle makes it.
    struggle = move_id == :STRUGGLE
    b = battle(mon(user_species, struggle ? [:TACKLE] : [move_id]), mon(foe_species, [:TACKLE]))
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    user   = b.battlers[0]
    target = b.battlers[1]
    target.ability = nil
    user.hp = [(user.totalhp * hp_fraction).floor, 1].max
    if neutral
      user.pbChangeTypes(:QMARKS)
      target.pbChangeTypes(:QMARKS)
    end
    arrange(b, user, setup)
    move = struggle ? Battle::Move::Struggle.new(b, nil) : Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    abilities.map do |ability|
      user.ability = ability
      move.calcType = move.pbCalcType(user)
      target.damageState.reset
      target.damageState.typeMod = move.pbCalcTypeMod(move.calcType, user, target)
      srand(SEED)
      move.pbCalcDamage(user, target)
      [target.damageState.calcDamage, move.calcType, target.damageState.typeMod]
    end
  end

  # The field and user state one measurement needs (mjolnir NV-9), set once on the
  # battlers before every ability is measured, so with/none/control share it:
  #   weather  - the field's weather (:Rain, :Hail, ...)
  #   terrain  - the field's terrain (:Grassy, ...)
  #   item     - the user's held item (:UTILITYUMBRELLA, ...)
  #   airborne - true lifts the user with Magnet Rise (ungrounded, off terrain)
  #   stats    - :physical or :special: which of Attack and Sp. Atk is strictly
  #              higher, by swapping the two (ties broken by one point)
  #   types    - the user's types, e.g. [:WATER, :DRAGON] (after neutral mode, so
  #              a same-type bonus can be measured; NV-10)
  def self.arrange(b, user, setup)
    b.field.weather = setup[:weather] if setup[:weather]
    b.field.terrain = setup[:terrain] if setup[:terrain]
    user.item = setup[:item] if setup[:item]
    user.effects[PBEffects::MagnetRise] = 5 if setup[:airborne]
    if setup[:stats]
      hi, lo = [user.attack, user.spatk].max, [user.attack, user.spatk].min
      lo = hi - 1 if lo == hi
      user.attack, user.spatk = (setup[:stats] == :physical) ? [hi, lo] : [lo, hi]
    end
    if setup[:types]
      user.types = setup[:types]
      user.effects[PBEffects::ExtraType] = nil
    end
  end

  # What a healing move would restore, for each ability in turn, on the SAME user
  # at the same HP: the move starts (pbOnStartUse, where weather-dependent heals
  # decide their amount) and pbHealAmount is read. Returns the amounts, then max HP.
  def self.heal(user_species, abilities, foe_species, move_id, hp_fraction)
    b = battle(mon(user_species, [move_id]), mon(foe_species, [:TACKLE]))
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    user = b.battlers[0]
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    amounts = abilities.map do |ability|
      user.ability = ability
      user.hp = [(user.totalhp * hp_fraction).floor, 1].max
      move.pbOnStartUse(user, [user])
      move.pbHealAmount(user)
    end
    amounts + [user.totalhp]
  end

  def self.run_all(mechanics)
    log("start mechanics=#{mechanics.join(',')} ruby=#{RUBY_VERSION} platform=#{RUBY_PLATFORM} " \
        "saves=#{SaveData::DIRECTORY} registered=#{($chrooked_selftest_cases || {}).size}")
    mechanics.each { |mechanic| guard("mechanic #{mechanic}") { run(mechanic) } }
  ensure
    log("DONE")
  end

  def self.run(mechanic)
    cases = $chrooked_selftest_cases || {}
    spec = cases[mechanic]
    if spec.nil?
      log("ERROR no case registered for '#{mechanic}' (registered: #{cases.keys.sort.join(', ')}); " \
          "is chrooked_#{mechanic}.rb installed in 998_ChrookedMods/?")
      return
    end
    log("mechanic #{mechanic} data ability=#{GameData::Ability.exists?(spec[:ability])}")
    guard("calc") do
      (spec[:calc] || []).each do |entry|
        move_id, hp, setup = entry.is_a?(Array) ? entry : [entry, 1.0]
        setup ||= {}
        abilities = [spec[:ability], nil]
        abilities << spec[:control] if spec[:control]
        (with, type, eff), (none, _, _), (control, _, _) =
          damage(spec[:user], abilities, spec[:foe], move_id, hp_fraction: hp, neutral: !!spec[:neutral], setup: setup)
        field = setup.empty? ? "" : " setup=#{setup.map { |k, v| "#{k}:#{v.is_a?(Array) ? v.join('/') : v}" }.join(',')}"
        log("CALC #{mechanic} move=#{move_id} hp=#{hp}#{field} type=#{type} eff=#{eff} with=#{with} none=#{none} " \
            "#{spec[:control] || 'control'}=#{control || '-'} ratio=#{format('%.3f', with.to_f / none)}")
      end
    end
    guard("without") do
      (spec[:without] || []).each do |move_id|
        (holder, _, _), (nonholder, _, _), (none, _, _) =
          damage(spec[:user], [spec[:ability], NON_HOLDER, nil], spec[:foe], move_id, neutral: !!spec[:neutral])
        result = nonholder == none ? "NORMAL" : "BOOSTED"
        obs(mechanic, "move=#{move_id} ability=false result=#{result} source=selftest " \
                      "holder=#{holder} #{NON_HOLDER}=#{nonholder} none=#{none}")
      end
    end
    guard("heal") do
      (spec[:heal] || []).each do |move_id, hp|
        hp ||= 0.5
        with, none, max = heal(spec[:user], [spec[:ability], nil], spec[:foe], move_id, hp)
        log("HEAL #{mechanic} move=#{move_id} hp=#{hp} with=#{with} none=#{none} max=#{max} " \
            "share=#{format('%.3f', with.to_f / max)}")
      end
    end
    Graphics.update if defined?(Graphics)
    guard("fight") do
      p1 = mon(spec[:user], spec[:fight])
      p1.ability = spec[:ability]
      b = battle(p1, mon(spec[:foe], [:TACKLE]))
      outcome = b.pbStartBattle
      log("FIGHT #{mechanic} outcome=#{outcome} turns=#{b.turnCount}")
    end
  end
end

module GameData
  class << self
    unless method_defined?(:chrooked_selftest_load_all)
      alias_method :chrooked_selftest_load_all, :load_all
      def load_all
        chrooked_selftest_load_all
        ChrookedSelfTest.trigger("load_all")
      end
    end
  end
end

module Game
  class << self
    unless method_defined?(:chrooked_selftest_set_up_system)
      alias_method :chrooked_selftest_set_up_system, :set_up_system
      def set_up_system
        ChrookedSelfTest.trigger("set_up_system")
        chrooked_selftest_set_up_system
      end
    end
  end
end

class Scene_Intro
  unless method_defined?(:chrooked_selftest_main)
    alias_method :chrooked_selftest_main, :main
    def main
      ChrookedSelfTest.trigger("title")
      chrooked_selftest_main
    end
  end
end

# The per-frame fallback costs nothing on unarmed boots: it is never installed.
if ChrookedSelfTest::ARMED
  module Graphics
    class << self
      unless method_defined?(:chrooked_selftest_update)
        alias_method :chrooked_selftest_update, :update
        def update(*args)
          chrooked_selftest_update(*args)
          ChrookedSelfTest.poll
        end
      end
    end
  end
end

ChrookedSelfTest.log("loaded armed=#{ChrookedSelfTest::ARMED} cwd=#{Dir.pwd} #{ChrookedSelfTest.owners}")
