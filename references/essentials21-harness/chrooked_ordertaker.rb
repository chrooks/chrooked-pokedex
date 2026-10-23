# chrooked:ordertaker
# ---------------------------------------------------------------------------
# Ruleset behavior "ordertaker": on entry, if a healthy Tatsugiri waits in its own
# trainer's party, Attack, Defense, Sp. Atk, Sp. Def and Speed each rise one stage.
#
# HAND-WRITTEN (mjolnir NV-28). Seam Battle::AbilityEffects::OnSwitchIn. The party is
# the holder's own trainer's (pbTeamIndexRangeFromBattlerIndex), so an ally trainer's
# Tatsugiri does not count; any Tatsugiri form, not fainted, not an egg, not the holder.
# When none can rise (all +6), nothing shows. Otherwise the splash, "<holder> is taking
# orders from <Tatsugiri>!", then each raise through pbRaiseStatStage, so Contrary,
# Simple and the cap behave as for any self-boost.
#
# The AI (Chris, 2026-10-23): Nova's switch scorer (Battle::AI#rate_replacement_pokemon)
# rates a party Pokemon by hazards, the foes' last moves and its own moves, and models
# no entry ability. For an Order Taker candidate whose trainer has a healthy Tatsugiri
# besides it, the wrapper adds 5 per stat, 25 for all five: the scale Nova's own move
# scoring gives a +1 (10 times the stage's 0.5 gain, 8 to 12 for an attacking stat).
# It does not model Contrary or Simple, or value keeping Tatsugiri alive.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:ordertaker] OBS ability=true entry=true ordered=<bool>   each entry
# ---------------------------------------------------------------------------

unless defined?(ChrookedLog)
  module ChrookedLog
    # Resolved once, at load, while the working directory is the game folder.
    LOG     = File.expand_path("chrooked_load.log")
    ENABLED = File.exist?(File.expand_path("chrooked-oracle.on"))

    def self.line(msg)
      write(msg) if ENABLED
    end

    def self.error(msg)
      write(msg)
    end

    def self.write(msg)
      File.open(LOG, "a") { |f| f.puts(msg) }
    rescue StandardError
      nil
    end
  end
end

