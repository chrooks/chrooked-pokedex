# chrooked:carnivore
# ---------------------------------------------------------------------------
# Ruleset behavior "carnivore": knocking out a foe heals the user 1/4 of its max HP.
#
# HAND-WRITTEN (mjolnir NV-14) to prove an effect on knocking out a foe before it
# becomes the ko_effect template. Seam Battle::AbilityEffects::OnEndOfUsingMove,
# which Nova fires for the user's ability after each move it uses, with the move's
# targets; shaped like Nova's Moxie (nothing if the knockout ended the battle; a
# target counts when its damage state says it fainted). The heal is Ice Body's:
# only while the user can heal (not fainted, below full HP, no Heal Block), 1/4 of
# max HP, with Nova's own "HP was restored" message. One heal however many foes
# fell, as the spec says.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:carnivore] OBS move=<ID> ability=true kos=<n> hp_full=<bool> change=<n> result=<HEALED|NONE>   after each move the holder uses
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
  ChrookedLog.line("[chrooked:carnivore] load prior_handler=" \
                   "#{!Battle::AbilityEffects::OnEndOfUsingMove[:CARNIVORE].nil?}")
  Battle::AbilityEffects::OnEndOfUsingMove.add(:CARNIVORE,
    proc { |ability, user, targets, move, battle|
      kos     = targets.count { |b| b.damageState.fainted }
      hp_full = user.hp >= user.totalhp
      before  = user.hp
      if kos > 0 && !battle.pbAllFainted?(user.idxOpposingSide) && user.canHeal?
        battle.pbShowAbilitySplash(user)
        user.pbRecoverHP(user.totalhp / 4)
        if Battle::Scene::USE_ABILITY_SPLASH
          battle.pbDisplay(_INTL("{1}'s HP was restored.", user.pbThis))
        else
          battle.pbDisplay(_INTL("{1} {2} restored its HP.", user.pbOfThis, user.abilityName))
        end
        battle.pbHideAbilitySplash(user)
      end
      change = user.hp - before
      ChrookedLog.line("[chrooked:carnivore] OBS move=#{move.id} ability=true kos=#{kos} hp_full=#{hp_full} " \
                       "change=#{change} result=#{change > 0 ? 'HEALED' : 'NONE'}")
    }
  )
  ($chrooked_selftest_cases ||= {})["carnivore"] = {
    ability: :CARNIVORE, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    ko: [{kos: 1, hp: 0.5}, {kos: 0, hp: 0.5}, {kos: 1, hp: 1.0}],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:carnivore] installed on OnEndOfUsingMove")
rescue StandardError => e
  ChrookedLog.error("[chrooked:carnivore] ERROR #{e.class}: #{e.message}")
end
