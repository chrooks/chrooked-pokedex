# chrooked:percussion
# Percussion — sound-based moves become physical and use Attack, not Sp. Atk.
#   damage-calc: damaging sound move => resolves as physical for the whole calc
#
# Implemented at the CATEGORY seam rather than by swapping stat values. Rejuv's
# pbCalcDamage picks the attack stat via pbHitsPhysicalStat? and the defense
# stat via pbHitsSpecialStat?, and both derive from pbIsPhysical?/pbIsSpecial?.
# Overriding the two predicates therefore moves the attack stat AND the defense
# stat together, and keeps every downstream consumer consistent (burn halving,
# Hustle, the physical crit table) instead of leaving a move that is physical
# for damage but special for everything else.
#
# @category is deliberately NOT rewritten: Soundproof, the move's displayed
# category, and the AI's own reads keep seeing a special sound move. Only the
# resolved-category questions answer differently, and only for this attacker.
#
# Test cases:
#   - damaging sound move + PERCUSSION => pbIsPhysical? true, pbIsSpecial? false
#   - the same move without PERCUSSION => untouched
#   - a non-sound special move + PERCUSSION => untouched
#   - a STATUS sound move (Growl, Sing) + PERCUSSION => stays status
#   - attacker nil (AI probing with no user) => untouched, no crash
module ChrookedPercussion
  # Defensive on purpose: this predicate is consulted for EVERY move in the
  # game, including the bare move objects the AI and the mod harness build, so
  # it reads @category directly and feature-tests isSoundBased? rather than
  # assuming the full PokeBattle_Move surface is present.
  def chrooked_percussion?(attacker)
    return false if attacker.nil?
    return false if @category == :status
    return false unless respond_to?(:isSoundBased?) && isSoundBased?
    attacker.ability == :PERCUSSION
  end

  def pbIsPhysical?(attacker, type = @type)
    return true if chrooked_percussion?(attacker)
    super
  end

  def pbIsSpecial?(attacker, type = @type)
    return false if chrooked_percussion?(attacker)
    super
  end
end
PokeBattle_Move.prepend(ChrookedPercussion) if defined?(PokeBattle_Move)
