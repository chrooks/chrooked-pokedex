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
#     $stats, $game_switches, $game_variables, and $PokemonSystem when the game has
#     not loaded it yet) and restores the previous values
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
  #   chance   - [move, {status:, status_rate:, flinch_rate:, setup:, n:}] entries
  #              for an on-hit chance (Infernal Maw's burn and flinch, NV-11): the
  #              damage A/B once, then the user's OnDealingHit handler fired n times
  #              (default 400) on a fresh target with a fixed seed; the observed
  #              rates are checked against the expected ones (within 3 standard
  #              deviations, exactly 0 when 0 is expected) and logged as the
  #              mechanic's OBS line, tagged source=selftest
  #   defend   - moves used AGAINST the ability's holder, for a defensive ability
  #              (a type immunity, NV-13): the target holds it and the move's
  #              MoveImmunity check runs as pbImmunityByAbility runs it, with the
  #              ability and without (DEFEND line); the port logs its own OBS line
  #              A defend entry may be [move, {mold_breaker: true}]: the attacker
  #              breaks the mold (NV-18). Every entry also logs the mechanic's OBS
  #              line with source=selftest, mold_breaker and immune
  #   struck   - [move, {status:, status_rate:, setup:, n:}] entries for a status
  #              the holder gives an attacker that touches it (NV-19): the foe's
  #              move handed to the holder's OnBeingHit n times (default 400),
  #              fixed seed; the foe's rate checked as chance's, logged as the
  #              mechanic's OBS line with side=struck, tagged source=selftest
  #   taken    - moves the foe uses on the holder (a defensive multiplier, NV-18):
  #              the damage it takes with the ability and without (TAKEN line);
  #              the port logs its own OBS line
  #   keeps    - [kind, {status:}] entries for an effect the game's own ability
  #              keeps beside a port (NV-18): measured with the ability and with
  #              none (keep_measure), logged as the mechanic's OBS line with
  #              case=keeps, tagged source=selftest
  #   drain    - [move, {hp_lost:, target_ability:}] entries for a heal-on-hit
  #              (NV-14): a hit that took hp_lost HP (default 100) is handed to the
  #              user's OnDealingHit handler, the user at half HP so a heal shows,
  #              the target holding target_ability if given (:LIQUIDOOZE); DRAIN
  #              line with the user's HP before and after; the port logs its own OBS
  #   ko       - {kos:, hp:, stages:} entries for an effect on knocking out a foe
  #              (NV-14): the user's move ends with kos foes fainted, as
  #              pbEffectsAfterMove hands them to OnEndOfUsingMove (the one foe,
  #              listed once per knockout and never really fainted, so the battle
  #              is not over); the user's HP fraction (default 0.5) and stat stages
  #              ({SPECIAL_ATTACK: 6}) are set first; KO line; the port logs its OBS
  #   priority - [move, hp_fraction] entries: the move's priority as
  #              pbCalculatePriority asks it of the user's ability (NV-14);
  #              PRIORITY line; the port logs its own OBS line
  #   compare  - [move, part, kind, setup] entries for a composed ability (NV-15,
  #              NV-16): one value measured with the composed ability, with that
  #              vanilla part alone, and with none, on the same battlers and seed;
  #              the composition carries the part when the first two match. kind
  #              (default :hit) is what is measured (see measure); setup as CALC's.
  #              Logged as the mechanic's OBS line, tagged source=selftest
  #   identity - parts a composed ability must answer to by name (NV-16): whether
  #              its holder's hasActiveAbility? says yes for the part, alone and in
  #              a list, and no for an ability it lacks. Logged as the mechanic's
  #              OBS line with case=identity, tagged source=selftest
  #   status   - for a status mechanic (frostbite, NV-12), the status the next
  #              three phases set on the user; ability is then nil:
  #   turn     - [move, n]: the user tries its move n times while in that status
  #              (Battle::Battler#pbTryUseMove, fixed seed); counts acted / cured
  #   status_damage - [move, ability] pairs: one hit's damage in the status vs
  #              without it, on the same battlers, with that ability (or none)
  #   chip     - abilities (nil = none): the end-of-round status damage the user
  #              takes with each, against 1/16 of max HP
  #   cure     - moves: whether the user is cured by using each
  #              (Battle::Battler#pbUseMove_CureUserStatus, the self-cure step)
  #   immune   - target type lists: whether the status can be inflicted on each
  #              (pbCanInflictStatus?, the gate every inflicting move goes through)
  #   (each logged as the mechanic's OBS line with case=turn|damage|chip|cure|immune
  #   and source=selftest)
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
    old = [$player, $bag, $stats, $game_switches, $game_variables, $PokemonSystem]
    old_dir = SaveData::DIRECTORY
    Dir.mkdir(SAVE_SCRATCH) unless File.directory?(SAVE_SCRATCH)
    swap_save_dir(SAVE_SCRATCH)
    $player         = Player.new("Lab", GameData::TrainerType.keys.first)
    $bag            = PokemonBag.new
    $stats          = GameStats.new
    $game_switches  = Game_Switches.new
    $game_variables = Game_Variables.new
    # Message code reads the options' language (the drain message, NV-14); the
    # self-test can run before the game has loaded them.
    $PokemonSystem ||= PokemonSystem.new
    yield
  ensure
    $player, $bag, $stats, $game_switches, $game_variables, $PokemonSystem = old
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
  def self.damage(user_species, abilities, foe_species, move_id, hp_fraction: 1.0, neutral: false, setup: {},
                  target_ability: nil)
    # Struggle is no PBS move: Essentials builds it in code, so the user knows
    # Tackle and the move object is made the way a battle makes it.
    struggle = move_id == :STRUGGLE
    b = battle(mon(user_species, struggle ? [:TACKLE] : [move_id]), mon(foe_species, [:TACKLE]))
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    user   = b.battlers[0]
    target = b.battlers[1]
    target.ability = target_ability
    user.hp = [(user.totalhp * hp_fraction).floor, 1].max
    if neutral
      user.pbChangeTypes(:QMARKS)
      target.pbChangeTypes(:QMARKS)
    end
    arrange(b, user, target, setup)
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
  #   target_types - the target's types, e.g. [:FIRE] for a burn-immune target (NV-11)
  #   status   - the user's status, e.g. :BURN (Guts, NV-16)
  def self.arrange(b, user, target, setup)
    user.status = setup[:status] if setup[:status]
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
    if setup[:target_types]
      target.types = setup[:target_types]
      target.effects[PBEffects::ExtraType] = nil
    end
  end

  # An on-hit chance, counted: the user's OnDealingHit handler fired n times on the
  # same target, reset before each roll (no status, no flinch), with a fixed seed.
  # Nova fires that registry only after a hit that dealt damage and missed any
  # substitute, so the count is of rolls on landed hits. Returns [statused, flinched].
  def self.rolls(spec, move_id, setup, n, status)
    b = battle(mon(spec[:user], [move_id]), mon(spec[:foe], [:TACKLE]))
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    user   = b.battlers[0]
    target = b.battlers[1]
    target.ability = nil
    if spec[:neutral]
      user.pbChangeTypes(:QMARKS)
      target.pbChangeTypes(:QMARKS)
    end
    arrange(b, user, target, setup)
    user.ability = spec[:ability]
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    move.calcType = move.pbCalcType(user)   # a handler may read the type as used (Pyre)
    srand(SEED)
    statused = flinched = 0
    n.times do
      target.status      = :NONE
      target.statusCount = 0
      target.effects[PBEffects::Flinch] = false
      Battle::AbilityEffects.triggerOnDealingHit(user.ability, user, target, move, b)
      statused += 1 if status && target.status == status
      flinched += 1 if target.effects[PBEffects::Flinch]
    end
    [statused, flinched]
  end

  # The holder struck n times: the foe's move handed to the holder's OnBeingHit
  # handler, as pbEffectsOnMakingHit does after a damaging hit, the foe's status
  # reset before each roll, fixed seed (NV-19). setup applies to the foe (types:)
  # and the holder (target_types:). Returns how many rolls left the foe in status.
  def self.struck_rolls(spec, move_id, setup, n, status)
    b = battle(mon(spec[:foe], [move_id]), mon(spec[:user], [:TACKLE]))
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    attacker, holder = b.battlers[0], b.battlers[1]
    attacker.ability = nil
    if spec[:neutral]
      attacker.pbChangeTypes(:QMARKS)
      holder.pbChangeTypes(:QMARKS)
    end
    arrange(b, attacker, holder, setup)
    holder.ability = spec[:ability]
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    move.calcType = move.pbCalcType(attacker)
    srand(SEED)
    count = 0
    n.times do
      attacker.status      = :NONE
      attacker.statusCount = 0
      Battle::AbilityEffects.triggerOnBeingHit(holder.ability, attacker, holder, move, b)
      count += 1 if attacker.status == status
    end
    count
  end

  # A fresh pair of battlers for the status phases: [battle, user, target].
  def self.pair(spec, move_id)
    b = battle(mon(spec[:user], [move_id]), mon(spec[:foe], [:TACKLE]))
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    user, target = b.battlers[0], b.battlers[1]
    target.ability = nil
    user.ability = nil
    if spec[:neutral]
      user.pbChangeTypes(:QMARKS)
      target.pbChangeTypes(:QMARKS)
    end
    [b, user, target]
  end

  # The user tries its move n times while in the status (fixed seed): how often it
  # acted, and how often the status was gone afterwards.
  def self.turns(spec, move_id, n)
    b, user, target = pair(spec, move_id)
    move = user.moves[0]
    srand(SEED)
    acted = cured = 0
    n.times do
      user.status = spec[:status]
      acted += 1 if user.pbTryUseMove([:UseMove, 0, move, target.index, 0], move, false, false)
      cured += 1 if user.status != spec[:status]
    end
    [acted, cured]
  end

  # Whether the target is immune to the move by its ability, through Nova's own
  # pbImmunityByAbility (the move's type as used; the attacker's Mold Breaker lifts
  # it, NV-18): [with the ability, without it, the type].
  def self.defend(spec, move_id, mold_breaker = false)
    b, user, target = pair(spec, move_id)
    target.ability = spec[:ability]
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    move.calcType = move.pbCalcType(user)
    b.moldBreaker = mold_breaker
    with = move.pbImmunityByAbility(user, target, false)
    [!!with, false, move.calcType]
  end

  # What a kept effect of the game's own ability measures, with `ability` on the user:
  #   :status     - whether a foe can give it the status (pbCanInflictStatus?)
  #   :eor_status - the HP its status changes at end of round, from half HP
  def self.keep_measure(spec, kind, status, ability)
    b, user, target = pair(spec, :TACKLE)
    user.ability = ability
    case kind
    when :status then user.pbCanInflictStatus?(status, target, false)
    when :eor_status
      user.hp = [user.totalhp / 2, 1].max
      user.status = status
      before = user.hp
      b.send(:pbEORStatusProblemDamage, [user])
      user.hp - before
    else
      raise ArgumentError, "unknown keeps kind #{kind.inspect}"
    end
  end

  # A hit that took hp_lost HP, as pbEffectsOnMakingHit hands it to the user's
  # OnDealingHit handler (damage dealt, no substitute), with the user at half HP:
  # [the user's HP before, after].
  def self.drain(spec, move_id, hp_lost, target_ability)
    b, user, target = pair(spec, move_id)
    user.ability   = spec[:ability]
    target.ability = target_ability
    user.hp = [user.totalhp / 2, 1].max
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    move.calcType = move.pbCalcType(user)
    target.damageState.calcDamage = hp_lost
    target.damageState.hpLost     = hp_lost
    before = user.hp
    Battle::AbilityEffects.triggerOnDealingHit(user.ability, user, target, move, b)
    [before, user.hp]
  end

  # The user's move ends with kos foes fainted, as pbEffectsAfterMove hands its
  # targets to OnEndOfUsingMove. The one foe is listed once per knockout with its
  # damage state marked fainted, but keeps its HP, so the battle is not over (a
  # knockout that ends the battle triggers nothing, as in Nova's Moxie).
  # Returns [hp before, hp after, stages before, stages after].
  def self.knockout(spec, kos, hp_fraction, stages, ability = spec[:ability])
    b, user, target = pair(spec, :TACKLE)
    user.ability = ability
    user.hp = [(user.totalhp * hp_fraction).floor, 1].max
    stages.each { |stat, n| user.stages[stat] = n }
    target.damageState.fainted = kos > 0
    targets = [target] * [kos, 1].max
    hp, before = user.hp, user.stages.dup
    Battle::AbilityEffects.triggerOnEndOfUsingMove(user.ability, user, targets, user.moves[0], b)
    [hp, user.hp, before, user.stages.dup]
  end

  # One value for a vanilla part's comparison, with `ability` on the user:
  #   :hit        - one hit's damage (the CALC measurement, setup applied)
  #   :airborne   - whether it is airborne (Levitate: how Ground moves miss it)
  #   :forced_out - whether a foe's move can force it out (Suction Cups)
  #   :stat_drop  - whether a foe can lower its Attack (Clear Body)
  #   :locked     - whether, locked into move by a choice, it can still pick Growl
  #   :ko         - the stat stages a knockout raises (Moxie)
  #   :hit_taken  - one hit's damage TO it, the foe attacking (Grass Pelt; NV-17)
  #   :speed      - its Speed, setup applied (Slush Rush in hail)
  #   :immune     - whether the foe's move fails against it by ability (Soundproof)
  #   :crit_taken - the critical-hit stage the foe's move gets against it (Battle Armor)
  #   :switch_in  - the field after it enters (Grassy Surge)
  def self.measure(spec, kind, move_id, setup, ability)
    case kind
    when :hit
      damage(spec[:user], [ability], spec[:foe], move_id, neutral: !!spec[:neutral], setup: setup)[0][0]
    when :hit_taken
      damage(spec[:foe], [nil], spec[:user], move_id, neutral: !!spec[:neutral], setup: setup,
             target_ability: ability)[0][0]
    when :ko
      _, _, before, after = knockout(spec, 1, 0.5, {}, ability)
      moved = after.select { |stat, n| before[stat] != n }.map { |stat, n| "#{stat}:#{before[stat]}->#{n}" }
      moved.empty? ? "unchanged" : moved.join(",")
    else
      b, user, target = pair(spec, move_id || :TACKLE)
      user.ability = ability
      arrange(b, user, target, setup)
      foe_move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id || :TACKLE))
      foe_move.calcType = foe_move.pbCalcType(target)
      case kind
      when :speed      then user.pbSpeed
      when :immune
        !!Battle::AbilityEffects.triggerMoveImmunity(ability, target, user, foe_move, foe_move.calcType, b, false)
      when :crit_taken then Battle::AbilityEffects.triggerCriticalCalcFromTarget(ability, target, user, foe_move, 0)
      when :switch_in
        Battle::AbilityEffects.triggerOnSwitchIn(ability, user, b, true)
        "#{b.field.weather}/#{b.field.terrain}"   # weather/terrain
      when :airborne   then user.airborne?
      when :forced_out then user.canBeForcedOutOfBattle?(false)
      when :stat_drop  then user.pbCanLowerStatStage?(:ATTACK, target, nil, false)
      when :locked
        user.effects[PBEffects::ChoiceBand] = move_id
        user.pbCanChooseMove?(Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:GROWL)), false, false)
      else
        raise ArgumentError, "unknown compare kind #{kind.inspect}"
      end
    end
  end

  # The move's priority as pbCalculatePriority asks it of the user's ability, at
  # hp_fraction of max HP: [the move's own priority, with the ability].
  def self.priority(spec, move_id, hp_fraction)
    b, user, target = pair(spec, move_id)
    user.ability = spec[:ability]
    user.hp = [(user.totalhp * hp_fraction).floor, 1].max
    move = user.moves[0]
    base = move.pbPriority(user)
    [base, Battle::AbilityEffects.triggerPriorityChange(user.ability, user, move, base)]
  end

  # One hit's damage with the user in the status and without it, same battlers.
  def self.status_damage(spec, move_id, ability)
    b, user, target = pair(spec, move_id)
    user.ability = ability
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    [spec[:status], :NONE].map do |status|
      user.status = status
      move.calcType = move.pbCalcType(user)
      target.damageState.reset
      target.damageState.typeMod = move.pbCalcTypeMod(move.calcType, user, target)
      srand(SEED)
      move.pbCalcDamage(user, target)
      target.damageState.calcDamage
    end
  end

  # The end-of-round status damage the user takes with an ability: [lost, max].
  def self.chip(spec, ability)
    b, user, _target = pair(spec, :TACKLE)
    user.ability = ability
    user.status = spec[:status]
    before = user.hp
    b.send(:pbEORStatusProblemDamage, [user])
    [before - user.hp, user.totalhp]
  end

  # Whether using a move cures the user of the status: the self-cure step of
  # pbUseMove, after the move's type for this use is set, as pbUseMove does.
  def self.cured_by?(spec, move_id)
    b, user, _target = pair(spec, move_id)
    user.status = spec[:status]
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    move.calcType = move.pbCalcType(user)
    user.pbUseMove_CureUserStatus(move)
    user.status != spec[:status]
  end

  # Whether the status can be inflicted on a target of these types.
  def self.inflictable?(spec, target_types)
    _b, user, target = pair(spec, :TACKLE)
    target.types = target_types
    target.effects[PBEffects::ExtraType] = nil
    target.pbCanInflictStatus?(spec[:status], user, false)
  end

  # Observed k of n against an expected rate: within 3 standard deviations, and
  # exactly 0 when 0 is expected.
  def self.rate_ok?(k, n, expected)
    return k == 0 if expected.to_f == 0
    (k.to_f / n - expected).abs <= 3 * Math.sqrt(expected * (1 - expected) / n)
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
    log("mechanic #{mechanic} data " +
        (spec[:ability] ? "ability=#{GameData::Ability.exists?(spec[:ability])}" : "status=#{spec[:status]}"))
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
    guard("chance") do
      (spec[:chance] || []).each do |move_id, opts|
        opts ||= {}
        setup = opts[:setup] || {}
        n = opts[:n] || 400
        (with, _, _), (none, _, _) =
          damage(spec[:user], [spec[:ability], nil], spec[:foe], move_id, neutral: !!spec[:neutral], setup: setup)
        statused, flinched = rolls(spec, move_id, setup, n, opts[:status])
        Graphics.update if defined?(Graphics)
        status_rate = opts[:status_rate] || 0
        flinch_rate = opts[:flinch_rate] || 0
        target_types = setup[:target_types] ? setup[:target_types].join('/') : "QMARKS"
        obs(mechanic, "move=#{move_id} ability=true source=selftest target_types=#{target_types} n=#{n} " \
                      "damage=#{with > none ? 'BOOSTED' : 'NORMAL'} with=#{with} none=#{none} " \
                      "status=#{opts[:status] || 'NONE'} status_rate=#{format('%.3f', statused.to_f / n)} " \
                      "status_expected=#{status_rate} status_ok=#{rate_ok?(statused, n, status_rate)} " \
                      "flinch_rate=#{format('%.3f', flinched.to_f / n)} flinch_expected=#{flinch_rate} " \
                      "flinch_ok=#{rate_ok?(flinched, n, flinch_rate)}")
      end
    end
    guard("defend") do
      (spec[:defend] || []).each do |entry|
        move_id, opts = entry.is_a?(Array) ? entry : [entry, {}]
        mold_breaker = !!(opts || {})[:mold_breaker]
        with, without, type = defend(spec, move_id, mold_breaker)
        log("DEFEND #{mechanic} move=#{move_id} type=#{type} mold_breaker=#{mold_breaker} " \
            "immune_with=#{with} immune_without=#{without}")
        obs(mechanic, "move=#{move_id} ability=true source=selftest mold_breaker=#{mold_breaker} immune=#{with}")
      end
    end
    guard("struck") do
      (spec[:struck] || []).each do |move_id, opts|
        opts ||= {}
        setup = opts[:setup] || {}
        n = opts[:n] || 400
        count = struck_rolls(spec, move_id, setup, n, opts[:status])
        Graphics.update if defined?(Graphics)
        rate = opts[:status_rate] || 0
        attacker_types = setup[:types] ? setup[:types].join('/') : "QMARKS"
        obs(mechanic, "move=#{move_id} ability=true source=selftest side=struck attacker_types=#{attacker_types} " \
                      "n=#{n} status=#{opts[:status] || 'NONE'} status_rate=#{format('%.3f', count.to_f / n)} " \
                      "status_expected=#{rate} status_ok=#{rate_ok?(count, n, rate)}")
      end
    end
    guard("taken") do
      (spec[:taken] || []).each do |move_id|
        with = damage(spec[:foe], [nil], spec[:user], move_id, neutral: !!spec[:neutral],
                      target_ability: spec[:ability])[0][0]
        none = damage(spec[:foe], [nil], spec[:user], move_id, neutral: !!spec[:neutral])[0][0]
        log("TAKEN #{mechanic} move=#{move_id} with=#{with} none=#{none} " \
            "ratio=#{format('%.3f', with.to_f / [none, 1].max)}")
      end
    end
    guard("keeps") do
      (spec[:keeps] || []).each do |kind, opts|
        status = (opts || {})[:status]
        with, none = [spec[:ability], nil].map { |a| keep_measure(spec, kind, status, a) }
        obs(mechanic, "case=keeps kind=#{kind} status=#{status} source=selftest with=#{with} none=#{none} " \
                      "changed=#{with != none}")
      end
    end
    guard("drain") do
      (spec[:drain] || []).each do |move_id, opts|
        opts ||= {}
        hp_lost = opts[:hp_lost] || 100
        before, after = drain(spec, move_id, hp_lost, opts[:target_ability])
        log("DRAIN #{mechanic} move=#{move_id} hp_lost=#{hp_lost} target_ability=#{opts[:target_ability] || 'none'} " \
            "hp=#{before}->#{after} change=#{after - before}")
      end
    end
    guard("ko") do
      (spec[:ko] || []).each do |opts|
        kos = opts[:kos] || 1
        hp_fraction = opts[:hp] || 0.5
        hp, hp_after, stages, stages_after = knockout(spec, kos, hp_fraction, opts[:stages] || {})
        moved = stages_after.select { |stat, n| stages[stat] != n }
                            .map { |stat, n| "#{stat}:#{stages[stat]}->#{n}" }
        log("KO #{mechanic} kos=#{kos} hp_fraction=#{hp_fraction} hp=#{hp}->#{hp_after} " \
            "stages=#{moved.empty? ? 'unchanged' : moved.join(',')}")
      end
    end
    guard("priority") do
      (spec[:priority] || []).each do |move_id, hp_fraction|
        hp_fraction ||= 1.0
        base, with = priority(spec, move_id, hp_fraction)
        log("PRIORITY #{mechanic} move=#{move_id} hp_fraction=#{hp_fraction} base=#{base} with=#{with}")
      end
    end
    guard("compare") do
      (spec[:compare] || []).each do |move_id, part, kind, setup|
        kind ||= :hit
        with, alone, none = [spec[:ability], part, nil].map { |a| measure(spec, kind, move_id, setup || {}, a) }
        obs(mechanic, "move=#{move_id || 'NONE'} ability=true source=selftest part=#{part} kind=#{kind} " \
                      "with=#{with} alone=#{alone} none=#{none} changed=#{with != none} " \
                      "result=#{with == alone ? 'MATCHES' : 'DIFFERS'}")
      end
    end
    guard("identity") do
      (spec[:identity] || []).each do |part|
        b, user, target = pair(spec, :TACKLE)
        user.ability = spec[:ability]
        obs(mechanic, "case=identity part=#{part} source=selftest has=#{user.hasActiveAbility?(part)} " \
                      "array=#{user.hasActiveAbility?([NON_HOLDER, part])} " \
                      "other=#{user.hasActiveAbility?(NON_HOLDER)}")
      end
    end
    guard("turn") do
      (spec[:turn] || []).each do |move_id, n|
        n ||= 50
        acted, cured = turns(spec, move_id, n)
        obs(mechanic, "case=turn move=#{move_id} source=selftest status=#{spec[:status]} n=#{n} " \
                      "acted=#{acted} cured=#{cured} result=#{acted == n && cured == 0 ? 'ACTS' : 'SKIPS'}")
      end
    end
    guard("status_damage") do
      (spec[:status_damage] || []).each do |move_id, ability|
        with, none = status_damage(spec, move_id, ability)
        obs(mechanic, "case=damage move=#{move_id} ability=#{ability || 'none'} source=selftest " \
                      "status=#{spec[:status]} with=#{with} none=#{none} ratio=#{format('%.3f', with.to_f / none)} " \
                      "result=#{with * 4 < none * 3 ? 'HALVED' : 'NORMAL'}")
      end
    end
    guard("chip") do
      (spec[:chip] || []).each do |ability|
        lost, max = chip(spec, ability)
        result = if lost == 0 then "NONE" elsif lost == max / 16 then "CHIP" else "WRONG" end
        obs(mechanic, "case=chip ability=#{ability || 'none'} source=selftest status=#{spec[:status]} " \
                      "lost=#{lost} max=#{max} expected=#{max / 16} result=#{result}")
      end
    end
    guard("cure") do
      (spec[:cure] || []).each do |move_id|
        obs(mechanic, "case=cure move=#{move_id} source=selftest status=#{spec[:status]} " \
                      "cured=#{cured_by?(spec, move_id)}")
      end
    end
    guard("immune") do
      (spec[:immune] || []).each do |target_types|
        can = inflictable?(spec, target_types)
        obs(mechanic, "case=immune target_types=#{target_types.join('/')} source=selftest " \
                      "status=#{spec[:status]} can_inflict=#{can} result=#{can ? 'AFFECTED' : 'IMMUNE'}")
      end
    end
    Graphics.update if defined?(Graphics)
    guard("fight") do
      next if (spec[:fight] || []).empty?
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
