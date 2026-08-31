# chrooked:soulsight
# Soulsight — "Prevents flinching; moves hit Ghosts; Fighting-type special
#   moves never miss."
#   accuracy-check: Fighting-type SPECIAL move => skip the roll
#   type-chart:     Normal/Fighting move vs an immune target => neutral (Scrappy)
#   flinch:         the holder never loses its turn to a flinch (Inner Focus)
# Test cases:
#   - Focus Blast (70% acc) never misses; Aura Sphere/Ki Blast/Chi Wave likewise
#   - a Fighting PHYSICAL move (Close Combat) keeps its normal accuracy
#   - Close Combat hits a Ghost; a Psychic move vs a Dark-type stays immune
#   - Fake Out's flinch does not stop the holder acting

# Never-miss is scoped to type + category, NOT the pulse flag, so it covers
# Vacuum Wave, Aura Spark, Chi Wave, Aura Sphere, Ki Blast and Focus Blast and
# adopts any future Fighting special for free. Physical Fighting is untouched.
CHROOKED_SURE_HIT[:SOULSIGHT] = lambda { |move, attacker|
  type = move.pbType(attacker)
  type == :FIGHTING && move.pbIsSpecial?(attacker, type) && move.pbIsDamaging?
}

# Scrappy. The floor lambda gets no opponent, so it must not fire on matchups
# other than the one it means to open. Gating on Normal/Fighting is exact:
# Ghost is the ONLY 0x matchup either type has, so nothing else can leak
# through (a Psychic move vs a Dark-type stays immune).
CHROOKED_TYPEMOD_FLOOR[:SOULSIGHT] = lambda { |move, attacker|
  [:NORMAL, :FIGHTING].include?(move.pbType(attacker))
}

# Flinch immunity has no registry hook. Rejuv sets effects[:Flinch] at 17 move
# sites but CONSUMES it at exactly one — Battler.rb pbTryUseMove, which already
# gates on `ability != :INNERFOCUS`. Clearing the flag just before that check is
# the one-site fix; the setter sites stay untouched.
# ponytail: clears the flag outright rather than teaching all 17 setters about
# a second ability. Upgrade path if a move ever needs to see a suppressed
# flinch: gate inside pbTryUseMove instead of zeroing the effect.
# MUST be a prepend, never alias_method. chrooked_frostbite.rb already prepends
# its own pbTryUseMove wrapper and loads first (f < s). An alias taken in the
# class body resolves through the prepended module, so the alias would capture
# frostbite's wrapper while this definition landed behind it — the two then call
# each other forever and the first move used blows the stack.
module ChrookedSoulsightNoFlinch
  def pbTryUseMove(*args, **kwargs)
    if @effects && @effects[:Flinch] && self.ability == :SOULSIGHT
      @effects[:Flinch] = false
    end
    super
  end
end
PokeBattle_Battler.prepend(ChrookedSoulsightNoFlinch) if defined?(PokeBattle_Battler)
