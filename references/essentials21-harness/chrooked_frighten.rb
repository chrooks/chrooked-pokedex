# chrooked:frighten
# ---------------------------------------------------------------------------
# Ruleset behavior "frighten": on entry, each adjacent foe's Sp. Atk falls one stage
# (Intimidate, for Sp. Atk).
#
# HAND-WRITTEN (mjolnir NV-28). Seam Battle::AbilityEffects::OnSwitchIn, Intimidate's
# cadence: the splash once, then each near foe on the other side, a Substitute
# blocking it as Intimidate's does, the drop through pbLowerStatStageByAbility (so
# Clear Body, Mist and the rest stop it as they stop any ability's drop). Nothing,
# and no splash, when no foe is there.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:frighten] OBS ability=true entry=true foes=<n>   each entry
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
  ChrookedLog.line("[chrooked:frighten] load prior_handler=#{!Battle::AbilityEffects::OnSwitchIn[:FRIGHTEN].nil?}")
  Battle::AbilityEffects::OnSwitchIn.add(:FRIGHTEN,
    proc { |ability, battler, battle, switch_in|
      foes = battle.allOtherSideBattlers(battler.index).select { |b| b.near?(battler) }
      ChrookedLog.line("[chrooked:frighten] OBS ability=true entry=true foes=#{foes.length}")
      next if foes.empty?
      battle.pbShowAbilitySplash(battler)
      foes.each do |b|
        if b.effects[PBEffects::Substitute] > 0
          battle.pbDisplay(_INTL("{1} is protected by its substitute!", b.pbThis))
          next
        end
        b.pbLowerStatStageByAbility(:SPECIAL_ATTACK, 1, battler, false)
      end
      battle.pbHideAbilitySplash(battler)
    }
  )
  ($chrooked_selftest_cases ||= {})["frighten"] = {
    ability: :FRIGHTEN, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["single", ->(t, spec) {
        b, holder, foe = t.pair(spec, :TACKLE)
        holder.ability = spec[:ability]
        Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
        "foe_spatk=#{foe.stages[:SPECIAL_ATTACK]}"
      }],
      ["empty", ->(t, spec) {
        b, holder, foe = t.pair(spec, :TACKLE)
        holder.ability = spec[:ability]
        foe.hp = 0   # fainted: no foe on the field
        Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
        "foe_spatk=#{foe.stages[:SPECIAL_ATTACK]} foes=#{b.allOtherSideBattlers(holder.index).length}"
      }],
      ["doubles", ->(t, spec) {
        b, holder, _ally, foe, foe2 = t.doubles(spec)
        holder.ability = spec[:ability]
        Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
        "foe_spatk=#{foe.stages[:SPECIAL_ATTACK]} second_foe_spatk=#{foe2.stages[:SPECIAL_ATTACK]}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:frighten] installed on OnSwitchIn")
rescue StandardError => e
  ChrookedLog.error("[chrooked:frighten] ERROR #{e.class}: #{e.message}")
end
