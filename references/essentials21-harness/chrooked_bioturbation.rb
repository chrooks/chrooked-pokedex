# chrooked:bioturbation
# ---------------------------------------------------------------------------
# Ruleset behavior "bioturbation": on entry Stealth Rock deals it its neutral 1/8 (no
# weakness or resistance), and afterwards every hazard on its side moves to the foes'
# side, capped at each hazard's maximum there.
#
# HAND-WRITTEN (mjolnir NV-26). It wraps Battle#pbEntryHazards for the holder:
#   1. Stealth Rock at 1/8 of max HP, behind Nova's own gates (takesIndirectDamage?,
#      Heavy-Duty Boots), with Nova's message; Nova's typed Stealth Rock is hidden for
#      the call, so Spikes, Toxic Spikes and Sticky Web run as Nova runs them.
#   2. Then, unless it fainted, Stealth Rock, Spikes (up to 3), Toxic Spikes (up to
#      2) and Sticky Web leave its side for the foes'; layers past the cap are lost.
#      The foes' entry effects do not fire: nothing enters.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:bioturbation] OBS ability=true entry=true moved=<bool>   each entry onto a side with hazards
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
  ChrookedLog.line("[chrooked:bioturbation] load prior_handler=" \
                   "#{!Battle::AbilityEffects::OnSwitchIn[:BIOTURBATION].nil?}")
  Battle.class_eval do
    unless method_defined?(:chrooked_bioturbation_pbEntryHazards)
      alias_method :chrooked_bioturbation_pbEntryHazards, :pbEntryHazards
      def pbEntryHazards(battler)
        return chrooked_bioturbation_pbEntryHazards(battler) if !battler.hasActiveAbility?(:BIOTURBATION)
        side = battler.pbOwnSide
        rock = side.effects[PBEffects::StealthRock]
        if rock && battler.takesIndirectDamage? && GameData::Type.exists?(:ROCK) &&
           !battler.hasActiveItem?(:HEAVYDUTYBOOTS)
          battler.pbReduceHP(battler.totalhp / 8, false)
          pbDisplay(_INTL("Pointed stones dug into {1}!", battler.pbThis))
          battler.pbItemHPHealCheck
        end
        begin
          side.effects[PBEffects::StealthRock] = false
          chrooked_bioturbation_pbEntryHazards(battler)
        ensure
          side.effects[PBEffects::StealthRock] = rock
        end
        return if battler.fainted?
        foes = battler.pbOpposingSide
        moved = false
        if side.effects[PBEffects::StealthRock]
          foes.effects[PBEffects::StealthRock] = true
          side.effects[PBEffects::StealthRock] = false
          moved = true
        end
        { PBEffects::Spikes => 3, PBEffects::ToxicSpikes => 2 }.each do |effect, cap|
          next if side.effects[effect] <= 0
          foes.effects[effect] = [foes.effects[effect] + side.effects[effect], cap].min
          side.effects[effect] = 0
          moved = true
        end
        if side.effects[PBEffects::StickyWeb]
          foes.effects[PBEffects::StickyWeb] = true
          side.effects[PBEffects::StickyWeb] = false
          moved = true
        end
        if moved
          pbShowAbilitySplash(battler)
          pbDisplay(_INTL("{1} churned the hazards over to the other side!", battler.pbThis))
          pbHideAbilitySplash(battler)
        end
        ChrookedLog.line("[chrooked:bioturbation] OBS ability=true entry=true moved=#{moved}")
      end
    end
  end
  # The holder enters onto its hazards (and the foes' preset), typed as given.
  chrooked_bioturbation_entry = lambda do |t, spec, own, foes, types = nil|
    b, holder, _foe = t.pair(spec, :TACKLE)
    holder.ability = spec[:ability]
    if types
      holder.types = types
      holder.effects[PBEffects::ExtraType] = nil
    end
    own.each { |effect, value| holder.pbOwnSide.effects[effect] = value }
    foes.each { |effect, value| holder.pbOpposingSide.effects[effect] = value }
    hp = holder.hp
    b.pbEntryHazards(holder)
    mine, theirs = holder.pbOwnSide.effects, holder.pbOpposingSide.effects
    "lost=#{hp - holder.hp} max=#{holder.totalhp} own_rock=#{mine[PBEffects::StealthRock]} " \
    "own_spikes=#{mine[PBEffects::Spikes]} foe_rock=#{theirs[PBEffects::StealthRock]} " \
    "foe_spikes=#{theirs[PBEffects::Spikes]}"
  end
  ($chrooked_selftest_cases ||= {})["bioturbation"] = {
    ability: :BIOTURBATION, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["ice_water_rock", ->(t, spec) {
        line = chrooked_bioturbation_entry.call(t, spec, {PBEffects::StealthRock => true}, {}, [:ICE, :WATER])
        "#{line} neutral=#{line[/lost=(\d+)/, 1].to_i == line[/max=(\d+)/, 1].to_i / 8}"
      }],
      ["spikes_rock", ->(t, spec) {
        line = chrooked_bioturbation_entry.call(t, spec, {PBEffects::StealthRock => true, PBEffects::Spikes => 3}, {})
        max = line[/max=(\d+)/, 1].to_i
        "#{line} expected=#{max / 4 + max / 8}"
      }],
      ["capped", ->(t, spec) {
        chrooked_bioturbation_entry.call(t, spec, {PBEffects::StealthRock => true, PBEffects::Spikes => 2},
                                         {PBEffects::Spikes => 3})
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:bioturbation] installed on Battle#pbEntryHazards")
rescue StandardError => e
  ChrookedLog.error("[chrooked:bioturbation] ERROR #{e.class}: #{e.message}")
end
