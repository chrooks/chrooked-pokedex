# encoding: utf-8
# chrooked:webweaver
# Web Weaver — "On entry, lays Sticky Web on the foe's side. Grounded foes
#   cannot flee."
#
# Only the HAZARD clause lives here. The trapping half is declared in the
# Ruleset as
#   behaviors: [webweaver, arenatrap]
# so chrooked_zz_zcompose.rb makes the holder a ChrookedAbilitySet of
# [:WEBWEAVER, :ARENATRAP]. Every vanilla Arena Trap check then matches the
# holder on its own, including pbCheckSideAbility.
#
# What used to be here was a PokeBattle_Battle prepend that rewrote
# pbCheckSideAbility to append :WEBWEAVER wherever :ARENATRAP appeared — a
# hand-copy of Arena Trap's reach that had to be kept in step by hand and only
# covered the one call site it knew about. Composition covers every site,
# including ones nobody enumerated. Do not reintroduce it.
CHROOKED_SWITCH_IN[:WEBWEAVER] = lambda { |battler, battle|
  side = battler.pbOpposingSide
  next if side.effects[:StickyWeb]
  battle.pbShowAbilityBox(battler)
  side.effects[:StickyWeb] = battler.pokemon
  battle.pbDisplay(_INTL("A sticky web has been laid out on the ground around the opposing team!"))
  battle.pbHideAbilityBox(battler)
}
