# chrooked:infernalmaw
# Infernal Maw — biting moves: +30% damage, 20% burn, 30% flinch.
#   damage-calc: biting move => x1.3
#   status-apply: biting hit => 20% burn (burnable targets)
#   status-apply: biting hit => 30% flinch
# Test cases:
#   - Bite/Crunch => 1.3x damage, may burn (20%), may flinch (30%)
#   - non-biting move => nothing
CHROOKED_DAMAGE_MODS[:INFERNALMAW] = lambda { |move, attacker, opponent|
  move.bitingMove? ? 1.3 : 1.0
}
CHROOKED_ON_DEAL[:INFERNALMAW] = lambda { |move, user, target, battle|
  next unless move.bitingMove?
  if target.pbCanBurn?(user, move) && battle.pbRandom(100) < 20
    battle.pbShowAbilityBox(user)
    target.pbBurn(user)
    battle.pbHideAbilityBox(user)
  end
  if battle.pbRandom(100) < 30 && !target.isFainted?
    target.effects[:Flinch] = true
  end
}
