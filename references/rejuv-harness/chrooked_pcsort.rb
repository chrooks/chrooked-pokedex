# chrooked:pcsort
# PC sort by date caught, both directions.
#   Adds "Date Caught (Newest)" and "Date Caught (Oldest)" to the Sort Box /
#   Sort PC menu (vanilla list: Storage.rb:784-793, comparators: 816-865).
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
# ponytail: no sort-direction toggle. Two menu entries match how every other
#   vanilla mode works (each is one fixed direction), and cost no new UI.
# Test cases (drive in-game — the harness can't open a PC):
#   - Sort Box => the two new entries appear last in the menu.
#   - "Date Caught (Newest)" => most recently caught first, eggs last.
#   - "Date Caught (Oldest)" => reverse of the above.
#   - Cancelling the menu => box untouched, no "was sorted" message.

module ChrookedPCSort
  NEWEST = "Date Caught (Newest)"
  OLDEST = "Date Caught (Oldest)"

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
  def self.resort(boxes, newest_first)
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
      a = caught_at(x)
      b = caught_at(y)
      order = newest_first ? (b <=> a) : (a <=> b)
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
    ChrookedPCSort.resort(ChrookedPCSort.boxes_for(minbox, maxbox),
                          @chrooked_sort_pick == :newest) if @chrooked_sort_pick
    ret
  ensure
    @chrooked_sort_menu = false
    @chrooked_sort_pick = nil
  end

  def pbShowCommands(msg, commands, *args, **kwargs)
    return super unless @chrooked_sort_menu

    # One menu per sort; clear the flag so nested prompts are untouched.
    @chrooked_sort_menu = false
    extended = commands + [_INTL(ChrookedPCSort::NEWEST), _INTL(ChrookedPCSort::OLDEST)]
    choice = super(msg, extended, *args, **kwargs)
    return choice if choice < commands.length

    @chrooked_sort_pick = choice == commands.length ? :newest : :oldest
    # Hand vanilla a mode it knows so its `case` assigns `pokes`; the date sort
    # replaces the result immediately after super returns.
    2 # Dex No.
  end
end
PokemonStorageScreen.prepend(ChrookedStorageSortHooks)
