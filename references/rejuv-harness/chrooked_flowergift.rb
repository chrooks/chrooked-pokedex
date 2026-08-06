# chrooked:flowergift
# Flower Gift — Fire/Grass moves get STAB regardless of own types; Morning Sun
#   always restores 75% max HP; the vanilla team Atk/SpDef sun buff is removed.
#   Form flip (Overcast <-> Sunshine) is native Rejuv (Battler.rb flowerGiftActive?)
#   and does not route through pbCheckSideAbility, so stripping the lookup kills
#   only the buff.
# Side effect (accepted): Rejuv's Cherrim Crest boosts ride the same lookup and
#   are silenced too.
# ponytail: 5 aiCheckSideAbility(:FLOWERGIFT) scoring sites still value the
#   removed buff — the AI slightly over-rates Cherrim. Patch if it ever matters.
# Test cases:
#   - Sunshine form (Fire/Fairy) Grass move => 1.5x from the grant, no stacking
#   - Overcast form Grass move => 1.5x total (natural STAB, grant returns 1.0)
#   - Morning Sun in sandstorm => 75% heal
#   - sun up, ally Cherrim on field => NO Atk/SpDef buff on anyone
CHROOKED_DAMAGE_MODS[:FLOWERGIFT] = lambda { |move, attacker, opponent|
  Chrooked.stab_grant(move, attacker, [:FIRE, :GRASS])
}
CHROOKED_HEAL_OVERRIDE[[:FLOWERGIFT, :MORNINGSUN]] = 0.75

# Strip :FLOWERGIFT from the side-ability lookup the 9 vanilla buff sites use
# (Battle_Move.rb atkmult/defmult, Battler.rb pbAttack/pbDefense/pbSpecialAttack/
# pbSpecialDefense). The form flip never calls this, so it keeps working.
if defined?(PokeBattle_Battle)
  module ChrookedFlowerGiftStrip
    def pbCheckSideAbility(abilities, battler, *args, **kwargs)
      return [] if abilities == :FLOWERGIFT
      abilities = abilities - [:FLOWERGIFT] if abilities.is_a?(Array)
      super(abilities, battler, *args, **kwargs)
    end
  end
  PokeBattle_Battle.prepend(ChrookedFlowerGiftStrip)
end
