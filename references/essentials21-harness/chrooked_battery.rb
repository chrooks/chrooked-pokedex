# chrooked:battery
# ---------------------------------------------------------------------------
# Ruleset behavior "battery": on entry, unless already charged, it charges as the move
# Charge does (its next Electric move deals double damage) and its Sp. Def rises by 1;
# the game's own ally boost to special moves stays.
#
# HAND-WRITTEN (mjolnir NV-27). Seam Battle::AbilityEffects::OnSwitchIn: it sets the
# same effects[PBEffects::Charge] = 2 the move sets, with the move's message, then
# raises Sp. Def through pbRaiseStatStageByAbility under the splash. Nova's Charge
# raises Sp. Def by 1 on any terrain, and Nova has no fields, so it is always 1. Nova
# spends and counts the charge down itself (pbEndTurn, the end of each round). Nova's
# own Battery handler (DamageCalcFromAlly) is untouched.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:battery] OBS ability=true entry=true charged=<bool>   each entry
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
  ChrookedLog.line("[chrooked:battery] load prior_handler=#{!Battle::AbilityEffects::OnSwitchIn[:BATTERY].nil?} " \
                   "ally_handler=#{!Battle::AbilityEffects::DamageCalcFromAlly[:BATTERY].nil?}")
  Battle::AbilityEffects::OnSwitchIn.add(:BATTERY,
    proc { |ability, battler, battle, switch_in|
      charge = battler.effects[PBEffects::Charge] == 0
      if charge
        battle.pbShowAbilitySplash(battler)
        battler.effects[PBEffects::Charge] = 2
        battle.pbDisplay(_INTL("{1} began charging power!", battler.pbThis))
        if battler.pbCanRaiseStatStage?(:SPECIAL_DEFENSE, battler)
          battler.pbRaiseStatStageByAbility(:SPECIAL_DEFENSE, 1, battler, false)
        end
        battle.pbHideAbilitySplash(battler)
      end
      ChrookedLog.line("[chrooked:battery] OBS ability=true entry=true charged=#{charge}")
    }
  )
  # The holder enters (Charge preset first), then the foe takes move_id from it: its
  # Charge, Sp. Def stage and the hit with that Charge against the same hit uncharged.
  chrooked_battery_entry = lambda do |t, spec, preset, move_id|
    b, holder, foe = t.pair(spec, move_id)
    holder.ability = spec[:ability]
    holder.effects[PBEffects::Charge] = preset
    Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
    charge, spdef = holder.effects[PBEffects::Charge], holder.stages[:SPECIAL_DEFENSE]
    charged = t.hit(b, holder, foe, move_id)
    holder.effects[PBEffects::Charge] = 0
    plain = t.hit(b, holder, foe, move_id)
    holder.effects[PBEffects::Charge] = charge
    "move=#{move_id} charge=#{charge} spdef=#{spdef} charged_hit=#{charged} plain_hit=#{plain} " \
    "doubled=#{charged >= plain * 2 - 1 && plain > 0}"
  end
  ($chrooked_selftest_cases ||= {})["battery"] = {
    ability: :BATTERY, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["entry_thunderbolt", ->(t, spec) { chrooked_battery_entry.call(t, spec, 0, :THUNDERBOLT) }],
      ["already_charged", ->(t, spec) { chrooked_battery_entry.call(t, spec, 1, :THUNDERBOLT) }],
      ["bug_move", ->(t, spec) { chrooked_battery_entry.call(t, spec, 0, :BUGBUZZ) }]
    ],
    without: [],
    fight: [:THUNDERBOLT, :BUGBUZZ]
  }
  ChrookedLog.line("[chrooked:battery] installed on OnSwitchIn")
rescue StandardError => e
  ChrookedLog.error("[chrooked:battery] ERROR #{e.class}: #{e.message}")
end
