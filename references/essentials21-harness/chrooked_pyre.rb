# chrooked:pyre
# ---------------------------------------------------------------------------
# Ruleset behavior "pyre": this Pokemon's Ghost-type moves gain a 30% chance to burn
# the target.
#
# HAND-WRITTEN (mjolnir NV-13) to prove an on-hit status chance on its own before it
# becomes the hit_status template: Infernal Maw's burn rider without its boost or
# flinch. Seam Battle::AbilityEffects::OnDealingHit, which Nova fires for the user's
# ability only after a hit that dealt damage and missed any substitute; shaped like
# Nova's Poison Touch (no effect on a target unaffected by additional effects or
# holding Shield Dust; pbCanBurn? checked before the roll). The gate is the move's
# type as used (move.calcType), so a move turned Ghost counts.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:pyre] OBS move=<ID> type=<TYPE> ability=true hit=true can_inflict=<bool> inflicted=<bool>   after a Ghost hit
# The chance cases are measured by the lab self-test and logged on this mechanic's
# behalf with source=selftest.
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
  ChrookedLog.line("[chrooked:pyre] load prior_on_hit=#{!Battle::AbilityEffects::OnDealingHit[:PYRE].nil?}")
  Battle::AbilityEffects::OnDealingHit.add(:PYRE,
    proc { |ability, user, target, move, battle|
      next if move.calcType != :GHOST
      next if !target.affectedByAdditionalEffects?
      next if target.hasActiveAbility?(:SHIELDDUST) && !target.beingMoldBroken?
      can_inflict = target.pbCanBurn?(user, false)
      inflicted = false
      if can_inflict && battle.pbRandom(100) < 30
        battle.pbShowAbilitySplash(user)
        msg = nil
        if !Battle::Scene::USE_ABILITY_SPLASH
          msg = _INTL("{1}'s {2} burned {3}!", user.pbThis, user.abilityName, target.pbThis(true))
        end
        target.pbBurn(user, msg)
        battle.pbHideAbilitySplash(user)
        inflicted = true
      end
      ChrookedLog.line("[chrooked:pyre] OBS move=#{move.id} type=#{move.calcType} ability=true hit=true " \
                       "can_inflict=#{can_inflict} inflicted=#{inflicted}")
    }
  )
  ($chrooked_selftest_cases ||= {})["pyre"] = {
    ability: :PYRE, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    chance: [
      [:SHADOWBALL, {status: :BURN, status_rate: 0.3, flinch_rate: 0}],
      [:FLAMETHROWER, {status: :BURN, status_rate: 0, flinch_rate: 0}],
      [:SHADOWBALL, {status: :BURN, status_rate: 0, flinch_rate: 0, setup: {target_types: [:FIRE]}}]
    ],
    without: [],
    fight: [:SHADOWBALL, :FLAMETHROWER]
  }
  ChrookedLog.line("[chrooked:pyre] installed on OnDealingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:pyre] ERROR #{e.class}: #{e.message}")
end
