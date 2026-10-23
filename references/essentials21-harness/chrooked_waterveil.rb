# chrooked:waterveil
# ---------------------------------------------------------------------------
# Ruleset behavior "waterveil": cannot be burned (vanilla, kept); on entry, surrounds
# itself with Aqua Ring.
#
# HAND-WRITTEN (mjolnir NV-21). Seam Battle::AbilityEffects::OnSwitchIn, beside Nova's
# own Water Veil handlers (StatusImmunity, StatusCure), which stay. The ring is the move
# Aqua Ring's own effect and message, set only when not already on (Baton Pass), so
# the move Aqua Ring then fails as it does on a ringed Pokemon.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:waterveil] OBS ability=true entry=true aqua_ring_before=<bool> set=<bool>   each entry
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
  ChrookedLog.line("[chrooked:waterveil] load prior_handler=#{!Battle::AbilityEffects::OnSwitchIn[:WATERVEIL].nil?}")
  Battle::AbilityEffects::OnSwitchIn.add(:WATERVEIL,
    proc { |ability, battler, battle, switch_in|
      before = battler.effects[PBEffects::AquaRing]
      if !before
        battle.pbShowAbilitySplash(battler)
        battler.effects[PBEffects::AquaRing] = true
        battle.pbDisplay(_INTL("{1} surrounded itself with a veil of water!", battler.pbThis))
        battle.pbHideAbilitySplash(battler)
      end
      ChrookedLog.line("[chrooked:waterveil] OBS ability=true entry=true aqua_ring_before=#{before} set=#{!before}")
    }
  )
  ($chrooked_selftest_cases ||= {})["waterveil"] = {
    ability: :WATERVEIL, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    entry: [["fresh", {}], ["passed", {aqua_ring: true}], ["reentry", {}]],
    keeps: [[:status, {status: :BURN}]],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:waterveil] installed on OnSwitchIn")
rescue StandardError => e
  ChrookedLog.error("[chrooked:waterveil] ERROR #{e.class}: #{e.message}")
end
