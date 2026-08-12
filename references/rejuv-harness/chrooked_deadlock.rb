# chrooked:deadlock
# Deadlock — "On entry, foes lose 1 Speed stage. Foes cannot switch out."
#   switch-in: Intimidate clone for Speed
#   escape-check: foes can't switch or flee, exactly like Shadow Tag
# Test cases:
#   - switch in vs two foes => both lose 1 Speed stage
#   - foe at -6 Speed / Clear Body / behind protection => unaffected, no crash
#   - foe tries to switch => blocked; Ghost / Shed Shell escape
#   - FLYING or Levitate foe tries to switch => still blocked (unlike Arena Trap)
#   - holder leaves the field => the trap lifts
CHROOKED_SWITCH_IN[:DEADLOCK] = lambda { |battler, battle|
  [battler.pbOpposing1, battler.pbOpposing2].each do |foe|
    next if !foe || foe.isFainted?
    next unless foe.pbCanReduceAnyStat?([PBStats::SPEED], battler, :Deadlock)
    battle.pbShowAbilityBox(battler)
    foe.pbChangeStats(PBStats::SPEED, -1, battler, :Deadlock)
    battle.pbHideAbilityBox(battler)
  end
}

# Trap clause: same seam Web Weaver rides, but keyed to SHADOW TAG rather than
# Arena Trap. Arena Trap's list is pushed only for GROUNDED foes, and Deadlock
# pins by predation, not by controlling the ground — a Flying-type or a Levitate
# holder is prey too. Shadow Tag's entry is unconditional and sits after the same
# Ghost / Shed Shell early returns, so riding it gives Deadlock exactly the
# documented behavior everywhere a trap is checked (player switch, run, AI).
#
# One clause rides along: a Shadow Tag holder is exempt from Shadow Tag, so it is
# also exempt from Deadlock. Rare enough to accept, and thematically fine — one
# ambusher does not fall for another's ambush.
if defined?(PokeBattle_Battle)
  module ChrookedDeadlockTrap
    def pbCheckSideAbility(abilities, battler, *args, **kwargs)
      abilities = Array(abilities)
      abilities += [:DEADLOCK] if abilities.include?(:SHADOWTAG)
      super(abilities, battler, *args, **kwargs)
    end
  end
  PokeBattle_Battle.prepend(ChrookedDeadlockTrap)
end
