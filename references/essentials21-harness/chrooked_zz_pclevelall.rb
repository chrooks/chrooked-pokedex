# chrooked:zz_pclevelall
# mod-group: convenience
# mod-summary: PC box menu: raise every Pokémon (party + boxes) to your highest level, evolving as they go.
# Static QoL mod (not a Ruleset behavior) — installed unless turned off for the Target.
# Essentials 21 port of references/rejuv-harness/chrooked_zz_pclevelall.rb.
#
# Adds "Level up all" to the PC box-name menu (:storage_box_interact) and
# "Level up party" to the party screen menu (:party_screen_menu, next to
# "Access Pokémon Boxes"). Each raises its set (party + boxes, or party only)
# to the highest level among them, learns the new level-up moves (pbLearnMove,
# so a full moveset still prompts) and evolves silently — no animation, one
# text list of who became what at the end. Eggs and shadow
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
#     eligible mon reads the top level, no evolution scene played, a text
#     list names each evolution, box icons updated.
#   - party screen -> menu -> "Level up party" => same, party only.
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
  # Returns "Name: Old → New" when it evolved (chained evolutions walk to the
  # end), else nil.
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
    evolve_quietly(mon, screen, learn_moves)
  end

  # PokemonEvolutionScene#pbEvolutionSuccess without the scene: no animation,
  # cry, jingle, or Pokédex page. Evolution moves (L0 + current level) prompt
  # only when the player asked for move prompts.
  def self.evolve_quietly(mon, screen, learn_moves)
    first = mon.speciesName
    name = mon.name
    hops = 0
    while (new_species = mon.check_evolution_on_level_up) && hops < 3
      $stats.evolution_count += 1
      mon.action_after_evolution(new_species)
      was_fainted = mon.fainted?
      mon.species = new_species
      mon.hp = 0 if was_fainted
      mon.calc_stats
      mon.ready_to_evolve = false
      $player.pokedex.register(mon)
      $player.pokedex.set_owned(new_species)
      if learn_moves
        mon.getMoveList.each do |row|
          pbLearnMove(mon, row[1], true) { screen&.update } if [0, mon.level].include?(row[0])
        end
      end
      hops += 1
    end
    return nil if hops == 0

    "#{name}: #{first} → #{mon.speciesName}"
  end

  # Raise `mons` (party, or party + boxes) to the highest level among them.
  def self.run(screen, mons)
    target = mons.reject { |mon| mon.egg? }.map(&:level).max || 1
    todo = eligible(mons, target)
    return screen.show_message(_INTL("Everyone is already at Lv. {1}.", target)) if todo.empty?
    return unless screen.show_confirm_message(_INTL("Raise {1} Pokémon to Lv. {2}?", todo.length, target))

    # Move prompts are the slow part of a big batch; let the player skip them.
    learn = screen.show_choice_message(_INTL("New level-up moves?"), [_INTL("Ask for each"), _INTL("Skip them all")])
    return if learn.nil? || learn < 0

    evolved = todo.map { |mon| raise_to(mon, target, screen, learn == 0) }.compact
    yield if block_given?
    screen.show_message(_INTL("Raised {1} Pokémon to Lv. {2}. {3} evolved.", todo.length, target, evolved.length))
    # One message per six lines so a big box stays readable.
    evolved.each_slice(6) { |lines| screen.show_message(lines.join("\n")) }
  end
end

MenuHandlers.add(:storage_box_interact, :chrooked_level_all, {
  "name"  => _INTL("Level up all"),
  "order" => 40
})

UI::PokemonStorage::ACTIONS.add(:chrooked_level_all, {
  :effect => proc { |screen|
    ChrookedPCLevelAll.run(screen, ChrookedPCLevelAll.all_mons(screen.storage)) { screen.refresh }
  }
})

# Party screen: the same menu that holds "Access Pokémon Boxes", party only.
MenuHandlers.add(:party_screen_menu, :chrooked_level_all_party, {
  "name"  => _INTL("Level up party"),
  "order" => 15
})

UI::Party::ACTIONS.add(:chrooked_level_all_party, {
  :effect => proc { |screen|
    ChrookedPCLevelAll.run(screen, screen.party.compact) { screen.refresh_party; screen.refresh }
  }
})
