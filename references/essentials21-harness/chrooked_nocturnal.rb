# chrooked:nocturnal
# ---------------------------------------------------------------------------
# Ruleset behavior "nocturnal": immune to Dark-type moves.
#
# HAND-WRITTEN (mjolnir NV-13) to prove a type immunity before it becomes the
# type_immunity template. Seam Battle::AbilityEffects::MoveImmunity, which Nova asks
# from pbImmunityByAbility for every move aimed at the holder (status moves such as
# Taunt included), only while the holder's ability is active and not bypassed by
# Mold Breaker, with the move's type as used. Shaped like Nova's Soundproof (the
# splash and "It doesn't affect..."), and like its type immunities (Volt Absorb's
# pbMoveImmunityHealingAbility) it never blocks a move the holder uses on itself.
# Blocking here means no damage and no secondary effect: Knock Off keeps the item.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:nocturnal] OBS move=<ID> type=<TYPE> ability=true result=<IMMUNE|NORMAL>   a move aimed at the holder
#     [chrooked:nocturnal] EST ...   an AI estimate, never scored
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
  ChrookedLog.line("[chrooked:nocturnal] load prior_handler=#{!Battle::AbilityEffects::MoveImmunity[:NOCTURNAL].nil?}")
  Battle::AbilityEffects::MoveImmunity.add(:NOCTURNAL,
    proc { |ability, user, target, move, type, battle, show_message|
      immune = type == :DARK && user.index != target.index
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s =~ /AI[ _]?Move/ } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:nocturnal] #{tag} move=#{move.id} type=#{type || 'NONE'} ability=true " \
                         "result=#{immune ? 'IMMUNE' : 'NORMAL'}")
      end
      next false if !immune
      if show_message
        battle.pbShowAbilitySplash(target)
        if Battle::Scene::USE_ABILITY_SPLASH
          battle.pbDisplay(_INTL("It doesn't affect {1}...", target.pbThis(true)))
        else
          battle.pbDisplay(_INTL("{1}'s {2} made {3} ineffective!", target.pbThis, target.abilityName, move.name))
        end
        battle.pbHideAbilitySplash(target)
      end
      next true
    }
  )
  ($chrooked_selftest_cases ||= {})["nocturnal"] = {
    ability: :NOCTURNAL, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    defend: [:KNOCKOFF, :SHADOWBALL, :TAUNT],
    without: [],
    fight: []
  }
  ChrookedLog.line("[chrooked:nocturnal] installed on MoveImmunity")
rescue StandardError => e
  ChrookedLog.error("[chrooked:nocturnal] ERROR #{e.class}: #{e.message}")
end
