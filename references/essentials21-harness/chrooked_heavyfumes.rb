# chrooked:heavyfumes
# ---------------------------------------------------------------------------
# Ruleset behavior "heavyfumes": every opposing Pokemon on the field loses 1/16 of its
# max HP at the end of each turn.
#
# HAND-WRITTEN (mjolnir NV-21). Seam Battle::AbilityEffects::EndOfRoundEffect, Nova's
# Bad Dreams shape: each foe near the holder, unless it is Poison- or Grass-type or
# takes no indirect damage (Magic Guard), loses floor(max HP / 16), at least 1
# (pbTakeEffectDamage, which a Substitute does not stop).
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:heavyfumes] OBS ability=true eor=true foe=<index> immune=<bool>   each foe, each end of round
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
  ChrookedLog.line("[chrooked:heavyfumes] load prior_handler=" \
                   "#{!Battle::AbilityEffects::EndOfRoundEffect[:HEAVYFUMES].nil?}")
  Battle::AbilityEffects::EndOfRoundEffect.add(:HEAVYFUMES,
    proc { |ability, battler, battle|
      showing = false
      battle.allOtherSideBattlers(battler.index).each do |b|
        next if !b.near?(battler)
        immune = b.pbHasType?(:POISON) || b.pbHasType?(:GRASS) || !b.takesIndirectDamage?
        ChrookedLog.line("[chrooked:heavyfumes] OBS ability=true eor=true foe=#{b.index} immune=#{immune}")
        next if immune
        battle.pbShowAbilitySplash(battler) if !showing
        showing = true
        b.pbTakeEffectDamage([b.totalhp / 16, 1].max) do |hp_lost|
          battle.pbDisplay(_INTL("{1} is choking on the fumes!", b.pbThis))
        end
      end
      battle.pbHideAbilitySplash(battler) if showing
    }
  )
  ($chrooked_selftest_cases ||= {})["heavyfumes"] = {
    ability: :HEAVYFUMES, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    eor: [["normal", {foe_types: [:NORMAL]}], ["poison", {foe_types: [:POISON]}],
          ["guarded", {foe_ability: :MAGICGUARD}], ["substitute", {foe_substitute: true}]],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:heavyfumes] installed on EndOfRoundEffect")
rescue StandardError => e
  ChrookedLog.error("[chrooked:heavyfumes] ERROR #{e.class}: #{e.message}")
end
