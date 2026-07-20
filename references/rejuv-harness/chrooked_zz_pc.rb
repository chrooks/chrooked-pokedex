# chrooked:zz_pc
# Static QoL mod (not a Ruleset behavior) — always installed by apply.
# Adds a "PC" option to the party menu that opens Box organize mode, so you can
# swap party members without walking to a Pokémon Center.
#
# Overworld-only comes free: MenuHandlers.build(:party_menu, ...) is called from
# exactly one place, PokemonScreen#pbPokemonScreen (Scripts/Party.rb:1618), which
# only the overworld/pause-menu entry (Utilities.rb:3603) reaches. Battle and
# every chooser flow (item use, move tutor) call pbStartScene + pbChoosePokemon
# directly and never build the menu — so no in-battle guard is needed.
#
# $PokemonStorage.party IS $Trainer.party (Storage.rb:54), the same array object
# the party screen holds, so the PC mutates it in place and re-showing the scene
# picks up withdrawals/deposits without re-fetching.
#
# Order 57 puts it after Season (55) and before the hidden-move slots (60+).
#
# Test cases:
#   - overworld party menu => "PC" appears; deposit/withdraw, back out, party
#     screen returns showing the new party
#   - use a Potion from the bag (chooser) => no menu, so no "PC"
#   - party menu mid-battle => no "PC"

MenuHandlers.add(:party_menu, :chrooked_pc,
  name:   proc { |*args| _INTL("PC") },
  order:  57,
  effect: proc { |screen, party, pkmnid|
    screen.scene.pbEndScene
    pbFadeOutIn(99999) {
      PokemonStorageScreen.new(PokemonStorageScene.new, $PokemonStorage).pbStartScreen(0)
    }
    Chrooked.log("PC opened from party menu")
    screen.scene.pbStartScene(
      party,
      party.length > 1 ? _INTL("Choose a Pokémon.") : _INTL("Choose Pokémon or cancel."),
      nil, false, autoheal: true
    )
    next nil
  }
)
