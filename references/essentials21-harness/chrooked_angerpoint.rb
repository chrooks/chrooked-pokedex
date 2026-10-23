# chrooked:angerpoint
# ---------------------------------------------------------------------------
# Ruleset behavior "angerpoint": a critical hit maxes the holder's higher attacking
# stat: Attack (vanilla) when its base Attack is at least its base Sp. Atk, otherwise
# Sp. Atk. Only that stat, never both; nothing if it is already at +6.
#
# HAND-WRITTEN (mjolnir NV-30). Seam Battle::AbilityEffects::OnBeingHit, Nova's own
# Anger Point handler with the stat chosen by the species' base stats (so a species
# always picks the same one): the critical hit, the raise to the maximum, the stage
# record, the StatUp animation and Nova's message.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:angerpoint] OBS ability=true critical=<bool> stat=<STAT>   each damaging hit taken
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
  ChrookedLog.line("[chrooked:angerpoint] load prior_handler=#{!Battle::AbilityEffects::OnBeingHit[:ANGERPOINT].nil?}")
  Battle::AbilityEffects::OnBeingHit.add(:ANGERPOINT,
    proc { |ability, user, target, move, battle|
      base = target.pokemon.baseStats
      stat = base[:SPECIAL_ATTACK] > base[:ATTACK] ? :SPECIAL_ATTACK : :ATTACK
      critical = target.damageState.critical
      ChrookedLog.line("[chrooked:angerpoint] OBS ability=true critical=#{critical} stat=#{stat}")
      next if !critical
      next if !target.pbCanRaiseStatStage?(stat, target)
      battle.pbShowAbilitySplash(target)
      target.stagesChangeRecord[0][stat] ||= 0
      target.stagesChangeRecord[0][stat] += Battle::Battler::STAT_STAGE_MAXIMUM - target.stages[stat]
      target.statsRaisedThisRound = true
      target.stages[stat] = Battle::Battler::STAT_STAGE_MAXIMUM
      battle.pbCommonAnimation("StatUp", target)
      if Battle::Scene::USE_ABILITY_SPLASH
        battle.pbDisplay(_INTL("{1} maxed its {2}!", target.pbThis, GameData::Stat.get(stat).name))
      else
        battle.pbDisplay(_INTL("{1}'s {2} maxed its {3}!", target.pbThis, target.abilityName,
                               GameData::Stat.get(stat).name))
      end
      battle.pbHideAbilitySplash(target)
    }
  )
  # A species with the ability takes a hit (critical or not; Sp. Atk preset first).
  chrooked_angerpoint_hit = lambda do |t, spec, species, critical, spatk_stage = 0|
    b = t.battle(t.mon(spec[:foe], [:TACKLE]), t.mon(species, [:TACKLE]))
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    foe, holder = b.battlers[0], b.battlers[1]
    holder.ability = spec[:ability]
    holder.stages[:SPECIAL_ATTACK] = spatk_stage
    holder.damageState.reset
    holder.damageState.critical = critical
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:TACKLE))
    Battle::AbilityEffects.triggerOnBeingHit(holder.ability, foe, holder, move, b)
    "attack=#{holder.stages[:ATTACK]} spatk=#{holder.stages[:SPECIAL_ATTACK]}"
  end
  ($chrooked_selftest_cases ||= {})["angerpoint"] = {
    ability: :ANGERPOINT, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["camerupt", ->(t, spec) { chrooked_angerpoint_hit.call(t, spec, :CAMERUPT, true) }],
      ["primeape", ->(t, spec) { chrooked_angerpoint_hit.call(t, spec, :PRIMEAPE, true) }],
      ["tie", ->(t, spec) { chrooked_angerpoint_hit.call(t, spec, :MEW, true) }],
      ["spatk_maxed", ->(t, spec) { chrooked_angerpoint_hit.call(t, spec, :CAMERUPT, true, 6) }],
      ["not_critical", ->(t, spec) { chrooked_angerpoint_hit.call(t, spec, :CAMERUPT, false) }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:angerpoint] installed on OnBeingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:angerpoint] ERROR #{e.class}: #{e.message}")
end
