# chrooked:zz_pclevelall
# mod-group: convenience
# mod-summary: PC box menu: raise every Pokémon (party + boxes) to the level cap or to your highest level, evolving as they go.
# Static QoL mod (not a Ruleset behavior) — installed unless turned off for the Target.
#
# Adds "Level Up All" to the PC box-name menu (click a box's name in any PC
# mode). It asks for a target — the badge level cap (PBExp.currentHardCapLevel)
# or the level of the highest-level Pokémon you own — then raises every
# Pokémon in the party and all boxes below that level to it. Each raise learns
# the new level-up moves (pbTryLearnMove, so a full moveset still prompts) and
# evolves silently — no animation, one text list of who became what at the
# end — so a Lv 36 Charmander becomes a Charizard in two quiet hops. Eggs, shadow mons, and Everstone holders behave as in vanilla
# (eggs/shadow skipped; Everstone levels but does not evolve).
#
# Why not reuse pbChangeLevel (the Rare Candy path chrooked_zz_levelcap.rb
# uses)? It prints a message and a stat window per Pokémon and calls
# scene.pbRefresh, which PokemonStorageScreen has no answer for. Across a
# full PC that is hundreds of clicks, so this file carries the quiet core of
# pbChangeLevel (ItemEffects.rb:672) and reports once at the end.
#
# Why the menu is hooked this way: same shape as chrooked_zz_pcsort.rb — a
# flag set around super on pbBoxCommands, then pbShowCommands appends one
# entry. pbBoxCommands' `case command` has no `else`, so handing it -1 after
# the work is done returns cleanly (Storage.rb:528).
#
# Test cases (drive in-game — the harness can't open a PC):
#   - PC -> click box name => "Level Up All" is the last entry before nothing.
#   - pick "Level cap (Lv N)" with under-levelled mons => confirm shows the
#     count; after it, every eligible mon reads Lv N, no evolution scene
#     played, a text list names each evolution, box sprites show the new species.
#   - pick "Highest Pokémon (Lv M)" => same, with M the top level you own.
#   - everyone already at target => one message, nothing changes.
#   - cancel at any prompt => nothing changes.
#   - "Skip them all" => no move prompts; levels and evolutions still happen.
#   - No-EXP mode on => entry does nothing but say so.

module ChrookedPCLevelAll
  LABEL = "Level Up All"

  def self.all_mons(storage)
    mons = storage.party.to_a.dup
    storage.boxes.each { |box| box.each { |mon| mons << mon if mon } }
    mons.compact
  end

  def self.eligible(mons, target)
    mons.reject { |mon| mon.isEgg? || (mon.isShadow? rescue false) || mon.level >= target }
  end

  # The quiet core of pbChangeLevel: no per-mon message, no scene refresh.
  # Returns "Name: Old → New" when it evolved (chained evolutions walk to the
  # end), else nil.
  def self.raise_to(mon, target, learn_moves)
    oldlevel = mon.level
    mon.level = target
    mon.exp = PBExp.startExperience(mon.level, mon.growthrate)
    mon.calcStats
    mon.changeHappiness(:LevelUp)
    if learn_moves
      mon.getMoveList.each do |row|
        pbTryLearnMove(mon, row[1], ignoreifknown: true) if row[0] <= mon.level && row[0] > oldlevel
      end
    end
    evolve_quietly(mon, learn_moves)
  end

  # The silent branch of pbCarryOutEvolution (Evolution.rb:721): no scene, no
  # cry, no "Congratulations". pbEndCore is the on-evolution move prompt, so it
  # runs only when the player asked for move prompts.
  def self.evolve_quietly(mon, learn_moves)
    first = getMonName(mon.species, mon.form)
    name = mon.name
    hops = 0
    while (evo = checkEvolution(mon)) && hops < 3
      scene = PokemonEvolutionScene.new
      scene.pbStartCore(mon, evo)
      scene.pbEvolutionCore
      scene.pbEndCore if learn_moves
      hops += 1
    end
    return nil if hops == 0

    "#{name}: #{first} → #{getMonName(mon.species, mon.form)}"
  end

  # One message per six lines so a big box stays readable.
  def self.report(screen, evolved)
    evolved.each_slice(6) { |lines| screen.pbDisplay(lines.join("\n")) }
  end
end

module ChrookedStorageLevelAllHooks
  def pbBoxCommands(mode)
    @chrooked_levelall_menu = true
    super
  ensure
    @chrooked_levelall_menu = false
  end

  def pbShowCommands(msg, commands, *args, **kwargs)
    return super unless @chrooked_levelall_menu

    # One menu per pbBoxCommands; clear so the submenus below are untouched.
    @chrooked_levelall_menu = false
    choice = super(msg, commands + [_INTL(ChrookedPCLevelAll::LABEL)], *args, **kwargs)
    return choice if choice < commands.length

    chrooked_level_all(*args, **kwargs)
    -1
  end

  def chrooked_level_all(*args, **kwargs)
    return pbDisplay(_INTL("EXP gain is off right now.")) if noExp?

    mons = ChrookedPCLevelAll.all_mons(@storage)
    cap = [PBExp.currentHardCapLevel, MAXIMUMLEVEL].min
    highest = mons.reject { |mon| mon.isEgg? }.map(&:level).max || 1
    pick = pbShowCommands(
      _INTL("Raise everyone to which level?"),
      [_INTL("Level cap (Lv. {1})", cap), _INTL("Highest Pokémon (Lv. {1})", highest), _INTL("Cancel")],
      *args, **kwargs
    )
    target = { 0 => cap, 1 => highest }[pick]
    return unless target

    todo = ChrookedPCLevelAll.eligible(mons, target)
    return pbDisplay(_INTL("Everyone is already at Lv. {1} or above.", target)) if todo.empty?
    return unless pbConfirm(_INTL("Raise {1} Pokémon to Lv. {2}?", todo.length, target))

    # Move prompts are the slow part of a big batch; let the player skip them.
    learn = pbShowCommands(_INTL("New level-up moves?"), [_INTL("Ask for each"), _INTL("Skip them all")], *args, **kwargs)
    return if learn < 0

    evolved = todo.map { |mon| ChrookedPCLevelAll.raise_to(mon, target, learn == 0) }.compact
    @scene.pbHardRefresh
    Chrooked.log("PC Level Up All: #{todo.length} mons -> Lv #{target}, #{evolved.length} evolved")
    pbDisplay(_INTL("Raised {1} Pokémon to Lv. {2}. {3} evolved.", todo.length, target, evolved.length))
    ChrookedPCLevelAll.report(self, evolved)
  end
end
PokemonStorageScreen.prepend(ChrookedStorageLevelAllHooks)
