# chrooked:mountaineer
# ---------------------------------------------------------------------------
# Ruleset behavior "mountaineer": Rock-type moves do not affect it, and Stealth Rock
# deals it no damage on entry.
#
# HAND-WRITTEN (mjolnir NV-26).
#   - MoveImmunity: a Rock move aimed at the holder fails, as the generated
#     type_immunity ports do (Mold Breaker skips it; never the holder's own move).
#   - Battle#pbEntryHazards hides Stealth Rock from the holder for its entry; Spikes,
#     Toxic Spikes and Sticky Web still apply.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:mountaineer] OBS move=<ID> type=<TYPE> ability=true result=<IMMUNE|NORMAL>   each immunity check (EST from the AI)
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
  ChrookedLog.line("[chrooked:mountaineer] load prior_handler=" \
                   "#{!Battle::AbilityEffects::MoveImmunity[:MOUNTAINEER].nil?}")
  Battle::AbilityEffects::MoveImmunity.add(:MOUNTAINEER,
    proc { |ability, user, target, move, type, battle, show_message|
      immune = type == :ROCK && user.index != target.index
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s =~ /AI[ _]?Move/ } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:mountaineer] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \
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
  Battle.class_eval do
    unless method_defined?(:chrooked_mountaineer_pbEntryHazards)
      alias_method :chrooked_mountaineer_pbEntryHazards, :pbEntryHazards
      def pbEntryHazards(battler)
        side = battler.pbOwnSide
        hide = side.effects[PBEffects::StealthRock] && battler.hasActiveAbility?(:MOUNTAINEER)
        side.effects[PBEffects::StealthRock] = false if hide
        chrooked_mountaineer_pbEntryHazards(battler)
      ensure
        side.effects[PBEffects::StealthRock] = true if hide
      end
    end
  end
  ($chrooked_selftest_cases ||= {})["mountaineer"] = {
    ability: :MOUNTAINEER, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    defend: [:ROCKSLIDE, :EARTHQUAKE],
    checks: [
      ["stealth_rock", ->(t, spec) {
        with, none = [spec[:ability], nil].map do |a|
          b, holder, _foe = t.pair(spec, :TACKLE)
          holder.ability = a
          holder.pbOwnSide.effects[PBEffects::StealthRock] = true
          hp = holder.hp
          b.pbEntryHazards(holder)
          [holder.hp - hp, holder.pbOwnSide.effects[PBEffects::StealthRock]]
        end
        "rock_with=#{with[0]} rock_none=#{none[0]} still_set=#{with[1]} spared=#{with[0] == 0 && none[0] < 0}"
      }]
    ],
    without: [],
    fight: []
  }
  ChrookedLog.line("[chrooked:mountaineer] installed on MoveImmunity and Battle#pbEntryHazards")
rescue StandardError => e
  ChrookedLog.error("[chrooked:mountaineer] ERROR #{e.class}: #{e.message}")
end
