# chrooked:mindwipe
# Mind Wipe — "Its attacks erase the memory of the foe's last move."
#   on-hit: each damaging hit erases 4 PP from the target's last used move.
#     Spite's body (Battle_MoveEffects.rb PokeBattle_Move_10E#pbEffectTarget):
#     scan target.moves for target.lastMoveUsed with pp > 0, pbSetPP(-4, floored
#     at 0). lastMoveUsed is -1 until the target has moved, so the scan finds
#     nothing and the hit passes silently. Fires once per hit (ON_DEAL runs from
#     pbEffectsOnDealingDamage), so multi-hit moves erase 4 per hit.
# Test cases:
#   - target last used Recover (10 PP) => "lost 4 PP from Recover!", 6 left
#   - target has not moved yet         => no message, no change
#   - target's last move at 0 PP       => no message, no change
#   - Rock Blast 3 hits                => 12 PP gone (capped at what remains)
CHROOKED_ON_DEAL[:MINDWIPE] = lambda { |move, user, target, battle|
  next if target.isFainted?
  wiped = target.moves.find { |m| m && m.move == target.lastMoveUsed && m.pp > 0 }
  next unless wiped
  reduction = [4, wiped.pp].min
  battle.pbShowAbilityBox(user)
  target.pbSetPP(wiped, wiped.pp - reduction)
  battle.pbDisplay(_INTL("{1} lost {2} PP from {3}!", target.pbThis, reduction, wiped.name))
  battle.pbHideAbilityBox(user)
}
