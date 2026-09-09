# chrooked:battery
# Battery — "On entry, the user charges up: Sp. Def rises and the next Electric
#   move is doubled." The vanilla ally Sp. Atk boost is untouched; this plugin
#   only adds the entry effect on top of it.
#
# Reuses the vanilla Charge counter (effects[:Charge] = 2) rather than a new
# Chrooked flag, so decay and consumption run through the same code path as the
# move Charge (Battle_MoveEffects.rb, PokeBattle_Move_021) and the 2.0x multiplier
# in Battle_Move.rb. The already-charged guard mirrors Electromorphosis
# (Battler.rb) — a battler that is already charged is left alone.
#
# Test cases (drive in-game — the harness can't prove battle behavior):
#   - Switch in uncharged, then Thunderbolt => Sp. Def +1 on entry, Thunderbolt doubled.
#   - Switch in already charged             => no message, no Sp. Def raise, counter kept.
#   - Switch in on an Electric field        => Sp. Def +2, matching the move Charge.

CHROOKED_SWITCH_IN[:BATTERY] = lambda { |battler, battle|
  next if battler.effects[:Charge] > 0
  battle.pbShowAbilityBox(battler)
  battler.effects[:Charge] = 2
  battle.pbAnimation(:CHARGE, battler, nil)
  battle.pbDisplay(_INTL("{1} began charging power!", battler.pbThis))
  statchange = (battle.respond_to?(:FE) && battle.FE == :ELECTERRAIN) ? 2 : 1
  battler.pbChangeStats(PBStats::SPDEF, statchange, battler, nil, abilitycheck: :skip)
  battle.pbHideAbilityBox(battler)
}
