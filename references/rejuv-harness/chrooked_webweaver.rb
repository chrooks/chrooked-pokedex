# chrooked:webweaver
# Web Weaver — "On entry, lays Sticky Web on the foe's side. Grounded foes cannot flee."
#   switch-in: set the Sticky Web side hazard on the opposing side (no stacking)
#   escape-check: grounded foes can't switch/flee, exactly like Arena Trap
# Test cases:
#   - switch in, no web up => opposing side gains Sticky Web + message
#   - switch in, web already up => nothing (no stack)
#   - grounded foe tries to switch => blocked; airborne / Ghost / Shed Shell escape
CHROOKED_SWITCH_IN[:WEBWEAVER] = lambda { |battler, battle|
  side = battler.pbOpposingSide
  next if side.effects[:StickyWeb]
  battle.pbShowAbilityBox(battler)
  side.effects[:StickyWeb] = battler.pokemon
  battle.pbDisplay(_INTL("A sticky web has been laid out on the ground around the opposing team!"))
  battle.pbHideAbilityBox(battler)
}

# Trap clause: every trap check builds an ability list gated the way Arena Trap
# needs (grounded-only push, after the Ghost/Shed Shell early returns), then asks
# pbCheckSideAbility. Riding that list means Web Weaver inherits ALL of Arena
# Trap's bypasses everywhere it is checked (player switch, run, AI) for free.
module ChrookedWebWeaverTrap
  def pbCheckSideAbility(abilities, battler, **kwargs)
    abilities = Array(abilities)
    abilities += [:WEBWEAVER] if abilities.include?(:ARENATRAP)
    super(abilities, battler, **kwargs)
  end
end
PokeBattle_Battle.prepend(ChrookedWebWeaverTrap)
