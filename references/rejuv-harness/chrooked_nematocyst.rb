# chrooked:nematocyst
# Nematocyst — "Water moves have a 30% chance to badly poison; any poison this
# Pokemon inflicts becomes bad poison."
#
# Two seams:
#   1. WATER PROC — after a damaging Water move deals damage (CHROOKED_ON_DEAL,
#      the venomous pattern), 30% chance to badly poison a poisonable target.
#   2. UPGRADE — prepend pbPoison so ANY poison whose source is a Nematocyst
#      holder is forced to toxic (bad poison). This also makes seam 1's poison
#      land as toxic even if seam 1 passed regular poison, and upgrades the
#      holder's own poison moves/abilities (Poison Sting, Poison Point, Sludge).
#
# pbPoison(attacker, toxic = false, message: nil) — attacker is the source, so
# effect 2 keys on `attacker.ability`. pbCanPoison? already gates on target
# immunity (Poison/Steel/Immunity) and on the target being status-free.
#
# Test cases (drive in-game):
#   - holder Surf vs Chansey => ~30% badly poisoned (statusCount 1, escalating).
#   - holder Poison Sting vs Snorlax => regular-poison chance lands as TOXIC.
#   - holder Surf vs Toxapex (Poison) => never poisons (immune).

# --- Seam 1: 30% badly-poison on a damaging Water move ------------------------
CHROOKED_ON_DEAL[:NEMATOCYST] = lambda { |move, user, target, battle|
  next unless move.pbType(user) == :WATER
  next unless target.pbCanPoison?(user, move)
  next if battle.pbRandom(100) >= 30
  battle.pbShowAbilityBox(user)
  target.pbPoison(user, true)
  battle.pbHideAbilityBox(user)
}

# --- Seam 2: every poison the holder inflicts becomes bad poison --------------
module ChrookedNematocystPoison
  def pbPoison(attacker, toxic = false, message: nil)
    toxic = true if attacker && attacker.ability == :NEMATOCYST
    super(attacker, toxic, message: message)
  end
end
PokeBattle_Battler.prepend(ChrookedNematocystPoison)
