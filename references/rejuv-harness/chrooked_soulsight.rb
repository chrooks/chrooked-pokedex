# chrooked:soulsight
# Soulsight — "Prevents flinching; moves hit Ghosts; Psychic moves +30% power;
#   Fighting-type special moves never miss."
#   accuracy-check: Fighting-type SPECIAL move => skip the roll
#   type-chart:     Normal/Fighting move vs an immune target => neutral (Scrappy)
#   damage-calc:    Psychic-type move => x1.3
#   flinch:         the holder never loses its turn to a flinch (Inner Focus)
# Test cases:
#   - Focus Blast (70% acc) never misses; Aura Sphere/Ki Blast/Chi Wave likewise
#   - a Fighting PHYSICAL move (Close Combat) keeps its normal accuracy
#   - Close Combat hits a Ghost; a Psychic move vs a Dark-type stays immune
#   - Extrasensory => 1.3x; a Fighting move gets no damage boost
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

CHROOKED_DAMAGE_MODS[:SOULSIGHT] = lambda { |move, attacker, opponent|
  move.pbType(attacker) == :PSYCHIC ? 1.3 : 1.0
}

# Flinch immunity has no registry hook. Rejuv sets effects[:Flinch] at 17 move
# sites but CONSUMES it at exactly one — Battler.rb pbTryUseMove, which already
# gates on `ability != :INNERFOCUS`. Clearing the flag just before that check is
# the one-site fix; the setter sites stay untouched.
# ponytail: clears the flag outright rather than teaching all 17 setters about
# a second ability. Upgrade path if a move ever needs to see a suppressed
# flinch: gate inside pbTryUseMove instead of zeroing the effect.
if defined?(PokeBattle_Battler)
  class PokeBattle_Battler
    if method_defined?(:pbTryUseMove) && !method_defined?(:chrooked_soulsight_trymove)
      alias_method :chrooked_soulsight_trymove, :pbTryUseMove
      def pbTryUseMove(*args)
        @effects[:Flinch] = false if @effects[:Flinch] && self.ability == :SOULSIGHT
        chrooked_soulsight_trymove(*args)
      end
    end
  end
end
