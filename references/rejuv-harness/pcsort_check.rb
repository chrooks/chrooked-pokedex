# Runnable check for the PC date-caught sort. No game needed:
#   docker run --rm -v "$PWD/references/rejuv-harness:/h:ro" ruby:3.2-slim ruby /h/pcsort_check.rb
def _INTL(s, *a) = s
STORAGEBOXES = 2

FakeMon = Struct.new(:name, :timeReceived, :dexnum, :form, :egg, :baseStats) do
  def isEgg? = egg
end

class FakeStorage
  attr_reader :boxes
  def initialize(boxes) = @boxes = boxes
  def [](box, slot = nil) = slot.nil? ? @boxes[box] : @boxes[box][slot]
  def []=(box, slot, val)
    @boxes[box][slot] = val
  end
  def currentBox = 0
end

# Structural stand-in for Storage.rb:769-877 — same menu call, same drain,
# same nil-`pokes` hazard (no `else` in the case).
class PokemonStorageScreen
  attr_reader :shown
  attr_reader :menus
  def pbShowCommands(msg, commands, *args, **kwargs)
    (@menus ||= []) << commands
    @shown ||= commands
    @picker.call(commands)
  end

  def pick_with(&blk)
    @shown = nil
    @menus = []
    @picker = blk
  end

  def pbSortPokemon(minbox = $PokemonStorage.currentBox, maxbox = $PokemonStorage.currentBox)
    commands = ["Nickname", "Level", "Dex No.", "Species", "Type", "Shiny", "Item", "Total IVs"]
    command = pbShowCommands("How would you like to sort?", commands)
    return -1 if command == -1

    boxes = (minbox..maxbox).to_a
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
    default = ->(x, y) { 2 * (x.dexnum <=> y.dexnum) + (x.form <=> y.form) }
    case command
    when 1 then pokes = mons.sort { |x, y| (y.timeReceived.to_s <=> x.timeReceived.to_s).nonzero? || default.call(x, y) }
    when 2 then pokes = mons.sort { |x, y| default.call(x, y) }
    end
    pokes += eggs.sort { |x, y| default.call(x, y) }   # NoMethodError if pokes is nil
    boxes.each do |box|
      (0...$PokemonStorage[box].length).each do |slot|
        $PokemonStorage[box, slot] = pokes.shift
        break if pokes.empty?
      end
    end
    0
  end
end

require_relative "chrooked_zz_pcsort"

def t(y) = Time.gm(y, 1, 1)
def fresh_storage
  $PokemonStorage = FakeStorage.new([
    #                                              HP  Atk Def SpA SpD Spe
    [FakeMon.new("mid",     t(2010), 3, 0, false, [ 50, 90, 50, 50, 50, 50]),  # BST 340
     FakeMon.new("oldest",  t(2001), 1, 0, false, [100, 40, 40, 40, 40, 40]),  # BST 300
     FakeMon.new("egg",     t(2005), 9, 0, true,  [255,255,255,255,255,255]),
     FakeMon.new("newest",  t(2020), 2, 0, false, [ 60, 60, 60, 60, 60,130]),  # BST 430
     FakeMon.new("glitched", :Glitched, 4, 0, false, [ 45, 45, 45, 45, 45, 45])],  # BST 270
  ])
end
def names = $PokemonStorage[0].map { |p| p&.name }
def check(label) = (yield ? puts("ok   #{label}") : abort("FAIL #{label}"))

screen = PokemonStorageScreen.new

fresh_storage
screen.pick_with { |c| c.index("Date Caught (Newest)") }
screen.pbSortPokemon
check("menu offers the three new entries") { screen.shown.last(3) == ["Date Caught (Newest)", "Date Caught (Oldest)", "Base Stats..."] }
check("vanilla modes still listed")   { screen.shown.first(8).include?("Total IVs") }
check("newest first")                 { names == ["newest", "mid", "oldest", "glitched", "egg"] }

fresh_storage
screen.pick_with { |c| c.index("Date Caught (Oldest)") }
screen.pbSortPokemon
check("oldest first, glitched leads") { names == ["glitched", "oldest", "mid", "newest", "egg"] }
check("eggs stay last")               { names.last == "egg" }
check("nothing is lost")              { names.compact.sort == %w[egg glitched mid newest oldest] }

fresh_storage
screen.pick_with { |_c| 1 } # a vanilla mode
check("vanilla mode still returns 0") { screen.pbSortPokemon == 0 }

fresh_storage
screen.pick_with { |_c| -1 } # cancel
check("cancel returns -1")            { screen.pbSortPokemon == -1 }
check("cancel leaves box untouched")  { names == ["mid", "oldest", "egg", "newest", "glitched"] }

# Base-stat submenu: first menu picks "Base Stats...", second picks the stat.
def stat_sort(screen, stat_label)
  fresh_storage
  answers = [->(c) { c.index("Base Stats...") }, ->(c) { stat_label ? c.index(stat_label) : -1 }]
  screen.pick_with { |c| answers.shift.call(c) }
  screen.pbSortPokemon
end

ret = stat_sort(screen, "BST")
check("submenu lists BST and six stats") { screen.menus[1] == ["BST", "HP", "Attack", "Defense", "Sp. Atk", "Sp. Def", "Speed"] }
check("BST highest first, egg last")     { names == ["newest", "mid", "oldest", "glitched", "egg"] }
check("stat sort returns vanilla value") { ret == 0 }

stat_sort(screen, "HP")
check("HP highest first")                { names == ["oldest", "newest", "mid", "glitched", "egg"] }

stat_sort(screen, "Attack")
check("Attack highest first")            { names == ["mid", "newest", "glitched", "oldest", "egg"] }

stat_sort(screen, "Speed")
check("Speed highest first")             { names == ["newest", "mid", "glitched", "oldest", "egg"] }

ret = stat_sort(screen, nil) # cancel the submenu
check("submenu cancel returns -1")       { ret == -1 }
check("submenu cancel leaves box alone") { names == ["mid", "oldest", "egg", "newest", "glitched"] }

puts "all checks passed"
