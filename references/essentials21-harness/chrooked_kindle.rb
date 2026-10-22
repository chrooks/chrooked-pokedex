# chrooked:kindle
# ---------------------------------------------------------------------------
# Ruleset behavior "kindle": this Pokemon's Fire-type moves deal 50% more
# damage. Unconditional - unlike Blaze, there is no HP threshold.
#
# Essentials 21 Seam: the ability handler registry. The damage calc
# (Battle::Move#pbCalcDamageMultipliersAbilities) calls
# Battle::AbilityEffects.triggerDamageCalcFromUser for the attacker's own
# ability, and only when user.abilityActive?, so suppression (Gastro Acid,
# Neutralizing Gas) is the engine's job and this handler can never run for a
# Pokemon without Kindle. Shape copied from Nova's Blaze handler minus the HP
# check: an attack-stat multiplier, so tiny hits land a little under 1.5x
# (the formula's flat +2 is never scaled). The AI's damage estimate
# (Battle::AI::AIMove#rough_damage) calls the same registry, so the AI prices
# Kindle in too.
#
# Install: Data/Scripts/998_ChrookedMods/ (chrooked-pokedex apply does this).
# Essentials loads every .rb under Data/Scripts in name order, files before
# folders, so this runs after 011_Battle defines the registry and before
# 999_Main starts the game: it registers at load - no method overrides and no
# deferred install (the 16.2 ports needed both).
#
# HARNESS (log oracle, marker-gated): lines go to chrooked_load.log in the game
# folder only when chrooked-oracle.on exists there at boot, so played copies
# stay silent unless a proof run asks. Errors are always written. Essentials
# evals each script with a bare file name, so relative paths resolve from the
# game folder (PC and Kirin).
#     [chrooked:kindle] OBS move=<ID> type=<TYPE> kindle=true result=<BOOSTED|NORMAL>   a real hit
#     [chrooked:kindle] EST move=<ID> type=<TYPE> kindle=true result=<BOOSTED|NORMAL>   an AI estimate
# The harness scores OBS lines only.
#
# Verified 2026-10-22 in the Nova V3.0 lab copy (Essentials 21.99, mkxp-z,
# Ruby 3.1.3) by the headless self-test: Flamethrower 1.500x, Surf 1.000x,
# Ember at full HP 1.474x; Blaze unchanged at full HP.
# ---------------------------------------------------------------------------

unless defined?(ChrookedLog)
  module ChrookedLog
    ENABLED = File.exist?("chrooked-oracle.on")

    def self.line(msg)
      write(msg) if ENABLED
    end

    def self.error(msg)
      write(msg)
    end

    def self.write(msg)
      File.open("chrooked_load.log", "a") { |f| f.puts(msg) }
    rescue StandardError
      nil
    end
  end
end

begin
  chrooked_table = Battle::AbilityEffects::DamageCalcFromUser
  ChrookedLog.line("[chrooked:kindle] load ruby=#{RUBY_VERSION} platform=#{RUBY_PLATFORM} " \
                   "prior_handler=#{!chrooked_table[:KINDLE].nil?}")
  chrooked_table.add(:KINDLE,
    proc { |ability, user, target, move, mults, power, type|
      boosted = (type == :FIRE)
      mults[:attack_multiplier] *= 1.5 if boosted
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:kindle] #{tag} move=#{move.id} type=#{type || 'NONE'} kindle=true " \
                         "result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
  ChrookedLog.line("[chrooked:kindle] installed on Battle::AbilityEffects::DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:kindle] ERROR #{e.class}: #{e.message}")
end
