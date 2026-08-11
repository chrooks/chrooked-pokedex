# chrooked:rootshelter
# Root Shelter — a HALF shield, not a Protect. The data layer ships the move on
#   Spiky Shield's function code (0x140) purely to inherit the protect-family
#   fail-on-repeat gate; every rider below is this file's job.
#     on-use     => set effects[:ChrookedRootShelter] for the round
#     damage-calc => damage against a sheltered battler is halved (floor 1)
#     on-hit     => whatever dealt the damage is seeded (Leech Seed rules)
#     round-end  => the flag clears alongside effects[:Protect]
#   The flag is deliberately NOT effects[:Protect]: the engine treats any truthy
#   value there as a full block (Battler.rb `hitflags[i] = target.effects[:Protect]`),
#   which would make Root Shelter a strictly better Protect.
# Test cases:
#   - shelter, then take Earthquake => half damage, attacker seeded
#   - shelter, then take a hit from a Grass-type => half damage, no seed
#   - shelter, then take Thunder Wave => paralysis lands (nothing is blocked)
#   - shelter twice in a row => the second use usually fails (ProtectRate)

# The repeat gate reads this list; without the entry ProtectRate resets every
# turn and the move would never fail on successive use.
if defined?(PBStuff) && defined?(PBStuff::RATESHARERS) &&
   !PBStuff::RATESHARERS.include?(:ROOTSHELTER)
  PBStuff::RATESHARERS << :ROOTSHELTER
end

module Chrooked
  module RootShelterMove
    def pbEffect(attacker, alltargets, hitnum = 0)
      return super if @move != :ROOTSHELTER
      attacker.effects[:ChrookedRootShelter] = true
      attacker.effects[:ProtectRate] += 1
      @battle.pbDisplay(_INTL("{1} hunkered down into its roots!", attacker.pbThis))
    end
  end

  module RootShelterDamage
    def pbCalcDamage(attacker, opponent, *args, **kwargs)
      dmg = super
      return dmg if !dmg.is_a?(Numeric) || dmg <= 0
      return dmg if !opponent || !opponent.effects[:ChrookedRootShelter]
      [(dmg / 2.0).round, 1].max
    end
  end

  module RootShelterSeed
    def pbEffectsOnDealingDamage(move, user, target, damage, *args)
      ret = super
      return ret if damage.to_i <= 0 || target.damagestate.substitute
      return ret if !target.effects[:ChrookedRootShelter]
      return ret if user.isFainted? || target.isFainted?
      return ret if user.effects[:LeechSeed] >= 0 || user.hasType?(:GRASS)
      user.effects[:LeechSeed] = target.index
      @battle.pbDisplay(_INTL("{1} was seeded!", user.pbThis))
      ret
    end
  end

  module RootShelterReset
    def pbEndOfRoundPhase(*args, **kwargs)
      ret = super
      @battlers.each { |b| b.effects[:ChrookedRootShelter] = nil if b }
      ret
    end
  end
end

# Guarded like the core's PokeBattle_Move_0D8 block: a Rejuv build that renamed
# or dropped the Spiky Shield funccode loses the shelter, not the whole mod.
PokeBattle_Move_140.prepend(Chrooked::RootShelterMove) if defined?(PokeBattle_Move_140)
PokeBattle_Move.prepend(Chrooked::RootShelterDamage)
PokeBattle_Battler.prepend(Chrooked::RootShelterSeed)
PokeBattle_Battle.prepend(Chrooked::RootShelterReset)
