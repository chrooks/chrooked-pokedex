# chrooked:dualaegis
# ---------------------------------------------------------------------------
# Ruleset behavior "dualaegis": erects Reflect and Light Screen on the user's side on
# entry.
#
# HAND-WRITTEN (mjolnir NV-21). Seam Battle::AbilityEffects::OnSwitchIn. Each screen
# as its move sets it (5 turns, 8 with Light Clay, the moves' messages), and only
# where that screen is not up already, so a Reflect already up keeps its turns.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:dualaegis] OBS ability=true entry=true reflect=<turns> light_screen=<turns>   each entry
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
  ChrookedLog.line("[chrooked:dualaegis] load prior_handler=#{!Battle::AbilityEffects::OnSwitchIn[:DUALAEGIS].nil?}")
  Battle::AbilityEffects::OnSwitchIn.add(:DUALAEGIS,
    proc { |ability, battler, battle, switch_in|
      side  = battler.pbOwnSide
      turns = battler.hasActiveItem?(:LIGHTCLAY) ? 8 : 5
      screens = [[PBEffects::Reflect, :REFLECT], [PBEffects::LightScreen, :LIGHTSCREEN]]
      raising = screens.select { |effect, _| side.effects[effect] == 0 }
      if !raising.empty?
        battle.pbShowAbilitySplash(battler)
        raising.each do |effect, move|
          side.effects[effect] = turns
          if move == :REFLECT
            battle.pbDisplay(_INTL("{1} raised {2} Defense!", GameData::Move.get(move).name, battler.pbOfTeam(true)))
          else
            battle.pbDisplay(_INTL("{1} raised {2} Special Defense!", GameData::Move.get(move).name,
                                   battler.pbOfTeam(true)))
          end
        end
        battle.pbHideAbilitySplash(battler)
      end
      ChrookedLog.line("[chrooked:dualaegis] OBS ability=true entry=true " \
                       "reflect=#{side.effects[PBEffects::Reflect]} light_screen=#{side.effects[PBEffects::LightScreen]}")
    }
  )
  ($chrooked_selftest_cases ||= {})["dualaegis"] = {
    ability: :DUALAEGIS, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    entry: [["bare", {}], ["reflect_up", {reflect: 3}], ["light_clay", {item: :LIGHTCLAY}]],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:dualaegis] installed on OnSwitchIn")
rescue StandardError => e
  ChrookedLog.error("[chrooked:dualaegis] ERROR #{e.class}: #{e.message}")
end
