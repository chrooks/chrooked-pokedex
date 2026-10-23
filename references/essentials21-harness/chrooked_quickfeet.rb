# chrooked:quickfeet
# ---------------------------------------------------------------------------
# Ruleset behavior "quickfeet": Speed 1.5x while statused with no paralysis drop (the
# game's own Quick Feet, kept), and burn and frostbite do not lower its damage, as Guts.
#
# HAND-WRITTEN (mjolnir NV-24). The Speed half stays Nova's SpeedCalc handler and
# pbSpeed's own Quick Feet test. Burn's halving lives in
# Battle::Move#pbCalcDamageMultipliersStatusConditions, which spares only Guts, so this
# wrapper undoes it for a burned holder's physical move. Frostbite's halving already
# spares Quick Feet (chrooked_frostbite.rb), and a swapped stat's burn rule does too
# (templates.py stat_swap), so none of them halves twice or undoes twice.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:quickfeet] OBS move=<ID> ability=true status=BURN spared=<bool>   each burned damage calc
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
  ChrookedLog.line("[chrooked:quickfeet] load prior_handler=" \
                   "#{!Battle::AbilityEffects::SpeedCalc[:QUICKFEET].nil?}")
  Battle::Move.class_eval do
    unless method_defined?(:chrooked_quickfeet_pbCalcDamageMultipliersStatusConditions)
      alias_method :chrooked_quickfeet_pbCalcDamageMultipliersStatusConditions, :pbCalcDamageMultipliersStatusConditions
      def pbCalcDamageMultipliersStatusConditions(user, target, numTargets, type, baseDmg, multipliers)
        chrooked_quickfeet_pbCalcDamageMultipliersStatusConditions(user, target, numTargets, type, baseDmg, multipliers)
        return if user.status != :BURN || !user.hasActiveAbility?(:QUICKFEET)
        # Nova halved it unless the holder has Guts; Quick Feet spares it the same way.
        spared = physicalMove? && damageReducedByBurn? && !user.hasActiveAbility?(:GUTS)
        multipliers[:final_damage_multiplier] *= 2 if spared
        ChrookedLog.line("[chrooked:quickfeet] OBS move=#{@id} ability=true status=BURN spared=#{spared}")
      end
    end
  end
  ($chrooked_selftest_cases ||= {})["quickfeet"] = {
    ability: :QUICKFEET, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    status_hit: [["burned_physical", :TACKLE, :BURN], ["frostbitten_special", :SWIFT, :FROZEN]],
    speed: [["paralyzed", {status: :PARALYSIS}]],
    without: [],
    fight: [:TACKLE, :SWIFT]
  }
  ChrookedLog.line("[chrooked:quickfeet] installed on Battle::Move#pbCalcDamageMultipliersStatusConditions")
rescue StandardError => e
  ChrookedLog.error("[chrooked:quickfeet] ERROR #{e.class}: #{e.message}")
end
