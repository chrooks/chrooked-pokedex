# encoding: utf-8
# chrooked:zz_zreduxinfo
# Static mod (not a Ruleset behavior) — always installed by apply.
# Sorts after zz_redux / zz_zcompose on purpose: it reopens ChrookedAbilitySet.
#
# 1. Ability box under Redux Mode names the ability that FIRED, not the primary.
#    Every vanilla site does `battler.ability == :INTIMIDATE` (or the reversed
#    Symbol / include? / case forms, all of which land in ChrookedAbilitySet#==
#    or #include?) right before it calls pbShowAbilityBox. So the set remembers
#    the last symbol that matched, and the box borrows it as the display name
#    for the duration of the show. A composed ability (chrooked_display set)
#    keeps its own name — its parts are not what the player should see.
#    ponytail: "last match" is a heuristic. A stray check of a different
#    ability between the match and the box would mislabel one popup; no
#    battle logic reads chrooked_display outside the show window.
# 2. Summary screens list every ability the species owns, not just the active
#    one: the ABILITY page gets each extra ability with its description; the
#    SKILLS pages get one "Also:" line under the active ability's text.
#    ponytail: the "Also:" line sits at y=352 by eye (no screenshot possible on
#    hestia) — nudge if it collides with the item row.

class ChrookedAbilitySet
  attr_accessor :chrooked_last

  alias_method :chrooked_info_eq, :==
  def ==(other)
    hit = chrooked_info_eq(other)
    @chrooked_last = other if hit && other.is_a?(Symbol)
    hit
  end

  alias_method :chrooked_info_include?, :include?
  def include?(sym)
    hit = chrooked_info_include?(sym)
    @chrooked_last = sym if hit
    hit
  end
end

module ChrookedReduxAbilityBox
  def pbShowAbilityBox(battler, item: nil, attrname: nil, crest: nil)
    set = battler.ability
    borrow = item.nil? && attrname.nil? && set.is_a?(ChrookedAbilitySet) &&
             set.chrooked_display.nil? && set.chrooked_last
    return super unless borrow
    set.chrooked_display = set.chrooked_last
    begin
      super
    ensure
      set.chrooked_display = nil
    end
  end
end
PokeBattle_Scene.prepend(ChrookedReduxAbilityBox) if defined?(PokeBattle_Scene)

module ChrookedSummaryAbilities
  def chrooked_other_abilities(pokemon)
    return [] unless pokemon.respond_to?(:getAbilityList)
    current = pokemon.ability.respond_to?(:to_sym) ? pokemon.ability.to_sym : pokemon.ability
    (pokemon.getAbilityList || []).compact.uniq.reject { |a| a == current }
  end

  def chrooked_also_line(pokemon)
    others = chrooked_other_abilities(pokemon)
    return nil if others.empty?
    _INTL("Also: {1}", others.map { |a| getAbilityName(a) }.join(", "))
  end

  def drawAbilPage(pokemon)
    super
    others = chrooked_other_abilities(pokemon)
    return if others.empty?
    overlay = @sprites["overlay"].bitmap
    memo = ""
    others.each do |a|
      abil = $cache.abil[a]
      next if abil.nil?
      memo += "<c3=F8F8F8,686868>" + _INTL("Also:") + " <c3=404040,B0B0B0>" + getAbilityName(a) + "\n"
      memo += "<c3=404040,B0B0B0>" + getAbilityDesc(a, false) + "\n"
    end
    # Below the active ability's memo block (drawn at y=78); 190 clears four
    # lines of name + description at this font.
    drawFormattedTextEx(overlay, 232, 190, 272, memo)
  end

  def drawPageThree(pokemon)
    super
    line = chrooked_also_line(pokemon)
    return unless line
    overlay = @sprites["overlay"].bitmap
    drawTextEx(overlay, 224, 352, 282, 1, line, PokemonSummaryScene::DarkBase, PokemonSummaryScene::DarkShadow)
  end

  def drawPageFour(pokemon)
    super
    line = chrooked_also_line(pokemon)
    return unless line
    overlay = @sprites["overlay"].bitmap
    drawTextEx(overlay, 224, 352, 282, 1, line, PokemonSummaryScene::DarkBase, PokemonSummaryScene::DarkShadow)
  end
end
if defined?(PokemonSummaryScene)
  PokemonSummaryScene.prepend(ChrookedSummaryAbilities)
end
