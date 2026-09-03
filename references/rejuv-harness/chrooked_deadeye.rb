# chrooked:deadeye
# Deadeye — "Non-contact attacks never miss and ignore the target's Defense and
#            Sp. Def boosts."
#   accuracy-check: damaging non-contact move => skip the roll (SURE_HIT).
#                   Semi-invulnerable turns are decided by invulMisses?, a
#                   separate gate, so Dive/Fly still dodge.
#   damage-calc:    damaging non-contact move => the target's POSITIVE Defense
#                   and Sp. Def stages count as 0 for this hit; negative stages
#                   still apply. Offensive Unaware, ranged only.
# Test cases:
#   - Hydro Pump into +6 evasion / Sand Veil => hits, no roll
#   - Snipe Shot into +2 Sp. Def => damage as if +0
#   - Snipe Shot into -1 Sp. Def => the -1 still applies
#   - Liquidation (contact) into +2 Def with lowered accuracy => vanilla both ways
#   - Hydro Pump into a foe mid-Dive => misses

module ChrookedDeadeye
  def self.applies?(move, attacker)
    attacker.ability == :DEADEYE && move.pbIsDamaging? && !move.contactMove?
  end
end

CHROOKED_SURE_HIT[:DEADEYE] = lambda { |move, attacker|
  ChrookedDeadeye.applies?(move, attacker)
}

# Rejuv reads the defender's stages straight out of `stages[]` inside
# pbDefense / pbSpDef (Battler.rb ~7296), with the only bypass being the
# attacker-side `unaware:` kwarg that pbCalcDamage derives from
# attacker.ability == :UNAWARE. Clamping the two stages around `super` is the
# one-site fix and also covers the AI's pbRoughDamage, which reads the same
# array. Same shape as the core's STAT_SWAP wrapper.
# ponytail: mutates the stages array in place and restores in `ensure`; a
# kwarg plumb through pbDefense would be cleaner if a second ability needs it.
module ChrookedDeadeyeDamage
  def pbCalcDamage(attacker, opponent, *args, **kwargs)
    return super unless opponent && ChrookedDeadeye.applies?(self, attacker)
    keys = [PBStats::DEFENSE, PBStats::SPDEF]
    saved = keys.map { |k| opponent.stages[k] }
    begin
      keys.each { |k| opponent.stages[k] = 0 if opponent.stages[k] > 0 }
      super
    ensure
      keys.each_with_index { |k, i| opponent.stages[k] = saved[i] }
    end
  end
end
PokeBattle_Move.prepend(ChrookedDeadeyeDamage) if defined?(PokeBattle_Move)
