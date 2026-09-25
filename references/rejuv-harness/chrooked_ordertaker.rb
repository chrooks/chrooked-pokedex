# chrooked:ordertaker
# Order Taker — "Raises all stats on entry if a Tatsugiri is in the party."
#   The singles translation of Commander: the partner directs from the team.
#   On switch-in (the lead at battle start included), if the holder's OWN
#   party holds a non-fainted, non-egg Tatsugiri (any form) other than the
#   holder itself, raise Atk/Def/SpA/SpD/Spe by 1 stage each.
#
# Party = @battle.pbPartySingleOwner(index): the holder's own trainer's party.
#   pbParty(index) is the whole side (every owner's party list) and would count
#   a multi-battle ally trainer's Tatsugiri. Self is excluded by pokemonIndex,
#   which indexes that single-owner party (Battle_Effects.rb:1285 relies on it)
#   and survives the AI's cloned fake battlers, unlike a pokemon identity test.
#
# The raise is vanilla Commander's own call (Battler.rb:2740):
#   pbChangeStats(PBStats::Omni, n, self, nil, abilitycheck: :hide)
#   so Contrary, Simple, the +6 cap and the stat-up animation/messages behave
#   as vanilla. The ability box shows only when something can actually change
#   (pbCanIncreaseAnyStat?, which is itself Contrary-aware).
#
# Fires through the core's CHROOKED_SWITCH_IN, i.e. every vanilla
# pbAbilitiesOnSwitchIn call: switch-in, battle-start leads, and the vanilla
# re-activations on gaining the ability (Skill Swap, Trace, Transform, boss
# ability change) — the same as any vanilla entry ability.
#
# AI: pbStatChangingSwitch (Battle_AI.rb:12856) is where the switch-in scorer
# pre-applies entry stat changes (Intrepid Sword etc., by symbol). It is
# prepended so an Order Taker switch-in candidate is scored with its +1s.
#
# Test cases (drive in-game — the harness can't run a battle):
#   - Dondozo leads, Tatsugiri in the back   => ability box, all five stats +1.
#   - Dondozo switches in, Tatsugiri fainted => nothing, no ability box.
#   - Dondozo, no Tatsugiri in party         => nothing.
#   - Multi battle, only the ALLY trainer has Tatsugiri => nothing.
#   - Dondozo already at +6 everywhere       => no ability box.
module ChrookedOrderTaker
  # The first living Tatsugiri in the owner's party other than slot
  # party_index, or nil.
  def self.commander(battle, battler_index, party_index)
    party = battle.pbPartySingleOwner(battler_index) || []
    party.each_with_index do |pkmn, i|
      next if i == party_index || pkmn.nil? || pkmn.isEgg? || pkmn.hp <= 0
      return pkmn if pkmn.species == :TATSUGIRI
    end
    nil
  end
end

CHROOKED_SWITCH_IN[:ORDERTAKER] = lambda { |battler, battle|
  commander = ChrookedOrderTaker.commander(battle, battler.index, battler.pokemonIndex)
  next unless commander
  next unless battler.pbCanIncreaseAnyStat?(PBStats::Omni, battler, nil)
  battle.pbShowAbilityBox(battler)
  battle.pbDisplay(_INTL("{1} is taking orders from {2}!", battler.pbThis, commander.name))
  battler.pbChangeStats(PBStats::Omni, 1, battler, nil, abilitycheck: :hide)
  battle.pbHideAbilityBox(battler)
}

if defined?(PokeBattle_AI)
  module ChrookedOrderTakerAI
    def pbStatChangingSwitch(mon, onlyabilities: false)
      ret = super
      # ponytail: skipped on the post-Mega re-run (onlyabilities) so a form
      # change can't count the boost twice; a Mega that newly gains Order Taker
      # is then unmodelled. Contrary/Simple on the same ability set are ignored.
      begin
        if !onlyabilities && mon.ability == :ORDERTAKER &&
           ChrookedOrderTaker.commander(@battle, mon.index, mon.pokemonIndex)
          PBStats::Omni.each { |stat| mon.stages[stat] = [mon.stages[stat] + 1, 6].min }
        end
      rescue StandardError
        # a mispredicted score is survivable; a crashed AI turn is not
      end
      ret
    end
  end
  PokeBattle_AI.prepend(ChrookedOrderTakerAI)
end
