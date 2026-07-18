/* Pure combined-type matchup logic for a single species (as opposed to
   typeChartGrid's single-type breakdown used by the Type Chart tab). Defense
   multiplies across both of the species' types (and folds in the selected
   ability, if any); offense takes the BEST of the species' own types per
   defender, since a dual-type attacker picks whichever STAB move fits. */

import { applyAbilityModifier } from "./abilityTypeModifiers";
import { axisOrder, cellKey, cellMap } from "./typeChartGrid";
import type { TypeChartCell } from "../types";

export interface SpeciesMatchupMember {
  type: string;
  /** The actual combined multiplier (may be off the usual 0/½/1/2 steps —
      e.g. ×4 or ×0.25 for a dual-type pairing). */
  value: number;
}

export interface SpeciesDefenseMatchups {
  weak: SpeciesMatchupMember[];
  neutral: SpeciesMatchupMember[];
  resist: SpeciesMatchupMember[];
  immune: SpeciesMatchupMember[];
}

export interface SpeciesOffenseMatchups {
  strong: SpeciesMatchupMember[];
  neutral: SpeciesMatchupMember[];
  resisted: SpeciesMatchupMember[];
  noEffect: SpeciesMatchupMember[];
}

export interface SpeciesMatchups {
  defense: SpeciesDefenseMatchups;
  offense: SpeciesOffenseMatchups;
}

export function speciesMatchups(
  types: readonly string[],
  cells: readonly TypeChartCell[],
  ability: string | null,
): SpeciesMatchups {
  const axis = axisOrder(cells);
  const byKey = cellMap(cells);

  const defense: SpeciesDefenseMatchups = {
    weak: [],
    neutral: [],
    resist: [],
    immune: [],
  };
  const offense: SpeciesOffenseMatchups = {
    strong: [],
    neutral: [],
    resisted: [],
    noEffect: [],
  };

  for (const other of axis) {
    let combined = 1;
    let sawDefense = false;
    for (const ownType of types) {
      const cell = byKey.get(cellKey(other, ownType));
      if (cell) {
        combined *= cell.multiplier;
        sawDefense = true;
      }
    }
    if (sawDefense) {
      const value = applyAbilityModifier(combined, other, ability);
      const member: SpeciesMatchupMember = { type: other, value };
      if (value === 0) defense.immune.push(member);
      else if (value < 1) defense.resist.push(member);
      else if (value === 1) defense.neutral.push(member);
      else defense.weak.push(member);
    }

    let best: number | null = null;
    for (const ownType of types) {
      const cell = byKey.get(cellKey(ownType, other));
      if (cell) best = best === null ? cell.multiplier : Math.max(best, cell.multiplier);
    }
    if (best !== null) {
      const member: SpeciesMatchupMember = { type: other, value: best };
      if (best === 0) offense.noEffect.push(member);
      else if (best < 1) offense.resisted.push(member);
      else if (best === 1) offense.neutral.push(member);
      else offense.strong.push(member);
    }
  }

  return { defense, offense };
}
