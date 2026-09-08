# chrooked:zz_eevee
# Static QoL mod (not a Ruleset behavior) — always installed by apply.
# Adds an "Eevee" option to the party menu for the eight Eeveelutions that
# switches the Pokemon to any other Eeveelution directly, the way
# chrooked_zz_darmanitan.rb toggles Zen. Idea from Elite Redux: once Eevee has
# evolved, the evolution is a build choice the player remakes out of battle.
#
# Eeveelutions are separate SPECIES, not forms, so this mirrors what the engine
# itself does at the end of an evolution (Scripts/Evolution.rb:685): set species,
# carry the ability slot across, updateMegaData, register the dex, rename if the
# nickname was the species name, calcStats. Species is a plain attr_accessor on
# PokeBattle_Pokemon and nothing reverts it after a battle, so no keep-form
# prepend is needed here.
#
# Rules:
#   - Eevee itself gets no option; it evolves once the normal way.
#   - Only form 0 shows the option (Rift Flareon and any other alt form stay put).
#   - Moves are untouched; level-up moves come from the new species from now on.
#   - Ability maps position-for-position, so an ability-capsule slot survives.
#
# Test cases:
#   - open the party menu on a Vaporeon => "Eevee" appears; picking Jolteon
#     changes species, typing, stats and ability, and the party sprite updates
#   - a Vaporeon nicknamed "Vaporeon" becomes "Jolteon"; one nicknamed "Bubbles" keeps it
#   - open the party menu on an Eevee or a Pidgey => no "Eevee" option
#   - a Rift Flareon (form 1) => no "Eevee" option

CHROOKED_EEVEELUTIONS = [
  :VAPOREON, :JOLTEON, :FLAREON, :ESPEON, :UMBREON, :LEAFEON, :GLACEON, :SYLVEON
]

# Position-preserving species set — same idea as CHROOKED_DARMANITAN_SET_FORM.
CHROOKED_EEVEE_SET_SPECIES = lambda { |pkmn, new_species|
  old_list = pkmn.getAbilityList
  idx = old_list.index(pkmn.ability) || (pkmn.personalID % [old_list.length, 1].max)
  old_name = getMonName(pkmn.species)
  pkmn.species = new_species
  pkmn.form = 0
  new_list = pkmn.getAbilityList
  pkmn.setAbility(new_list[idx] || new_list[0]) if new_list && !new_list.empty?
  pkmn.updateMegaData
  pkmn.name = getMonName(new_species) if pkmn.name == old_name
  pkmn.calcStats
  $Trainer.pokedex.setSeen(pkmn)
  $Trainer.pokedex.setOwned(pkmn)
}

MenuHandlers.add(:party_menu, :chrooked_eevee,
  name:      proc { |*args| _INTL("Eevee") },
  order:     57, # after Zen (56), before the hidden-move slots (60+)
  condition: proc { |screen, party, pkmnid|
    pkmn = party[pkmnid]
    next !pkmn.isEgg? && pkmn.form == 0 && CHROOKED_EEVEELUTIONS.include?(pkmn.species)
  },
  effect:    proc { |screen, party, pkmnid|
    pkmn = party[pkmnid]
    choices = CHROOKED_EEVEELUTIONS.map { |s| getMonName(s) }
    cmd = screen.scene.pbShowCommands(
      _INTL("Change {1}'s evolution?", pkmn.name), choices,
      CHROOKED_EEVEELUTIONS.index(pkmn.species) || 0
    )
    if cmd >= 0 && CHROOKED_EEVEELUTIONS[cmd] != pkmn.species
      old_species = pkmn.species
      old_abil = pkmn.ability
      CHROOKED_EEVEE_SET_SPECIES.call(pkmn, CHROOKED_EEVEELUTIONS[cmd])
      screen.scene.pbHardRefresh
      # Proof trail: one line in chrooked.log (game root) per party-menu switch.
      # Same ability on both sides of the arrow means the slot swap no-opped.
      Chrooked.log("EEVEE party #{old_species} -> #{pkmn.species}" \
                   " abil=#{old_abil} -> #{pkmn.ability}")
      screen.pbDisplay(_INTL("{1} shifted to {2}.", pkmn.name, choices[cmd]))
    end
    next nil
  }
)
