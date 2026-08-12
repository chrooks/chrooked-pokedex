# chrooked:rimefang
# Rimefang — biting moves: +30% damage, 30% frostbite, 30% flinch. The Ice-side
# twin of Infernal Maw: same shape, frostbite where that one burns.
#   damage-calc: biting move => x1.3
#   status-apply: biting hit => 30% frostbite (pbCanFreeze? gate, so Ice-types are immune)
#   status-apply: biting hit => 30% flinch
# Test cases:
#   - Bite/Crunch => 1.3x damage, may frostbite (30%), may flinch (30%)
#   - non-biting move => nothing
#   - Ice-type target => 1.3x and flinch still roll, frostbite cannot land
#
# pbFreeze prints the frostbite wording through chrooked_frostbite.rb's text
# prepend, so no message is passed here (same as chrooked_frostbody.rb).
CHROOKED_DAMAGE_MODS[:RIMEFANG] = lambda { |move, attacker, opponent|
  move.bitingMove? ? 1.3 : 1.0
}
CHROOKED_ON_DEAL[:RIMEFANG] = lambda { |move, user, target, battle|
  next unless move.bitingMove?
  if target.pbCanFreeze?(user, move) && battle.pbRandom(100) < 30
    battle.pbShowAbilityBox(user)
    target.pbFreeze
    battle.pbHideAbilityBox(user)
  end
  if battle.pbRandom(100) < 30 && !target.isFainted?
    target.effects[:Flinch] = true
  end
}
