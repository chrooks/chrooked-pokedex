# chrooked:dilation
# ---------------------------------------------------------------------------
# Ruleset behavior "dilation": on entry, sets Trick Room for five turns; ends it if
# already active.
#
# HAND-WRITTEN (mjolnir NV-21). Seam Battle::AbilityEffects::OnSwitchIn, as Drought's
# entry. The toggle is the move Trick Room's own (StartSlowerBattlersActFirst): 5
# turns when off, 0 when on, with its messages, under the ability's splash.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:dilation] OBS ability=true entry=true trick_room=<before>-><after>   each entry
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
  ChrookedLog.line("[chrooked:dilation] load prior_handler=#{!Battle::AbilityEffects::OnSwitchIn[:DILATION].nil?}")
  Battle::AbilityEffects::OnSwitchIn.add(:DILATION,
    proc { |ability, battler, battle, switch_in|
      before = battle.field.effects[PBEffects::TrickRoom]
      battle.pbShowAbilitySplash(battler)
      if before > 0
        battle.field.effects[PBEffects::TrickRoom] = 0
        battle.pbDisplay(_INTL("{1} reverted the dimensions!", battler.pbThis))
      else
        battle.field.effects[PBEffects::TrickRoom] = 5
        battle.pbDisplay(_INTL("{1} twisted the dimensions!", battler.pbThis))
      end
      battle.pbHideAbilitySplash(battler)
      ChrookedLog.line("[chrooked:dilation] OBS ability=true entry=true " \
                       "trick_room=#{before}->#{battle.field.effects[PBEffects::TrickRoom]}")
    }
  )
  ($chrooked_selftest_cases ||= {})["dilation"] = {
    ability: :DILATION, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    entry: [["calm", {}], ["twisted", {trick_room: 3}]],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:dilation] installed on OnSwitchIn")
rescue StandardError => e
  ChrookedLog.error("[chrooked:dilation] ERROR #{e.class}: #{e.message}")
end
