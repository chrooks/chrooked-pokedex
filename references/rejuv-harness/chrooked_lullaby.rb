# chrooked:lullaby
# Lullaby — "This Pokemon's sound moves have a 30% chance to make the target
#            drowsy (Yawn's effect: it sleeps at the end of the next turn
#            unless it switches)."
#   on-hit: a damaging sound move dealt damage (not into a Substitute) => 30%
#           => target.effects[:Yawn] = 2, exactly what the move Yawn writes
#           (Battle_MoveEffects.rb:213; the end-of-round tick at Battle.rb:6842
#           puts it to sleep through pbCanSleep?).
#   Skipped when the target is already drowsy, already has a status, or cannot
#   sleep (pbCanSleep?: Insomnia, Vital Spirit, Sweet Veil, Electric Terrain,
#   Safeguard via pbCanStatus?, Uproar ...). Flat 30%: NOT doubled by Serene
#   Grace, by decision — do not pair the two on one species.
# Test cases:
#   - Hyper Voice hits => ~30% the target grows drowsy and sleeps next turn's end
#   - Tackle (not a sound move) or Sing (status) => never
#   - target already drowsy or already statused => no second roll lands
#   - target with Insomnia / Vital Spirit, or on Electric Terrain => never
#   - hit into a Substitute => never (core gates on damagestate.substitute)
module ChrookedLullaby
  CHANCE = 30
end

# user = the Lullaby holder, target = the foe. The core only fires this after a
# damaging hit that missed any Substitute, with the user still standing.
CHROOKED_ON_DEAL[:LULLABY] = lambda { |move, user, target, battle|
  next unless move.respond_to?(:isSoundBased?) && move.isSoundBased?
  next if target.isFainted? || target.effects[:Yawn] > 0 || !target.status.nil?
  next unless target.pbCanSleep?(user, move)
  next if battle.pbRandom(100) >= ChrookedLullaby::CHANCE
  battle.pbShowAbilityBox(user)
  target.effects[:Yawn] = 2
  battle.pbDisplay(_INTL("{1} made {2} drowsy!", user.pbThis, target.pbThis(true)))
  battle.pbHideAbilityBox(user)
}
