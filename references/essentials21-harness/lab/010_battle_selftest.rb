# chrooked dex lab: headless battle self-test for ported mechanics.
# LAB-ONLY - lives in the lab copy's Data/Scripts/998_ChrookedDexLab/ and is
# never deployed to a played copy.
#
# Runs only when chrooked-selftest.on exists in the game folder; its first word
# names the mechanic (e.g. "kindle"). Compile boots without the marker are
# unaffected. It runs at boot, after Game.initialize has loaded GameData and
# before Game.set_up_system (which can stop at a language prompt), uses only
# in-memory new-game values, never saves, and writes to chrooked_load.log.
# The runner (scripts/nova_selftest.ps1) kills the game once it logs DONE.
#
# The port's own OBS lines are marker-gated too: the runner also creates
# chrooked-oracle.on, and the harness scores those OBS lines against the spec.
#
# Two phases, both through Essentials' own battle code:
#   CALC  - damage-calc mechanics: Battle::Move#pbCalcDamage on the SAME
#           battlers and RNG seed with the ability, with none, and with a
#           control ability, so the effect is measured rather than assumed.
#   FIGHT - one AI-vs-AI battle in Battle::DebugSceneNoVisuals (the scene the
#           Battle Frontier simulator uses), so the handler fires in real flow.
module ChrookedSelfTest
  MARKER = "chrooked-selftest.on"
  LEVEL  = 50
  SEED   = 12_345

  # One entry per ported mechanic.
  #   ability  - the ability under test        control - a comparison ability
  #   user/foe - species for both phases       calc    - moves measured in CALC
  #   fight    - the ability holder's moves in FIGHT (the foe only knows Tackle)
  CASES = {
    "kindle" => {
      ability: :KINDLE, control: :BLAZE, user: :NUMEL, foe: :SNORLAX,
      calc: [:FLAMETHROWER, :SURF, :TACKLE, :EMBER],
      fight: [:EMBER, :FLAMETHROWER, :TACKLE]
    }
  }

  def self.log(msg)
    File.open("chrooked_load.log", "a") { |f| f.puts("[chrooked:selftest] #{msg}") }
  rescue StandardError
    nil
  end

  def self.guard(phase)
    yield
  rescue Exception => e   # report everything; the lab boot must survive
    log("ERROR #{phase} #{e.class}: #{e.message} @ #{(e.backtrace || [])[0, 3].join(' | ')}")
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
  def self.damage(user_species, abilities, foe_species, move_id)
    b = battle(mon(user_species, [move_id]), mon(foe_species, [:TACKLE]))
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    user   = b.battlers[0]
    target = b.battlers[1]
    target.ability = nil
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
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

  def self.run(mechanic)
    spec = CASES[mechanic]
    log("start mechanic=#{mechanic} ruby=#{RUBY_VERSION} platform=#{RUBY_PLATFORM}")
    if spec.nil?
      log("ERROR no case for '#{mechanic}' in CASES (known: #{CASES.keys.join(', ')})")
      return
    end
    log("data ability=#{GameData::Ability.exists?(spec[:ability])}")
    guard("setup") { SaveData.load_new_game_values }
    guard("calc") do
      (spec[:calc] || []).each do |move_id|
        (with, type, eff), (none, _, _), (control, _, _) =
          damage(spec[:user], [spec[:ability], nil, spec[:control]], spec[:foe], move_id)
        log("CALC move=#{move_id} type=#{type} eff=#{eff} with=#{with} none=#{none} " \
            "#{spec[:control]}=#{control} ratio=#{format('%.3f', with.to_f / none)}")
      end
    end
    guard("fight") do
      p1 = mon(spec[:user], spec[:fight])
      p1.ability = spec[:ability]
      b = battle(p1, mon(spec[:foe], [:TACKLE]))
      outcome = b.pbStartBattle
      log("FIGHT outcome=#{outcome} turns=#{b.turnCount}")
    end
  ensure
    log("DONE")
  end
end

module Game
  class << self
    unless method_defined?(:chrooked_selftest_set_up_system)
      alias_method :chrooked_selftest_set_up_system, :set_up_system
      def set_up_system
        if File.exist?(ChrookedSelfTest::MARKER)
          mechanic = File.read(ChrookedSelfTest::MARKER).split.first.to_s.downcase
          ChrookedSelfTest.guard("run") { ChrookedSelfTest.run(mechanic) }
        end
        chrooked_selftest_set_up_system
      end
    end
  end
end
