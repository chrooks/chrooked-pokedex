# encoding: utf-8
# chrooked:zz_redux
# Static mod (not a Ruleset behavior) — always installed by apply.
# "Redux Mode" Options toggle: when On, every battler enters battle with ALL
# of its species' abilities (regular + hidden) active at once, Tectonic-style.
#
# Rejuv has no single ability-check seam — ~1650 direct `battler.ability == :X`
# comparisons plus `include?`/`case` sites. So instead of rewriting call sites,
# the battler's @ability becomes a ChrookedAbilitySet whose `==` matches ANY
# owned ability. A Symbol#== fallback covers the reversed comparisons,
# Array#include? and case/when sites. Hash lookups ($cache.abil[ability]) fall
# through to the primary ability via hash/eql?, so names/descriptions display
# the primary.
# ponytail: known ceilings — (1) changeAbility (Skill Swap / Trace / Mummy /
# Gastro Acid recovery) collapses the mon to the single new ability for the
# rest of the battle; (2) messages and the ability box show the primary
# ability's name only. Upgrade path: wrap changeAbility and getAbilityName.

class ChrookedAbilitySet
  attr_reader :list, :primary

  def initialize(list)
    @list = list.compact.uniq
    @primary = @list.first
  end

  # Symbols are interned, so equal? is exact comparison without re-entering
  # the patched Symbol#==.
  def ==(other)
    return !(@list & other.list).empty? if other.is_a?(ChrookedAbilitySet)
    @list.any? { |a| a.equal?(other) }
  end

  def include?(sym)
    @list.any? { |a| a.equal?(sym) }
  end

  # Hash lookups (e.g. $cache.abil[ability]) resolve to the primary ability.
  def eql?(other)
    @primary.eql?(other)
  end

  def hash
    @primary.hash
  end

  def to_sym
    @primary
  end

  # Object#to_s would shadow method_missing — delegate explicitly.
  def to_s
    @primary.to_s
  end

  def inspect
    "ChrookedAbilitySet#{@list.inspect}"
  end

  def method_missing(name, *args, &block)
    @primary.send(name, *args, &block)
  end

  def respond_to_missing?(name, include_private = false)
    @primary.respond_to?(name, include_private)
  end
end

# Covers `:X == battler.ability`, `[:X, :Y].include?(battler.ability)` and
# `case battler.ability when :X` — everywhere the set lands on the right-hand
# side of a Symbol comparison. Fast path first: the original == short-circuits
# before the is_a? check, so plain symbol comparisons pay one branch.
class Symbol
  unless method_defined?(:chrooked_orig_eq)
    alias_method :chrooked_orig_eq, :==
    def ==(other)
      return true if chrooked_orig_eq(other)
      other.is_a?(ChrookedAbilitySet) && other.include?(self)
    end

    # case/when compiles to an optimized jump table that only deopts when
    # Symbol#=== itself is redefined — routing through == is not enough.
    def ===(other)
      self == other
    end
  end
end

# $Settings is a PokemonOptions (Scripts/Options.rb:255) — PokemonSystem in
# ConversionClasses.rb is only the legacy save-conversion shim.
if defined?(PokemonOptions)
  class PokemonOptions
    attr_writer :chrooked_redux

    # nil on saves from before this mod → default Off (EnumOption index 1).
    def chrooked_redux
      @chrooked_redux.nil? ? 1 : @chrooked_redux
    end
  end
end

if defined?(PokeBattle_Battler)
  class PokeBattle_Battler
    if method_defined?(:pbInitPokemon)
      alias_method :chrooked_redux_init, :pbInitPokemon
      def pbInitPokemon(pkmn, pkmnIndex)
        chrooked_redux_init(pkmn, pkmnIndex)
        return unless $Settings && $Settings.chrooked_redux == 0
        list = [@ability]
        list.concat(pkmn.getAbilityList) if pkmn.respond_to?(:getAbilityList)
        list = list.compact.uniq
        return unless list.length > 1
        set = ChrookedAbilitySet.new(list)
        @ability = set
        # changeAbility restores from @backupability after suppression ends —
        # keep the full set there so Gastro Acid wearing off re-arms it.
        @backupability = set
      end
    end
  end
end

if defined?(PokemonOptionScene)
  class PokemonOptionScene
    alias_method :chrooked_redux_initOptions, :initOptions
    def initOptions
      optionList = chrooked_redux_initOptions
      option = EnumOption.new(
        _INTL("Redux Mode"), [_INTL("On"), _INTL("Off")],
        proc { $Settings.chrooked_redux },
        proc { |value| $Settings.chrooked_redux = value },
        _INTL("When On, every Pokémon fights with all of its abilities (hidden included) active at once.")
      )
      # First entry of the Battle section; falls back to just above "Back".
      idx = optionList.index(_INTL("Battle"))
      if idx
        optionList.insert(idx + 1, option)
      else
        optionList.insert(-2, option)
      end
      return optionList
    end
  end
end