begin
  ChrookedLog.line("[chrooked:ordertaker] load prior_handler=" \
                   "#{!Battle::AbilityEffects::OnSwitchIn[:ORDERTAKER].nil?}")
  chrooked_ordertaker_stats = [:ATTACK, :DEFENSE, :SPECIAL_ATTACK, :SPECIAL_DEFENSE, :SPEED]
  # The healthy Tatsugiri, besides `holder`, in the party of the trainer at idx_battler.
  chrooked_ordertaker_chief = lambda do |battle, idx_battler, holder|
    first, last = battle.pbTeamIndexRangeFromBattlerIndex(idx_battler)
    party = battle.pbParty(idx_battler)
    (first...last).map { |i| party[i] }.find do |pkmn|
      pkmn && !pkmn.equal?(holder) && pkmn.isSpecies?(:TATSUGIRI) && pkmn.able?
    end
  end
  Battle::AbilityEffects::OnSwitchIn.add(:ORDERTAKER,
    proc { |ability, battler, battle, switch_in|
      chief = chrooked_ordertaker_chief.call(battle, battler.index, battler.pokemon)
      raisable = chief ? chrooked_ordertaker_stats.select { |s| battler.pbCanRaiseStatStage?(s, battler) } : []
      ordered = !raisable.empty?
      if ordered
        battle.pbShowAbilitySplash(battler)
        battle.pbDisplay(_INTL("{1} is taking orders from {2}!", battler.pbThis, chief.name))
        raisable.each { |s| battler.pbRaiseStatStage(s, 1, battler) }
        battle.pbHideAbilitySplash(battler)
      end
      ChrookedLog.line("[chrooked:ordertaker] OBS ability=true entry=true ordered=#{ordered}")
    }
  )
  Battle::AI.class_eval do
    unless method_defined?(:chrooked_ordertaker_rate_replacement_pokemon)
      alias_method :chrooked_ordertaker_rate_replacement_pokemon, :rate_replacement_pokemon
      define_method(:rate_replacement_pokemon) do |idxBattler, pkmn, score|
        score = chrooked_ordertaker_rate_replacement_pokemon(idxBattler, pkmn, score)
        if pkmn.ability_id == :ORDERTAKER && chrooked_ordertaker_chief.call(@battle, idxBattler, pkmn)
          score += 5 * chrooked_ordertaker_stats.length   # a +1 in each, on Nova's own scale
        end
        score
      end
    end
  end
  # The holder leads a party with `reserve` behind it; it enters (stages preset first).
  chrooked_ordertaker_entry = lambda do |t, spec, reserve, stages: 0, fainted: false|
    holder = t.mon(spec[:user], [:TACKLE])
    holder.ability = spec[:ability]
    back = reserve ? t.mon(reserve, [:TACKLE]) : nil
    back.hp = 0 if back && fainted
    party1 = [holder, back].compact
    foe = t.mon(spec[:foe], [:TACKLE])
    tt = GameData::TrainerType.keys.first
    t1 = NPCTrainer.new("LabA", tt)
    t1.party = party1
    t2 = NPCTrainer.new("LabB", tt)
    t2.party = [foe]
    b = Battle.new(Battle::DebugSceneNoVisuals.new, party1, [foe], t1, t2)
    b.debug          = true
    b.controlPlayer  = true
    b.internalBattle = false
    b.pbCreateBattler(0, holder, 0)
    b.pbCreateBattler(1, foe, 0)
    battler = b.battlers[0]
    chrooked_ordertaker_stats.each { |s| battler.stages[s] = stages }
    Battle::AbilityEffects.triggerOnSwitchIn(battler.ability, battler, b, true)
    "stages=#{chrooked_ordertaker_stats.map { |s| battler.stages[s] }.join('/')}"
  end
  ($chrooked_selftest_cases ||= {})["ordertaker"] = {
    ability: :ORDERTAKER, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["tatsugiri", ->(t, spec) { chrooked_ordertaker_entry.call(t, spec, :TATSUGIRI) }],
      ["fainted", ->(t, spec) { chrooked_ordertaker_entry.call(t, spec, :TATSUGIRI, fainted: true) }],
      ["none", ->(t, spec) { chrooked_ordertaker_entry.call(t, spec, :PIKACHU) }],
      # A multi battle: the holder's trainer has only it; the ally trainer has a Tatsugiri.
      ["multi", ->(t, spec) {
        holder = t.mon(spec[:user], [:TACKLE])
        holder.ability = spec[:ability]
        ally, tatsugiri = t.mon(:PIKACHU, [:TACKLE]), t.mon(:TATSUGIRI, [:TACKLE])
        foes = [t.mon(spec[:foe], [:TACKLE]), t.mon(spec[:foe], [:TACKLE])]
        tt = GameData::TrainerType.keys.first
        t1 = NPCTrainer.new("LabA", tt)
        t1.party = [holder]
        t3 = NPCTrainer.new("LabC", tt)
        t3.party = [ally, tatsugiri]
        t2 = NPCTrainer.new("LabB", tt)
        t2.party = foes
        b = Battle.new(Battle::DebugSceneNoVisuals.new, [holder, ally, tatsugiri], foes, [t1, t3], t2)
        b.debug          = true
        b.controlPlayer  = true
        b.internalBattle = false
        b.party1starts = [0, 1]
        b.setBattleMode("double")
        b.pbCreateBattler(0, holder, 0)
        b.pbCreateBattler(2, ally, 1)
        b.pbCreateBattler(1, foes[0], 0)
        b.pbCreateBattler(3, foes[1], 1)
        battler = b.battlers[0]
        Battle::AbilityEffects.triggerOnSwitchIn(battler.ability, battler, b, true)
        "stages=#{chrooked_ordertaker_stats.map { |s| battler.stages[s] }.join('/')} " \
        "own_team=#{b.pbTeamLengthFromBattlerIndex(0)}"
      }],
      ["maxed", ->(t, spec) { chrooked_ordertaker_entry.call(t, spec, :TATSUGIRI, stages: 6) }],
      # The AI rates switching in the holder (in the back) with a Tatsugiri beside it,
      # and with the Tatsugiri fainted.
      ["ai_switch", ->(t, spec) {
        lead, holder, tatsugiri = t.mon(spec[:foe], [:TACKLE]), t.mon(spec[:user], [:TACKLE]), t.mon(:TATSUGIRI, [:TACKLE])
        holder.ability = spec[:ability]
        foe = t.mon(spec[:foe], [:TACKLE])
        tt = GameData::TrainerType.keys.first
        t1 = NPCTrainer.new("LabA", tt)
        t1.party = [lead, holder, tatsugiri]
        t2 = NPCTrainer.new("LabB", tt)
        t2.party = [foe]
        b = Battle.new(Battle::DebugSceneNoVisuals.new, [lead, holder, tatsugiri], [foe], t1, t2)
        b.debug          = true
        b.controlPlayer  = true
        b.internalBattle = false
        b.pbCreateBattler(0, lead, 0)
        b.pbCreateBattler(1, foe, 0)
        ai = b.instance_variable_get(:@battleAI)
        ai.create_ai_objects
        ai.set_up(0)
        with_chief = ai.rate_replacement_pokemon(0, holder, 100)
        tatsugiri.hp = 0
        without = ai.rate_replacement_pokemon(0, holder, 100)
        "score=#{with_chief} score_without_tatsugiri=#{without} bonus=#{(with_chief - without).round}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:ordertaker] installed on OnSwitchIn")
rescue StandardError => e
  ChrookedLog.error("[chrooked:ordertaker] ERROR #{e.class}: #{e.message}")
end
