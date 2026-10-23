# chrooked:frisk
# ---------------------------------------------------------------------------
# Ruleset behavior "frisk": the game's own Frisk (it reveals the foes' held items on
# entry), and on entry each adjacent foe is under Embargo for 2 rounds; a longer
# Embargo already there is kept.
#
# HAND-WRITTEN (mjolnir NV-28). OnSwitchIn keeps Nova's own handler, called first (it
# reveals items only for the player's Pokemon, as Nova's does), then sets
# effects[PBEffects::Embargo] to 2 on each near foe below 2, Embargo's own counter, so
# Nova's itemActive? stops the item and Nova counts it down and announces its end at
# the end of each round.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:frisk] OBS ability=true entry=true embargoed=<n>   each entry
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
  chrooked_frisk_own = Battle::AbilityEffects::OnSwitchIn[:FRISK]
  ChrookedLog.line("[chrooked:frisk] load prior_handler=#{!chrooked_frisk_own.nil?}")
  Battle::AbilityEffects::OnSwitchIn.add(:FRISK,
    proc { |ability, battler, battle, switch_in|
      chrooked_frisk_own&.call(ability, battler, battle, switch_in)
      embargoed = 0
      battle.allOtherSideBattlers(battler.index).each do |b|
        next if !b.near?(battler) || b.effects[PBEffects::Embargo] >= 2
        b.effects[PBEffects::Embargo] = 2
        battle.pbDisplay(_INTL("{1} can't use items anymore!", b.pbThis))
        embargoed += 1
      end
      ChrookedLog.line("[chrooked:frisk] OBS ability=true entry=true embargoed=#{embargoed}")
    }
  )
  # The holder enters against a foe holding Leftovers (an Embargo preset first), then
  # `rounds` ends of round pass: the foe's Embargo and whether its item works.
  chrooked_frisk_scene = lambda do |t, spec, preset, rounds|
    b, holder, foe = t.pair(spec, :TACKLE)
    holder.ability = spec[:ability]
    foe.item = :LEFTOVERS
    foe.effects[PBEffects::Embargo] = preset
    Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
    after_entry = foe.effects[PBEffects::Embargo]
    rounds.times { b.send(:pbEORCountDownBattlerEffect, [foe], PBEffects::Embargo) }
    "embargo_on_entry=#{after_entry} embargo=#{foe.effects[PBEffects::Embargo]} item_works=#{foe.itemActive?}"
  end
  ($chrooked_selftest_cases ||= {})["frisk"] = {
    ability: :FRISK, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["leftovers", ->(t, spec) { chrooked_frisk_scene.call(t, spec, 0, 0) }],
      ["longer_embargo", ->(t, spec) { chrooked_frisk_scene.call(t, spec, 5, 0) }],
      ["three_rounds", ->(t, spec) { chrooked_frisk_scene.call(t, spec, 0, 2) }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:frisk] installed on OnSwitchIn")
rescue StandardError => e
  ChrookedLog.error("[chrooked:frisk] ERROR #{e.class}: #{e.message}")
end
