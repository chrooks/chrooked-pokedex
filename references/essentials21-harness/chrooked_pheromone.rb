# chrooked:pheromone
# ---------------------------------------------------------------------------
# Ruleset behavior "pheromone": while it is on the field, foes cannot switch out or
# flee; Ghost types and Shed Shell holders can, and U-turn or Baton Pass still switch.
#
# HAND-WRITTEN (mjolnir NV-28). Seam Battle::AbilityEffects::TrappingByTarget, Shadow
# Tag's handler without its own exemption. Nova asks it when a foe tries to switch or
# run, after letting Ghost types (MORE_TYPE_EFFECTS) and Shed Shell (CertainSwitching)
# go, and shows "<holder>'s Pheromone prevents switching!"; a move that switches its
# user (pbCanChooseNonActive?) never asks.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md. Its checks measure it.
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
  ChrookedLog.line("[chrooked:pheromone] load prior_handler=" \
                   "#{!Battle::AbilityEffects::TrappingByTarget[:PHEROMONE].nil?}")
  Battle::AbilityEffects::TrappingByTarget.add(:PHEROMONE,
    proc { |ability, switcher, bearer, battle|
      next true
    }
  )
  # The holder against a foe with a second Pokemon in reserve (so a switch has
  # somewhere to go), the foe typed or holding first.
  chrooked_pheromone_scene = lambda do |t, spec, foe_types: nil, foe_item: nil|
    holder = t.mon(spec[:user], [:TACKLE])
    holder.ability = spec[:ability]
    party2 = [t.mon(spec[:foe], [:UTURN]), t.mon(spec[:foe], [:TACKLE])]
    tt = GameData::TrainerType.keys.first
    t1 = NPCTrainer.new("LabA", tt)
    t1.party = [holder]
    t2 = NPCTrainer.new("LabB", tt)
    t2.party = party2
    b = Battle.new(Battle::DebugSceneNoVisuals.new, [holder], party2, t1, t2)
    b.debug          = true
    b.controlPlayer  = true
    b.internalBattle = false
    b.pbCreateBattler(0, holder, 0)
    b.pbCreateBattler(1, party2[0], 0)
    foe = b.battlers[1]
    foe.ability = nil
    foe.item = foe_item
    if foe_types
      foe.types = foe_types
      foe.effects[PBEffects::ExtraType] = nil
    end
    "can_switch=#{b.pbCanSwitchOut?(foe.index)} u_turn_can_switch=#{b.pbCanChooseNonActive?(foe.index)}"
  end
  ($chrooked_selftest_cases ||= {})["pheromone"] = {
    ability: :PHEROMONE, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["trapped", ->(t, spec) { chrooked_pheromone_scene.call(t, spec) }],
      ["ghost_or_shed", ->(t, spec) {
        ghost = chrooked_pheromone_scene.call(t, spec, foe_types: [:GHOST])[/can_switch=(\w+)/, 1]
        shed = chrooked_pheromone_scene.call(t, spec, foe_item: :SHEDSHELL)[/can_switch=(\w+)/, 1]
        "ghost_can_switch=#{ghost} shed_can_switch=#{shed}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:pheromone] installed on TrappingByTarget")
rescue StandardError => e
  ChrookedLog.error("[chrooked:pheromone] ERROR #{e.class}: #{e.message}")
end
