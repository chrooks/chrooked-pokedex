# chrooked:zz_pclevelall
# mod-group: convenience
# mod-summary: PC box menu: raise every Pokémon (party + boxes) to your highest level, evolving as they go.
# Static QoL mod (not a Ruleset behavior) — installed unless turned off for the Target.
# Essentials 21 port of references/rejuv-harness/chrooked_zz_pclevelall.rb.
#
# Adds "Level up all" to the PC box-name menu (:storage_box_interact). It raises
# every Pokémon in the party and all boxes to the level of the highest-level
# Pokémon you own, learns the new level-up moves (pbLearnMove, so a full
# moveset still prompts) and runs the normal evolution scene. Eggs and shadow
# mons are skipped; Everstone stays vanilla (levels, does not evolve).
#
# Why only "highest" here: stock Essentials has no badge level cap, so the
# Rejuv port's "Level cap" option has nothing to read. Add it when Nova gains
# a cap (ponytail: one more entry in the choice menu).
#
# Why not pbChangeLevel (Item_Utilities.rb:469)? One message plus a stat
# window per Pokémon; across a full PC that is hundreds of clicks. This file
# carries its quiet core and reports once at the end.
#
# Test cases (drive in-game — the harness can't open a PC):
#   - PC -> click box name => "Level up all" sits before "Cancel".
#   - with under-levelled mons => confirm shows the count; after it every
#     eligible mon reads the top level, evolutions ran, box icons updated.
#   - everyone already at the top level => one message, nothing changes.
#   - cancel at any prompt => nothing changes.
#   - "Skip them all" => no move prompts; levels and evolutions still happen.

module ChrookedPCLevelAll
  def self.all_mons(storage)
    mons = storage.party.to_a.dup
    storage.boxes.each { |box| box.each { |mon| mons << mon if mon } }
    mons.compact
  end

  def self.eligible(mons, target)
    mons.reject { |mon| mon.egg? || (mon.shadowPokemon? rescue false) || mon.level >= target }
  end

  # The quiet core of pbChangeLevel: no per-mon message, no stat window.
  def self.raise_to(mon, target, screen, learn_moves)
    old_level = mon.level
    mon.level = target # also sets exp (Pokemon#level=)
    mon.calc_stats
    mon.changeHappiness("vitamin")
    if learn_moves && $PokemonSystem.skip_move_learning == 0
      mon.getMoveList.each do |row|
        next if row[0] <= old_level || row[0] > mon.level

        pbLearnMove(mon, row[1], true) { screen&.update }
      end
    end
    new_species = mon.check_evolution_on_level_up
    return unless new_species

    pbFadeOutInWithMusic do
      evo = PokemonEvolutionScene.new
      evo.pbStartScreen(mon, new_species)
      evo.pbEvolution
      evo.pbEndScreen
    end
  end

  def self.run(screen)
    mons = all_mons(screen.storage)
    target = mons.reject { |mon| mon.egg? }.map(&:level).max || 1
    todo = eligible(mons, target)
    return screen.show_message(_INTL("Everyone is already at Lv. {1}.", target)) if todo.empty?
    return unless screen.show_confirm_message(_INTL("Raise {1} Pokémon to Lv. {2}?", todo.length, target))

    # Move prompts are the slow part of a big batch; let the player skip them.
    learn = screen.show_choice_message(_INTL("New level-up moves?"), [_INTL("Ask for each"), _INTL("Skip them all")])
    return if learn.nil? || learn < 0

    todo.each { |mon| raise_to(mon, target, screen, learn == 0) }
    screen.refresh
    screen.show_message(_INTL("Raised {1} Pokémon to Lv. {2}.", todo.length, target))
  end
end

MenuHandlers.add(:storage_box_interact, :chrooked_level_all, {
  "name"  => _INTL("Level up all"),
  "order" => 40
})

UI::PokemonStorage::ACTIONS.add(:chrooked_level_all, {
  :effect => proc { |screen| ChrookedPCLevelAll.run(screen) }
})
