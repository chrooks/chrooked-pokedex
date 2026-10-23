# chrooked:deadlock
# ---------------------------------------------------------------------------
# Ruleset behavior "deadlock": on entry each adjacent foe's Speed falls one stage, and
# while it is on the field foes cannot switch out or flee.
#
# HAND-WRITTEN (mjolnir NV-28).
#   - OnSwitchIn, Intimidate's cadence for Speed (as chrooked_frighten.rb): every
#     entry, the splash once, a Substitute or Clear Body stopping the drop.
#   - TrappingByTarget, as Shadow Tag but without its own exemption: Nova asks the
#     trapping abilities of the foes on the field each time one tries to switch or
#     run, so the trap ends the moment the holder leaves or faints. Ghost types
#     (MORE_TYPE_EFFECTS) and Shed Shell (CertainSwitching) are let go before it asks;
#     U-turn and Baton Pass never ask.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:deadlock] OBS ability=true entry=true foes=<n>   each entry
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
  ChrookedLog.line("[chrooked:deadlock] load prior_handler=#{!Battle::AbilityEffects::OnSwitchIn[:DEADLOCK].nil?}")
  Battle::AbilityEffects::OnSwitchIn.add(:DEADLOCK,
    proc { |ability, battler, battle, switch_in|
      foes = battle.allOtherSideBattlers(battler.index).select { |b| b.near?(battler) }
      ChrookedLog.line("[chrooked:deadlock] OBS ability=true entry=true foes=#{foes.length}")
      next if foes.empty?
      battle.pbShowAbilitySplash(battler)
      foes.each do |b|
        if b.effects[PBEffects::Substitute] > 0
          battle.pbDisplay(_INTL("{1} is protected by its substitute!", b.pbThis))
          next
        end
        b.pbLowerStatStageByAbility(:SPEED, 1, battler, false)
      end
      battle.pbHideAbilitySplash(battler)
    }
  )
  Battle::AbilityEffects::TrappingByTarget.add(:DEADLOCK,
    proc { |ability, switcher, bearer, battle|
      next true
    }
  )
  # The holder enters (entries times; the foe set up first), then the foe asks to switch.
  chrooked_deadlock_scene = lambda do |t, spec, entries: 1, foe_types: nil, foe_item: nil, foe_ability: nil,
                                       holder_gone: false|
    b, holder, foe = t.pair(spec, :TACKLE)
    holder.ability = spec[:ability]
    foe.ability = foe_ability
    foe.item = foe_item
    if foe_types
      foe.types = foe_types
      foe.effects[PBEffects::ExtraType] = nil
    end
    entries.times { Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true) }
    holder.hp = 0 if holder_gone
    "foe_speed=#{foe.stages[:SPEED]} can_switch=#{b.pbCanSwitchOut?(foe.index)}"
  end
  ($chrooked_selftest_cases ||= {})["deadlock"] = {
    ability: :DEADLOCK, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["entry", ->(t, spec) { chrooked_deadlock_scene.call(t, spec) }],
      ["trapped", ->(t, spec) { chrooked_deadlock_scene.call(t, spec) }],
      ["holder_gone", ->(t, spec) { chrooked_deadlock_scene.call(t, spec, holder_gone: true) }],
      ["ghost", ->(t, spec) { chrooked_deadlock_scene.call(t, spec, foe_types: [:GHOST]) }],
      ["shed_shell", ->(t, spec) { chrooked_deadlock_scene.call(t, spec, foe_item: :SHEDSHELL) }],
      ["clear_body", ->(t, spec) { chrooked_deadlock_scene.call(t, spec, foe_ability: :CLEARBODY) }],
      ["twice", ->(t, spec) { chrooked_deadlock_scene.call(t, spec, entries: 2) }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:deadlock] installed on OnSwitchIn and TrappingByTarget")
rescue StandardError => e
  ChrookedLog.error("[chrooked:deadlock] ERROR #{e.class}: #{e.message}")
end
