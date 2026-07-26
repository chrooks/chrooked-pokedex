# chrooked:bioturbation
# Bioturbation — "On entry, type-based hazards hit the user at neutral
# effectiveness; then every hazard on the user's side is flung to the foe's."
#
# Two seams, both bespoke to this ability (the core's generic tables don't cover
# an in-flight type-effectiveness rewrite), so they live here rather than in the
# generated core:
#
#   1. NEUTRALIZE — pbOnActiveOne runs the hazard damage inline (Stealth Rock,
#      electrified Spikes, corrosive field) via PBTypes.typesEff(atype, types).
#      While a Bioturbation holder is being switched in we flag it, and the
#      typesEff wrapper returns a neutral Typemod for that holder's own types —
#      so a 2x/4x/0.5x/immune matchup all pay the flat neutral rate (1/8 for SR).
#   2. RELOCATE — pbOnActiveOne ends by calling pbAbilitiesOnSwitchIn, so the
#      existing CHROOKED_SWITCH_IN table fires AFTER all hazard damage resolves.
#      There we move every own-side hazard layer to the foe's side, capped at
#      each hazard's natural max (SR 1, Spikes 3, Toxic Spikes 2, Web 1).
#
# Test cases (drive in-game — the harness can't prove battle behavior):
#   - Walrein (Ice/Water) into Stealth Rock => 1/8 HP (not 1/4), SR then on foe.
#   - Mon into 3 Spikes + SR => Spikes 3-layer flat dmg + SR neutralized; both move.
#   - Foe already at 3 Spikes; enter into 2 Spikes + SR => SR moves, extra Spikes discarded.

# --- Seam 1: neutralize the holder's own entry-hazard type effectiveness -------
module ChrookedBioturbNeutralize
  def typesEff(attackType, types, inverse: false)
    holder = $chrooked_bioturb_neutralize
    return Typemod.normal if holder && types == holder.types
    super
  end
end
class << PBTypes
  prepend ChrookedBioturbNeutralize
end

module ChrookedBioturbActive
  def pbOnActiveOne(pkmn)
    return super unless pkmn && !pkmn.isFainted? && pkmn.ability == :BIOTURBATION
    prev = $chrooked_bioturb_neutralize
    $chrooked_bioturb_neutralize = pkmn
    begin
      super
    ensure
      $chrooked_bioturb_neutralize = prev
    end
  end
end
PokeBattle_Battle.prepend(ChrookedBioturbActive)

# --- Seam 2: fling all own-side hazards to the foe's side (after damage) -------
CHROOKED_SWITCH_IN[:BIOTURBATION] = lambda { |battler, battle|
  own = battler.pbOwnSide
  opp = battler.pbOpposingSide
  moved = false
  if own.effects[:StealthRock]
    own.effects[:StealthRock] = false
    opp.effects[:StealthRock] = true
    moved = true
  end
  if own.effects[:Spikes] > 0
    opp.effects[:Spikes] = [opp.effects[:Spikes] + own.effects[:Spikes], 3].min
    own.effects[:Spikes] = 0
    moved = true
  end
  if own.effects[:ToxicSpikes] > 0
    opp.effects[:ToxicSpikes] = [opp.effects[:ToxicSpikes] + own.effects[:ToxicSpikes], 2].min
    own.effects[:ToxicSpikes] = 0
    moved = true
  end
  if own.effects[:StickyWeb]
    opp.effects[:StickyWeb] = own.effects[:StickyWeb] unless opp.effects[:StickyWeb]
    own.effects[:StickyWeb] = nil
    moved = true
  end
  if moved
    battle.pbShowAbilityBox(battler)
    battle.pbDisplay(_INTL("{1} churned the earth, flinging the hazards back!", battler.pbThis))
    battle.pbHideAbilityBox(battler)
  end
}
