# chrooked:zz_pcsort
# Static QoL mod (not a Ruleset behavior) — always installed by apply.
#
# PC sort by date caught (both directions) and by base stats.
#   Adds "Date Caught (Newest)", "Date Caught (Oldest)" and "Base Stats..." to
#   the Sort Box / Sort PC menu. "Base Stats..." opens a submenu: BST, HP,
#   Attack, Defense, Sp. Atk, Sp. Def, Speed — highest first.
#   (vanilla list: Storage.rb:784-793, comparators: 816-865)
#
# Why it is shaped this way: vanilla's `case command` has no `else`, so an
# unrecognised index leaves `pokes` nil and crashes on `pokes += eggs`
# (Storage.rb:868). Rather than copy all eight vanilla comparators into this
# file — which would rot the moment Rejuv edits one — the wrapper lets vanilla
# run a cheap Dex No. sort it already knows, then re-sorts by date afterwards.
# The extra pass costs one drain/writeback over boxes the player just asked to
# reorder; nothing here duplicates vanilla logic.
#
# The menu is found by a flag set around `super`, not by sniffing the command
# strings, so a future Rejuv release that adds a ninth sort mode still works.
#
# timeReceived (Pokemon.rb:1347) returns a Time, the Symbol :Glitched, or
# Time.gm(2000) when unset. Only a Time is comparable, so anything else sorts
# as epoch 0 — glitched and unstamped mons gather at the "oldest" end.
#
# ponytail: eggs keep vanilla's treatment — sorted by Dex No. and parked at the
#   end — because an egg has no catch date to sort by.
# ponytail: no sort-direction toggle. Date gets two entries; base stats sort
#   highest first only, like vanilla Level and Total IVs. A submenu keeps the
#   top menu to eleven entries on the handheld screen.
# Test cases (drive in-game — the harness can't open a PC):
#   - Sort Box => the two new entries appear last in the menu.
#   - "Date Caught (Newest)" => most recently caught first, eggs last.
#   - "Date Caught (Oldest)" => reverse of the above.
#   - "Base Stats..." -> "BST" => highest base stat total first, eggs last.
#   - Cancelling the base-stat submenu => box untouched.
#   - Cancelling the menu => box untouched, no "was sorted" message.

module ChrookedPCSort
  NEWEST = "Date Caught (Newest)"
  OLDEST = "Date Caught (Oldest)"
  BASE_STATS = "Base Stats..."

  # Base-stat submenu: label => key. baseStats (Pokemon.rb:195) is form-aware and
  # reads the patched MONHASH, so Ruleset stat overrides sort correctly.
  # Order [HP, Atk, Def, SpA, SpD, Spe] matches :BaseStats.
  STAT_MODES = [
    ["BST",     ->(p) { p.baseStats.sum }],
    ["HP",      ->(p) { p.baseStats[0] }],
    ["Attack",  ->(p) { p.baseStats[1] }],
    ["Defense", ->(p) { p.baseStats[2] }],
    ["Sp. Atk", ->(p) { p.baseStats[3] }],
    ["Sp. Def", ->(p) { p.baseStats[4] }],
    ["Speed",   ->(p) { p.baseStats[5] }],
  ].freeze

  # Epoch seconds, or 0 for :Glitched / anything non-Time.
  def self.caught_at(poke)
    stamp = poke.timeReceived
    stamp.is_a?(Time) ? stamp.to_i : 0
  end

  def self.boxes_for(minbox, maxbox)
    return (minbox..maxbox).to_a if minbox <= maxbox
    (minbox...STORAGEBOXES).to_a + (0..maxbox).to_a
  end

  # Mirrors vanilla's drain -> sort -> writeback (Storage.rb:802-876).
  # `key` maps a mon to a comparable number; highest_first flips the order.
  def self.resort(boxes, key, highest_first)
    mons = []
    eggs = []
    boxes.each do |box|
      (0...$PokemonStorage[box].length).each do |slot|
        poke = $PokemonStorage[box, slot]
        next unless poke

        poke.isEgg? ? eggs.push(poke) : mons.push(poke)
        $PokemonStorage[box, slot] = nil
      end
    end
    tiebreak = ->(x, y) { 2 * (x.dexnum <=> y.dexnum) + (x.form <=> y.form) }
    sorted = mons.sort do |x, y|
      a = key.call(x)
      b = key.call(y)
      order = highest_first ? (b <=> a) : (a <=> b)
      order == 0 ? tiebreak.call(x, y) : order
    end
    sorted += eggs.sort { |x, y| tiebreak.call(x, y) }
    boxes.each do |box|
      (0...$PokemonStorage[box].length).each do |slot|
        $PokemonStorage[box, slot] = sorted.shift
        break if sorted.empty?
      end
    end
  end
end

module ChrookedStorageSortHooks
  def pbSortPokemon(minbox = $PokemonStorage.currentBox, maxbox = $PokemonStorage.currentBox)
    @chrooked_sort_menu = true
    @chrooked_sort_pick = nil
    ret = super
    if @chrooked_sort_pick
      key, highest_first = @chrooked_sort_pick
      ChrookedPCSort.resort(ChrookedPCSort.boxes_for(minbox, maxbox), key, highest_first)
    end
    ret
  ensure
    @chrooked_sort_menu = false
    @chrooked_sort_pick = nil
  end

  def pbShowCommands(msg, commands, *args, **kwargs)
    return super unless @chrooked_sort_menu

    # One menu per sort; clear the flag so the submenu below is untouched.
    @chrooked_sort_menu = false
    extra = [ChrookedPCSort::NEWEST, ChrookedPCSort::OLDEST, ChrookedPCSort::BASE_STATS]
    choice = super(msg, commands + extra.map { |label| _INTL(label) }, *args, **kwargs)
    return choice if choice < commands.length

    case extra[choice - commands.length]
    when ChrookedPCSort::NEWEST
      @chrooked_sort_pick = [ChrookedPCSort.method(:caught_at), true]
    when ChrookedPCSort::OLDEST
      @chrooked_sort_pick = [ChrookedPCSort.method(:caught_at), false]
    when ChrookedPCSort::BASE_STATS
      labels = ChrookedPCSort::STAT_MODES.map { |label, _| _INTL(label) }
      stat = super(_INTL("Sort by which base stat?\nHighest first."), labels, *args, **kwargs)
      # Cancelling the submenu cancels the whole sort, before vanilla drains.
      return -1 if stat < 0

      @chrooked_sort_pick = [ChrookedPCSort::STAT_MODES[stat][1], true]
    end
    # Hand vanilla a mode it knows so its `case` assigns `pokes`; the chrooked
    # sort replaces the result immediately after super returns.
    2 # Dex No.
  end
end
PokemonStorageScreen.prepend(ChrookedStorageSortHooks)
