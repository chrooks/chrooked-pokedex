# chrooked:pastelveil
# ---------------------------------------------------------------------------
# Ruleset behavior "pastelveil": the game's own Pastel Veil (it and its allies cannot be
# poisoned), and Poison-type moves do not affect it, its allies not included.
#
# HAND-WRITTEN (mjolnir NV-29). Nova's Pastel Veil keeps its status handlers; this adds
# a MoveImmunity handler, the generated type_immunity ports' code for Poison: a Poison
# move aimed at the holder fails ("It doesn't affect..."), status moves included,
# unless Mold Breaker skips it; never the holder's own move.
#
# It also mends Nova's own OnSwitchIn handler, which cures poison on entry: its first
# line reads `status != :POISON & allAllies.none? {...}`, and `&` binds before `!=`,
# so every Pastel Veil entry raised NoMethodError (Symbol#&). The handler is Nova's
# with `&&` there, as Essentials 21 writes it.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:pastelveil] OBS move=<ID> type=<TYPE> ability=true result=<IMMUNE|NORMAL>   each immunity check (EST from the AI)
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
  ChrookedLog.line("[chrooked:pastelveil] load prior_handler=" \
                   "#{!Battle::AbilityEffects::MoveImmunity[:PASTELVEIL].nil?} " \
                   "status_handler=#{!Battle::AbilityEffects::StatusImmunity[:PASTELVEIL].nil?}")
  Battle::AbilityEffects::MoveImmunity.add(:PASTELVEIL,
    proc { |ability, user, target, move, type, battle, show_message|
      immune = type == :POISON && user.index != target.index
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s =~ /AI[ _]?Move/ } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:pastelveil] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \
                         "result=#{immune ? 'IMMUNE' : 'NORMAL'}")
      end
      next false if !immune
      if show_message
        battle.pbShowAbilitySplash(target)
        if Battle::Scene::USE_ABILITY_SPLASH
          battle.pbDisplay(_INTL("It doesn't affect {1}...", target.pbThis(true)))
        else
          battle.pbDisplay(_INTL("{1} {2} made {3} ineffective!",
                                 target.pbOfThis, target.abilityName, move.name))
        end
        battle.pbHideAbilitySplash(target)
      end
      next true
    }
  )
  Battle::AbilityEffects::OnSwitchIn.add(:PASTELVEIL,
    proc { |ability, battler, battle, switch_in|
      next if battler.status != :POISON && battler.allAllies.none? { |ally| ally.status == :POISON }
      battle.pbShowAbilitySplash(battler)
      if battler.status == :POISON
        battler.pbCureStatus(Battle::Scene::USE_ABILITY_SPLASH)
        if !Battle::Scene::USE_ABILITY_SPLASH
          battler.battle.pbDisplay(_INTL("{1} {2} cured its poisoning!", battler.pbOfThis, battler.abilityName))
        end
      end
      battler.allAllies.each do |ally|
        next if ally.status != :POISON
        ally.pbCureStatus(Battle::Scene::USE_ABILITY_SPLASH)
        if !Battle::Scene::USE_ABILITY_SPLASH
          battle.pbDisplay(_INTL("{1} {2} cured {3} poisoning!",
                                 battler.pbOfThis, battler.abilityName, ally.pbOfThis(true)))
        end
      end
      battle.pbHideAbilitySplash(battler)
    }
  )
  ($chrooked_selftest_cases ||= {})["pastelveil"] = {
    ability: :PASTELVEIL, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    defend: [:SLUDGEBOMB, :TOXIC],
    checks: [
      # Doubles: the foe's Sludge Bomb at the holder's ally, who can still not be poisoned.
      ["ally", ->(t, spec) {
        b, holder, ally, foe, _foe2 = t.doubles(spec)
        holder.ability = spec[:ability]
        move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:SLUDGEBOMB))
        move.calcType = move.pbCalcType(foe)
        "ally_immune=#{!!move.pbImmunityByAbility(foe, ally, false)} " \
        "ally_can_be_poisoned=#{ally.pbCanPoison?(foe, false)}"
      }],
      # Beside the test cases: Nova's entry cure, which raised before the mend.
      ["entry_cure", ->(t, spec) {
        b, holder, ally, _foe, _foe2 = t.doubles(spec)
        holder.ability = spec[:ability]
        holder.status = :POISON
        ally.status = :POISON
        Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
        "holder_status=#{holder.status} ally_status=#{ally.status}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:pastelveil] installed on MoveImmunity")
rescue StandardError => e
  ChrookedLog.error("[chrooked:pastelveil] ERROR #{e.class}: #{e.message}")
end
