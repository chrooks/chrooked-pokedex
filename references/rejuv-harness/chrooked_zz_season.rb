# chrooked:zz_season
# Static QoL mod (not a Ruleset behavior) — always installed by apply.
# Adds a "Season" option to the party menu for Deerling/Sawsbuck that opens a
# Spring/Summer/Autumn/Winter picker and sets the form directly. Replaces the
# vanilla petal-item flow (PINKPETAL/GREENPETAL/ORANGEPETAL/BLUEPETAL).
#
# Uses Rejuv's own additive seam (MenuHandlers.add on :party_menu, see
# Scripts/PartyMenu_Registry.rb) — no method override, so this survives updates.
# Form indices match the petal items in Scripts/ItemEffects.rb:
#   0 Spring, 1 Summer, 2 Autumn, 3 Winter
# Order 55 puts it between Rename (50) and the hidden-move slots (60+).
#
# Test cases:
#   - open party menu on a Spring Sawsbuck => "Season" appears; picking Winter
#     changes typing/stats and the party sprite updates
#   - open party menu on a Pidgey => no "Season" option
#   - open the picker and cancel => form unchanged

CHROOKED_SEASON_FORMS = [
  _INTL("Spring"), _INTL("Summer"), _INTL("Autumn"), _INTL("Winter")
]

MenuHandlers.add(:party_menu, :chrooked_season,
  name:      proc { |*args| _INTL("Season") },
  order:     55,
  condition: proc { |screen, party, pkmnid|
    pkmn = party[pkmnid]
    next !pkmn.isEgg? && [:DEERLING, :SAWSBUCK].include?(pkmn.species)
  },
  effect:    proc { |screen, party, pkmnid|
    pkmn = party[pkmnid]
    cmd = screen.scene.pbShowCommands(
      _INTL("Change {1}'s season?", pkmn.name), CHROOKED_SEASON_FORMS, pkmn.form
    )
    if cmd >= 0 && cmd != pkmn.form
      old_form = pkmn.form
      pkmn.changeForm(cmd)
      screen.scene.pbHardRefresh
      # Proof trail: one line in chrooked.log (game root) per party-menu season change.
      Chrooked.log("SEASON party #{pkmn.species} #{CHROOKED_SEASON_FORMS[old_form]}" \
                   "(#{old_form}) -> #{CHROOKED_SEASON_FORMS[cmd]}(#{pkmn.form})")
      screen.pbDisplay(_INTL("{1} shifted to {2}.", pkmn.name, CHROOKED_SEASON_FORMS[cmd]))
    end
    next nil
  }
)
