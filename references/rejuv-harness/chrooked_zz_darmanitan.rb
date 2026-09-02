# chrooked:zz_darmanitan
# Static QoL mod (not a Ruleset behavior) — always installed by apply.
# Adds a "Zen" option to the party menu for Darmanitan that switches between its
# Standard and Zen form directly, the way chrooked_zz_season.rb does for Sawsbuck.
# Elite Redux does the same thing: the form is a build choice the player makes out
# of battle, not a low-HP panic state, so no line carries the Zen Mode ability.
#
# Three things this has to do that the Season menu does not:
#
# 1. SWAP THE ABILITY. PokeBattle_Pokemon#changeForm (Scripts/Pokemon.rb:793) sets
#    the form and nothing else — @ability is a stored attr_accessor, so a form
#    change alone leaves the old ability in place and the Zen form's ability slots
#    are dead data. Gracidea and Reveal Glass (Scripts/ItemEffects.rb:1312, :1334)
#    fix this with a bare initAbility, but that re-rolls from
#    personalID % list.length and wipes an ability-capsule pick. We capture the
#    index off the old list instead and set the matching entry of the new one, so
#    a capsuled slot survives and the mapping is position-for-position:
#      Standard 0/1/2 (Kindle / Sheer Force / Hammerfist)
#        -> Zen 0/1/2 (Sage Power / Soulsight / Impenetrable)
#      Galar Standard 0/1/2 (Permafrost / Thick Fat / Guts)
#        -> Galar Zen 0/1/2 (Immolate / Kindle / Aftermath)
#
# 2. KEEP THE FORM. changeFormOnLeavingField (Scripts/Pokemon.rb:891) does
#    `self.form = @form - 1 if @species == :DARMANITAN && @form.odd?`, and
#    Battler#pbResetForm calls it on faint, switch, and battle end. Without the
#    prepend below, a Zen pick does not survive a single battle. Sawsbuck is not in
#    that list, which is why the Season menu needed no equivalent.
#
# 3. STAY ON ITS OWN BRANCH. Forms are 0 Unova Standard, 1 Unova Zen,
#    2 Galar Standard, 3 Galar Zen (confirmed from the branch tests in
#    Scripts/Battler.rb:1766-1779). The picker only ever offers the two forms of
#    the branch the Pokemon is already on — a Unova Darmanitan cannot become Galar.
#
# Test cases:
#   - open the party menu on a Unova Darmanitan => "Zen" appears, offering
#     Standard/Zen only; picking Zen changes typing, stats, AND ability
#   - the same Darmanitan enters a battle, switches out, and stays Zen
#   - open the party menu on a Galar Darmanitan => the picker offers
#     Galar Standard/Galar Zen, never the Unova pair
#   - a Darmanitan whose ability was set by an ability capsule keeps that SLOT
#     across the toggle rather than re-rolling off personalID
#   - open the party menu on a Pidgey => no "Zen" option

CHROOKED_DARMANITAN_FORMS = [
  _INTL("Standard"), _INTL("Zen"), _INTL("Galar Standard"), _INTL("Galar Zen")
]

# Position-preserving form set: unlike a bare initAbility this survives an
# ability-capsule pick, and it does not care whether the two forms declare the
# same number of ability slots.
CHROOKED_DARMANITAN_SET_FORM = lambda { |pkmn, new_form|
  old_list = pkmn.getAbilityList
  idx = old_list.index(pkmn.ability) || (pkmn.personalID % [old_list.length, 1].max)
  pkmn.changeForm(new_form)
  new_list = pkmn.getAbilityList
  pkmn.setAbility(new_list[idx] || new_list[0]) if new_list && !new_list.empty?
}

MenuHandlers.add(:party_menu, :chrooked_zen,
  name:      proc { |*args| _INTL("Zen") },
  order:     56, # just after Season (55), before the hidden-move slots (60+)
  condition: proc { |screen, party, pkmnid|
    pkmn = party[pkmnid]
    next !pkmn.isEgg? && pkmn.species == :DARMANITAN
  },
  effect:    proc { |screen, party, pkmnid|
    pkmn = party[pkmnid]
    base = (pkmn.form / 2) * 2                 # 0 for the Unova pair, 2 for Galar
    choices = [CHROOKED_DARMANITAN_FORMS[base], CHROOKED_DARMANITAN_FORMS[base + 1]]
    cmd = screen.scene.pbShowCommands(
      _INTL("Change {1}'s form?", pkmn.name), choices, pkmn.form - base
    )
    if cmd >= 0 && (base + cmd) != pkmn.form
      old_form = pkmn.form
      old_abil = pkmn.ability
      CHROOKED_DARMANITAN_SET_FORM.call(pkmn, base + cmd)
      screen.scene.pbHardRefresh
      # Proof trail: one line in chrooked.log (game root) per party-menu form change.
      # If the ability column reads the same on both sides, the swap in
      # CHROOKED_DARMANITAN_SET_FORM silently no-opped — that is the bug to look for.
      Chrooked.log("DARMANITAN party #{CHROOKED_DARMANITAN_FORMS[old_form]}(#{old_form})" \
                   " -> #{CHROOKED_DARMANITAN_FORMS[pkmn.form]}(#{pkmn.form})" \
                   " abil=#{old_abil} -> #{pkmn.ability}")
      screen.pbDisplay(_INTL("{1} shifted to {2}.", pkmn.name, CHROOKED_DARMANITAN_FORMS[pkmn.form]))
    end
    next nil
  }
)

# Stop the engine reverting a deliberately chosen Zen form on switch/faint/battle end.
# prepend + super, never alias_method — the guard keeps a second load from stacking.
if !defined?(ChrookedDarmanitanKeepForm)
  module ChrookedDarmanitanKeepForm
    def changeFormOnLeavingField
      keep = (@species == :DARMANITAN) ? @form : nil
      super
      self.form = keep if keep && self.form != keep
    end
  end
  PokeBattle_Pokemon.prepend(ChrookedDarmanitanKeepForm)
end
