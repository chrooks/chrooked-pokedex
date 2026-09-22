# chrooked:mawcannon
# Maw Cannon — "Pulse moves use this Pokemon's Attack stat."
#   damage-calc: a damaging pulse move resolves as PHYSICAL for this attacker
#
# Same seam as Percussion (chrooked_percussion.rb), which does this for sound
# moves: Rejuv's pbCalcDamage picks the attack stat via pbHitsPhysicalStat? and
# the defense stat via pbHitsSpecialStat?, both derived from pbIsPhysical? /
# pbIsSpecial?. Overriding the two predicates moves both stats together and keeps
# every downstream consumer consistent, rather than leaving a move that is
# physical for damage and special for everything else.
#
# @category is deliberately NOT rewritten: Mega Launcher, the displayed category
# and the AI's reads keep seeing a special pulse move. Only the resolved-category
# questions answer differently, and only for this attacker.
#
# Test cases (drive in-game):
#   - Dragon Pulse + MAWCANNON  => damage scales off Attack, defended by Defense
#   - Flame Burst (pulse) + MAWCANNON => same
#   - Waterfall (not a pulse)   => untouched
#   - Heal Pulse (status)       => stays status, no crash
module ChrookedMawCannon
  # Defensive on purpose: this predicate is consulted for EVERY move in the game,
  # including the bare move objects the AI and the mod harness build.
  def chrooked_maw_cannon?(attacker)
    return false if attacker.nil?
    return false if @category == :status
    return false unless respond_to?(:pulseMove?) && pulseMove?
    attacker.ability == :MAWCANNON
  end

  def pbIsPhysical?(attacker, type = @type)
    return true if chrooked_maw_cannon?(attacker)
    super
  end

  def pbIsSpecial?(attacker, type = @type)
    return false if chrooked_maw_cannon?(attacker)
    super
  end
end
PokeBattle_Move.prepend(ChrookedMawCannon) if defined?(PokeBattle_Move)
